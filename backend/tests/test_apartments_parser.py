"""RED scaffold — Plan 04-04 SCRAP-01 Apartments.com parser constants.

Real parser-from-fixture tests land in Plan 04 once Playwright captures the
live page. This RED scaffold pins the two compile-time constants the Plan 04
implementation must export.
"""
from __future__ import annotations

# Import target — does not exist yet.
from app.workers.scrapers.apartments import (  # noqa: F401
    _LISTING_ROOT_SELECTOR,
    _PHOTO_HOST_SUFFIXES,
)


def test_listing_selector_defined():
    """Root selector for prefilter must mention `.placard` (Apartments DOM contract)."""
    assert ".placard" in _LISTING_ROOT_SELECTOR


def test_photo_host_suffix():
    """Photo-host allowlist must include `apartments.com` for src render safety."""
    assert any("apartments.com" in s for s in _PHOTO_HOST_SUFFIXES)
