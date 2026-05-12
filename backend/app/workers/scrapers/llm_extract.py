"""Claude Haiku 4.5 forced-tool-use listing extractor — Plan 04-02 SCRAP-06.

Public surface:
    - ``extract(text, source_url, source_name="apartments", guard=None) -> list[Listing]``
    - ``Listing`` — Pydantic model validating LLM tool-call output.
    - ``_TOOL_CHOICE`` — module constant forcing the ``extract_listings`` tool.

Design (D-01 .. D-04, D-08):
    - **Forced tool use** prevents prose injection from scraped text (T-04-01).
      Every ``messages.create`` carries ``tool_choice=_TOOL_CHOICE``.
    - **Prompt caching**: the system instruction block and tool definition both
      carry ``cache_control={"type":"ephemeral"}`` so subsequent calls within
      the cache TTL pay ~10% input cost on the cached portion.
    - **Sonnet escalation**: if Haiku returns an empty ``listings[]``, retry
      *once* with ``claude-sonnet-4-6`` (D-04). The same ``_TOOL_CHOICE`` is
      reused — never construct it inline (Pitfall 2 cache-invalidation).
    - **Pydantic validation** drops out-of-range items (T-04-07): price,
      bed/bath, sqft, lat, lng all bounded by Field constraints; invalid
      items are silently dropped.
    - **AsyncAnthropic(max_retries=1)** prevents retry-storm token spend
      (T-04-10 / Pitfall 10).

SECURITY:
    - Accepts plain text only — raw HTML is rejected at the contract level
      (T-04-01 / D-07). Callers MUST run ``prefilter()`` first.
    - The Anthropic API key is read once from ``Settings`` at first-call
      time and never logged or serialized (T-04-04).
"""
from __future__ import annotations

from typing import Any

import structlog
from anthropic import AsyncAnthropic
from pydantic import BaseModel, Field, ValidationError

from ...settings import settings

log = structlog.get_logger()

# --- Model + tool constants (module-level for prompt-cache stability) --------

_PRIMARY_MODEL = "claude-haiku-4-5"
_ESCALATION_MODEL = "claude-sonnet-4-6"

# Pitfall 2 — _TOOL_CHOICE is a module constant. Never construct inline; the
# tool_choice payload participates in the prompt cache key, and any drift
# would silently bust the cache breakpoint and explode token spend.
_TOOL_CHOICE: dict[str, str] = {"type": "tool", "name": "extract_listings"}

_SYSTEM = (
    "You extract structured rental listings from pre-filtered listing text. "
    "Call the extract_listings tool with the listings array. "
    "Never invent prices, addresses, or coordinates — if a field is not "
    "present in the text, omit it (do not guess). "
    "Drop any item where the price is implausible (under $100 or over "
    "$100,000) or the address is missing."
)

_MAX_OUTPUT_TOKENS = 4096


class Listing(BaseModel):
    """Validated listing payload returned by the extract_listings tool.

    Field ranges enforce T-04-07 (LLM-output integrity): items outside these
    ranges are dropped by the caller.
    """

    address: str | None = None
    price: int | None = Field(default=None, ge=0, le=100_000)
    beds: float | None = Field(default=None, ge=0, le=20)
    baths: float | None = Field(default=None, ge=0, le=20)
    sqft: int | None = Field(default=None, ge=0, le=20_000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    amenities: list[str] | None = None
    source_url: str
    image_url: str | None = None
    posted_date: str | None = None
    source_name: str = "apartments"


# ---------------------------- tool schema -----------------------------------

# Pydantic emits a JSON schema with all the field constraints; embed it as the
# tool input_schema so Claude self-checks before returning.
_LISTING_SCHEMA = Listing.model_json_schema()

_TOOL: dict[str, Any] = {
    "name": "extract_listings",
    "description": (
        "Extract rental listings from pre-filtered apartment listing text. "
        "Return one entry per distinct unit visible in the input."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "listings": {
                "type": "array",
                "items": _LISTING_SCHEMA,
            },
        },
        "required": ["listings"],
    },
}


# ----------------------------- client factory --------------------------------

_client_singleton: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    """Return a cached AsyncAnthropic client (singleton per worker process).

    Tests monkeypatch this symbol directly to inject a MagicMock. Pitfall 10:
    ``max_retries=1`` prevents the SDK from amplifying token spend on transient
    errors (T-04-10).
    """
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            max_retries=1,
        )
    return _client_singleton


# ------------------------------- pricing -------------------------------------

# Claude Haiku 4.5 pricing (per CLAUDE.md §LLM Strategy):
#   input:        $1.00 / M tokens  → 1e-6 USD/token
#   cached input: $0.10 / M tokens  → 1e-7 USD/token
#   output:       $5.00 / M tokens  → 5e-6 USD/token
_USD_PER_INPUT_TOKEN = 1e-6
_USD_PER_CACHED_INPUT_TOKEN = 1e-7
_USD_PER_OUTPUT_TOKEN = 5e-6


def _cost_usd(input_tokens: int, output_tokens: int, cache_read_tokens: int) -> float:
    """Compute Haiku-rate cost in USD including the cache-read discount line."""
    return (
        input_tokens * _USD_PER_INPUT_TOKEN
        + cache_read_tokens * _USD_PER_CACHED_INPUT_TOKEN
        + output_tokens * _USD_PER_OUTPUT_TOKEN
    )


# ---------------------------- core call helper -------------------------------


async def _call_model(
    client: AsyncAnthropic,
    model: str,
    text: str,
    source_url: str,
    source_name: str,
) -> tuple[list[Listing], Any]:
    """Issue one forced-tool-use call and return (validated listings, usage)."""
    resp = await client.messages.create(
        model=model,
        max_tokens=_MAX_OUTPUT_TOKENS,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[{**_TOOL, "cache_control": {"type": "ephemeral"}}],
        tool_choice=_TOOL_CHOICE,
        messages=[{"role": "user", "content": text}],
    )

    # Pull the tool_use block; ignore any other content blocks defensively.
    listings_raw: list[dict[str, Any]] = []
    for block in resp.content or []:
        if getattr(block, "type", None) == "tool_use":
            payload = getattr(block, "input", None) or {}
            listings_raw = list(payload.get("listings") or [])
            break

    validated: list[Listing] = []
    for item in listings_raw:
        if not isinstance(item, dict):
            continue
        merged = {
            **item,
            # Stamp authoritative source identity from the caller — never
            # trust the LLM to set these.
            "source_url": item.get("source_url") or source_url,
            "source_name": source_name,
        }
        try:
            validated.append(Listing(**merged))
        except ValidationError as exc:
            log.warning(
                "llm.dropped_invalid_listing",
                errors=len(exc.errors()),
                source_url=source_url,
            )
            continue

    return validated, resp.usage


# ------------------------------- public API ----------------------------------


async def extract(
    text: str,
    source_url: str,
    source_name: str = "apartments",
    guard: Any = None,
) -> list[Listing]:
    """Extract structured rental listings from pre-filtered listing text.

    Args:
        text: Plain-text output of :func:`prefilter` — never raw HTML
            (T-04-01 / D-07).
        source_url: Origin URL the text was scraped from. Stamped onto
            every returned listing.
        source_name: Logical source identifier (e.g. ``"apartments"``,
            ``"craigslist"``) — stamped onto every returned listing.
        guard: Optional :class:`BudgetGuard`. When supplied, the call's
            real token usage (input + output) and Haiku-rate cost are
            recorded via :meth:`BudgetGuard.record_spend`. The cached-input
            discount line is included in the cost figure.

    Returns:
        List of validated :class:`Listing` instances. Invalid items
        (Pydantic ValidationError) are dropped silently — they never
        flow to the database (T-04-07).

    Behavior:
        - First call uses ``claude-haiku-4-5``.
        - If Haiku returns an empty listings array, retry once with
          ``claude-sonnet-4-6`` (D-04).
        - Every call passes ``tool_choice=_TOOL_CHOICE`` (SCRAP-06).
    """
    client = _get_client()

    try:
        listings, usage = await _call_model(
            client, _PRIMARY_MODEL, text, source_url, source_name
        )
    except Exception as exc:  # pragma: no cover — defence; SDK already retries
        log.warning(
            "llm.extract_error",
            model=_PRIMARY_MODEL,
            source_url=source_url,
            error_type=type(exc).__name__,
        )
        raise

    cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)

    if not listings:
        log.info(
            "llm.empty_extract",
            model=_PRIMARY_MODEL,
            source_url=source_url,
        )
        # D-04: escalate to Sonnet once on empty extract.
        try:
            listings, usage2 = await _call_model(
                client, _ESCALATION_MODEL, text, source_url, source_name
            )
        except Exception as exc:  # pragma: no cover
            log.warning(
                "llm.extract_error",
                model=_ESCALATION_MODEL,
                source_url=source_url,
                error_type=type(exc).__name__,
            )
            raise
        cache_read += int(getattr(usage2, "cache_read_input_tokens", 0) or 0)
        input_tokens += int(getattr(usage2, "input_tokens", 0) or 0)
        output_tokens += int(getattr(usage2, "output_tokens", 0) or 0)
        model_used = _ESCALATION_MODEL
    else:
        model_used = _PRIMARY_MODEL

    if guard is not None:
        await guard.record_spend(
            tokens=input_tokens + output_tokens,
            cost_usd=_cost_usd(input_tokens, output_tokens, cache_read),
        )

    log.info(
        "llm.extracted",
        model=model_used,
        count=len(listings),
        cache_read=cache_read,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        source_url=source_url,
    )
    return listings
