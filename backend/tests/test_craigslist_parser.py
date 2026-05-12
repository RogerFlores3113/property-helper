"""Tests for Craigslist HTML parsers — SCRAP-02 (assumptions A1/A2/A3)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.workers.scrapers.craigslist import parse_listing, parse_search_results

FIX = Path(__file__).parent / "fixtures"


def test_parse_listing_detail():
    html = (FIX / "craigslist_detail.html").read_text()
    src = "https://sfbay.craigslist.org/pen/apa/d/example/1234567890.html"
    data, photo_url = parse_listing(html, source_url=src)

    assert data["source_url"] == src
    assert data["source_name"] == "craigslist"

    lat = data.get("lat")
    lng = data.get("lng")
    assert lat is None or (-90.0 <= float(lat) <= 90.0)
    assert lng is None or (-180.0 <= float(lng) <= 180.0)
    # Fixture is verified to have data-latitude/data-longitude.
    assert lat is not None and lng is not None

    assert data.get("price") is None or isinstance(data["price"], int)
    assert data.get("beds") is None or isinstance(data["beds"], int)
    assert data.get("baths") is None or isinstance(data["baths"], (int, float))

    assert isinstance(data["amenities"], list)
    assert len(data["amenities"]) <= 8

    assert data.get("address") is None or isinstance(data["address"], str)
    assert data.get("posted_date") is None or re.match(
        r"^\d{4}-\d{2}-\d{2}$", data["posted_date"]
    )

    assert photo_url is None or isinstance(photo_url, str)


def test_parse_search_results():
    html = (FIX / "craigslist_search.html").read_text()
    urls = parse_search_results(html)
    assert isinstance(urls, list)
    assert len(urls) > 0
    for u in urls:
        assert u.endswith(".html")
        assert u.startswith("http://") or u.startswith("https://")


def test_lat_lng_range_validation():
    # Synthetic HTML with out-of-range coords → parser returns None for those fields.
    bad_html = """<html><body>
    <div id="map" data-latitude="999.0" data-longitude="-9999.0"></div>
    </body></html>"""
    data, _ = parse_listing(bad_html, source_url="https://x.craigslist.org/x.html")
    assert data["lat"] is None
    assert data["lng"] is None


# ---------------------------------------------------------------------------
# Phase 5 RED addition — Pitfall 8: persist sqft so dedup_key can use it
# ---------------------------------------------------------------------------


@pytest.mark.red_phase_05
def test_sqft_persisted_to_data():
    """Pitfall 8 (05-RESEARCH): parse_listing must surface `sqft` (int) when the
    HTML has the ft² attribute group, or omit / set to None when absent.

    Plan 05-03 will add this extraction so compute_dedup_key has a sqft value
    to round into the dedup key.
    """
    # Craigslist detail pages embed sqft in a span with class 'shared-line-bubble'
    # whose data-rdf is 'http://schema.org/floorSize' (per 05-RESEARCH Pitfall 8).
    with_sqft = """<html><body>
    <p class="attrgroup">
      <span class="shared-line-bubble" data-rdf="http://schema.org/floorSize">
        <b>850</b>ft<sup>2</sup>
      </span>
    </p>
    </body></html>"""
    data, _ = parse_listing(
        with_sqft, source_url="https://sfbay.craigslist.org/x.html"
    )
    assert data.get("sqft") == 850, (
        f"sqft must be parsed as int 850, got {data.get('sqft')!r}"
    )

    without_sqft = """<html><body><p>No bubble here.</p></body></html>"""
    data2, _ = parse_listing(
        without_sqft, source_url="https://sfbay.craigslist.org/y.html"
    )
    assert data2.get("sqft") in (None, 0) or "sqft" not in data2, (
        f"sqft must be None/absent when missing, got {data2.get('sqft')!r}"
    )
