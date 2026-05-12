---
phase: 05-cache-dedup-freshness
plan: 02
subsystem: cache-hit-fast-path (CACH-01)
tags: [cache, filter-hash, coordinator, fast-path, supabase, asyncpg]
requires:
  - 05-01 (migration 0002 + RED scaffolds)
  - 04-03 (run_search_coordinator + mark_done — extended here)
provides:
  - app.workers.cache (compute_filter_hash, copy_cached_listings)
  - POST /api/jobs persists filter_hash + chips
  - GET /api/jobs/{id} exposes expires_at + chips
  - run_search_coordinator cache-hit short-circuit
affects:
  - backend/app/workers/coordinator.py (read filter_hash + short-circuit before fan-out)
  - backend/app/routes/jobs.py (persist on POST, expose on GET)
tech-stack:
  added: []
  patterns:
    - "SHA-256 over canonical (type, str(value))-sorted chips for cache key"
    - "INSERT-from-SELECT row copy that explicitly carries expires_at + dedup_key (Pitfall 4)"
    - "JSONB column persist via json.dumps + ::jsonb cast (Pitfall 1)"
    - "Cache-hit short-circuit BEFORE counter SETs / fan-out (Pitfall 6 option a)"
key-files:
  created:
    - backend/app/workers/cache.py
  modified:
    - backend/app/routes/jobs.py
    - backend/app/workers/coordinator.py
    - backend/tests/test_filter_hash.py
    - backend/tests/test_jobs_api.py
    - backend/tests/test_coordinator.py
decisions:
  - "compute_filter_hash accepts both Pydantic ChipModel and dict — single helper covers API (Pydantic) and worker (dict) callsites without forcing a model import in cache.py."
  - "Cache-hit path uses option (a) from Pitfall 6: it short-circuits BEFORE `status='running'` and BEFORE any Redis counter SET. The status flips directly from 'pending' to 'completed' guarded by `WHERE status='pending'`. This avoids needing to special-case mark_done's WHERE status='running' guard."
  - "copy_cached_listings parses asyncpg's `INSERT 0 N` status string for the rowcount; `try/except (ValueError, IndexError)` returns 0 on any parse anomaly (defence-in-depth)."
metrics:
  duration: "~12 min"
  completed: 2026-05-12T07:39Z
  tasks_completed: 3
  files_changed: 5
---

# Phase 5 Plan 02: CACH-01 cache-hit fast-path Summary

One-liner: New `app/workers/cache.py` (compute_filter_hash +
copy_cached_listings); POST /api/jobs persists filter_hash + chips,
GET exposes both on the response; run_search_coordinator short-circuits
to 'completed' when a prior job's filter_hash has ≥1 fresh listing,
copying the rows in a single round-trip and skipping fan-out entirely.

## New `app/workers/cache.py` Public Surface

```python
def compute_filter_hash(chips: Iterable[ChipModel | dict]) -> str
async def copy_cached_listings(conn, new_job_id: str, filter_hash: str) -> int
```

Behavior:
- `compute_filter_hash` — strips `id` and `flex` (D-01 + Pitfall 6),
  sorts by `(type, str(value))`, `json.dumps(sort_keys=True,
  separators=(",", ":"))`, returns 64-char lowercase SHA-256 hex.
- `copy_cached_listings` — single `INSERT … SELECT` joining listings
  to search_jobs on `s.filter_hash = $2 AND s.id != $1 AND
  l.expires_at > now()`, ordered by `created_at DESC`, `LIMIT 100`
  (D-04 / T-05-08 storage cap). Carries `expires_at` and `dedup_key`
  forward verbatim (Pitfall 4). Returns int rowcount.

## Diff Summary

### `backend/app/routes/jobs.py`
- POST: imports `compute_filter_hash`, computes hash from `body.chips`,
  serializes `[c.model_dump() for c in body.chips]` to a JSON string,
  INSERT extended to `(id, status, query, filter_hash, chips) VALUES
  ($1, 'pending', $2, $3, $4::jsonb)`.
- GET: SELECT extended with `chips` (search_jobs) and `expires_at`
  (listings). Response gains `job.chips` (decoded via the existing
  `json.loads-if-str` defensive pattern) and `listings[].expires_at`
  (ISO-8601 string).

### `backend/app/workers/coordinator.py`
- New import: `from .cache import copy_cached_listings`.
- New top-of-`run_search_coordinator` block (24 lines): fetch
  `filter_hash`, call `copy_cached_listings`; on `copied > 0` run
  `UPDATE … status='completed' … WHERE … status='pending'`, log
  `coordinator.cache_hit`, return. Otherwise fall through to existing
  fan-out (untouched).

## Per-Task pytest Counts

| Task | Test file | Tests run | Pass | Notes |
|------|-----------|-----------|------|-------|
| 1 | `tests/test_filter_hash.py` | 4 | 4 | All 4 GREEN; marker removed file-wide |
| 2 | `tests/test_jobs_api.py` | 6 | 6 | All 6 GREEN incl. 2 new Phase 5 tests |
| 3 | `tests/test_coordinator.py` | 9 | 8 | 2 new cache tests GREEN; `test_dedup_runs_once` intentionally remains RED for plan 05-03 |

**Suite-wide** (excluding plan 05-03 RED scaffolds in `test_dedup.py` +
`test_listings_api.py`, and `-m "not red_phase_05"` to exclude the 5
still-marked tests): **82 passed**, 5 deselected.

## Deviations from Plan

### Marker removal scoped per-test, not whole-file

The plan said "remove `pytestmark = pytest.mark.red_phase_05` marker line
from backend/tests/test_filter_hash.py" (file-level — done) and
"Remove the `pytestmark = pytest.mark.red_phase_05` marker from the
relevant test functions in test_jobs_api.py" + "from the relevant tests
in test_coordinator.py" (per-test — done on the two cache tests; NOT
done on `test_dedup_runs_once` because it covers SCRAP-08 / plan
05-03's dedup work, which is not in scope here). No functional
deviation — exactly what the plan called for once the dedup test is
recognized as out-of-scope for 05-02.

### Cleanup: removed unused `pytest` import in test_filter_hash.py

When the file-level `pytestmark = pytest.mark.red_phase_05` line was
removed (per plan), `import pytest` became unused. Removed it to keep
the file lint-clean. Pure cleanup, no behavior change.

No deviations from CONTEXT D-01 / D-03 / D-04 / D-05 — the implementation
matches the canonical-form, JSONB persistence, INSERT-from-SELECT row
copy, and short-circuit-before-fan-out specs exactly.

## Auth Gates / Checkpoints

None. Plan was fully autonomous (autonomous: true). All tests ran
locally against the live Supabase dev DB (`SUPABASE_DB_URL` from
`backend/.env`).

## Known Stubs

None. All three behaviors are wired end-to-end:
- compute_filter_hash is exported and called from `routes/jobs.py`.
- copy_cached_listings is exported and called from
  `workers/coordinator.py`.
- POST persists + GET exposes filter_hash, chips, and expires_at.

## Threat Flags

None. The implementation matches every disposition in the plan's
`<threat_model>`:

- T-05-06 (SQL injection): all queries use `$1/$2` parameter binding;
  `filter_hash` is server-computed from Pydantic-validated chips and
  never user-supplied directly.
- T-05-08 (DoS via cache row growth): `LIMIT 100` cap on the row copy
  is in place.
- T-05-09 (chips JSONB unknown values): ChipModel `Literal` type enum
  rejects unknown types with 422 before `compute_filter_hash` runs.

## Self-Check: PASSED

- `backend/app/workers/cache.py` — FOUND (40+ lines, exports
  `compute_filter_hash` and `copy_cached_listings`).
- `backend/app/routes/jobs.py` — modified (filter_hash persisted on
  POST; chips + expires_at exposed on GET).
- `backend/app/workers/coordinator.py` — modified (cache-hit
  short-circuit calling `copy_cached_listings`).
- `backend/tests/test_filter_hash.py` — marker removed; 4 tests GREEN.
- `backend/tests/test_jobs_api.py` — markers removed from 2 new tests;
  6 tests GREEN.
- `backend/tests/test_coordinator.py` — markers removed from 2 cache
  tests; 8/9 GREEN (`test_dedup_runs_once` remains RED for 05-03).
- Commit `bcee461` (Task 1) — FOUND in `git log --oneline`.
- Commit `3a89074` (Task 2) — FOUND in `git log --oneline`.
- Commit `5e2eb1b` (Task 3) — FOUND in `git log --oneline`.
- copy_cached_listings SQL: `grep -n 'expires_at\|dedup_key'
  backend/app/workers/cache.py` confirms both columns appear in both
  the INSERT column list and the SELECT clause (Pitfall 4).
