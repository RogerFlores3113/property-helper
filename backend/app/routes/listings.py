"""PATCH /api/listings/{id}/extend — TTL extension endpoint (CACH-02 / D-09).

User-facing freshness extension: a stale listing card surfaces an "extend"
button (frontend Plan 05-04) which PATCHes this endpoint, bumping
``expires_at`` to ``now() + 28 days``.

Pitfall 9 + T-05-10 (IDOR): this endpoint accepts any valid listing UUID
from any caller pre-Phase-6. Auth + RLS scoping to the owning user are
deferred to Phase 6 (Auth) — see TODO marker below. Threat is explicitly
``accept`` per the plan threat model.

Pydantic ``UUID4`` path-param validation (D-19): malformed UUIDs return
422 with a structured error, not 500.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import UUID4

from ..db import get_pool

router = APIRouter(prefix="/api/listings", tags=["listings"])


# TODO(Phase 6): scope this endpoint to the owning user via Supabase Auth
# + RLS. Pre-Phase-6 this is unauthenticated (T-05-10 — accepted gap;
# matches the Phase 1 "RLS deferred" stance).
@router.patch("/{listing_id}/extend")
async def extend_listing(listing_id: UUID4) -> dict:
    """Bump ``expires_at`` on the given listing to ``now() + 28 days``.

    Returns ``{"id": str, "expires_at": isoformat}`` on success;
    404 if the listing does not exist; 422 (Pydantic) if the UUID is
    malformed.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE listings "
            "   SET expires_at = now() + interval '28 days' "
            " WHERE id = $1 "
            "RETURNING id, expires_at",
            listing_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="listing not found")
    return {
        "id": str(row["id"]),
        "expires_at": row["expires_at"].isoformat(),
    }
