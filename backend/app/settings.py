"""Application settings — pydantic-settings BaseSettings singleton.

Reads from backend/.env per D-02 (single env contract documented at .env.example).
Env var defaults match D-10 exactly.
"""
import os

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Test hook: when PH_DISABLE_ENV_FILE=1, do not load values from .env.
# Used by test_settings_requires_anthropic_key to assert fail-fast behavior
# when ANTHROPIC_API_KEY is absent from both env and any .env file.
_ENV_FILE = None if os.environ.get("PH_DISABLE_ENV_FILE") == "1" else ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Supabase (D-04)
    supabase_db_url: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str  # backend only — never expose to client

    # Redis (D-03)
    redis_url: str = "redis://localhost:6379"

    # Anthropic — D-09 / ASVS V14: required at startup, no default.
    # pydantic-settings is case-insensitive, so this reads ANTHROPIC_API_KEY.
    anthropic_api_key: str

    # Cost guard defaults (D-10)
    max_iters: int = 10
    token_budget: int = 50_000
    max_tool_result_bytes: int = 8192

    # Scraper config (Phase 3 D-03) — clamped to <=30 (Open Question #2 / T-03-06)
    scraper_max_listings: int = 10

    @field_validator("scraper_max_listings")
    @classmethod
    def _clamp_max_listings(cls, v: int) -> int:
        return min(max(v, 1), 30)


settings = Settings()
