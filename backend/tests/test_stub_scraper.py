"""Stub scraper tests — CACH-04 (300-500 char payload) + end-to-end run_search."""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest

from app.workers.stub_scraper import _fake_listing, run_search


def test_payload_size():
    listing = _fake_listing()
    serialized = json.dumps(listing)
    assert 300 <= len(serialized) <= 500, (
        f"listing serialized to {len(serialized)} chars (need 300-500)"
    )


async def test_run_search(clean_db, pg_pool, monkeypatch):
    # Skip the 1.5s of cumulative sleep across 3 iters.
    real_sleep = asyncio.sleep

    async def fast_sleep(_):
        await real_sleep(0)

    monkeypatch.setattr("app.workers.stub_scraper.asyncio.sleep", fast_sleep)

    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'test')",
        job_id,
    )

    ctx = {"db": pg_pool}
    await run_search(ctx, job_id)

    row = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id = $1",
        job_id,
    )
    assert row["status"] == "completed"
    assert row["completed_at"] is not None

    listing_count = await pg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE job_id = $1", job_id
    )
    assert listing_count == 9

    daily_tokens = await pg_pool.fetchval(
        "SELECT estimated_tokens FROM daily_spend WHERE date = CURRENT_DATE"
    )
    assert daily_tokens == 1500
