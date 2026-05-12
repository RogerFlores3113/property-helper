"""BaseScraper Protocol — interface shared by all Phase 4+ source scrapers.

This is intentionally a typing.Protocol (structural) rather than an ABC so each
source module can be a flat module with a free `run_search` ARQ task plus pure
parser helpers, while still being type-checkable as a "scraper".
"""
from __future__ import annotations

from typing import Any, Protocol


class BaseScraper(Protocol):
    """Structural interface for a per-source scraper.

    A scraper must expose an async `scrape` coroutine that performs the
    end-to-end search → fetch → parse → insert flow for one source. Phase 3
    implements this contract as a module-level `run_search(ctx, job_id)` ARQ
    task (see scrapers.craigslist); Phase 4 may wrap multiple sources behind
    classes implementing this protocol.
    """

    async def scrape(
        self,
        job_id: str,
        query: str,
        chips: list[Any],
        max_listings: int,
    ) -> None: ...
