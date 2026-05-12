"""Cross-source deduplication helper — SCRAP-08 / D-12 + D-13.

Public surface::

    def compute_dedup_key(address, beds, sqft) -> str | None
    async def run_dedup_for_job(conn, job_id) -> int

``compute_dedup_key`` is the canonical form ``lower(trim(addr))|beds|sqft_bucket_100``
defined in 05-CONTEXT D-12. Returns ``None`` (opt-out, never deduped) when
address is falsy after strip or beds is missing — those rows insert with
``dedup_key = NULL`` and ``run_dedup_for_job`` ignores them.

``run_dedup_for_job`` is invoked exactly once per job by
``coordinator.mark_done`` when the job crosses the terminal=='completed'
threshold (D-13 + Pitfall 5). It groups duplicate listings by ``dedup_key``,
retains the oldest row as canonical, merges every contributing source into
``data.sources_list`` (Pattern 3 — canonical's own source seeded first), and
DELETEs the duplicates with ``id = ANY($1::uuid[])`` parameter binding
(T-05-11 — no string interpolation).

Idempotency: a second run on the same job is a safe no-op because each
``dedup_key`` group now has size 1 (T-05-15).
"""
from __future__ import annotations

import json
import uuid as _uuid
from typing import Any

import structlog

log = structlog.get_logger()


def compute_dedup_key(
    address: str | None,
    beds: int | None,
    sqft: int | None,
) -> str | None:
    """Return the canonical dedup key per D-12, or None for opt-out rows.

    Form: ``f"{addr.strip().lower()}|{beds}|{sqft_bucket_100}"``.

    - ``address`` falsy after strip → None (cannot dedupe without address).
    - ``beds`` None → None (Craigslist studios with no BR tag opt-out).
    - ``sqft`` None or non-int → bucket is the literal ``"?"`` sentinel so
      "same address+beds, unknown sqft" rows still collide.
    - ``sqft`` int ≥ 0 → bucket is ``str(int(sqft // 100) * 100)`` (100 ft²
      tolerance band).
    """
    if not address:
        return None
    addr = address.strip().lower()
    if addr == "":
        return None
    if beds is None:
        return None

    if isinstance(sqft, int) and sqft >= 0:
        sqft_bucket = str((sqft // 100) * 100)
    else:
        sqft_bucket = "?"

    return f"{addr}|{beds}|{sqft_bucket}"


def _decode_data(raw: Any) -> dict:
    """asyncpg JSONB defensive decode (Pitfall 1)."""
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


async def run_dedup_for_job(conn, job_id: str) -> int:
    """Merge duplicate listings within ``job_id`` and return the deleted count.

    Pattern 3 (05-RESEARCH §Cross-cutting):
      1. SELECT all listings for the job with dedup_key IS NOT NULL,
         ordered by created_at ASC (oldest = canonical).
      2. Group in Python by dedup_key.
      3. For each group with size > 1:
         - canonical = group[0]; duplicates = group[1:].
         - Seed canonical's own (source_name, source_url) into sources_list
           (Open Question 1 resolution).
         - Append each duplicate's source pair if not already present.
         - UPDATE canonical's data with the new sources_list ($1::jsonb).
         - DELETE duplicates with id = ANY($1::uuid[]) parameter binding.
      4. Return total rows deleted.
    """
    rows = await conn.fetch(
        "SELECT id, data, dedup_key, created_at, photo_url "
        "FROM listings "
        "WHERE job_id = $1 AND dedup_key IS NOT NULL "
        "ORDER BY created_at ASC",
        job_id,
    )

    # Group by dedup_key preserving SQL order (Python 3.7+ dict preserves insert order).
    groups: dict[str, list] = {}
    for row in rows:
        key = row["dedup_key"]
        groups.setdefault(key, []).append(row)

    total_deleted = 0
    for key, group in groups.items():
        if len(group) <= 1:
            continue
        canonical = group[0]
        duplicates = group[1:]

        canon_data = _decode_data(canonical["data"])

        # Pattern 3: seed canonical's own source first.
        sources_list: list[dict] = []
        seen: set[tuple[str, str]] = set()
        canon_source_name = canon_data.get("source_name")
        canon_source_url = canon_data.get("source_url")
        if canon_source_name and canon_source_url:
            sources_list.append(
                {"source_name": canon_source_name, "source_url": canon_source_url}
            )
            seen.add((canon_source_name, canon_source_url))

        # Append each duplicate's (source_name, source_url) if not already present.
        for dup in duplicates:
            dup_data = _decode_data(dup["data"])
            dn = dup_data.get("source_name")
            du = dup_data.get("source_url")
            if dn and du and (dn, du) not in seen:
                sources_list.append({"source_name": dn, "source_url": du})
                seen.add((dn, du))

        canon_data["sources_list"] = sources_list

        await conn.execute(
            "UPDATE listings SET data = $1::jsonb WHERE id = $2",
            json.dumps(canon_data),
            canonical["id"],
        )

        # Cast each id explicitly to uuid.UUID so the ANY($1::uuid[]) binding works
        # whether asyncpg returned str or uuid.UUID for the id column.
        dup_ids: list[_uuid.UUID] = []
        for dup in duplicates:
            raw_id = dup["id"]
            if isinstance(raw_id, _uuid.UUID):
                dup_ids.append(raw_id)
            else:
                try:
                    dup_ids.append(_uuid.UUID(str(raw_id)))
                except (ValueError, TypeError):
                    continue

        if dup_ids:
            await conn.execute(
                "DELETE FROM listings WHERE id = ANY($1::uuid[])",
                dup_ids,
            )
            total_deleted += len(dup_ids)

        log.info(
            "coordinator.dedup_merged",
            job_id=str(job_id),
            dedup_key=key,
            canonical_id=str(canonical["id"]),
            merged_sources=len(sources_list),
            duplicates_deleted=len(dup_ids),
        )

    return total_deleted
