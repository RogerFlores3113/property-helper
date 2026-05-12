"""Apartments.com scraper GREEN tests — Plan 04-04 Task 2.

Covers the 12 behavior bullets in 04-04-PLAN.md <behavior>:
1.  stealth_async called before page.goto.
2.  acquire_domain_slot wraps every page.goto.
3.  prefilter() runs before llm_extract.extract — raw HTML never reaches the LLM.
4.  photo_host whitelist drops non-apartments.com image hosts (T-04-03 server defense).
5.  photo_host whitelist accepts apartments.com hosts.
6.  mark_done(failed=False) on a clean run.
7.  mark_done(failed=True) on an exception, with re-raise.
8.  No location match → short-circuit success path; no Playwright launch.
9.  Browser context closed even when an inner step raises (Pitfall 6).
10. check_iter() called once per detail-page iteration (not per payload).
11. ENABLED_SOURCES includes both "craigslist" and "apartments".
12. WorkerSettings.functions registers run_search_apartments.

Replaces the Plan 04-01 RED scaffold wholesale (per Plan 04-04 <action>): the
scaffold's ``run_search_apartments(ctx)`` shape and ``mark_done(ctx, job_id, ...)``
signature do not match the actual surface delivered by Plans 04-02/04-03
(``run_search_apartments(ctx, job_id)``, ``mark_done(redis, db, job_id, *, failed)``).
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.scrapers import apartments as apartments_mod
from app.workers.scrapers.apartments import _PHOTO_HOST_SUFFIXES, run_search_apartments


# ----------------------------- helpers ----------------------------------------


def _make_anchor(href: str):
    """Build a mock playwright Locator anchor exposing get_attribute."""
    anchor = MagicMock()
    anchor.get_attribute = AsyncMock(return_value=href)
    return anchor


def _make_locator(anchors):
    locator = MagicMock()
    locator.all = AsyncMock(return_value=anchors)
    return locator


def _build_playwright_mock(detail_hrefs=None, raw_html="<html><body>raw</body></html>"):
    """Construct nested mocks emulating async_playwright() → browser → context → page."""
    detail_hrefs = detail_hrefs or [
        "https://www.apartments.com/1234-mission-st-san-francisco-ca-9z8x7y6/",
    ]

    page = MagicMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value=raw_html)
    page.wait_for_selector = AsyncMock()
    page.locator = MagicMock(
        return_value=_make_locator([_make_anchor(h) for h in detail_hrefs])
    )

    context = MagicMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()

    browser = MagicMock()
    browser.new_context = AsyncMock(return_value=context)
    browser.close = AsyncMock()

    chromium = MagicMock()
    chromium.launch = AsyncMock(return_value=browser)

    pw_obj = MagicMock(chromium=chromium)

    pw_cm = MagicMock()
    pw_cm.__aenter__ = AsyncMock(return_value=pw_obj)
    pw_cm.__aexit__ = AsyncMock(return_value=None)

    pw_factory = MagicMock(return_value=pw_cm)

    return pw_factory, page, browser, context


# ----------------------------- ctx + db helpers --------------------------------


def _make_ctx(redis_obj=None):
    db = MagicMock()
    db.fetchrow = AsyncMock(return_value={"query": "2BR in SF Bay Area under $5k"})
    db.execute = AsyncMock()
    if redis_obj is None:
        redis_obj = MagicMock()
    return {"db": db, "redis": redis_obj}, db


def _patch_default_extract(monkeypatch, listings=None):
    """Default: monkeypatch llm_extract.extract → return one synthesized Listing
    with an apartments.com image_url so INSERT path executes."""
    if listings is None:
        listings = [
            SimpleNamespace(
                model_dump=lambda: {
                    "address": "1234 Mission St, San Francisco, CA 94103",
                    "price": 3495,
                    "beds": 2.0,
                    "baths": 1.5,
                    "sqft": 1100,
                    "amenities": ["In-Unit W/D"],
                    "source_url": "https://www.apartments.com/x/",
                    "image_url": "https://images1.apartments.com/x.jpg",
                    "posted_date": "2026-04-28",
                    "source_name": "apartments",
                    "lat": 37.7707,
                    "lng": -122.4108,
                }
            )
        ]

    async def fake_extract(text, source_url, source_name="apartments", guard=None):
        if guard is not None:
            await guard.record_spend(tokens=1200, cost_usd=0.001)
        return listings

    monkeypatch.setattr(apartments_mod.llm_extract, "extract", fake_extract)


def _patch_default_prefilter(monkeypatch):
    monkeypatch.setattr(apartments_mod, "prefilter", lambda raw, sel=None: "PREFILTERED")


def _patch_acquire_recorder(monkeypatch):
    """Replace acquire_domain_slot with a recording async context manager."""
    calls: list[str] = []

    class FakeSlot:
        def __init__(self, redis, url, **kw):
            calls.append(url)
            self.url = url

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return None

    monkeypatch.setattr(apartments_mod, "acquire_domain_slot", FakeSlot)
    return calls


def _patch_mark_done_recorder(monkeypatch):
    """Patch mark_done in apartments module to record (failed: bool) calls."""
    calls: list[bool] = []

    async def fake_mark_done(redis, db, job_id, *, failed):
        calls.append(failed)

    monkeypatch.setattr(apartments_mod, "mark_done", fake_mark_done)
    return calls


def _patch_stealth_recorder(monkeypatch):
    order: list[str] = []

    async def fake_stealth(page):
        order.append("stealth")

    monkeypatch.setattr(apartments_mod, "stealth_async", fake_stealth)
    return order


# ============================== TESTS =========================================


async def test_stealth_async_called_before_goto(monkeypatch):
    """stealth_async runs exactly once and BEFORE the first page.goto (T-04-08)."""
    order = _patch_stealth_recorder(monkeypatch)
    pw_factory, page, *_ = _build_playwright_mock()

    async def fake_goto(url, **kw):
        order.append(f"goto:{url}")

    page.goto = AsyncMock(side_effect=fake_goto)
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    ctx, _ = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    assert order.count("stealth") == 1
    assert order.index("stealth") < next(
        i for i, ev in enumerate(order) if ev.startswith("goto:")
    )


async def test_acquire_domain_slot_wraps_every_goto(monkeypatch):
    """acquire_domain_slot is called once per page.goto (D-20 / SCRAP-04)."""
    pw_factory, page, *_ = _build_playwright_mock(
        detail_hrefs=[
            "https://www.apartments.com/d1/",
            "https://www.apartments.com/d2/",
        ]
    )
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    calls = _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    ctx, _ = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    # 1 search-page goto + 2 detail-page gotos.
    assert page.goto.await_count == 3
    assert len(calls) == 3


async def test_prefilter_runs_before_llm(monkeypatch):
    """SCRAP-06 / SCRAP-07: extract() receives prefilter() output, not raw HTML."""
    raw = "<html><body>RAW PAGE BODY</body></html>"
    pw_factory, page, *_ = _build_playwright_mock(raw_html=raw)
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    monkeypatch.setattr(apartments_mod, "prefilter", lambda raw_html, sel=None: "PREFILTERED")

    seen_text: list[str] = []

    async def fake_extract(text, source_url, source_name="apartments", guard=None):
        seen_text.append(text)
        return []

    monkeypatch.setattr(apartments_mod.llm_extract, "extract", fake_extract)

    ctx, _ = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    assert seen_text, "llm_extract.extract was never called"
    assert all(t == "PREFILTERED" for t in seen_text)
    assert raw not in seen_text


async def test_photo_host_whitelist_drops_non_apartments(monkeypatch):
    """T-04-03: LLM-supplied image_url with non-apartments.com host → photo_url=NULL."""
    pw_factory, page, *_ = _build_playwright_mock()
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    _patch_default_extract(
        monkeypatch,
        listings=[
            SimpleNamespace(
                model_dump=lambda: {
                    "address": "1 Evil St",
                    "price": 2000,
                    "image_url": "https://evil.example.com/x.jpg",
                    "source_url": "https://www.apartments.com/x/",
                    "source_name": "apartments",
                }
            )
        ],
    )

    ctx, db = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    listing_inserts = [
        c for c in db.execute.await_args_list if "INSERT INTO listings" in c.args[0]
    ]
    assert len(listing_inserts) == 1
    # INSERT: (sql, id, job_id, serialized_jsonb, photo_url, created_at)
    photo_url = listing_inserts[0].args[4]
    assert photo_url is None, f"expected None for evil host; got {photo_url!r}"


async def test_photo_host_whitelist_accepts_apartments(monkeypatch):
    """An apartments.com image host passes through unchanged."""
    pw_factory, page, *_ = _build_playwright_mock()
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    img = "https://images1.apartments.com/i2/abc/100/primary-photo.jpg"
    _patch_default_extract(
        monkeypatch,
        listings=[
            SimpleNamespace(
                model_dump=lambda: {
                    "address": "1 Mission",
                    "price": 3000,
                    "image_url": img,
                    "source_url": "https://www.apartments.com/x/",
                    "source_name": "apartments",
                }
            )
        ],
    )

    ctx, db = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    listing_inserts = [
        c for c in db.execute.await_args_list if "INSERT INTO listings" in c.args[0]
    ]
    assert len(listing_inserts) == 1
    assert listing_inserts[0].args[4] == img


async def test_mark_done_called_on_success(monkeypatch):
    pw_factory, *_ = _build_playwright_mock()
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    calls = _patch_mark_done_recorder(monkeypatch)

    ctx, _ = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")
    assert calls == [False]


async def test_mark_done_called_on_exception(monkeypatch):
    """page.goto raises → mark_done(failed=True), exception re-raised."""
    pw_factory, page, *_ = _build_playwright_mock()
    page.goto = AsyncMock(side_effect=RuntimeError("network blew up"))
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    calls = _patch_mark_done_recorder(monkeypatch)

    ctx, _ = _make_ctx()
    with pytest.raises(RuntimeError):
        await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")
    assert calls == [True]


async def test_no_location_match_short_circuits(monkeypatch):
    """Unknown location → mark_done(failed=False) and no Playwright launch."""
    pw_factory, *_ = _build_playwright_mock()
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    calls = _patch_mark_done_recorder(monkeypatch)

    ctx, db = _make_ctx()
    db.fetchrow = AsyncMock(return_value={"query": "completely unknown place xyz"})

    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    assert calls == [False]
    # No Playwright launch when there is no allowlisted target.
    pw_factory.assert_not_called()


async def test_browser_context_closed_on_exception(monkeypatch):
    """Pitfall 6: browser.close runs even when an inner step raises."""
    pw_factory, page, browser, context = _build_playwright_mock()
    page.goto = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    ctx, _ = _make_ctx()
    with pytest.raises(RuntimeError):
        await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    browser.close.assert_awaited()
    context.close.assert_awaited()


async def test_check_iter_called_once_per_detail(monkeypatch):
    """Pitfall 3: guard.check_iter called once per detail-page iteration."""
    pw_factory, page, *_ = _build_playwright_mock(
        detail_hrefs=[
            "https://www.apartments.com/d1/",
            "https://www.apartments.com/d2/",
            "https://www.apartments.com/d3/",
        ]
    )
    monkeypatch.setattr(apartments_mod, "async_playwright", pw_factory)
    _patch_stealth_recorder(monkeypatch)
    _patch_acquire_recorder(monkeypatch)
    _patch_default_prefilter(monkeypatch)
    _patch_default_extract(monkeypatch)
    _patch_mark_done_recorder(monkeypatch)

    iter_calls: list[int] = []
    real_guard_class = apartments_mod.BudgetGuard

    class CountingGuard(real_guard_class):
        @classmethod
        def from_env(cls, db):
            inst = real_guard_class.from_env(db)
            inst.__class__ = cls
            return inst

        def check_iter(self):
            iter_calls.append(1)
            super().check_iter()

    monkeypatch.setattr(apartments_mod, "BudgetGuard", CountingGuard)

    ctx, _ = _make_ctx()
    await run_search_apartments(ctx, "00000000-0000-0000-0000-000000000000")

    assert len(iter_calls) == 3


def test_enabled_sources_includes_apartments():
    from app.workers.coordinator import ENABLED_SOURCES

    assert "craigslist" in ENABLED_SOURCES
    assert "apartments" in ENABLED_SOURCES


def test_worker_settings_registers_apartments():
    from app.workers.settings import WorkerSettings

    names = [f.__name__ for f in WorkerSettings.functions]
    assert "run_search_apartments" in names


def test_photo_host_suffix_constant_contains_apartments():
    assert any("apartments.com" in s for s in _PHOTO_HOST_SUFFIXES)
