"""POST /api/jobs and GET /api/jobs/{id} — fire-and-forget endpoint (CACH-03)."""
from __future__ import annotations

import json
import uuid

from arq.connections import ArqRedis, RedisSettings, create_pool
from fastapi import APIRouter, HTTPException
from pydantic import UUID4, BaseModel

from ..db import get_pool
from ..settings import settings

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class CreateJobBody(BaseModel):
    """Validated POST body — rejects anything else with 422 (ASVS V5)."""

    query: str


_arq: ArqRedis | None = None


async def arq() -> ArqRedis:
    """Lazy ArqRedis pool factory (one connection pool per process)."""
    global _arq
    if _arq is None:
        _arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    return _arq


@router.post("")
async def create_job(body: CreateJobBody) -> dict:
    job_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO search_jobs (id, status, query) VALUES ($1, 'pending', $2)",
            job_id,
            body.query,
        )
    redis = await arq()
    await redis.enqueue_job("run_search", job_id)
    return {"job_id": job_id, "status": "pending"}


@router.get("/{job_id}")
async def get_job(job_id: UUID4) -> dict:
    """Return {job, listings} for an existing search job (CACH-03)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        job = await conn.fetchrow(
            "SELECT id, status, query, created_at, completed_at FROM search_jobs WHERE id = $1",
            job_id,
        )
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        listings = await conn.fetch(
            "SELECT id, job_id, data, photo_url, created_at FROM listings "
            "WHERE job_id = $1 ORDER BY created_at ASC",
            job_id,
        )

    return {
        "job": {
            "id": str(job["id"]),
            "status": job["status"],
            "query": job["query"],
            "created_at": job["created_at"].isoformat() if job["created_at"] else None,
            "completed_at": (
                job["completed_at"].isoformat() if job["completed_at"] else None
            ),
        },
        "listings": [
            {
                "id": str(row["id"]),
                "job_id": str(row["job_id"]),
                "data": json.loads(row["data"]) if isinstance(row["data"], str) else row["data"],
                "photo_url": row["photo_url"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            for row in listings
        ],
    }
