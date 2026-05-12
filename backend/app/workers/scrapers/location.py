"""Location chip → Craigslist subdomain whitelist (T-03-01 SSRF mitigation).

The output of `location_to_search_url` is the ONLY value that should ever be
passed as the search URL to httpx. User-supplied location strings are filtered
through this dict whitelist — arbitrary host strings cannot become fetch targets.
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
