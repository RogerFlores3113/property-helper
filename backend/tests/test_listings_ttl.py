"""RED — listings.expires_at TTL column behavior (CACH-02).

Covers decisions:
  - D-07 (05-CONTEXT): expires_at NOT NULL DEFAULT now()+28d.
  - D-12 (05-CONTEXT): "fresh" predicate is expires_at > now(); "stale" is the
        complement. Used by the cache-hit lookup in Plan 05-02.

These tests require the live schema (migration 0002 applied) and run against
SUPABASE_DB_URL. They are pre-implementation in the sense that no production
code reads or writes expires_at yet — Plan 05-02 will wire it up.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.red_phase_05


async def _insert_job(pg_pool, job_id: str) -> None:
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'q')",
        job_id,
    )


async def test_expires_at_default_is_28_days(pg_pool, clean_db):
    job_id = str(uuid.uuid4())
    await _insert_job(pg_pool, job_id)
    listing_id = str(uuid.uuid4())
    await pg_pool.execute(
        """INSERT INTO listings (id, job_id, data, photo_url)
           VALUES ($1, $2, $3::jsonb, NULL)""",
        listing_id,
        job_id,
        json.dumps({"address": "x"}),
    )
    row = await pg_pool.fetchrow(
        "SELECT expires_at, created_at FROM listings WHERE id = $1", listing_id
    )
    assert row["expires_at"] is not None
    delta = row["expires_at"] - row["created_at"]
    # 28 days ± 1 minute tolerance.
    assert abs(delta - timedelta(days=28)) < timedelta(minutes=1), (
        f"expires_at should be created_at + 28d, got delta={delta}"
    )


async def test_expires_at_not_null(pg_pool, clean_db):
    """Direct INSERT without specifying expires_at must still produce non-NULL
    (proven by the column default firing)."""
    job_id = str(uuid.uuid4())
    await _insert_job(pg_pool, job_id)
    listing_id = str(uuid.uuid4())
    await pg_pool.execute(
        """INSERT INTO listings (id, job_id, data) VALUES ($1, $2, $3::jsonb)""",
        listing_id,
        job_id,
        json.dumps({"a": 1}),
    )
    val = await pg_pool.fetchval(
        "SELECT expires_at FROM listings WHERE id = $1", listing_id
    )
    assert val is not None


async def test_fresh_vs_stale_predicate(pg_pool, clean_db):
    job_id = str(uuid.uuid4())
    await _insert_job(pg_pool, job_id)
    stale_id = str(uuid.uuid4())
    fresh_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await pg_pool.execute(
        """INSERT INTO listings (id, job_id, data, expires_at)
           VALUES ($1, $2, $3::jsonb, $4)""",
        stale_id,
        job_id,
        json.dumps({"a": 1}),
        now - timedelta(days=1),
    )
    await pg_pool.execute(
        """INSERT INTO listings (id, job_id, data, expires_at)
           VALUES ($1, $2, $3::jsonb, $4)""",
        fresh_id,
        job_id,
        json.dumps({"a": 2}),
        now + timedelta(days=1),
    )
    fresh_rows = await pg_pool.fetch(
        "SELECT id FROM listings WHERE expires_at > now() AND job_id = $1", job_id
    )
    fresh_ids = {str(r["id"]) for r in fresh_rows}
    assert fresh_id in fresh_ids
    assert stale_id not in fresh_ids
