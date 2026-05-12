"""Integration tests for scrapers.craigslist.run_search_craigslist —
SCRAP-02 + SCRAP-04 + SCRAP-05.

Uses httpx.MockTransport to mock all outbound HTTP. Uses clean_db + pg_pool +
arq_redis fixtures from conftest (skips when SUPABASE_DB_URL unset).

Plan 04-03 changes:
  - run_search → run_search_craigslist (rename).
  - Every fetch wrapped by acquire_domain_slot (D-20).
  - mark_done (in coordinator) owns terminal status writes (D-15) — this
    module no longer writes status='completed'/'failed' directly.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest

FIX = Path(__file__).parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text()


def _make_handler(robots_body: str, search_body: str, detail_body: str, call_log: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        host = request.url.host
        call_log.setdefault("urls", []).append(str(request.url))
        assert host.endswith(".craigslist.org") or host == "craigslist.org" or host == "www.craigslist.org", (
            f"non-craigslist host fetched: {host}"
        )
        if path == "/robots.txt":
            return httpx.Response(200, text=robots_body)
        if path.startswith("/search/"):
            call_log["search_fetched"] = call_log.get("search_fetched", 0) + 1
            return httpx.Response(200, text=search_body)
        if path.endswith(".html"):
            call_log["detail_fetched"] = call_log.get("detail_fetched", 0) + 1
            return httpx.Response(200, text=detail_body)
        return httpx.Response(404, text="not found")
    return handler


async def _install_fake_client(monkeypatch, handler):
    """Patch the module-level client factory inside scrapers.craigslist."""
    from app.workers.scrapers import craigslist as cl

    def _factory():
        transport = httpx.MockTransport(handler)
        return httpx.AsyncClient(transport=transport)

    monkeypatch.setattr(cl, "_make_client", _factory)


# --- Plan 04-03 surface tests -------------------------------------------------


def test_craigslist_function_renamed():
    """Plan 04-03: run_search → run_search_craigslist. Old name must be gone."""
    from app.workers.scrapers.craigslist import run_search_craigslist  # noqa: F401

    from app.workers.scrapers import craigslist as cl

    assert not hasattr(cl, "run_search"), (
        "Old run_search name must be removed (D-15 + Plan 04-03 rename)"
    )


async def test_craigslist_calls_acquire_domain_slot_per_fetch(
    clean_db, pg_pool, arq_redis, monkeypatch
):
    """SCRAP-04 wiring: every fetch wrapped by acquire_domain_slot, including
    the search page and at least one detail page, with craigslist hostnames."""
    from app.workers.scrapers import craigslist as cl

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    captured_urls: list[str] = []
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_slot(redis, url, timeout_s=30.0):
        captured_urls.append(url)
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", fake_slot)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )
    # Prime coordinator counters so mark_done can resolve.
    await arq_redis.set(f"expected:{job_id}", 1, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await cl.run_search_craigslist(
        {"db": pg_pool, "redis": arq_redis}, job_id
    )

    assert len(captured_urls) >= 2, (
        f"expected ≥2 acquire_domain_slot calls (search + ≥1 detail), got {captured_urls}"
    )
    for url in captured_urls:
        assert "craigslist" in url, f"non-craigslist URL acquired a slot: {url}"


async def test_craigslist_calls_mark_done_on_success(
    clean_db, pg_pool, arq_redis, monkeypatch
):
    """On a successful run, mark_done is called exactly once with failed=False."""
    from app.workers.scrapers import craigslist as cl

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    # No-op the rate limiter so the test focuses on mark_done.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop(redis, url, timeout_s=30.0):
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", noop)

    recorder: list[dict] = []

    async def fake_mark_done(redis, db, job_id, *, failed):
        recorder.append({"failed": failed, "job_id": job_id})

    monkeypatch.setattr(cl, "mark_done", fake_mark_done)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )

    await cl.run_search_craigslist(
        {"db": pg_pool, "redis": arq_redis}, job_id
    )

    assert len(recorder) == 1, f"expected exactly one mark_done call, got {recorder}"
    assert recorder[0]["failed"] is False


async def test_craigslist_calls_mark_done_on_exception(
    clean_db, pg_pool, arq_redis, monkeypatch
):
    """On exception, mark_done(failed=True) is called and the exception propagates."""
    from app.workers.scrapers import craigslist as cl

    # Force the search query → URL resolution to succeed but the fetch to bomb.
    handler_calls: list[str] = []

    def boom_handler(request: httpx.Request) -> httpx.Response:
        handler_calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=_read("craigslist_robots.txt"))
        # Detail/search → raise inside the scraper via guard.check_payload-like
        # path: easiest is to make every non-robots fetch raise a non-HTTPError.
        raise RuntimeError("induced failure")

    def _factory():
        transport = httpx.MockTransport(boom_handler)
        return httpx.AsyncClient(transport=transport)

    monkeypatch.setattr(cl, "_make_client", _factory)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop(redis, url, timeout_s=30.0):
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", noop)

    recorder: list[dict] = []

    async def fake_mark_done(redis, db, job_id, *, failed):
        recorder.append({"failed": failed, "job_id": job_id})

    monkeypatch.setattr(cl, "mark_done", fake_mark_done)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )

    with pytest.raises(RuntimeError, match="induced failure"):
        await cl.run_search_craigslist(
            {"db": pg_pool, "redis": arq_redis}, job_id
        )

    assert len(recorder) == 1, f"expected one mark_done(failed=True), got {recorder}"
    assert recorder[0]["failed"] is True


def test_craigslist_does_not_write_status_completed():
    """D-15: only mark_done flips terminal status — source must contain no
    literal status='completed' SQL."""
    src = Path(
        Path(__file__).parent.parent / "app" / "workers" / "scrapers" / "craigslist.py"
    ).read_text()
    assert "status='completed'" not in src, (
        "scrapers/craigslist.py must not contain literal status='completed' "
        "SQL — D-15 says mark_done owns the terminal flip."
    )


# --- Pre-existing integration tests (rewired to new name + ctx) --------------


async def test_run_search_inserts_real_listing(
    clean_db, pg_pool, arq_redis, monkeypatch
):
    from app.workers.scrapers.craigslist import run_search_craigslist
    from app.workers.scrapers import craigslist as cl

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    # No-op rate limiter so the test runs fast.
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop(redis, url, timeout_s=30.0):
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", noop)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )
    # Prime counters for mark_done.
    await arq_redis.set(f"expected:{job_id}", 1, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await run_search_craigslist({"db": pg_pool, "redis": arq_redis}, job_id)

    row = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id = $1", job_id
    )
    # mark_done flips to 'completed' on the final call (expected=1).
    assert row["status"] == "completed"
    assert row["completed_at"] is not None

    n = await pg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE job_id = $1", job_id
    )
    assert n >= 1, "expected at least one inserted listing"

    n_with_coords = await pg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE job_id = $1 "
        "AND data->>'source_name' = 'craigslist' "
        "AND data->>'lat' IS NOT NULL",
        job_id,
    )
    assert n_with_coords >= 1


async def test_robots_disallow_skips_url(clean_db, pg_pool, arq_redis, monkeypatch):
    from app.workers.scrapers.craigslist import run_search_craigslist
    from app.workers.scrapers import craigslist as cl

    deny_robots = "User-agent: *\nDisallow: /search/apa\nDisallow: /\n"
    call_log: dict = {}
    handler = _make_handler(
        robots_body=deny_robots,
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop(redis, url, timeout_s=30.0):
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", noop)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 1, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await run_search_craigslist({"db": pg_pool, "redis": arq_redis}, job_id)

    assert call_log.get("search_fetched", 0) == 0, "search URL was fetched despite disallow"
    n = await pg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE job_id = $1", job_id
    )
    assert n == 0

    row = await pg_pool.fetchrow(
        "SELECT status FROM search_jobs WHERE id = $1", job_id
    )
    # mark_done(failed=False) on the disallow path → terminal 'completed'.
    assert row["status"] == "completed"


async def test_daily_spend_row_written(clean_db, pg_pool, arq_redis, monkeypatch):
    from app.workers.scrapers.craigslist import run_search_craigslist
    from app.workers.scrapers import craigslist as cl

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop(redis, url, timeout_s=30.0):
        yield

    monkeypatch.setattr(cl, "acquire_domain_slot", noop)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'sf bay area')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 1, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await run_search_craigslist({"db": pg_pool, "redis": arq_redis}, job_id)

    row = await pg_pool.fetchrow(
        "SELECT estimated_tokens, estimated_cost_usd FROM daily_spend "
        "WHERE date = CURRENT_DATE"
    )
    assert row is not None, "no daily_spend row written for current date"
    assert row["estimated_tokens"] >= 0
