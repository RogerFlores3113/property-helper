"""RED scaffold — Plan 04-02 SCRAP-06 LLM extractor.

Imports modules that do not yet exist. Pytest collection ERRORs with
ModuleNotFoundError until Plan 02 lands `app.workers.scrapers.llm_extract`.
That is the intentional Wave-0 RED state.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# Import target — does not exist yet. Collection error is expected.
from app.workers.scrapers.llm_extract import (  # noqa: F401
    _TOOL_CHOICE,
    Listing,
    extract,
)


@pytest.fixture
def mock_anthropic(monkeypatch):
    """Patch llm_extract._get_client() with an AsyncMock messages.create."""
    from app.workers.scrapers import llm_extract

    client = MagicMock()
    client.messages.create = AsyncMock()
    monkeypatch.setattr(llm_extract, "_get_client", lambda: client)
    return client


async def test_forced_tool_choice(mock_anthropic):
    """Extractor passes tool_choice=_TOOL_CHOICE to anthropic.messages.create."""
    mock_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="tool_use", input={"listings": []})]
    )
    await extract("trimmed html", source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert kwargs["tool_choice"] == _TOOL_CHOICE


async def test_pre_filtered_text_only(mock_anthropic):
    """messages[0].content equals the trimmed-html string the caller passed."""
    mock_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="tool_use", input={"listings": []})]
    )
    payload = "PRE-FILTERED LISTING CONTENT"
    await extract(payload, source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs
    assert kwargs["messages"][0]["content"] == payload


async def test_cache_control_on_system_and_tools(mock_anthropic):
    """System + tools both carry cache_control={"type":"ephemeral"} for prompt caching."""
    mock_anthropic.messages.create.return_value = MagicMock(
        content=[MagicMock(type="tool_use", input={"listings": []})]
    )
    await extract("x", source_url="https://example.com")
    kwargs = mock_anthropic.messages.create.call_args.kwargs

    # system may be list[dict] with cache_control breakpoint
    system = kwargs["system"]
    if isinstance(system, list):
        assert any(
            block.get("cache_control") == {"type": "ephemeral"} for block in system
        )
    else:
        raise AssertionError("system must be a list with cache_control breakpoint")

    tools = kwargs["tools"]
    assert any(
        t.get("cache_control") == {"type": "ephemeral"} for t in tools
    )


async def test_escalation_to_sonnet_on_empty(mock_anthropic):
    """When Haiku returns empty listings, retry with claude-sonnet-4-6."""
    empty = MagicMock(content=[MagicMock(type="tool_use", input={"listings": []})])
    populated = MagicMock(
        content=[
            MagicMock(
                type="tool_use",
                input={
                    "listings": [
                        {
                            "address": "1 Main St",
                            "price": 2000,
                            "beds": 1,
                            "source_url": "https://example.com/x",
                        }
                    ]
                },
            )
        ]
    )
    mock_anthropic.messages.create.side_effect = [empty, populated]
    await extract("x", source_url="https://example.com")
    # Second call should target Sonnet.
    second_kwargs = mock_anthropic.messages.create.call_args_list[1].kwargs
    assert second_kwargs["model"] == "claude-sonnet-4-6"


async def test_pydantic_validation_drops_bad_listing(mock_anthropic):
    """LLM listing with implausible price (999999) is dropped by Listing model."""
    mock_anthropic.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                type="tool_use",
                input={
                    "listings": [
                        {
                            "address": "ok",
                            "price": 999999,  # implausible — must be dropped
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
                },
            )
        ]
    )
    results = await extract("x", source_url="https://example.com")
    prices = [l.price for l in results]
    assert 999999 not in prices
    assert 2500 in prices
