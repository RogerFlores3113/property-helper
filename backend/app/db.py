"""asyncpg pool factory for the Supabase transaction pooler.

Pitfall 2 mitigation: when connecting to the Supabase transaction pooler (port 6543),
asyncpg MUST be configured with statement_cache_size=0. Transaction-mode pooling
rotates connections per transaction; asyncpg's per-connection prepared-statement
cache will reference statements that no longer exist on the rotated connection,
surfacing as `prepared statement "__asyncpg_stmt_X__" does not exist` under load.
"""
from __future__ import annotations

import asyncpg

from .settings import settings

_pool: asyncpg.Pool | None = None


async def init_pool() -> asyncpg.Pool:
    """Initialize the global asyncpg pool (idempotent)."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.supabase_db_url,
            min_size=1,
            max_size=5,  # Supabase free-tier pooler is shared — stay small
            command_timeout=30,
            statement_cache_size=0,  # Pitfall 2: REQUIRED for pgbouncer transaction pooler
        )
    return _pool


async def close_pool() -> None:
    """Close the global asyncpg pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_pool() -> asyncpg.Pool:
    """Return the global asyncpg pool. Raises if init_pool() was not called."""
    if _pool is None:
        raise RuntimeError("asyncpg pool not initialized — call init_pool() first")
    return _pool
