"""RED — compute_dedup_key + run_dedup_for_job (SCRAP-08).

Covers decisions:
  - D-12 (05-CONTEXT): dedup_key = "lower(address)|beds|round(sqft/100)*100",
        NULL when address or beds missing, "?" suffix when sqft missing.
  - Pattern 3 (05-RESEARCH §Cross-cutting Patterns): merging duplicates retains
        the canonical row and writes `data.sources_list` with one entry per
        contributing source (canonical's own source seeded first).

This file imports app.workers.scrapers.dedup which does not exist yet — the
ImportError is the RED signal. Plan 05-03 will create the module.
"""
from __future__ import annotations

import json
import uuid

from app.workers.scrapers.dedup import (
    compute_dedup_key,
    run_dedup_for_job,
)


def test_compute_dedup_key_formula():
    assert compute_dedup_key("123 Main St ", 2, 750) == "123 main st|2|700"


def test_compute_dedup_key_missing_address_returns_none():
    assert compute_dedup_key(None, 2, 750) is None
    assert compute_dedup_key("", 2, 750) is None


def test_compute_dedup_key_missing_beds_returns_none():
    assert compute_dedup_key("123 Main St", None, 750) is None


def test_compute_dedup_key_missing_sqft_uses_question_mark():
    assert compute_dedup_key("123 Main St", 2, None) == "123 main st|2|?"


async def _insert_listing(
    pg_pool,
    *,
    job_id: str,
    dedup_key: str | None,
    source_name: str,
    source_url: str,
    created_at_sql: str = "now()",
) -> str:
    listing_id = str(uuid.uuid4())
    data = {"source_name": source_name, "source_url": source_url}
    await pg_pool.execute(
        f"""INSERT INTO listings (id, job_id, data, dedup_key, created_at)
            VALUES ($1, $2, $3::jsonb, $4, {created_at_sql})""",
        listing_id,
        job_id,
        json.dumps(data),
        dedup_key,
    )
    return listing_id


async def test_run_dedup_for_job_merges_sources(pg_pool, clean_db):
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    # Canonical (older / first-seen) is the craigslist entry.
    canonical_id = await _insert_listing(
        pg_pool,
        job_id=job_id,
        dedup_key="123 main st|2|700",
        source_name="craigslist",
        source_url="https://sfbay.craigslist.org/x.html",
        created_at_sql="now() - interval '1 minute'",
    )
    dup_id = await _insert_listing(
        pg_pool,
        job_id=job_id,
        dedup_key="123 main st|2|700",
        source_name="apartments",
        source_url="https://www.apartments.com/y",
    )

    await run_dedup_for_job(pg_pool, job_id)

    # Duplicate deleted, canonical retained.
    rows = await pg_pool.fetch(
        "SELECT id, data FROM listings WHERE job_id = $1", job_id
    )
    ids = {str(r["id"]) for r in rows}
    assert canonical_id in ids
    assert dup_id not in ids
    assert len(rows) == 1

    raw = rows[0]["data"]
    data = json.loads(raw) if isinstance(raw, str) else raw
    sources_list = data.get("sources_list")
    assert sources_list is not None and len(sources_list) == 2
    names = [s["source_name"] for s in sources_list]
    # Pattern 3: canonical's own source seeded first.
    assert names[0] == "craigslist"
    assert "apartments" in names


async def test_run_dedup_for_job_skips_singletons(pg_pool, clean_db):
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    only_id = await _insert_listing(
        pg_pool,
        job_id=job_id,
        dedup_key="solo|1|500",
        source_name="craigslist",
        source_url="https://sfbay.craigslist.org/solo.html",
    )

    await run_dedup_for_job(pg_pool, job_id)

    rows = await pg_pool.fetch(
        "SELECT id, data FROM listings WHERE job_id = $1", job_id
    )
    assert len(rows) == 1
    assert str(rows[0]["id"]) == only_id
    raw = rows[0]["data"]
    data = json.loads(raw) if isinstance(raw, str) else raw
    # No merge happened → no sources_list added.
    assert "sources_list" not in data


async def test_run_dedup_for_job_skips_null_dedup_key(pg_pool, clean_db):
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    a = await _insert_listing(
        pg_pool,
        job_id=job_id,
        dedup_key=None,
        source_name="craigslist",
        source_url="https://sfbay.craigslist.org/a.html",
    )
    b = await _insert_listing(
        pg_pool,
        job_id=job_id,
        dedup_key=None,
        source_name="apartments",
        source_url="https://www.apartments.com/b",
    )

    await run_dedup_for_job(pg_pool, job_id)

    rows = await pg_pool.fetch(
        "SELECT id FROM listings WHERE job_id = $1", job_id
    )
    ids = {str(r["id"]) for r in rows}
    assert {a, b}.issubset(ids), "NULL dedup_key rows must never be merged/deleted"
