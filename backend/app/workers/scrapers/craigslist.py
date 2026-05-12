"""Craigslist apartments scraper — SCRAP-02, SCRAP-04, SCRAP-05, D-07.

ARQ entrypoint: run_search_craigslist(ctx, job_id)
Pure helpers: parse_search_results(html), parse_listing(html, source_url)

Renamed from run_search → run_search_craigslist in Plan 04-03 so the parallel
coordinator (run_search_coordinator) can fan out one ARQ sub-task per source.
Inline jitter sleeps replaced by acquire_domain_slot (Redis SET NX PX 1000)
which serializes fetches across all workers (D-20 / SCRAP-04). Terminal
status writes removed — mark_done (in app.workers.coordinator) is the only
path that flips search_jobs.status to its terminal value (D-15).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
import structlog
from selectolax.parser import HTMLParser

from ...guards.budget import BudgetExceeded, BudgetGuard
from ...settings import settings
from ..coordinator import mark_done
from ..rate_limit import acquire_domain_slot
from .location import location_to_search_url
from .robots import USER_AGENT, RobotsCache

log = structlog.get_logger()

_REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=10.0)
_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Photo-host whitelist (T-03-05): only persist photo URLs whose hostname ends
# with one of these. Anything else is dropped to None to prevent attacker-
# controlled tracker URLs from being persisted/rendered.
_PHOTO_HOST_SUFFIXES = ("craigslist.org", "craigslistimages.org")


def _make_client() -> httpx.AsyncClient:
    """Module-level factory — tests monkeypatch this to inject MockTransport."""
    return httpx.AsyncClient(headers=_HEADERS, timeout=_REQUEST_TIMEOUT, follow_redirects=True)


# ----------------------------- pure parsers ----------------------------------

def parse_search_results(html: str) -> list[str]:
    """Extract listing detail URLs from a Craigslist search results page."""
    tree = HTMLParser(html)
    urls: list[str] = []
    seen: set[str] = set()
    selectors = (
        "li.cl-static-search-result a",
        "li.result-row a.result-title",
        "a[href$='.html']",
    )
    for sel in selectors:
        for node in tree.css(sel):
            href = node.attributes.get("href")
            if not href or not href.endswith(".html"):
                continue
            # Normalize relative URLs (defensive; CL usually emits absolute).
            if href.startswith("/"):
                href = urljoin("https://www.craigslist.org", href)
            if href in seen:
                continue
            seen.add(href)
            urls.append(href)
        if urls:
            break
    return urls


_PRICE_RE = re.compile(r"\$?([\d,]+)")
_BR_RE = re.compile(r"(\d+)\s*BR", re.IGNORECASE)
_BA_RE = re.compile(r"(\d+(?:\.\d+)?)\s*Ba", re.IGNORECASE)


def _parse_price(text: str | None) -> int | None:
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_attrgroup(tree: HTMLParser) -> tuple[int | None, float | None, int | None]:
    """Extract beds/baths/sqft from the .attrgroup section."""
    beds: int | None = None
    baths: float | None = None
    sqft: int | None = None
    for node in tree.css(".attrgroup span, p.attrgroup span"):
        text = node.text(strip=True)
        if not text:
            continue
        if beds is None:
            mb = _BR_RE.search(text)
            if mb:
                try:
                    beds = int(mb.group(1))
                except ValueError:
                    pass
        if baths is None:
            mba = _BA_RE.search(text)
            if mba:
                try:
                    baths = float(mba.group(1))
                except ValueError:
                    pass
        if sqft is None and text.lower().endswith("ft2"):
            digits = re.sub(r"[^\d]", "", text)
            if digits:
                try:
                    sqft = int(digits)
                except ValueError:
                    pass
    return beds, baths, sqft


def _parse_posted_date(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    # Pitfall 5: ensure offset has colon (Python 3.12 fromisoformat handles both,
    # but normalize for safety in case of older deployment).
    s = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", s)
    s = s.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date().isoformat()
    except ValueError:
        return None


def _safe_float(raw: str | None, lo: float, hi: float) -> float | None:
    """Cast to float and range-check (T-03-03 / ASVS V5)."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (ValueError, TypeError):
        return None
    if not (lo <= v <= hi):
        return None
    return v


def parse_listing(html: str, source_url: str) -> tuple[dict, str | None]:
    """Extract structured fields from a Craigslist apartment detail page."""
    tree = HTMLParser(html)

    # lat/lng from <div id="map" data-latitude data-longitude> (D-07)
    map_div = tree.css_first("#map")
    lat = lng = None
    if map_div is not None:
        lat = _safe_float(map_div.attributes.get("data-latitude"), -90.0, 90.0)
        lng = _safe_float(map_div.attributes.get("data-longitude"), -180.0, 180.0)

    # Price — first .price node
    price_node = tree.css_first(".price")
    price = _parse_price(price_node.text() if price_node else None)

    # Beds / baths / sqft
    beds, baths, _sqft = _parse_attrgroup(tree)

    # Posted date — <time datetime="...">
    time_node = tree.css_first("time.timeago, time[datetime]")
    posted_date = _parse_posted_date(
        time_node.attributes.get("datetime") if time_node else None
    )

    # First photo — prefer the full-size href from #thumbs <a>, fall back to <img src>.
    # Craigslist thumbnail <img src> are low-res (e.g. 300x300); the parent <a href>
    # links to the full-size image (600x450 or larger). Swap any embedded size token
    # in the URL to 1200x900 for maximum available resolution.
    thumb_anchor = tree.css_first("#thumbs a")
    img = tree.css_first("#thumbs a img, .gallery .slide img, .gallery img")
    raw_photo = None
    if thumb_anchor is not None:
        raw_photo = thumb_anchor.attributes.get("href")
    if not raw_photo and img is not None:
        raw_photo = img.attributes.get("src")
    # Upgrade resolution: replace WxH size token with 1200x900.
    if raw_photo:
        import re as _re
        raw_photo = _re.sub(r"\d+x\d+(?:c)?(?=\.\w+$)", "1200x900", raw_photo)
    photo_url = raw_photo
    if photo_url:
        try:
            host = urlparse(photo_url).hostname or ""
        except ValueError:
            host = ""
        if not any(host.endswith(suf) for suf in _PHOTO_HOST_SUFFIXES):
            photo_url = None

    # Amenities — short text bubbles inside .attrgroup (skip key:value lines)
    amenities: list[str] = []
    for n in tree.css(".attrgroup span, p.attrgroup span"):
        text = n.text(strip=True)
        if not text or ":" in text:
            continue
        # Drop the BR/BA bubble — captured above as structured fields.
        if _BR_RE.search(text) or _BA_RE.search(text) or text.lower().endswith("ft2"):
            continue
        if text in amenities:
            continue
        amenities.append(text)
        if len(amenities) >= 8:
            break

    # Address — .mapaddress or .street-address
    addr_node = tree.css_first(".mapaddress, h2.street-address, .postingaddress")
    address = addr_node.text(strip=True) if addr_node else None

    data = {
        "address": address,
        "price": price,
        "beds": beds,
        "baths": baths,
        "amenities": amenities,
        "source_url": source_url,
        "source_name": "craigslist",
        "posted_date": posted_date,
        "lat": lat,
        "lng": lng,
    }
    return data, photo_url


# ----------------------------- ARQ task --------------------------------------

async def run_search_craigslist(ctx, job_id: str) -> None:
    """ARQ sub-task — Craigslist source for the parallel coordinator (Plan 04-03).

    Driven by run_search_coordinator. Status flips are owned exclusively by
    mark_done (D-15) — this function never writes terminal status (completed
    or failed) directly. Every outbound HTTP fetch is serialized through
    acquire_domain_slot (D-20 / SCRAP-04), replacing the previous inline
    per-process jitter (random.uniform with a half-second floor) which only
    coordinated within a single worker process.

    Calls mark_done(redis, db, job_id, failed=False) on success and
    mark_done(redis, db, job_id, failed=True) on any exception (and re-raises).
    """
    db = ctx["db"]
    redis = ctx["redis"]
    guard = BudgetGuard.from_env(db=db)

    try:
        # 1. Read the job row for the query string (chips/global_flex ignored in Phase 3).
        job_row = await db.fetchrow(
            "SELECT query FROM search_jobs WHERE id=$1", job_id
        )
        query = (job_row["query"] if job_row else "") or ""

        # 2. Resolve to a Craigslist search URL via the whitelist (T-03-01 SSRF).
        search_url = location_to_search_url(query)
        if search_url is None:
            log.info("scraper.no_location_match", job_id=job_id, query=query[:80])
            await guard.record_spend(tokens=0, cost_usd=0.0)
            await mark_done(redis, db, job_id, failed=False)
            return

        client = _make_client()
        try:
            robots = RobotsCache(client)

            # 3. robots.txt gate on the search URL itself.
            if not await robots.allow(search_url):
                log.info("scraper.search_disallowed", job_id=job_id, url=search_url)
                await guard.record_spend(tokens=0, cost_usd=0.0)
                await mark_done(redis, db, job_id, failed=False)
                return

            # 4. Fetch search results page — rate-limited per-domain (D-20).
            try:
                async with acquire_domain_slot(redis, search_url):
                    resp = await client.get(search_url)
                    resp.raise_for_status()
            except httpx.HTTPError as e:
                log.warning("scraper.fetch_failed", url=search_url, error=str(e))
                await guard.record_spend(tokens=0, cost_usd=0.0)
                await mark_done(redis, db, job_id, failed=False)
                return

            detail_urls = parse_search_results(resp.text)[: settings.scraper_max_listings]
            log.info(
                "scraper.search_parsed",
                job_id=job_id,
                url=search_url,
                count=len(detail_urls),
            )

            # 5. Fetch + parse each detail page — rate-limited per-domain (D-20).
            # check_iter() placement preserved (Pitfall 3); only the inline
            # jitter sleep is replaced by acquire_domain_slot.
            inserted = 0
            for detail_url in detail_urls:
                try:
                    guard.check_iter()
                except BudgetExceeded:
                    raise

                if not await robots.allow(detail_url):
                    continue

                try:
                    async with acquire_domain_slot(redis, detail_url):
                        dresp = await client.get(detail_url)
                        dresp.raise_for_status()
                except httpx.HTTPError as e:
                    log.warning("scraper.fetch_failed", url=detail_url, error=str(e))
                    continue

                listing_data, photo_url = parse_listing(dresp.text, source_url=detail_url)
                serialized = json.dumps(listing_data)

                # Per-payload guard on the extracted JSON, not raw HTML (COST-03).
                try:
                    guard.check_payload(len(serialized.encode()))
                except BudgetExceeded:
                    log.warning(
                        "scraper.payload_oversize",
                        url=detail_url,
                        bytes=len(serialized.encode()),
                    )
                    continue
                await db.execute(
                    """INSERT INTO listings (id, job_id, data, photo_url, created_at)
                       VALUES ($1, $2, $3::jsonb, $4, $5)""",
                    str(uuid.uuid4()),
                    job_id,
                    serialized,
                    photo_url,
                    datetime.now(timezone.utc),
                )
                inserted += 1

            # 6. Record spend (Pitfall 7 — tokens=0 for non-LLM scraping).
            await guard.record_spend(tokens=0, cost_usd=0.0)

            log.info("scraper.completed", job_id=job_id, inserted=inserted)
        finally:
            await client.aclose()

        # 7. Terminal success — mark_done owns the status flip (D-15).
        await mark_done(redis, db, job_id, failed=False)
    except BudgetExceeded:
        # D-15: never write status here; mark_done handles partial-vs-full
        # failure semantics via the Redis failed counter (D-16).
        await mark_done(redis, db, job_id, failed=True)
        raise
    except Exception:
        await mark_done(redis, db, job_id, failed=True)
        raise
