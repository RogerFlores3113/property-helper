"""Integration tests for scrapers.craigslist.run_search — SCRAP-02 + SCRAP-05.

Uses httpx.MockTransport to mock all outbound HTTP. Uses clean_db + pg_pool
fixtures from conftest (skips when SUPABASE_DB_URL unset).
"""
from __future__ import annotations

import asyncio
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
        # Only craigslist.org hosts ever fetched (T-03-01 SSRF mitigation).
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

    # No-op sleep (Pitfall 3 jitter)
    real_sleep = asyncio.sleep
    async def fast_sleep(_):
        await real_sleep(0)
    monkeypatch.setattr(cl.asyncio, "sleep", fast_sleep)


async def test_run_search_inserts_real_listing(clean_db, pg_pool, monkeypatch):
    from app.workers.scrapers.craigslist import run_search

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'sf bay area')",
        job_id,
    )

    await run_search({"db": pg_pool}, job_id)

    row = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id = $1", job_id
    )
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


async def test_robots_disallow_skips_url(clean_db, pg_pool, monkeypatch):
    from app.workers.scrapers.craigslist import run_search

    deny_robots = "User-agent: *\nDisallow: /search/apa\nDisallow: /\n"
    call_log: dict = {}
    handler = _make_handler(
        robots_body=deny_robots,
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'sf bay area')",
        job_id,
    )

    await run_search({"db": pg_pool}, job_id)

    assert call_log.get("search_fetched", 0) == 0, "search URL was fetched despite disallow"
    n = await pg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE job_id = $1", job_id
    )
    assert n == 0

    row = await pg_pool.fetchrow(
        "SELECT status FROM search_jobs WHERE id = $1", job_id
    )
    assert row["status"] == "completed"


async def test_daily_spend_row_written(clean_db, pg_pool, monkeypatch):
    from app.workers.scrapers.craigslist import run_search

    call_log: dict = {}
    handler = _make_handler(
        robots_body=_read("craigslist_robots.txt"),
        search_body=_read("craigslist_search.html"),
        detail_body=_read("craigslist_detail.html"),
        call_log=call_log,
    )
    await _install_fake_client(monkeypatch, handler)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'sf bay area')",
        job_id,
    )
    await run_search({"db": pg_pool}, job_id)

    row = await pg_pool.fetchrow(
        "SELECT estimated_tokens, estimated_cost_usd FROM daily_spend "
        "WHERE date = CURRENT_DATE"
    )
    assert row is not None, "no daily_spend row written for current date"
    assert row["estimated_tokens"] >= 0
