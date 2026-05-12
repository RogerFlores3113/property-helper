"""ARQ WorkerSettings — Phase 1 stub scraper worker.

Run with: cd backend && uv run arq app.workers.settings.WorkerSettings

Per T-02-07 mitigation: max_tries=1 so a failing run doesn't duplicate the 9
fake listings on retry.
"""
from __future__ import annotations

from arq.connections import RedisSettings

from ..db import close_pool, init_pool
from ..settings import settings
from .scrapers.craigslist import run_search


async def startup(ctx):
    ctx["db"] = await init_pool()


async def shutdown(ctx):
    await close_pool()


class WorkerSettings:
    functions = [run_search]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 5
    max_tries = 1  # T-02-07: avoid duplicate fake-data inserts on retry
