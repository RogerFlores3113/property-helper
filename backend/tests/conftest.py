"""Shared pytest fixtures for Phase 1 backend tests.

Per VALIDATION.md Wave 0 Requirements:
- pg_pool: asyncpg pool wired to SUPABASE_DB_URL (skip if unset)
- clean_db: TRUNCATE all 3 tables between tests
- arq_redis: fakeredis-backed broker for ARQ unit tests
"""
from __future__ import annotations

import os

import asyncpg
import fakeredis.aioredis
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def pg_pool():
    """Yield an asyncpg pool against SUPABASE_DB_URL; skip if env var unset."""
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        pytest.skip("SUPABASE_DB_URL not configured — DB-integration tests skipped")
    pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=2,
        statement_cache_size=0,
        command_timeout=30,
    )
    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def clean_db(pg_pool):
    """TRUNCATE the 3 Phase 1 tables before and after each test."""
    await pg_pool.execute(
        "TRUNCATE TABLE listings, search_jobs, daily_spend RESTART IDENTITY CASCADE"
    )
    yield
    await pg_pool.execute(
        "TRUNCATE TABLE listings, search_jobs, daily_spend RESTART IDENTITY CASCADE"
    )


@pytest_asyncio.fixture
async def arq_redis():
    """Yield a fakeredis-backed broker stand-in for ARQ unit tests."""
    redis = fakeredis.aioredis.FakeRedis()
    try:
        yield redis
    finally:
        await redis.aclose()
