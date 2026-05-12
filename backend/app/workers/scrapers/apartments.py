"""Apartments.com scraper — Plan 04-04 (SCRAP-01, SCRAP-03, SCRAP-04, SCRAP-06, SCRAP-07).

Task 1 lands the module-level constants needed by the parser-layer tests
(_LISTING_ROOT_SELECTOR, _PHOTO_HOST_SUFFIXES). Task 2 will add the
``run_search_apartments`` ARQ task body (Playwright + stealth + prefilter +
llm_extract + acquire_domain_slot + mark_done).
"""
from __future__ import annotations

# Listing-root CSS selector for prefilter(). Both selectors are required
# because the live Apartments.com search page uses ``#placardContainer ul li``
# wrappers AND each card is an ``article.placard`` — we want either form to
# match (selectolax css() supports a comma-grouped selector). Verified against
# the captured fixtures in backend/tests/fixtures/apartments/.
_LISTING_ROOT_SELECTOR: str = "#placardContainer ul li, .placard"

# Photo-host allowlist (defense in depth for T-04-03 tracker injection):
# any LLM-extracted ``image_url`` whose hostname does not end in one of these
# suffixes is dropped to ``None`` before INSERT.
_PHOTO_HOST_SUFFIXES: tuple[str, ...] = ("apartments.com",)
