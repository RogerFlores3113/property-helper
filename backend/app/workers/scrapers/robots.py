"""RobotsCache — per-job-run robots.txt enforcement (SCRAP-05, D-05/D-06).

One fetch per origin. Fail-open on fetch error (logs robots.fetch_failed). All
allow/disallow decisions are logged via structlog for SC#3 verifiability.
"""
from __future__ import annotations

from urllib.parse import urlparse

import httpx
import structlog
from protego import Protego

log = structlog.get_logger()

# Realistic browser UA — Pitfall 3 (Craigslist 403s default python-httpx UA).
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class RobotsCache:
    """Per-job-run cache: one fetch per origin (D-06)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client
        self._parsers: dict[str, Protego] = {}

    async def allow(self, url: str) -> bool:
        origin = self._origin(url)
        parser = self._parsers.get(origin)
        if parser is None:
            parser = await self._load(origin)
            self._parsers[origin] = parser
        allowed = parser.can_fetch(url, USER_AGENT)
        if not allowed:
            log.info("robots.disallow", url=url, origin=origin)
        return allowed

    async def _load(self, origin: str) -> Protego:
        robots_url = f"{origin}/robots.txt"
        try:
            r = await self._client.get(robots_url, timeout=10.0)
            r.raise_for_status()
            log.info(
                "robots.fetched",
                origin=origin,
                size=len(r.text),
                disallow_count=r.text.lower().count("disallow:"),
            )
            return Protego.parse(r.text)
        except httpx.HTTPError as e:
            # Fail-open: log loudly and treat as fully allowed.
            log.warning("robots.fetch_failed", origin=origin, error=str(e))
            return Protego.parse("")

    @staticmethod
    def _origin(url: str) -> str:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}"
