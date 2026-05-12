"""Plan 04-02 SCRAP-06 LLM extractor — GREEN suite.

Eight behavior bullets from Plan 04-02 Task 2:

1. forced_tool_choice — every messages.create call carries tool_choice=_TOOL_CHOICE
2. pre_filtered_text_only — user message content is the literal text arg, no HTML
3. cache_control_on_system_and_tools — both system + tools carry ephemeral breakpoint
4. haiku_used_first_then_sonnet_on_empty — Haiku call first; Sonnet retry on empty
5. no_escalation_when_haiku_succeeds — single call when Haiku returns ≥1 listing
6. pydantic_validation_drops_bad_listing — out-of-range price filtered out
7. record_spend_called_with_real_usage — guard.record_spend tokens + cost include cache discount
8. max_retries_one — AsyncAnthropic constructed with max_retries=1 (Pitfall 10)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.guards.budget import BudgetGuard
from app.workers.scrapers import llm_extract
from app.workers.scrapers.llm_extract import _TOOL_CHOICE, Listing, extract


def _tool_use_response(listings, *, input_tokens=100, output_tokens=50, cache_read=0):
    """Build a MagicMock that mimics anthropic.types.Message shape."""
    block = MagicMock()
    block.type = "tool_use"
    block.input = {"listings": listings}
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=0,
    )
    return resp


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch _get_client() with a MagicMock whose messages.create is an AsyncMock."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock()
    monkeypatch.setattr(llm_extract, "_get_client", lambda: client)
    return client


@pytest.fixture
def guard():
    """Real BudgetGuard with AsyncMock db so record_spend is observable."""
    db = AsyncMock()
    return BudgetGuard(
        max_iters=10,
        token_budget=100_000,
        max_tool_result_bytes=8192,
        db=db,
    )


# 1. -------------------------------------------------------------------------


async def test_forced_tool_choice(mock_anthropic):
    """tool_choice=_TOOL_CHOICE is passed on every create() call (SCRAP-06)."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [
            {
                "address": "1 Main",
                "price": 2000,
                "source_url": "https://example.com/x",
            }
        ]
    )
    await extract("trimmed", source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == _TOOL_CHOICE
    # And the constant is the documented payload.
    assert _TOOL_CHOICE == {"type": "tool", "name": "extract_listings"}


# 2. -------------------------------------------------------------------------


async def test_pre_filtered_text_only(mock_anthropic):
    """messages[0].content is the exact text the caller passed — no HTML."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [{"address": "x", "price": 1, "source_url": "https://example.com/x"}]
    )
    payload = "PRE-FILTERED LISTING CONTENT no html here"
    await extract(payload, source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert kwargs["messages"][0]["content"] == payload
    assert "<" not in kwargs["messages"][0]["content"]


# 3. -------------------------------------------------------------------------


async def test_cache_control_on_system_and_tools(mock_anthropic):
    """Both system[0] and tools[0] carry cache_control={'type':'ephemeral'} (D-02)."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [{"address": "x", "price": 1, "source_url": "https://example.com/x"}]
    )
    await extract("x", source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs

    system = kwargs["system"]
    assert isinstance(system, list)
    assert any(
        block.get("cache_control") == {"type": "ephemeral"} for block in system
    )

    tools = kwargs["tools"]
    assert isinstance(tools, list)
    assert any(t.get("cache_control") == {"type": "ephemeral"} for t in tools)


# 4. -------------------------------------------------------------------------


async def test_haiku_used_first_then_sonnet_on_empty(mock_anthropic):
    """Empty Haiku response triggers a single Sonnet retry (D-04)."""
    empty = _tool_use_response([])
    populated = _tool_use_response(
        [
            {
                "address": "1 Main St",
                "price": 2000,
                "beds": 1,
                "source_url": "https://example.com/x",
            }
        ]
    )
    mock_anthropic.messages.create.side_effect = [empty, populated]

    results = await extract("x", source_url="https://example.com")

    assert mock_anthropic.messages.create.call_count == 2
    first_kwargs = mock_anthropic.messages.create.call_args_list[0].kwargs
    second_kwargs = mock_anthropic.messages.create.call_args_list[1].kwargs
    assert first_kwargs["model"] == "claude-haiku-4-5"
    assert second_kwargs["model"] == "claude-sonnet-4-6"
    # Same _TOOL_CHOICE constant must be reused (Pitfall 2 cache invalidation).
    assert first_kwargs["tool_choice"] is _TOOL_CHOICE
    assert second_kwargs["tool_choice"] is _TOOL_CHOICE
    assert len(results) == 1


# 5. -------------------------------------------------------------------------


async def test_no_escalation_when_haiku_succeeds(mock_anthropic):
    """A populated Haiku response means exactly one create() call."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [
            {
                "address": "1 Main",
                "price": 2000,
                "source_url": "https://example.com/x",
            }
        ]
    )
    await extract("x", source_url="https://example.com")
    assert mock_anthropic.messages.create.call_count == 1
    only_kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert only_kwargs["model"] == "claude-haiku-4-5"


# 6. -------------------------------------------------------------------------


async def test_pydantic_validation_drops_bad_listing(mock_anthropic):
    """Out-of-range price (>100_000) is dropped; valid listings pass through (T-04-07)."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [
            {
                "address": "bad",
                "price": 9999999,  # > 100_000 → drop
                "beds": 1,
                "source_url": "https://example.com/a",
            },
            {
                "address": "good",
                "price": 2500,
                "beds": 2,
                "source_url": "https://example.com/b",
            },
        ]
    )
    results = await extract("x", source_url="https://example.com")
    prices = [l.price for l in results]
    assert 9999999 not in prices
    assert 2500 in prices
    assert len(results) == 1


# 7. -------------------------------------------------------------------------


async def test_record_spend_called_with_real_usage(mock_anthropic, guard):
    """guard.record_spend(tokens=input+output, cost_usd=...) with cache discount."""
    mock_anthropic.messages.create.return_value = _tool_use_response(
        [
            {
                "address": "1 Main",
                "price": 2000,
                "source_url": "https://example.com/x",
            }
        ],
        input_tokens=1000,
        output_tokens=200,
        cache_read=500,
    )

    spy = AsyncMock(wraps=guard.record_spend)
    guard.record_spend = spy  # type: ignore[method-assign]

    await extract("x", source_url="https://example.com", guard=guard)

    spy.assert_awaited_once()
    call_kwargs = spy.await_args.kwargs
    assert call_kwargs["tokens"] == 1200  # input + output
    # Cost = 1000*1e-6 + 500*1e-7 + 200*5e-6 = 0.001 + 0.00005 + 0.001 = 0.00205
    assert call_kwargs["cost_usd"] == pytest.approx(0.00205)
    # Confirm the cache-read discount line item is included (cost without it
    # would be 0.002 even without the cache token; with cache_read=500 at $0.10/M
    # the discounted line adds 0.00005).
    assert call_kwargs["cost_usd"] > 1000 * 1e-6 + 200 * 5e-6 - 1e-9


# 8. -------------------------------------------------------------------------


def test_max_retries_one(monkeypatch):
    """AsyncAnthropic is constructed with max_retries=1 (Pitfall 10 / T-04-10)."""
    captured: dict = {}

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

    # Reset the cached singleton so _get_client() rebuilds via _FakeClient.
    monkeypatch.setattr(llm_extract, "AsyncAnthropic", _FakeClient)
    monkeypatch.setattr(llm_extract, "_client_singleton", None)

    llm_extract._get_client()
    assert captured.get("max_retries") == 1
    assert "api_key" in captured


# Additional sanity: the Listing model exports all D-03 fields.
def test_listing_model_has_required_fields():
    fields = set(Listing.model_fields.keys())
    expected = {
        "address",
        "price",
        "beds",
        "baths",
        "sqft",
        "lat",
        "lng",
        "amenities",
        "source_url",
        "image_url",
        "posted_date",
        "source_name",
    }
    missing = expected - fields
    assert not missing, f"Listing model missing fields: {missing}"
