"""RED scaffold — Plan 04-04 SCRAP-01 Apartments.com scraper integration.

Patches async_playwright, the rate-limit acquire, and the LLM extractor so the
scraper can be exercised without live network. Collection ERRORs until Plan 04
lands `app.workers.scrapers.apartments`.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import target — does not exist yet.
from app.workers.scrapers.apartments import run_search_apartments  # noqa: F401


def _playwright_chain():
    """Build a minimal AsyncMock chain emulating playwright → page."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value="<html><body>raw page content</body></html>")
    page.locator = MagicMock()

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    playwright = MagicMock(chromium=chromium)
    enter = AsyncMock(return_value=playwright)
    exit_ = AsyncMock(return_value=None)

    pw_factory = MagicMock()
    pw_factory.return_value.__aenter__ = enter
    pw_factory.return_value.__aexit__ = exit_
    return pw_factory, page


@pytest.fixture
def playwright_chain(monkeypatch):
    pw_factory, page = _playwright_chain()
    monkeypatch.setattr(
        "app.workers.scrapers.apartments.async_playwright", pw_factory
    )
    return pw_factory, page


async def test_stealth_async_called_before_goto(playwright_chain, monkeypatch):
    """playwright_stealth.stealth_async runs before page.goto."""
    order: list[str] = []

    async def fake_stealth(page):
        order.append("stealth")

    async def fake_goto(url, **kwargs):
        order.append("goto")

    monkeypatch.setattr(
        "app.workers.scrapers.apartments.stealth_async", fake_stealth
    )
    _, page = playwright_chain
    page.goto = AsyncMock(side_effect=fake_goto)

    ctx = {"job_id": "00000000-0000-0000-0000-000000000000", "query": "2BR SF"}
    await run_search_apartments(ctx)

    assert order[0] == "stealth"
    assert "goto" in order


async def test_acquire_domain_slot_wraps_every_goto(playwright_chain, monkeypatch):
    """Every page.goto is wrapped by acquire_domain_slot."""
    calls: list[str] = []

    class FakeSlot:
        def __init__(self, redis, url, **kw):
            calls.append(url)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

    monkeypatch.setattr(
        "app.workers.scrapers.apartments.acquire_domain_slot", FakeSlot
    )
    ctx = {"job_id": "00000000-0000-0000-0000-000000000000", "query": "2BR SF"}
    await run_search_apartments(ctx)
    assert len(calls) >= 1, "acquire_domain_slot must wrap at least the search goto"


async def test_pre_filter_runs_before_llm(playwright_chain, monkeypatch):
    """llm_extract.extract receives the prefilter() output, not raw page.content()."""
    raw = "<html>RAW</html>"
    _, page = playwright_chain
    page.content = AsyncMock(return_value=raw)

    monkeypatch.setattr(
        "app.workers.scrapers.apartments.prefilter",
        lambda text, selector=None: "PREFILTERED",
    )

    seen: list[str] = []

    async def fake_extract(text, **kwargs):
        seen.append(text)
        return []

    monkeypatch.setattr(
        "app.workers.scrapers.apartments.llm_extract.extract", fake_extract
    )

    ctx = {"job_id": "00000000-0000-0000-0000-000000000000", "query": "2BR SF"}
    await run_search_apartments(ctx)
    assert all(s != raw for s in seen), "extract() must never see raw page content"
    assert "PREFILTERED" in seen


async def test_mark_done_called_on_success(playwright_chain, monkeypatch):
    """On clean run, mark_done is called with failed=False."""
    calls: list[bool] = []

    async def fake_mark(ctx, job_id, failed=False):
        calls.append(failed)

    monkeypatch.setattr("app.workers.scrapers.apartments.mark_done", fake_mark)
    ctx = {"job_id": "00000000-0000-0000-0000-000000000000", "query": "2BR SF"}
    await run_search_apartments(ctx)
    assert calls == [False]


async def test_mark_done_called_on_exception(playwright_chain, monkeypatch):
    """If page.goto raises, mark_done is called with failed=True."""
    _, page = playwright_chain
    page.goto = AsyncMock(side_effect=RuntimeError("network blew up"))

    calls: list[bool] = []

    async def fake_mark(ctx, job_id, failed=False):
        calls.append(failed)

    monkeypatch.setattr("app.workers.scrapers.apartments.mark_done", fake_mark)
    ctx = {"job_id": "00000000-0000-0000-0000-000000000000", "query": "2BR SF"}
    await run_search_apartments(ctx)
    assert calls == [True]
