"""Settings tests — ANTHROPIC_API_KEY contract (D-09, ASVS V14).

Settings() must fail fast at import time when ANTHROPIC_API_KEY is unset.
This prevents silent runtime failures when the LLM extractor (Plan 02) tries
to call Anthropic without credentials.
"""
from __future__ import annotations

import importlib

import pytest
from pydantic import ValidationError


def test_settings_requires_anthropic_key(monkeypatch):
    """Importing Settings without ANTHROPIC_API_KEY raises ValidationError."""
    from app import settings as settings_module  # ensure cached in sys.modules first

    # Remove the key from environment so pydantic-settings cannot find it.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Force settings to ignore the on-disk .env file for this test.
    monkeypatch.setenv("PH_DISABLE_ENV_FILE", "1")

    # Reload to re-run module-level Settings() construction.
    with pytest.raises(ValidationError) as excinfo:
        importlib.reload(settings_module)

    assert "anthropic_api_key" in str(excinfo.value).lower()

    # Restore: reload again with the env var so other tests stay green.
    monkeypatch.delenv("PH_DISABLE_ENV_FILE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-for-pytest")
    importlib.reload(settings_module)
