"""GREEN tests — Plan 04-03 SCRAP-03 parallel coordinator.

Covers the 6 behaviors from the plan's <behavior> block:
  - test_fanout_enqueues_all_sources
  - test_mark_done_completes_on_last
  - test_partial_failure
  - test_all_failed
  - test_counter_ttl_set
  - test_status_not_double_flipped
"""
from __future__ import annotations

import uuid

from app.workers.coordinator import (
    ENABLED_SOURCES,
    mark_done,
    run_search_coordinator,
)


async def test_fanout_enqueues_all_sources(arq_redis, pg_pool, clean_db, monkeypatch):
    """Coordinator (1) flips status='running', (2) primes counter keys with
    1h TTL, (3) enqueues exactly one sub-task per enabled source (set equality,
    no duplicates, no extras).
    """
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

    monkeypatch.setattr(arq_redis, "enqueue_job", fake_enqueue, raising=False)

    ctx = {"redis": arq_redis, "db": pg_pool}
    await run_search_coordinator(ctx, job_id)

    expected_fns = {f"run_search_{s}" for s in ENABLED_SOURCES}
    assert set(calls) == expected_fns
    assert len(calls) == len(ENABLED_SOURCES), "no duplicates expected"

    row = await pg_pool.fetchrow(
        "SELECT status FROM search_jobs WHERE id=$1", job_id
    )
    assert row["status"] == "running"

    expected_raw = await arq_redis.get(f"expected:{job_id}")
    completed_raw = await arq_redis.get(f"completed:{job_id}")
    failed_raw = await arq_redis.get(f"failed:{job_id}")
    assert int(expected_raw) == len(ENABLED_SOURCES)
    assert int(completed_raw) == 0
    assert int(failed_raw) == 0


async def test_mark_done_completes_on_last(arq_redis, pg_pool, clean_db):
    """status flips to 'completed' only after the Nth (final) mark_done call."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 2, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await mark_done(arq_redis, pg_pool, job_id, failed=False)
    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "running"

    await mark_done(arq_redis, pg_pool, job_id, failed=False)
    row = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id=$1", job_id
    )
    assert row["status"] == "completed"
    assert row["completed_at"] is not None


async def test_partial_failure(arq_redis, pg_pool, clean_db):
    """D-16: one failed + one succeeded → status='completed', failed counter=1."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 2, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await mark_done(arq_redis, pg_pool, job_id, failed=True)
    await mark_done(arq_redis, pg_pool, job_id, failed=False)

    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "completed"

    failed_n = int(await arq_redis.get(f"failed:{job_id}"))
    assert failed_n == 1


async def test_all_failed(arq_redis, pg_pool, clean_db):
    """All sources failed → status='failed'."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 2, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await mark_done(arq_redis, pg_pool, job_id, failed=True)
    await mark_done(arq_redis, pg_pool, job_id, failed=True)

    row = await pg_pool.fetchrow("SELECT status FROM search_jobs WHERE id=$1", job_id)
    assert row["status"] == "failed"


async def test_counter_ttl_set(arq_redis, pg_pool, clean_db, monkeypatch):
    """Pitfall 8: every counter key must have a TTL > 0 after both
    run_search_coordinator (initial SET) and mark_done (refresh)."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', 'q')",
        job_id,
    )

    async def fake_enqueue(fn, *args, **kwargs):
        return None

    monkeypatch.setattr(arq_redis, "enqueue_job", fake_enqueue, raising=False)

    ctx = {"redis": arq_redis, "db": pg_pool}
    await run_search_coordinator(ctx, job_id)

    assert await arq_redis.ttl(f"expected:{job_id}") > 0
    assert await arq_redis.ttl(f"completed:{job_id}") > 0
    assert await arq_redis.ttl(f"failed:{job_id}") > 0

    await mark_done(arq_redis, pg_pool, job_id, failed=False)
    # completed key TTL must be refreshed (still > 0).
    assert await arq_redis.ttl(f"completed:{job_id}") > 0


async def test_status_not_double_flipped(arq_redis, pg_pool, clean_db):
    """A third mark_done call after status already flipped must not error
    and must not change status (idempotency safeguard via WHERE guard)."""
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'running', 'q')",
        job_id,
    )
    await arq_redis.set(f"expected:{job_id}", 2, ex=3600)
    await arq_redis.set(f"completed:{job_id}", 0, ex=3600)
    await arq_redis.set(f"failed:{job_id}", 0, ex=3600)

    await mark_done(arq_redis, pg_pool, job_id, failed=False)
    await mark_done(arq_redis, pg_pool, job_id, failed=False)

    row1 = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id=$1", job_id
    )
    assert row1["status"] == "completed"
    completed_at_1 = row1["completed_at"]

    # Third call — must not error, must not change status or completed_at.
    await mark_done(arq_redis, pg_pool, job_id, failed=False)

    row2 = await pg_pool.fetchrow(
        "SELECT status, completed_at FROM search_jobs WHERE id=$1", job_id
    )
    assert row2["status"] == "completed"
    assert row2["completed_at"] == completed_at_1
