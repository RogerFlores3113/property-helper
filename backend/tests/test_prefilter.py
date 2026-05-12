"""RED scaffold — Plan 04-02 SCRAP-07 HTML prefilter.

The prefilter() function trims raw HTML to the listing container before sending
to the LLM, dramatically reducing token cost. Collection ERRORs until Plan 02
lands `app.workers.scrapers.prefilter`.
"""
from __future__ import annotations

from pathlib import Path

# Import target — does not exist yet.
from app.workers.scrapers.prefilter import prefilter  # noqa: F401

FIX = Path(__file__).parent / "fixtures" / "apartments"


def test_prefilter_reduces_token_count():
    """Raw page reduced to listing region — output ≤ 1/5 of input size."""
    raw = (FIX / "search.html").read_text()
    filtered = prefilter(raw, selector=".placard")
    assert filtered, "prefilter must return non-empty string when selector matches"
    assert len(filtered) <= len(raw) / 5, (
        f"prefilter should compress to ≤20% of raw size; got "
        f"{len(filtered)}/{len(raw)}"
    )


def test_prefilter_returns_empty_when_no_match():
    """Selector with no matches returns empty string (not None)."""
    raw = "<html><body><div>no listings here</div></body></html>"
    filtered = prefilter(raw, selector=".placard")
    assert filtered == ""
