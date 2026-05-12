"""RED — PATCH /api/listings/{id}/extend (CACH-02).

Covers decisions:
  - D-12 (05-CONTEXT): user-initiated freshness extension bumps expires_at to
        now()+28d, refreshing a stale listing in place.
  - D-19 (Phase 1): malformed UUID returns 422, not 500 (Pydantic UUID4).

This file imports app.routes.listings which does not exist yet — the
ImportError is the RED signal. Plan 05-02 will add the router.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx

from app import db as db_module
from app.main import app as main_app
from app.routes import listings as listings_route  # noqa: F401


async def test_extend_bumps_expires_at(clean_db, pg_pool, monkeypatch):
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    job_id = str(uuid.uuid4())
    await pg_pool.execute(
        "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'completed', 'q')",
        job_id,
    )
    listing_id = str(uuid.uuid4())
    stale_expires = datetime.now(timezone.utc) - timedelta(days=1)
    await pg_pool.execute(
        """INSERT INTO listings (id, job_id, data, expires_at)
           VALUES ($1, $2, $3::jsonb, $4)""",
        listing_id,
        job_id,
        json.dumps({"address": "x"}),
        stale_expires,
    )

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(f"/api/listings/{listing_id}/extend")
        assert resp.status_code == 200
        body = resp.json()
        assert "expires_at" in body
        new_expires = datetime.fromisoformat(body["expires_at"])
        delta = new_expires - datetime.now(timezone.utc)
        assert abs(delta - timedelta(days=28)) < timedelta(minutes=1), (
            f"expected ~28d in the future, got {delta}"
        )

    db_val = await pg_pool.fetchval(
        "SELECT expires_at FROM listings WHERE id = $1", listing_id
    )
    assert db_val > stale_expires + timedelta(days=27)


async def test_extend_404(clean_db, pg_pool, monkeypatch):
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    missing = str(uuid.uuid4())
    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch(f"/api/listings/{missing}/extend")
        assert resp.status_code == 404


async def test_extend_invalid_uuid_returns_422(clean_db, pg_pool, monkeypatch):
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.patch("/api/listings/not-a-uuid/extend")
        assert resp.status_code == 422
