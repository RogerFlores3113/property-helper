"""Jobs API tests — POST /api/jobs and GET /api/jobs/{id} (CACH-03)."""
from __future__ import annotations

import json
import uuid

import httpx
import pytest

from app import db as db_module
from app.main import app as main_app
from app.routes import jobs as jobs_route


class _StubArq:
    """Stand-in for ArqRedis — records enqueue calls without touching Redis."""

    def __init__(self):
        self.calls = []

    async def enqueue_job(self, function_name, *args, **kwargs):
        self.calls.append((function_name, args, kwargs))
        return None


async def test_fire_and_forget(clean_db, pg_pool, monkeypatch):
    # Wire the existing pg_pool fixture into the app-level db module so the
    # route handlers reuse the same connection (and TRUNCATE applies).
    monkeypatch.setattr(db_module, "_pool", pg_pool)

    # Stub ARQ so POST doesn't attempt a real Redis connection.
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # ---- POST /api/jobs ----
        resp = await client.post("/api/jobs", json={"query": "test query"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        job_id = body["job_id"]
        # Validates as a UUID
        uuid.UUID(job_id)

        # ---- Validation: missing query → 422 ----
        bad = await client.post("/api/jobs", json={"not_query": 1})
        assert bad.status_code == 422

        # Simulate worker output: insert 2 fake listings for this job.
        for _ in range(2):
            await pg_pool.execute(
                """INSERT INTO listings (id, job_id, data, photo_url, created_at)
                   VALUES (gen_random_uuid(), $1, $2::jsonb, $3, NOW())""",
                job_id,
                json.dumps({"address": "x"}),
                "https://placehold.co/600x400",
            )

        # ---- GET /api/jobs/{id} ----
        get_resp = await client.get(f"/api/jobs/{job_id}")
        assert get_resp.status_code == 200
        got = get_resp.json()
        assert got["job"]["id"] == job_id
        assert got["job"]["status"] == "pending"
        assert len(got["listings"]) == 2

        # ---- 404 for unknown UUID ----
        random_id = str(uuid.uuid4())
        nf = await client.get(f"/api/jobs/{random_id}")
        assert nf.status_code == 404
        assert nf.json()["detail"] == "job not found"

        # ---- 422 for malformed UUID ----
        bad_id = await client.get("/api/jobs/not-a-uuid")
        assert bad_id.status_code == 422

    # Verify the enqueue side-effect fired exactly once for the POST.
    # Plan 04-03: POST enqueues the coordinator, not the source sub-task.
    assert len(stub.calls) == 1
    fn, args, _ = stub.calls[0]
    assert fn == "run_search_coordinator"
    assert args[0] == job_id


async def test_jobs_post_enqueues_coordinator(clean_db, pg_pool, monkeypatch):
    """Plan 04-03: POST /api/jobs enqueues run_search_coordinator (not run_search)."""
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/jobs", json={"query": "sf bay area"})
        assert resp.status_code == 200

    assert len(stub.calls) == 1
    fn, args, _ = stub.calls[0]
    assert fn == "run_search_coordinator", (
        f"POST /api/jobs must enqueue run_search_coordinator; got {fn!r}"
    )


async def test_query_max_length(clean_db, pg_pool, monkeypatch):
    """CR-01 / T-04-05 — POST /api/jobs caps query at 512 chars.

    Boundary: 512 accepted (200), 513 rejected (422).
    """
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        ok = await client.post("/api/jobs", json={"query": "x" * 512})
        assert ok.status_code == 200, ok.text

        too_long = await client.post("/api/jobs", json={"query": "x" * 513})
        assert too_long.status_code == 422


# ---------------------------------------------------------------------------
# Phase 5 RED additions — filter_hash + chips persistence, expires_at exposure
# ---------------------------------------------------------------------------


@pytest.mark.red_phase_05
async def test_create_job_persists_filter_hash_and_chips(
    clean_db, pg_pool, monkeypatch
):
    """POST /api/jobs with chips → DB row has non-NULL filter_hash (64-char hex)
    and chips JSONB equal to the posted chips."""
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    chips = [
        {"id": "1", "type": "beds", "value": 2, "flex": False},
        {"id": "2", "type": "max_price", "value": 5000, "flex": False},
    ]
    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/jobs", json={"query": "2br sfbay", "chips": chips}
        )
        assert resp.status_code == 200, resp.text
        job_id = resp.json()["job_id"]

    row = await pg_pool.fetchrow(
        "SELECT filter_hash, chips FROM search_jobs WHERE id = $1", job_id
    )
    import re as _re

    assert row["filter_hash"] is not None
    assert _re.match(r"^[0-9a-f]{64}$", row["filter_hash"]), (
        f"filter_hash must be sha256 hex, got {row['filter_hash']!r}"
    )
    stored = row["chips"]
    if isinstance(stored, str):
        stored = json.loads(stored)
    assert stored is not None
    # Compare as set-of-tuples since chip ordering may be canonicalized server-side.
    posted = {(c["type"], c["value"]) for c in chips}
    got = {(c["type"], c["value"]) for c in stored}
    assert got == posted


@pytest.mark.red_phase_05
async def test_get_job_exposes_expires_at_and_chips(clean_db, pg_pool, monkeypatch):
    """GET /api/jobs/{id} listings include `expires_at` ISO string; job
    payload includes `chips`."""
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    chips = [{"id": "1", "type": "beds", "value": 2, "flex": False}]
    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/jobs", json={"query": "q", "chips": chips}
        )
        job_id = resp.json()["job_id"]

        await pg_pool.execute(
            """INSERT INTO listings (id, job_id, data)
               VALUES (gen_random_uuid(), $1, $2::jsonb)""",
            job_id,
            json.dumps({"address": "x"}),
        )

        got = await client.get(f"/api/jobs/{job_id}")
        assert got.status_code == 200
        body = got.json()
        assert body["job"].get("chips") is not None
        assert len(body["listings"]) == 1
        assert body["listings"][0].get("expires_at") is not None
        # ISO-8601 format check (round-trippable).
        from datetime import datetime as _dt

        _dt.fromisoformat(body["listings"][0]["expires_at"])


async def test_query_min_length(clean_db, pg_pool, monkeypatch):
    """CR-01 — empty query rejected with 422."""
    monkeypatch.setattr(db_module, "_pool", pg_pool)
    stub = _StubArq()

    async def fake_arq():
        return stub

    monkeypatch.setattr(jobs_route, "arq", fake_arq)

    transport = httpx.ASGITransport(app=main_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        empty = await client.post("/api/jobs", json={"query": ""})
        assert empty.status_code == 422
