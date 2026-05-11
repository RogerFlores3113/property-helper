"""ARQ stub scraper task — D-13/D-14/D-15.

Loop shape: 3 outer iterations × 3 listings = 9 listings total per job.
Each iteration calls BudgetGuard.{check_iter, check_payload×3, record_spend}.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from ..guards.budget import BudgetExceeded, BudgetGuard


def _fake_listing() -> dict:
    """Return a fake listing dict whose JSON serializes to 300-500 chars (CACH-04)."""
    return {
        "address": "1234 Mock Street, Apt 5B, San Francisco, CA 94110",
        "price": 3200,
        "beds": 2,
        "baths": 1,
        "amenities": [
            "in-unit washer/dryer",
            "covered parking",
            "dishwasher",
            "central heating",
            "hardwood floors",
            "pet friendly",
        ],
        "source_url": "https://example.com/listing/abc123def456",
        "posted_date": "2026-05-09",
    }


async def run_search(ctx, job_id: str) -> None:
    """ARQ entrypoint — drives 3 iters × 3 listings = 9 listings total."""
    db = ctx["db"]
    guard = BudgetGuard.from_env(db=db)

    try:
        await db.execute(
            "UPDATE search_jobs SET status='running' WHERE id=$1", job_id
        )
        for _ in range(3):
            guard.check_iter()
            for _ in range(3):
                listing = _fake_listing()
                serialized = json.dumps(listing)
                payload = serialized.encode()
                guard.check_payload(len(payload))
                await db.execute(
                    """INSERT INTO listings (id, job_id, data, photo_url, created_at)
                       VALUES ($1, $2, $3::jsonb, $4, $5)""",
                    str(uuid.uuid4()),
                    job_id,
                    serialized,
                    "https://placehold.co/600x400",
                    datetime.now(timezone.utc),
                )
            await guard.record_spend(tokens=500)
            await asyncio.sleep(0.5)
        await db.execute(
            "UPDATE search_jobs SET status='completed', completed_at=NOW() WHERE id=$1",
            job_id,
        )
    except BudgetExceeded:
        await db.execute(
            "UPDATE search_jobs SET status='failed' WHERE id=$1", job_id
        )
        raise
