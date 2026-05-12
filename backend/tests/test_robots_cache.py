"""Tests for RobotsCache — SCRAP-05 (D-05/D-06).

Uses httpx.MockTransport to inject canned robots.txt responses. No live network.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
import pytest

from app.workers.scrapers.robots import RobotsCache

FIXTURE = Path(__file__).parent / "fixtures" / "craigslist_robots.txt"


def _robots_text() -> str:
    return FIXTURE.read_text()


def _make_client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


async def test_allow_disallow():
    text = _robots_text()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, text=text)

    async with _make_client(handler) as client:
        cache = RobotsCache(client)
        assert await cache.allow("https://sfbay.craigslist.org/search/apa") is True
        assert (
            await cache.allow("https://sfbay.craigslist.org/reply/abc/123") is False
        )


async def test_one_fetch_per_origin():
    text = _robots_text()
    fetch_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fetch_count
        fetch_count += 1
        return httpx.Response(200, text=text)

    async with _make_client(handler) as client:
        cache = RobotsCache(client)
        await cache.allow("https://sfbay.craigslist.org/search/apa")
        await cache.allow("https://sfbay.craigslist.org/pen/apa/d/foo.html")
        await cache.allow("https://sfbay.craigslist.org/nby/apa/d/bar.html")

    assert fetch_count == 1, f"expected 1 robots.txt fetch, got {fetch_count}"


async def test_disallow_skipped(caplog):
    text = _robots_text()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=text)

    caplog.set_level(logging.INFO)
    async with _make_client(handler) as client:
        cache = RobotsCache(client)
        allowed = await cache.allow("https://sfbay.craigslist.org/reply/foo")

    assert allowed is False
    # structlog logs through stdlib logging by default; the event key 'robots.disallow'
    # appears in the rendered message.
    assert any("robots.disallow" in rec.getMessage() for rec in caplog.records)


async def test_fetch_failure_logs_and_allows(caplog):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    caplog.set_level(logging.WARNING)
    async with _make_client(handler) as client:
        cache = RobotsCache(client)
        allowed = await cache.allow("https://sfbay.craigslist.org/search/apa")

    assert allowed is True  # fail-open per RESEARCH Pattern 1
    assert any("robots.fetch_failed" in rec.getMessage() for rec in caplog.records)
