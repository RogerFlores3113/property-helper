"""Plan 04-02 SCRAP-04 per-domain rate limiter — GREEN suite.

Six behavior bullets from Plan 04-02 Task 3:

1. serializes_concurrent_requests — 3 callers on same host serialize ≥0.9s apart
2. jitter_in_range — at least one sleep recorded in [0.1, 0.5]
3. per_domain_isolation — different hosts do not block each other
4. timeout_raises_TimeoutError — second acquire times out when held
5. uses_url_hostname_as_key — Redis SET key is rate_limit:{hostname} (not path)
6. handles_missing_hostname — unparseable URL falls back to rate_limit:unknown
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.workers.rate_limit import acquire_domain_slot


# 1. -------------------------------------------------------------------------


async def test_serializes_concurrent_requests(arq_redis):
    """3 concurrent acquires on same host serialize to ≥0.9s apart (SCRAP-04)."""
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


# 2. -------------------------------------------------------------------------


async def test_jitter_in_range(arq_redis, monkeypatch):
    """At least one captured asyncio.sleep value is in the [0.1, 0.5] jitter band (D-18)."""
    captured: list[float] = []
    orig_sleep = asyncio.sleep

    async def fake_sleep(s):
        captured.append(s)
        await orig_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    async with acquire_domain_slot(arq_redis, "https://example.com/x"):
        pass
    assert any(0.1 <= s <= 0.5 for s in captured), captured


# 3. -------------------------------------------------------------------------


async def test_per_domain_isolation(arq_redis):
    """Concurrent acquires for different hosts both finish fast (no cross-block)."""
    start = time.monotonic()

    async def call(host: str) -> float:
        async with acquire_domain_slot(arq_redis, f"https://{host}/x"):
            return time.monotonic() - start

    a, b = await asyncio.gather(call("a.example"), call("b.example"))
    assert max(a, b) < 1.0, f"different hosts must not serialize; got {a=} {b=}"


# 4. -------------------------------------------------------------------------


async def test_timeout_raises_TimeoutError(arq_redis):
    """Second acquire on same host with held key + timeout_s=0.5 → TimeoutError."""
    url = "https://example.com/x"

    async with acquire_domain_slot(arq_redis, url):
        with pytest.raises(asyncio.TimeoutError):
            async with acquire_domain_slot(arq_redis, url, timeout_s=0.5):
                pass


# 5. -------------------------------------------------------------------------


async def test_uses_url_hostname_as_key(arq_redis, monkeypatch):
    """Redis SET is keyed by rate_limit:{hostname} only (T-04-06, no path)."""
    seen_keys: list[str] = []
    orig_set = arq_redis.set

    async def recording_set(key, value, *args, **kwargs):
        seen_keys.append(key.decode() if isinstance(key, bytes) else str(key))
        return await orig_set(key, value, *args, **kwargs)

    monkeypatch.setattr(arq_redis, "set", recording_set)

    async with acquire_domain_slot(
        arq_redis, "https://www.craigslist.org/search/apa?query=foo"
    ):
        pass

    assert seen_keys, "expected at least one redis.set call"
    assert seen_keys[0] == "rate_limit:www.craigslist.org"
    # Path/query MUST NOT leak into the key.
    for key in seen_keys:
        assert "/search" not in key
        assert "query=foo" not in key


# 6. -------------------------------------------------------------------------


async def test_handles_missing_hostname(arq_redis, monkeypatch):
    """Unparseable URL → key falls back to rate_limit:unknown and proceeds."""
    seen_keys: list[str] = []
    orig_set = arq_redis.set

    async def recording_set(key, value, *args, **kwargs):
        seen_keys.append(key.decode() if isinstance(key, bytes) else str(key))
        return await orig_set(key, value, *args, **kwargs)

    monkeypatch.setattr(arq_redis, "set", recording_set)

    async with acquire_domain_slot(arq_redis, "not-a-url"):
        pass

    assert seen_keys[0] == "rate_limit:unknown"
