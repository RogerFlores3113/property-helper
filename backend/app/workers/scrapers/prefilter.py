"""HTML pre-filter — Plan 04-02 SCRAP-07.

Compresses raw scraped HTML to a plain-text view of only the listing region
before any LLM sees it. Two-stage pipeline per D-05/D-06/D-07:

1. selectolax extracts only the DOM subtrees matching the listing root selector
   (e.g. ``.placard`` for Apartments.com). Everything else (nav, footer, scripts,
   ads, header chrome) is dropped at the source.
2. trafilatura is then run on the concatenated listing-region HTML to strip
   the remaining boilerplate and emit plain text.

The token-reduction floor is asserted by tests at ≥5× compression on the
apartments fixture (SCRAP-07).

SECURITY: This module is the single allowed entry point for raw-HTML → text.
Raw HTML is never sent to the LLM (T-04-01 / D-07).
"""
from __future__ import annotations

import structlog
import trafilatura
from selectolax.parser import HTMLParser

log = structlog.get_logger()


def prefilter(raw_html: str, selector: str) -> str:
    """Reduce ``raw_html`` to the plain text of only the listing region.

    Args:
        raw_html: Raw scraped HTML document.
        selector: CSS selector identifying listing root nodes
            (e.g. ``".placard"`` for Apartments.com, ``"li.result-row"`` for
            legacy Craigslist search pages).

    Returns:
        Plain text extracted from the matched subtrees. Returns ``""`` when
        the selector matches nothing.
    """
    tree = HTMLParser(raw_html)
    roots = tree.css(selector)
    if not roots:
        log.warning(
            "prefilter.no_roots",
            selector=selector,
            raw_bytes=len(raw_html),
        )
        return ""

    # Stage 1: concatenate matched subtree HTML.
    chunks: list[str] = []
    for root in roots:
        html_chunk = root.html
        if html_chunk:
            chunks.append(html_chunk)
    if not chunks:
        log.warning(
            "prefilter.no_roots",
            selector=selector,
            raw_bytes=len(raw_html),
        )
        return ""
    combined = "\n".join(chunks)

    # Stage 2: trafilatura main-content extraction → plain text.
    extracted = trafilatura.extract(
        combined,
        output_format="txt",
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )
    text = extracted or ""

    # Fallback: when trafilatura cannot resolve a "main article" within tiny
    # listing-card fragments it returns None. Fall back to stripping tags
    # ourselves so the listing text still reaches the LLM. selectolax already
    # removed scripts/styles upstream of the root region by virtue of the
    # selector, but we additionally strip <script> nodes inside each root
    # before reading .text() to be defence-in-depth (T-04-01).
    if not text:
        text_parts: list[str] = []
        for root in roots:
            # Drop any nested script/style nodes from the matched region.
            for bad in root.css("script, style, noscript"):
                bad.decompose()
            node_text = root.text(separator=" ", strip=True)
            if node_text:
                text_parts.append(node_text)
        text = "\n".join(text_parts)

    log.info(
        "prefilter.done",
        selector=selector,
        raw_bytes=len(raw_html),
        filtered_bytes=len(text),
    )
    return text
