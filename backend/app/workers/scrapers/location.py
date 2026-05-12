"""Location chip → source-specific search-URL allowlists (T-03-01 / T-04-02 SSRF).

The output of `location_to_search_url` / `location_to_apartments_url` is the
ONLY value that should ever be passed as the search URL to httpx / Playwright.
User-supplied location strings are filtered through dict allowlists — arbitrary
host strings cannot become fetch targets.

Phase 4 Plan 04 adds the Apartments.com counterpart per D-09 / Open Question #2.
"""
from __future__ import annotations

# Craigslist publishes the official region list at
# https://reference.craigslist.org/Areas. Phase 3 ships a curated subset that
# covers the launch + expansion markets (PROJECT.md "Context"). Phase 4 can
# sync the full list nightly.
_CITY_TO_SUBDOMAIN: dict[str, str] = {
    "san francisco": "sfbay",
    "sf": "sfbay",
    "sf bay area": "sfbay",
    "bay area": "sfbay",
    "los angeles": "losangeles",
    "la": "losangeles",
    "new york": "newyork",
    "new york city": "newyork",
    "nyc": "newyork",
    "champaign": "champaignil",
    "champaign il": "champaignil",
    "champaign-urbana": "champaignil",
    "urbana": "champaignil",
    "chicago": "chicago",
    "seattle": "seattle",
    "boston": "boston",
    "austin": "austin",
}


def location_to_search_url(location: str) -> str | None:
    """Map a free-text location to a Craigslist apartments search URL.

    Returns None if no known Craigslist region matches — callers should treat
    None as "no scraping target" and complete the job with zero listings.
    """
    if not location:
        return None
    key = location.lower().strip()
    sub = _CITY_TO_SUBDOMAIN.get(key)
    if sub is None:
        # Substring fallback — match any known city contained within the query
        # (e.g., "2BR in SF Bay Area under $5k" contains "sf bay area").
        for k, v in _CITY_TO_SUBDOMAIN.items():
            if k in key:
                sub = v
                break
    if sub is None:
        return None
    return f"https://{sub}.craigslist.org/search/apa"


# Apartments.com slug allowlist (T-04-02 SSRF mitigation). Slugs sourced from
# the public Apartments.com URL scheme (e.g. https://www.apartments.com/sf-bay-area-ca/).
# Mirrors the Craigslist coverage so a single user query that maps to one source
# also maps to the other.
_CITY_TO_APARTMENTS_SLUG: dict[str, str] = {
    "san francisco": "sf-bay-area-ca",
    "sf": "sf-bay-area-ca",
    "sf bay area": "sf-bay-area-ca",
    "bay area": "sf-bay-area-ca",
    "los angeles": "los-angeles-ca",
    "la": "los-angeles-ca",
    "new york": "new-york-ny",
    "new york city": "new-york-ny",
    "nyc": "new-york-ny",
    "champaign": "champaign-il",
    "champaign il": "champaign-il",
    "champaign-urbana": "champaign-il",
    "urbana": "urbana-il",
    "chicago": "chicago-il",
    "seattle": "seattle-wa",
    "boston": "boston-ma",
    "austin": "austin-tx",
}


def location_to_apartments_url(query: str) -> str | None:
    """Map a free-text location to an Apartments.com search URL.

    Returns None if no allowlisted Apartments.com slug matches — callers should
    treat None as "no Apartments.com target" and complete the sub-task with
    zero listings (gates T-04-02 SSRF: the URL is constructed from a server-side
    enum, never from raw user input).
    """
    if not query:
        return None
    key = query.lower().strip()
    slug = _CITY_TO_APARTMENTS_SLUG.get(key)
    if slug is None:
        # Word-boundary substring fallback — match any allowlisted city that
        # appears as a whole token in the query (e.g., "2BR in SF Bay Area
        # under $5k" contains "sf bay area"). A naive `if k in key` would
        # match short keys ("la") inside unrelated words ("place"), poking a
        # hole through the T-04-02 SSRF allowlist.
        import re

        for k, v in _CITY_TO_APARTMENTS_SLUG.items():
            if re.search(rf"\b{re.escape(k)}\b", key):
                slug = v
                break
    if slug is None:
        return None
    return f"https://www.apartments.com/{slug}/"
