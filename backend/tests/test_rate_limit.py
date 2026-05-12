"""RED scaffold — Plan 04-03 SCRAP-04 per-domain rate limiter.

acquire_domain_slot(redis, url, jitter=(0.1, 0.5), timeout_s=...) is an async
context manager (or coroutine) that serializes acquires within a domain to ≥1s
apart and adds 0.1-0.5s jitter. Collection ERRORs until Plan 03 lands
`app.workers.rate_limit`.
"""
from __future__ import annotations

import asyncio
import time

import pytest

# Import target — does not exist yet.
from app.workers.rate_limit import acquire_domain_slot  # noqa: F401


async def test_serializes_concurrent_requests(arq_redis):
    """3 concurrent acquires against same host serialize to ≥0.9s apart."""
    url = "https://example.com/listing/x"
    timestamps: list[float] = []

    async def caller():
        async with acquire_domain_slot(arq_redis, url):
            timestamps.append(time.monotonic())

    await asyncio.gather(caller(), caller(), caller())
    timestamps.sort()
    deltas = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    for d in deltas:
        assert d >= 0.9, f"acquires should be ≥0.9s apart, got {d}"


async def test_jitter_in_range(arq_redis, monkeypatch):
    """Sleep called with a jitter value in [0.1, 0.5]."""
    captured: list[float] = []
    orig_sleep = asyncio.sleep

    async def fake_sleep(s):
        captured.append(s)
        await orig_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    async with acquire_domain_slot(arq_redis, "https://example.com/x"):
        pass
    # At least one captured sleep value must be in jitter band.
    assert any(0.1 <= s <= 0.5 for s in captured), captured


async def test_per_domain_isolation(arq_redis):
    """Different hosts do not serialize against each other."""
    start = time.monotonic()

    async def call(host):
        async with acquire_domain_slot(arq_redis, f"https://{host}/x"):
            return time.monotonic() - start

    a, b = await asyncio.gather(call("a.example"), call("b.example"))
    # Both should finish within the single-request budget (no cross-host blocking).
    assert max(a, b) < 1.0, f"different hosts must not serialize; got {a=} {b=}"


async def test_timeout_raises_TimeoutError(arq_redis):
    """A second acquire with timeout_s=0.5 raises TimeoutError if held."""
    url = "https://example.com/x"

    async with acquire_domain_slot(arq_redis, url):
        with pytest.raises(asyncio.TimeoutError):
            async with acquire_domain_slot(arq_redis, url, timeout_s=0.5):
                pass
