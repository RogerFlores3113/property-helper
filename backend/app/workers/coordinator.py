"""Parallel coordinator — Plan 04-03 SCRAP-03 fan-out + completion counter.

Public surface::

    async def run_search_coordinator(ctx, job_id: str) -> None
    async def mark_done(redis, db, job_id: str, *, failed: bool) -> None
    ENABLED_SOURCES: list[str]   # initially ["craigslist"]; Plan 04 appends "apartments"

Pattern (D-13/D-14/D-15/D-16):

1. Coordinator flips ``search_jobs.status='running'`` once, then SETs three
   Redis counter keys with a 1h TTL (Pitfall 8) — ``expected:{job_id}=N``,
   ``completed:{job_id}=0``, ``failed:{job_id}=0`` — and enqueues one ARQ
   sub-task per source in :data:`ENABLED_SOURCES`. The coordinator does NOT
   block on sub-tasks (Pitfall 5); it returns immediately.

2. Each sub-task calls ``mark_done(redis, db, job_id, failed=...)`` exactly
   once at its terminal point (success and exception paths). ``mark_done`` is
   the *only* place that writes terminal status — sub-tasks never UPDATE
   ``search_jobs.status`` directly (D-15). It is also idempotent: the UPDATE
   is guarded by ``WHERE id=$1 AND status='running'`` so a stale third call
   becomes a no-op.

3. Partial-failure semantics (D-16): one bad source does not poison the whole
   job. The terminal status is ``'failed'`` iff *every* sub-task failed
   (``failed_n >= expected``); otherwise it is ``'completed'``.

SECURITY (threat model):

- Redis counter keys use server-issued UUIDs (``job_id``); user input never
  reaches the Redis key space.
- 1h TTL on every counter key prevents unbounded Redis growth even if a
  sub-task is lost.
- Idempotent ``mark_done`` UPDATE prevents double-flip races.
"""
from __future__ import annotations

from typing import Any

import structlog

log = structlog.get_logger()

# Module-level list — Plan 04-04 appended "apartments". Keep it a list, not a
# tuple, so future plans can append additional sources in place.
ENABLED_SOURCES: list[str] = ["craigslist", "apartments"]

# 1-hour TTL on counter keys (Pitfall 8) — long enough for the slowest source
# to complete, short enough to bound Redis growth if a sub-task is lost.
_COUNTER_TTL_S = 3600


def _expected_key(job_id: str) -> str:
    return f"expected:{job_id}"


def _completed_key(job_id: str) -> str:
    return f"completed:{job_id}"


def _failed_key(job_id: str) -> str:
    return f"failed:{job_id}"


async def run_search_coordinator(ctx: dict, job_id: str) -> None:
    """ARQ entrypoint — fan-out one sub-task per enabled source.

    Flips ``search_jobs.status`` to ``'running'`` once, primes the Redis
    counter keys with a 1h TTL, then ``enqueue_job`` for every source in
    :data:`ENABLED_SOURCES`. Does NOT block on the sub-tasks (Pitfall 5) —
    each sub-task calls :func:`mark_done` which owns the terminal flip.
    """
    db = ctx["db"]
    redis = ctx["redis"]

    await db.execute(
        "UPDATE search_jobs SET status='running' WHERE id=$1", job_id
    )

    # Prime the counter keys (Pitfall 8: ex=3600 on every initial SET).
    await redis.set(_expected_key(job_id), len(ENABLED_SOURCES), ex=_COUNTER_TTL_S)
    await redis.set(_completed_key(job_id), 0, ex=_COUNTER_TTL_S)
    await redis.set(_failed_key(job_id), 0, ex=_COUNTER_TTL_S)

    for src in ENABLED_SOURCES:
        await redis.enqueue_job(f"run_search_{src}", job_id)

    log.info(
        "coordinator.fanned_out",
        job_id=job_id,
        sources=list(ENABLED_SOURCES),
    )


async def mark_done(
    redis: Any,
    db: Any,
    job_id: str,
    *,
    failed: bool,
) -> None:
    """Sub-task completion hook — increments counters and (on the final call)
    flips ``search_jobs.status`` to ``'completed'`` or ``'failed'``.

    Idempotent: the terminal UPDATE is guarded by ``status='running'`` so a
    stale third invocation after the job already flipped is a no-op.

    Partial-failure rule (D-16): the job is ``'failed'`` only when every
    sub-task failed; one or more successes mean the job is ``'completed'``.
    """
    if failed:
        await redis.incr(_failed_key(job_id))
        await redis.expire(_failed_key(job_id), _COUNTER_TTL_S)

    await redis.incr(_completed_key(job_id))
    # Refresh TTL so the key cannot quietly disappear mid-job (Pitfall 8).
    await redis.expire(_completed_key(job_id), _COUNTER_TTL_S)

    completed_raw = await redis.get(_completed_key(job_id))
    expected_raw = await redis.get(_expected_key(job_id))
    failed_raw = await redis.get(_failed_key(job_id))

    completed_n = int(completed_raw) if completed_raw is not None else 0
    expected_n = int(expected_raw) if expected_raw is not None else 0
    failed_n = int(failed_raw) if failed_raw is not None else 0

    if expected_n == 0 or completed_n < expected_n:
        # Not the final call yet — leave status='running'.
        return

    # D-16: partial failure ≠ overall failure.
    terminal = "failed" if failed_n >= expected_n else "completed"

    # Guarded UPDATE — only the first crossing of (completed >= expected)
    # flips status. Subsequent (stale) calls become no-ops.
    await db.execute(
        "UPDATE search_jobs SET status=$1, completed_at=NOW() "
        "WHERE id=$2 AND status='running'",
        terminal,
        job_id,
    )

    log.info(
        "coordinator.done",
        job_id=job_id,
        status=terminal,
        failed_n=failed_n,
        expected_n=expected_n,
    )
