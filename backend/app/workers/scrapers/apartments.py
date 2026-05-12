"""Apartments.com scraper — Plan 04-04 (SCRAP-01, SCRAP-03, SCRAP-04, SCRAP-06, SCRAP-07).

ARQ entrypoint: ``run_search_apartments(ctx, job_id)`` — driven by
``run_search_coordinator`` (Plan 04-03). Status flips are owned exclusively by
``mark_done`` (D-15); this function never writes terminal status directly.

Pattern:
    1. Read the job query and resolve to the Apartments.com search URL via the
       slug allowlist (T-04-02 SSRF). None → mark_done(failed=False) and return.
    2. Open three nested ``async with`` context managers (Pitfall 6):
       ``async_playwright()`` → ``chromium.launch(headless=True)`` →
       ``browser.new_context(...)``. ``stealth_async(page)`` BEFORE any goto
       (D-10 / T-04-08).
    3. Every ``page.goto`` is wrapped by ``acquire_domain_slot`` (D-20 / SCRAP-04).
    4. ``raw_html = await page.content()`` → ``text = prefilter(raw, _LISTING_ROOT_SELECTOR)``
       → ``await llm_extract.extract(text, source_url, "apartments", guard)``.
       Raw HTML never reaches the LLM (T-04-01 / SCRAP-06 / SCRAP-07).
    5. LLM-extracted ``image_url`` host whitelisted to ``apartments.com``
       suffixes before INSERT (T-04-03 server-side defense in depth).
    6. Terminal: ``mark_done(redis, db, job_id, failed=False)`` on success;
       ``mark_done(..., failed=True)`` and re-raise on any exception.

SECURITY (threat model T-04-01 through T-04-08 from 04-04-PLAN.md):
    - Forced tool-use + Pydantic field bounds in llm_extract contain LLM output.
    - URL constructed only via ``location_to_apartments_url`` allowlist.
    - LLM-fabricated ``source_url`` is overridden by the loop's ``detail_url``
      (the URL Claude was actually given) inside llm_extract.
    - photo_url host suffix check rejects non-apartments.com image hosts.
    - Playwright headless, no extensions, no user_data_dir; fresh context per job.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

import structlog
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

from ...guards.budget import BudgetExceeded, BudgetGuard
from ...settings import settings
from ..coordinator import mark_done
from ..rate_limit import acquire_domain_slot
from . import llm_extract
from .location import location_to_apartments_url
from .prefilter import prefilter
from .robots import USER_AGENT

log = structlog.get_logger()


# ---- module-level constants (kept stable for prompt-cache + grep contracts) --

_LISTING_ROOT_SELECTOR: str = "#placardContainer ul li, .placard"

# Photo-host allowlist (defense in depth for T-04-03 tracker injection):
# any LLM-extracted ``image_url`` whose hostname does not end in one of these
# suffixes is dropped to ``None`` before INSERT. The frontend
# ``isAllowedApartmentsUrl`` helper (Plan 04-01) is the second layer.
_PHOTO_HOST_SUFFIXES: tuple[str, ...] = ("apartments.com",)


# ---- playwright-stealth compatibility shim -----------------------------------
#
# playwright-stealth 2.x exposes its API as ``Stealth().apply_stealth_async``
# (per the library's README/CHANGELOG) instead of the legacy
# ``stealth_async(page)`` free function. We keep the symbol name
# ``stealth_async`` so the test/grep contracts in 04-04-PLAN.md continue to
# match and so the call site below reads naturally; the wrapper just routes
# to whichever shape the installed version provides.

async def stealth_async(page) -> None:  # pragma: no cover — wrapper
    """Apply playwright-stealth fingerprint patches to ``page`` (D-10 / T-04-08).

    Compatible with both ``Stealth().apply_stealth_async(page)`` (v2+) and a
    free-function ``stealth_async`` if a future version reintroduces it.
    """
    stealth = Stealth()
    apply_async = getattr(stealth, "apply_stealth_async", None)
    if apply_async is not None:
        await apply_async(page)
        return
    # Fallback for any version that ships the legacy free function.
    from playwright_stealth import stealth_async as _legacy_stealth_async  # type: ignore[attr-defined]

    await _legacy_stealth_async(page)


# ---- ARQ task ----------------------------------------------------------------


async def run_search_apartments(ctx, job_id: str) -> None:
    """ARQ sub-task — Apartments.com source for the parallel coordinator.

    Calls ``mark_done(redis, db, job_id, failed=False)`` on success and
    ``mark_done(redis, db, job_id, failed=True)`` on any exception (re-raised
    afterwards so ARQ records the run as failed).
    """
    db = ctx["db"]
    redis = ctx["redis"]
    guard = BudgetGuard.from_env(db=db)

    try:
        # 1. Read the job row for the query string.
        job_row = await db.fetchrow(
            "SELECT query FROM search_jobs WHERE id=$1", job_id
        )
        query = (job_row["query"] if job_row else "") or ""

        # 2. Resolve to an Apartments.com search URL via the SSRF allowlist
        #    (T-04-02). None → short-circuit success path (no scraping target).
        search_url = location_to_apartments_url(query)
        if search_url is None:
            log.info("scraper.no_location_match", job_id=job_id, source="apartments", query=query[:80])
            await guard.record_spend(tokens=0, cost_usd=0.0)
            await mark_done(redis, db, job_id, failed=False)
            return

        inserted = 0
        # 3. Three nested async-with (Pitfall 6 — guarantees browser.close on
        #    any exception). headless=True, no user_data_dir, fresh context per
        #    job (D-12 / T-04-08).
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="en-US",
                    timezone_id="America/Los_Angeles",
                    user_agent=USER_AGENT,
                )
                try:
                    page = await context.new_page()
                    # D-10 / T-04-08: stealth BEFORE any goto.
                    await stealth_async(page)

                    # 4. Search page — rate-limited per domain (D-20).
                    async with acquire_domain_slot(redis, search_url):
                        await page.goto(
                            search_url,
                            wait_until="domcontentloaded",
                            timeout=30000,
                        )
                    try:
                        await page.wait_for_selector(".placard", timeout=15000)
                    except Exception as e:  # noqa: BLE001 — non-fatal
                        log.warning(
                            "scraper.placard_wait_failed",
                            source="apartments",
                            url=search_url,
                            error=type(e).__name__,
                        )

                    # 5. Collect detail URLs from the search page.
                    detail_urls: list[str] = []
                    locator = page.locator("article.placard a.property-link, .placard a.property-link")
                    anchors = await locator.all()
                    seen: set[str] = set()
                    for anchor in anchors:
                        href = await anchor.get_attribute("href")
                        if not href or href in seen:
                            continue
                        # Only follow apartments.com hrefs (defense in depth).
                        try:
                            host = urlparse(href).hostname or ""
                        except ValueError:
                            continue
                        if not host.endswith("apartments.com"):
                            continue
                        seen.add(href)
                        detail_urls.append(href)
                    detail_urls = detail_urls[: settings.scraper_max_listings]

                    log.info(
                        "scraper.search_parsed",
                        source="apartments",
                        job_id=job_id,
                        url=search_url,
                        count=len(detail_urls),
                    )

                    # 6. For each detail page: rate-limit → goto → prefilter →
                    #    llm_extract → host-whitelist photo_url → INSERT.
                    for detail_url in detail_urls:
                        # Iter guard once per page iteration (Pitfall 3 — NOT
                        # per payload check).
                        try:
                            guard.check_iter()
                        except BudgetExceeded:
                            raise

                        async with acquire_domain_slot(redis, detail_url):
                            await page.goto(
                                detail_url,
                                wait_until="domcontentloaded",
                                timeout=30000,
                            )

                        raw_html = await page.content()
                        text = prefilter(raw_html, _LISTING_ROOT_SELECTOR)
                        if not text:
                            log.info(
                                "scraper.prefilter_empty",
                                source="apartments",
                                url=detail_url,
                            )
                            continue

                        # COST-03 / D-08: enforce 8 KB cap on what reaches the LLM.
                        try:
                            guard.check_payload(len(text.encode()))
                        except BudgetExceeded:
                            log.warning(
                                "scraper.payload_oversize",
                                source="apartments",
                                url=detail_url,
                                bytes=len(text.encode()),
                            )
                            continue

                        listings = await llm_extract.extract(
                            text, detail_url, "apartments", guard
                        )

                        for item in listings:
                            data = item.model_dump() if hasattr(item, "model_dump") else dict(item)
                            image_url = data.pop("image_url", None)

                            # Stamp authoritative source identity (cannot trust LLM).
                            data["source_url"] = detail_url
                            data["source_name"] = "apartments"

                            # T-04-03 server-side defense: only persist photos
                            # whose hostname ends in apartments.com.
                            photo_url: str | None = None
                            if image_url:
                                try:
                                    host = urlparse(image_url).hostname or ""
                                except ValueError:
                                    host = ""
                                if any(host.endswith(s) for s in _PHOTO_HOST_SUFFIXES):
                                    photo_url = image_url

                            serialized = json.dumps(data, default=str)
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
                finally:
                    await context.close()
            finally:
                await browser.close()

        log.info(
            "scraper.completed",
            source="apartments",
            job_id=job_id,
            inserted=inserted,
        )

        # 7. Terminal success — mark_done owns the status flip (D-15).
        await mark_done(redis, db, job_id, failed=False)
    except BudgetExceeded:
        log.warning("scraper.budget_exceeded", source="apartments", job_id=job_id)
        await mark_done(redis, db, job_id, failed=True)
        raise
    except Exception as exc:
        log.error(
            "scraper.error",
            source="apartments",
            job_id=job_id,
            error_type=type(exc).__name__,
            error=str(exc)[:200],
        )
        await mark_done(redis, db, job_id, failed=True)
        raise
