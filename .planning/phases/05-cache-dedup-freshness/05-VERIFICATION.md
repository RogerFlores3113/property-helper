---
phase: 05-cache-dedup-freshness
verified: 2026-05-12T17:00:00Z
status: passed
score: 10/10 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/10
  gaps_closed:
    - "CORS allow_methods now includes PATCH — Extend round-trip unblocked (backend/app/main.py line 31)"
    - "ROADMAP.md SC#1 wording updated to filter-hash-only with explicit v2 deferral note for bbox"
    - "Human E2E smoke for SC#1/SC#2/SC#3 completed by developer on 2026-05-12 (documented in 05-05-SUMMARY.md Task 3)"
  gaps_remaining: []
  regressions: []
---

# Phase 5: Cache, Dedup & Freshness Verification Report

**Phase Goal:** Make repeat/overlapping searches feel instant via a shared bbox+filter-hash cache, merge duplicate listings across sources, and surface TTL/freshness state clearly to the user.
**Verified:** 2026-05-12T17:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure plan 05-05

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | Migration 0002 file exists and is idempotent with all 10 statements | VERIFIED | `backend/migrations/0002_cache_dedup_freshness.sql` exists; all 10 DDL statements present including Pitfall-10 two-step NOT NULL backfill; all `IF NOT EXISTS` guards present |
| 2  | compute_filter_hash is deterministic across chip ordering and ignores the flex field | VERIFIED | `backend/app/workers/cache.py` implements SHA-256 over canonical sorted `(type, value)` pairs; flex and id dropped; 4 tests pass green |
| 3  | POST /api/jobs computes filter_hash and persists it + chips JSONB on the new search_jobs row | VERIFIED | `backend/app/routes/jobs.py` calls `compute_filter_hash(body.chips)` and inserts `(id, status, query, filter_hash, chips)` with `$4::jsonb` cast |
| 4  | GET /api/jobs/{id} response includes chips on job and expires_at on each listing | VERIFIED | `backend/app/routes/jobs.py` SELECT includes `chips` on search_jobs and `expires_at` on listings; response serializes both |
| 5  | When a new job's filter_hash matches a prior job with >=1 fresh listing, coordinator copies rows and flips status='completed' without enqueueing any scraper sub-task | VERIFIED | `backend/app/workers/coordinator.py` `run_search_coordinator` reads filter_hash, calls `copy_cached_listings`, on `copied > 0` executes guarded UPDATE and returns before fan-out; `coordinator.cache_hit` log emitted |
| 6  | compute_dedup_key produces lower(trim(addr))\|beds\|sqft_bucket_100 form | VERIFIED | `backend/app/workers/scrapers/dedup.py` implements correct formula; 4 unit tests pass green |
| 7  | Both scrapers stamp dedup_key on INSERT (craigslist + apartments) | VERIFIED | `craigslist.py` imports `compute_dedup_key` and extends INSERT; `apartments.py` does the same |
| 8  | run_dedup_for_job merges duplicate listings into canonical row's data.sources_list and DELETEs duplicates | VERIFIED | `backend/app/workers/scrapers/dedup.py` correctly groups by dedup_key, seeds canonical's own source first, appends duplicates' sources, UPDATEs canonical, DELETEs duplicates via `id = ANY($1::uuid[])` |
| 9  | PATCH /api/listings/{id}/extend bumps expires_at by 28d and returns the new value; Malformed UUID returns 422, missing returns 404 | VERIFIED | `backend/app/routes/listings.py` implements the route; wired into `main.py` via `app.include_router(listings.router)` |
| 10 | Extend button calls PATCH /api/listings/{id}/extend and updates local listing state on 200; CORS preflight succeeds | VERIFIED | `backend/app/main.py` line 31: `allow_methods=["GET", "POST", "PATCH", "OPTIONS"]` — PATCH is present; frontend code correctly calls PATCH and updates state on 200; human smoke confirmed preflight passes (05-05-SUMMARY.md Task 3) |
| 11 | ListingCard renders amber 'data from X — expired' label when expires_at <= now() | VERIFIED | `ListingCard.tsx` computes `isStale` and applies `text-amber-600` + `" — expired"` suffix; 2 vitest tests verify both stale and fresh states |
| 12 | Listing type includes expires_at: string and sources_list?: {source_name, source_url}[] | VERIFIED | `frontend/app/types.ts` has `expires_at: string` on `Listing` and `sources_list?: SourceEntry[]` on `ListingData`; `SearchJob.chips?: Chip[]` also added |
| 13 | sources_list URLs are gated by safeUrl per-source host whitelist before rendering | VERIFIED | `safeUrl.ts` exports `isAllowedSourceUrl(source_name, url)` dispatching to per-source validators; `ListingCard.tsx` filters via `safeSources`; 2 vitest tests verify allow/deny |
| 14 | Manual E2E smoke verifies SC#1, SC#2, SC#3 against live stack | VERIFIED | Developer ran all four sub-tests (A: cache hit sub-second, B: stale label + Extend PATCH round-trip, C: Re-search round-trip, D: cross-source dedup) on 2026-05-12 and confirmed all pass; documented in 05-05-SUMMARY.md Task 3 section |
| 15 | A search whose filter hash matches a recent search returns cached listings sub-second (bbox deferred to v2) | VERIFIED | ROADMAP.md SC#1 updated to reflect filter-hash-only implementation with explicit bbox deferral note; filter_hash cache short-circuit confirmed working by human smoke; 05-CONTEXT D-02/D-03 documents v2 scope |

**Score:** 10/10 truths verified

### Gap Closure Summary

Three gaps from the initial verification were closed by plan 05-05:

**BLOCKER 1 — CORS PATCH (CLOSED):** `backend/app/main.py` CORSMiddleware `allow_methods` updated from `["GET", "POST", "OPTIONS"]` to `["GET", "POST", "PATCH", "OPTIONS"]` in commit `c48fd64`. Verified directly at line 31 of the file.

**BLOCKER 2 — Human E2E smoke gate (CLOSED):** Developer ran all four sub-tests on 2026-05-12. Human confirmed: CORS preflight passes, Extend button returns 200, stale/fresh UI flips correctly, Re-search posts new job, SC#1 cache-hit timing met. Documented in 05-05-SUMMARY.md.

**WARNING — bbox scope deviation (CLOSED):** ROADMAP.md SC#1 updated in commit `4419b38` to read "filter hash matches a recent search" with inline v2 deferral note for bbox-overlap. Old "geographic bounding box + filter hash overlaps" wording removed. Phase goal line (line 83) retains "bbox+filter-hash" as original intent statement — intentionally left per 05-05-SUMMARY.md scope analysis.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/migrations/0002_cache_dedup_freshness.sql` | Schema diff for Phase 5 | VERIFIED | All 10 statements; idempotent; Pitfall-10 backfill pattern |
| `backend/app/workers/cache.py` | compute_filter_hash + copy_cached_listings | VERIFIED | Both functions exported; LIMIT 100 cap; expires_at + dedup_key carried in INSERT-from-SELECT |
| `backend/app/routes/jobs.py` | filter_hash + chips on POST; expires_at + chips on GET | VERIFIED | filter_hash computed and inserted; chips serialized as JSONB; GET returns both |
| `backend/app/workers/coordinator.py` | cache-hit fast-path + dedup hook | VERIFIED | `copy_cached_listings` called before fan-out; `run_dedup_for_job` called in `mark_done` terminal='completed' branch |
| `backend/app/workers/scrapers/dedup.py` | compute_dedup_key + run_dedup_for_job | VERIFIED | Both exports; Pattern 3 sources_list seeding; uuid cast for ANY($1::uuid[]) |
| `backend/app/routes/listings.py` | PATCH /api/listings/{id}/extend | VERIFIED | Route exists with UUID4 path param; 404/422 handled; TODO(Phase 6) RLS marker present |
| `frontend/app/types.ts` | expires_at + sources_list on Listing; chips on JobResponse | VERIFIED | All three additions confirmed |
| `frontend/app/components/ListingCard.tsx` | Stale-state rendering + Extend/Re-search + sources_list | VERIFIED | isStale, amber label, buttons, sources_list multi-link rendering all present |
| `frontend/app/components/safeUrl.ts` | isAllowedSourceUrl dispatcher | VERIFIED | Exports `isAllowedSourceUrl(source_name, url)` |
| `frontend/app/page.tsx` | handleExtend + handleResearch wired to ListingList | VERIFIED | Both handlers defined; passed to ListingList as `onExtend`/`onResearch`; ListingList forwards to ListingCard |
| `backend/app/main.py` | PATCH in CORS allow_methods | VERIFIED | Line 31: `allow_methods=["GET", "POST", "PATCH", "OPTIONS"]` — confirmed in file |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/routes/jobs.py` | `backend/app/workers/cache.py` | `compute_filter_hash(body.chips)` at POST time | WIRED | Import confirmed; called in `create_job` before INSERT |
| `backend/app/workers/coordinator.py` | `backend/app/workers/cache.py` | `copy_cached_listings(db, job_id, filter_hash)` before fan-out | WIRED | Import confirmed; called in `run_search_coordinator` |
| `backend/app/workers/scrapers/craigslist.py` | `backend/app/workers/scrapers/dedup.py` | `compute_dedup_key(address, beds, sqft)` before INSERT | WIRED | Import confirmed; called before INSERT |
| `backend/app/workers/scrapers/apartments.py` | `backend/app/workers/scrapers/dedup.py` | `compute_dedup_key(address, beds, sqft)` before INSERT | WIRED | Import confirmed; called before INSERT |
| `backend/app/workers/coordinator.py` | `backend/app/workers/scrapers/dedup.py` | `run_dedup_for_job(db, job_id)` in terminal='completed' branch of mark_done | WIRED | Import confirmed; called in try/except in `mark_done` terminal branch |
| `backend/app/main.py` | `backend/app/routes/listings.py` | `app.include_router(listings.router)` | WIRED | Import at line 11; include_router at line 36 |
| `frontend/app/components/ListingCard.tsx` | `PATCH /api/listings/{id}/extend` | fetch in onExtend handler (page.tsx) | WIRED | page.tsx handleExtend correctly calls PATCH; CORS middleware now includes PATCH; human smoke confirmed preflight + 200 response |
| `frontend/app/components/ListingCard.tsx` | `POST /api/jobs` | fetch in onResearch handler (page.tsx) | WIRED | page.tsx handleResearch POSTs /api/jobs with persisted chips; human smoke confirmed new job_id written to localStorage |
| `frontend/app/components/ListingCard.tsx` | `frontend/app/components/safeUrl.ts` | `isAllowedSourceUrl` per sources_list entry | WIRED | Import and filter confirmed in ListingCard.tsx |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `ListingCard.tsx` | `isStale` | `listing.expires_at` | Yes — from DB via GET /api/jobs/{id} serialized as ISO string | FLOWING |
| `ListingCard.tsx` | `safeSources` | `listing.data.sources_list` | Yes — populated by `run_dedup_for_job` when duplicates found | FLOWING (conditional on duplicates existing) |
| `coordinator.py` `run_search_coordinator` | `copied` | `copy_cached_listings` DB INSERT-from-SELECT | Yes — counts real rows from DB; returns 0 on cache miss | FLOWING |
| `coordinator.py` `mark_done` | `deleted` | `run_dedup_for_job` DB operations | Yes — real SELECT + UPDATE + DELETE against DB | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| compute_filter_hash deterministic | `cd backend && uv run pytest tests/test_filter_hash.py -x` | 4 passed | PASS |
| compute_dedup_key formula | `cd backend && uv run pytest tests/test_dedup.py -x` | 4 unit passed, 3 skipped (DB) | PASS |
| Craigslist sqft persisted | `cd backend && uv run pytest tests/test_craigslist_parser.py -x` | 4 passed | PASS |
| Full backend suite | `cd backend && uv run pytest -x` | 64 passed, 33 skipped (DB) | PASS |
| Frontend vitest suite | `cd frontend && npm test -- --run` | 8 files, 45 tests passed | PASS |
| Frontend build | `cd frontend && npm run build` | Clean, no TS errors | PASS |

### Probe Execution

No probe scripts found in `scripts/*/tests/probe-*.sh`. Phase 05 does not use the probe pattern.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CACH-01 | 05-02 | New searches check the shared listing cache first; cached listings returned instantly without re-scraping | SATISFIED | `compute_filter_hash` + `copy_cached_listings` + coordinator fast-path implemented, tested, and human-smoke-confirmed sub-second on live stack |
| CACH-02 | 05-03, 05-04 | Listings expire after 3–4 weeks; expired listings labeled "data from X date"; user offered re-search/extend option | SATISFIED | Backend: `expires_at DEFAULT now()+28d` + PATCH endpoint. Frontend: amber label + Extend/Re-search buttons. CORS PATCH gap closed. Human smoke confirmed Extend round-trip (PATCH 200, UI flips from stale to fresh). |
| SCRAP-08 | 05-03 | Scraped listings from multiple sources deduplicated using normalized address+beds+sqft key; duplicate sources merged into single listing with `sources[]` array | SATISFIED | `compute_dedup_key` + `run_dedup_for_job` implemented; both scrapers stamp dedup_key; mark_done fires dedup exactly once on terminal='completed' |

### Anti-Patterns Found

No blockers remaining.

No `TBD`, `FIXME`, or `XXX` markers found in any Phase 5 modified files.

The `TODO(Phase 6)` in `backend/app/routes/listings.py` is a documented accepted threat (T-05-10, IDOR pre-auth) referencing follow-up work in Phase 6 and is not a debt marker.

### Human Verification Required

All human verification items are closed. Developer confirmed all four sub-tests on 2026-05-12:

- **SC#1 cache hit sub-second:** Confirmed sub-second completion, `coordinator.cache_hit` log with `copied > 0`, no fan-out for second job.
- **SC#2 Extend round-trip:** CORS preflight returns 204 with `Access-Control-Allow-Methods: PATCH`; follow-up PATCH returns 200; card flips from amber-stale to fresh without page reload.
- **SC#2 Re-search round-trip:** New job_id written to localStorage; page reattaches to new job.
- **SC#3 Cross-source dedup:** At least one listing with `sources_list.length >= 2`; `coordinator.dedup_merged` log emitted; ListingCard renders multi-link sources_list.

---

_Verified: 2026-05-12T17:00:00Z_
_Verifier: Claude (gsd-verifier)_
_Re-verification after gap closure plan 05-05_
