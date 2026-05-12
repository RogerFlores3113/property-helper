"""Apartments.com parser-layer tests — Plan 04-04 Task 1 GREEN.

Exercises:
- prefilter against the captured search.html fixture (SCRAP-07 ≥5x reduction).
- The _LISTING_ROOT_SELECTOR and _PHOTO_HOST_SUFFIXES module constants exported
  by app.workers.scrapers.apartments (RED scaffold pins from Plan 04-01).
- location_to_apartments_url SSRF allowlist (T-04-02): known cities resolve to
  https://www.apartments.com/<slug>/; unknown cities return None.

Note on fixture provenance: the captured search.html lives in
backend/tests/fixtures/apartments/search.html. Apartments.com is Akamai-
protected and the research/CI environment could not capture a live page
directly. The fixture here was structurally synthesized to mirror the live
DOM contract documented in 04-RESEARCH.md (#placardContainer ul li > article.placard
with property-link / property-pricing / property-address descendants).
A real live-capture is the recommended replacement when the dev box can reach
the page (see 04-04-SUMMARY.md "Deferred Items" section).
"""
from __future__ import annotations

from pathlib import Path

from app.workers.scrapers.apartments import (
    _LISTING_ROOT_SELECTOR,
    _PHOTO_HOST_SUFFIXES,
)
from app.workers.scrapers.location import location_to_apartments_url
from app.workers.scrapers.prefilter import prefilter

_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "apartments"


def _read_fixture(name: str) -> str:
    return (_FIXTURE_DIR / name).read_text(encoding="utf-8")


# ---------- prefilter against captured search.html ----------------------------


def test_prefilter_reduces_search_page_at_least_5x():
    """SCRAP-07 against the captured fixture: filtered ≤ raw / 5."""
    raw = _read_fixture("search.html")
    filtered = prefilter(raw, _LISTING_ROOT_SELECTOR)
    assert filtered, "prefilter returned empty — selector did not match fixture"
    assert len(filtered) <= len(raw) // 5, (
        f"compression ratio insufficient: raw={len(raw)}B filtered={len(filtered)}B "
        f"ratio={len(filtered) / len(raw):.3f} (target ≤ 0.2)"
    )


def test_prefilter_preserves_listing_signal():
    """The filtered text must include at least one human-visible price + address
    + beds string from the live fixture — sanity check that the selector grabs
    the right region of the page rather than discarding listing content."""
    raw = _read_fixture("search.html")
    filtered = prefilter(raw, _LISTING_ROOT_SELECTOR)
    # Pricing visible to a human user on the live search page:
    assert "$3,495" in filtered or "3,495" in filtered
    # Address fragment:
    assert "Mission St" in filtered
    # Beds string:
    assert "Beds" in filtered or "Bed" in filtered


def test_prefilter_strips_site_chrome_from_search():
    """Footer / nav / script content must not survive the filter (T-04-01
    defense-in-depth — even though selectolax already drops them at the source).
    """
    raw = _read_fixture("search.html")
    filtered = prefilter(raw, _LISTING_ROOT_SELECTOR)
    # Footer regulatory disclosure should be gone — listings region only.
    assert "CoStar Group" not in filtered
    assert "Privacy Policy" not in filtered
    # Inline analytics constants from <script> blocks must not leak.
    assert "__TRACK" not in filtered
    assert "dataLayer" not in filtered


# ---------- listing-detail fixture --------------------------------------------


def test_listing_detail_fixture_exists_and_has_placard():
    """Captured detail page is non-empty and contains the .placard root the
    Plan 04 implementation will prefilter against."""
    raw = _read_fixture("listing_sample.html")
    assert len(raw) > 1000
    assert "placard" in raw
    filtered = prefilter(raw, _LISTING_ROOT_SELECTOR)
    assert filtered, "prefilter on detail page returned empty"
    assert "Mission Bay Lofts" in filtered


# ---------- module-constant contract (Plan 04-01 RED → GREEN here) ------------


def test_listing_selector_defined():
    """Root selector for prefilter must mention `.placard` (Apartments DOM contract)."""
    assert ".placard" in _LISTING_ROOT_SELECTOR


def test_photo_host_suffix():
    """Photo-host allowlist must include `apartments.com` for src render safety."""
    assert any("apartments.com" in s for s in _PHOTO_HOST_SUFFIXES)


# ---------- location_to_apartments_url SSRF allowlist -------------------------


def test_location_san_francisco_resolves():
    url = location_to_apartments_url("San Francisco")
    assert url is not None
    assert url.startswith("https://www.apartments.com/")


def test_location_champaign_resolves():
    url = location_to_apartments_url("Champaign")
    assert url is not None
    assert url.startswith("https://www.apartments.com/")


def test_location_substring_fallback():
    """A natural-language query containing an allowlisted phrase still resolves
    — mirrors the Craigslist location.py substring-match behavior."""
    url = location_to_apartments_url("2BR in SF Bay Area under $5k")
    assert url is not None
    assert url.startswith("https://www.apartments.com/")


def test_location_unknown_returns_none():
    """SSRF gate (T-04-02): unknown places never produce a URL."""
    assert location_to_apartments_url("not-a-real-place-xyz") is None


def test_location_empty_returns_none():
    assert location_to_apartments_url("") is None
