"""Tests for Craigslist HTML parsers — SCRAP-02 (assumptions A1/A2/A3)."""
from __future__ import annotations

import re
from pathlib import Path

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
