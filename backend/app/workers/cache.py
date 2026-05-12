"""Cache module — filter_hash + cache-hit row copy (CACH-01).

Implements two public helpers used by the API and the coordinator:

- :func:`compute_filter_hash` — deterministic SHA-256 over canonical chips
  (D-01, 05-CONTEXT). Sorts by (type, str(value)); ignores the ``flex``
  field (Pitfall 6 — flex toggles ranking, not the cache key) and the
  client-side ``id`` field. Accepts both Pydantic ``ChipModel`` instances
  and raw dicts so it can be called from API and worker contexts.

- :func:`copy_cached_listings` — single-INSERT-from-SELECT row copy that
  carries each prior listing's ``expires_at`` and ``dedup_key`` forward to
  the new job (D-04, D-05, Pattern 2). CRITICAL (Pitfall 4): the SELECT
  and INSERT explicitly list ``expires_at`` and ``dedup_key`` so they are
  NOT reset to the column DEFAULT (``now() + 28 days``) on the copy.
  Capped at 100 rows (D-04) to bound storage growth (T-05-08).

The cache lookup joins ``listings`` to ``search_jobs`` on the prior
``filter_hash`` and filters ``l.expires_at > now()`` so stale listings
never feed a cache hit.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def _canonicalize(chips: Iterable[Any]) -> list[dict[str, Any]]:
    """Reduce chips to the canonical [(type, value)] form used for hashing.

    Accepts either Pydantic ``ChipModel`` instances (have ``model_dump``) or
    raw dicts. Drops ``id`` and ``flex`` (D-01, Pitfall 6). Sorts by
    ``(type, str(value))`` so chip-order is irrelevant.
    """
    normalized: list[dict[str, Any]] = []
    for chip in chips:
        if hasattr(chip, "model_dump"):
            d = chip.model_dump()
        else:
            d = dict(chip)
        normalized.append({"type": d["type"], "value": d["value"]})
    normalized.sort(key=lambda c: (c["type"], str(c["value"])))
    return normalized


def compute_filter_hash(chips: Iterable[Any]) -> str:
    """Compute the 64-char hex SHA-256 cache key for a chip set.

    Deterministic across:
      - chip ordering (canonical sort by (type, str(value)))
      - ``flex`` toggles (dropped before hashing — Pitfall 6)
      - ``id`` values (dropped before hashing — client-side identifier)

    Whitespace-stable: ``json.dumps(..., sort_keys=True,
    separators=(",", ":"))`` eliminates spacing drift.
    """
    canonical = _canonicalize(chips)
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def copy_cached_listings(conn: Any, new_job_id: str, filter_hash: str) -> int:
    """Copy fresh listings from any prior job with matching ``filter_hash``.

    Returns the number of rows copied (parsed from asyncpg's ``INSERT 0 N``
    status string). Returns 0 when there is no cache hit or all prior
    listings are stale.

    Pitfall 4: ``expires_at`` and ``dedup_key`` are explicitly carried
    forward from the source row — they are NEVER reset to the column
    DEFAULT (``now() + 28 days``), which would silently extend the TTL on
    cache hits and create freshness drift.

    Bound (D-04, T-05-08): ``LIMIT 100`` caps storage growth at ~50 KB per
    cache hit (~500 chars per listing).
    """
    status = await conn.execute(
        """
        INSERT INTO listings (id, job_id, data, photo_url, created_at, expires_at, dedup_key)
        SELECT gen_random_uuid(), $1, l.data, l.photo_url, l.created_at, l.expires_at, l.dedup_key
        FROM listings l
        JOIN search_jobs s ON s.id = l.job_id
        WHERE s.filter_hash = $2
          AND s.id != $1
          AND l.expires_at > now()
        ORDER BY l.created_at DESC
        LIMIT 100
        """,
        new_job_id,
        filter_hash,
    )
    # asyncpg returns "INSERT 0 N" — last whitespace-separated token is N.
    try:
        return int(status.split()[-1])
    except (ValueError, IndexError):
        return 0
