"""Plan 04-02 SCRAP-07 HTML prefilter — GREEN suite.

Asserts the three behaviors required by Plan 04-02 Task 1:

1. Token reduction floor: prefilter compresses to ≤1/5 of raw on the
   apartments fixture (SCRAP-07).
2. Empty result when the selector matches nothing.
3. Script tags inside the listing region are stripped (T-04-01 defence-in-depth).
"""
from __future__ import annotations

from pathlib import Path

from app.workers.scrapers.prefilter import prefilter

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


def test_prefilter_strips_scripts_and_nav():
    """A <script> tag inside the listing region must not survive prefilter output."""
    raw = (
        "<html><body>"
        "<nav>nav junk</nav>"
        "<div class='placard'>"
        "<script>alert(1)</script>"
        "Real listing text: 2BR/1BA $2500/mo at 1 Main St"
        "</div>"
        "<footer>footer junk</footer>"
        "</body></html>"
    )
    filtered = prefilter(raw, selector=".placard")
    assert filtered, "expected listing text to survive prefilter"
    assert "alert(1)" not in filtered
    assert "<script" not in filtered.lower()
    # Listing signal must still be present.
    assert "2BR" in filtered or "2500" in filtered or "Main St" in filtered
