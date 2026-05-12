"""Application settings — pydantic-settings BaseSettings singleton.

Reads from backend/.env per D-02 (single env contract documented at .env.example).
Env var defaults match D-10 exactly.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
