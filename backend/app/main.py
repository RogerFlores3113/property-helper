"""FastAPI application entrypoint — Phase 1 backend skeleton."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import close_pool, init_pool
from .logging import configure_logging
from .routes import jobs, listings

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    try:
        yield
    finally:
        await close_pool()


app = FastAPI(lifespan=lifespan, title="property-helper-backend")

# Pitfall 6 mitigation: exact origin allow-list, NOT wildcards.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(jobs.router)
app.include_router(listings.router)
