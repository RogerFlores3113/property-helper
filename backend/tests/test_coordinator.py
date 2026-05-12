"""RED scaffold — Plan 04-03 SCRAP-03 parallel coordinator.

run_search_coordinator(ctx, job_id) fans out per-source ARQ jobs.
mark_done(ctx, job_id, failed: bool) is called by each source when complete;
the last call (when remaining == 0) flips search_jobs.status accordingly.

Collection ERRORs until Plan 03 lands `app.workers.coordinator`.
"""
from __future__ import annotations

import uuid

# Import target — does not exist yet.
from app.workers.coordinator import (  # noqa: F401
    ENABLED_SOURCES,
    mark_done,
    run_search_coordinator,
)


async def test_fanout_enqueues_all_sources(arq_redis, pg_pool, clean_db, monkeypatch):
    """Coordinator enqueues one job per enabled source and sets expected=N."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', $2)",
        job_id,
        "test",
    )

    calls: list[str] = []

    async def fake_enqueue(fn, *args, **kwargs):
        calls.append(fn)
        return None

    monkeypatch.setattr(arq_redis, "enqueue_job", fake_enqueue)

    ctx = {"redis": arq_redis, "pg_pool": pg_pool}
    await run_search_coordinator(ctx, job_id)

    expected_fns = {f"run_search_{s}" for s in ENABLED_SOURCES}
    assert set(calls) == expected_fns

    row = await pg_pool.fetchrow(
        "SELECT status, expected FROM search_jobs WHERE id = $1", job_id
    )
    assert row["status"] == "running"
    assert row["expected"] == len(ENABLED_SOURCES)


async def test_mark_done_completes_on_last(pg_pool, clean_db):
    """status flips to 'completed' only after the Nth (final) mark_done call."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query, expected, completed_n) "
        "VALUES ($1, 'running', 'q', 2, 0)",
        job_id,
    )
    ctx = {"pg_pool": pg_pool}

    await mark_done(ctx, job_id, failed=False)
    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "running"

    await mark_done(ctx, job_id, failed=False)
    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "completed"


async def test_partial_failure(pg_pool, clean_db):
    """one failed + one succeeded → status='completed', failed_n=1."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query, expected, completed_n, failed_n) "
        "VALUES ($1, 'running', 'q', 2, 0, 0)",
        job_id,
    )
    ctx = {"pg_pool": pg_pool}

    await mark_done(ctx, job_id, failed=True)
    await mark_done(ctx, job_id, failed=False)

    row = await pg_pool.fetchrow(
        "SELECT status, failed_n FROM search_jobs WHERE id=$1", job_id
    )
    assert row["status"] == "completed"
    assert row["failed_n"] == 1


async def test_all_failed(pg_pool, clean_db):
    """All sources failed → status='failed'."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query, expected, completed_n, failed_n) "
        "VALUES ($1, 'running', 'q', 2, 0, 0)",
        job_id,
    )
    ctx = {"pg_pool": pg_pool}

    await mark_done(ctx, job_id, failed=True)
    await mark_done(ctx, job_id, failed=True)

    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "failed"
