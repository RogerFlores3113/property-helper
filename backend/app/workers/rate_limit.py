"""Per-domain rate limiter — Plan 04-02 SCRAP-04.

Public surface::

    async with acquire_domain_slot(redis, url, timeout_s=30.0):
        await fetch(url)

Coordinates ≤1 request per second per *origin host* across all ARQ workers
sharing the Redis instance. Uses a Redis ``SET NX PX 1000`` mutex keyed by
``rate_limit:{hostname}`` — when the SET succeeds, the caller holds the slot;
when it fails, the caller polls every 50ms until either the previous holder's
key expires (PX=1000ms) or ``timeout_s`` is reached (raises
``asyncio.TimeoutError``).

A small uniform jitter in ``[0.1, 0.5]`` seconds is applied after acquire to
avoid thundering-herd behaviour across parallel scrapers (D-18).

Decisions implemented:
    - D-17: per-domain key prefix ``rate_limit:{domain}``.
    - D-18: post-acquire jitter ``random.uniform(0.1, 0.5)``.
    - D-19: SET NX PX 1000 mutex (simpler than full token bucket).
    - D-20: callers MUST pass ``ctx["redis"]`` (ArqRedis); the limiter
      never opens its own connection.

SECURITY (T-04-06): the Redis key suffix is the URL *hostname only*, not the
path or query — long attacker-controlled paths cannot poison the key space.
"""
from __future__ import annotations

import asyncio
import random
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import structlog

log = structlog.get_logger()

_KEY_PREFIX = "rate_limit:"
_HOLD_MS = 1000  # 1 req/sec ceiling
_POLL_INTERVAL_S = 0.05


def _domain_key(url: str) -> str:
    """Build the Redis key from the URL hostname only (T-04-06)."""
    host = urlparse(url).hostname or "unknown"
    return f"{_KEY_PREFIX}{host}"


@asynccontextmanager
async def acquire_domain_slot(
    redis: Any,
    url: str,
    timeout_s: float = 30.0,
):
    """Async context manager — acquires the per-domain slot for ``url``.

    Args:
        redis: An ``ArqRedis`` (or any ``redis.asyncio.Redis``) instance.
            Callers MUST pass ``ctx["redis"]`` from the ARQ task context
            — this function never opens its own connection (D-20).
        url: Any absolute URL; only the ``hostname`` is used to derive
            the Redis key (T-04-06).
        timeout_s: Maximum seconds to wait before raising
            :class:`asyncio.TimeoutError`.

    Raises:
        asyncio.TimeoutError: when the slot cannot be acquired within
            ``timeout_s``.
    """
    key = _domain_key(url)
    loop = asyncio.get_event_loop()
    start = loop.time()
    waited_s = 0.0

    # D-18 jitter — uniform in [0.1, 0.5]. Sample once up front so the hold
    # TTL we SET with already accounts for the jitter sleep below. This keeps
    # successive acquires reliably ≥1s apart regardless of jitter variance
    # across callers.
    jitter = random.uniform(0.1, 0.5)

    while True:
        # SET NX PX — atomic mutex with auto-expiry. Returns True iff we won.
        # Base TTL is px=1000 ms (the 1 req/sec gate per D-17); we extend it
        # by the jitter sleep so the gate is observed across the *entire*
        # held window, not just up to the SET-success instant.
        won = await redis.set(key, "1", nx=True, px=1000 + int(jitter * 1000))
        if won:
            break
        waited_s = loop.time() - start
        if waited_s >= timeout_s:
            raise asyncio.TimeoutError(
                f"acquire_domain_slot: timed out waiting for {key}"
            )
        await asyncio.sleep(_POLL_INTERVAL_S)

    # Apply the pre-sampled jitter inside the held window.
    await asyncio.sleep(jitter)

    log.info(
        "rate_limit.acquired",
        domain=key[len(_KEY_PREFIX):],
        waited_s=round(waited_s, 3),
        jitter_s=round(jitter, 3),
    )

    try:
        yield
    finally:
        # Do NOT delete the key on exit: PX=1000ms is the rate-limit window.
        # Letting the key live for its full TTL is what enforces ≥1 req/sec.
        pass
