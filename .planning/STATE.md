---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
status: ready_to_plan
stopped_at: Plan 05-03 complete — SCRAP-08 dedup + CACH-02 TTL extend landed; dedup.py + listings.py + scraper INSERTs + mark_done hook GREEN
last_updated: "2026-05-12T16:09:45.600Z"
progress:
  total_phases: 8
  completed_phases: 5
  total_plans: 18
  completed_plans: 17
  percent: 63
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Non-technical users say what they want once in natural language and get consolidated, map-visualized apartment results without being asked anything else.
**Current phase:** 6

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation Skeleton | ✅ Complete |
| 2 | Search Input & NL Parsing | ✅ Complete |
| 3 | First Scraper + Map Results | ✅ Complete |
| 4 | LLM Extraction & Multi-Source | ✅ Complete |
| 5 | Cache, Dedup & Freshness | ⏳ Pending |
| 6 | Auth | ⏳ Pending |
| 7 | Dashboard | ⏳ Pending |
| 8 | Observability | ⏳ Pending |

## Active Phase

**Phase 5: Cache, Dedup & Freshness**
Goal: Add listing deduplication, shared global cache, and TTL-based freshness management so repeated searches return instant cached results and stale listings are flagged.
Status: Ready to plan

## Log

- 2026-05-10: Project initialized
- 2026-05-10: Roadmap created (5 phases, 34/34 v1 requirements mapped)
- 2026-05-10: Roadmap revised to 8 atomic phases (34/34 v1 requirements mapped); split prior Phase 2 into Search Input + First Scraper/Map, prior Phase 4 into Cache/Dedup + Auth, prior Phase 5 into Dashboard + Observability
- 2026-05-11: Completed Plan 01-01 — repo scaffold, backend uv project, Supabase migration 0001 applied to live dev project (ref ebxglaywpuynshplrtys), Next.js 15 + supabase-js client, pytest 7-stub scaffold green; smoke test prints `schema-push-verified`. Requirements COST-01/02/03 + CACH-03/04 scaffolded (behavior lands in 01-02).
- 2026-05-11: Completed Plan 01-02 — BudgetGuard (COST-01/02/03), FastAPI /api/jobs POST+GET (CACH-03), ARQ stub_scraper (3 iters × 3 listings, CACH-04). Full backend test suite green: `7 passed`. Six per-task commits (3 RED + 3 GREEN TDD pairs).
- 2026-05-11: Completed Plan 01-03 (code) — frontend/app/page.tsx implements UI-SPEC verbatim with Supabase Realtime dual-channel subscription (listings INSERT + search_jobs UPDATE), localStorage fire-and-forget reattach via GET /api/jobs/{id}, mergeById dedup (Pitfall 1), and useEffect cleanup via removeChannel (Pitfall 7). `npm run build` clean. Task 2 manual end-to-end smoke (all 5 ROADMAP success criteria) is a checkpoint:human-verify awaiting execution.
- 2026-05-11: Plan 01-03 fully complete — Task 2 manual smoke PASSED with resume signal `phase-1-complete`. All 5 ROADMAP success criteria verified: SC#1 enqueue+running, SC#2 streaming <1s (after pull-on-connect fix), SC#3 fire-and-forget reload (after jsonb parsing fix), SC#4 listings ~315 chars, SC#5 pytest 7 passed + daily_spend row with estimated_tokens=4500. Two post-execution bug fixes committed in 28c5d20 (jobs.py jsonb parsing + page.tsx pull-on-connect race). **Phase 1 complete.**
- 2026-05-12: Completed Plan 03-01 — replaced stub_scraper with real Craigslist scraper (httpx + selectolax + protego); RobotsCache enforces SCRAP-05 (one-fetch-per-origin, structlog SC#3 audit, fail-open on 5xx); parse_listing extracts lat/lng (D-07, range-validated), price/beds/baths/amenities/posted_date/source_url/source_name; photo URL whitelisted to craigslist.org/craigslistimages.org (T-03-05); SCRAPER_MAX_LISTINGS clamped to ≤30 (T-03-06); CreateJobBody now type-validates Phase 2 chips/global_flex (Pitfall 9, chip persistence deferred to Phase 4). +10 backend tests (17 total). SCRAP-02 + SCRAP-05 marked complete.
- 2026-05-12: Completed Plan 03-02 — MapView (MapLibre + OpenFreeMap positron) with cluster source + price-pin symbol layer + setFeatureState hover/select sync (`promoteId:'id'`); ListingList with cardRefs Map for D-14 scroll-into-view; React.memo ListingCard with custom comparator (Pitfall 8); slide-out ListingDrawer (Escape/× close); safeUrl.ts host-whitelist helpers (T-03-09/T-03-10) gate every rendered source link and photo URL. page.tsx now uses D-11 side-by-side grid while preserving Realtime subscription verbatim; Pitfall 6 reset (`setSelectedId(null); setHoveredId(null);`) added to startSearch. +4 frontend test files / +18 tests (28 total). MAP-01/02/03/04 marked complete. Bundle +275 kB (maplibre-gl).
- 2026-05-12: Plan 05-01 Tasks 1+3 complete (commits 0223d15, 286d2c3) — migration 0002 file ready + 19 RED tests (4 new files + 3 extended). Task 2 (`checkpoint:human-action`, blocking) awaits user: run `cd backend && npx supabase db push` and confirm verification SQL, then resume signal `migration-0002-pushed`.
- 2026-05-12: **Plan 05-04 complete.** Frontend freshness UI surfacing for CACH-01/CACH-02/SCRAP-08 landed. `Listing.expires_at` (required) + `ListingData.sources_list` (optional) + `SearchJob.chips` (optional) added to types.ts. New `isAllowedSourceUrl(source_name, url)` per-source dispatcher in safeUrl.ts (T-05-18). ListingCard now renders amber "data from X — expired" label + Extend/Re-search buttons when `expires_at <= now()`, plus a multi-link sources_list `<ul>` when ≥2 entries pass the host whitelist. React.memo comparator extended to compare `expires_at` and `sources_list` (Pitfall 8 / T-05-23). page.tsx adds `currentJob: SearchJob | null` state, `handleExtend` (PATCH /api/listings/{id}/extend → splice expires_at into local state on 200) and `handleResearch` (POST /api/jobs with persisted chips → reload); ListingList forwards both to ListingCard. +6 vitest tests in `frontend/__tests__/ListingCard.test.tsx`; suite-wide **45 passed**; `npm run build` clean. 3 task commits: 6ccf43c (types + safeUrl), aa2e576 (ListingCard + tests), 21740b1 (page.tsx + ListingList wiring). Task 3 checkpoint:human-verify auto-approved per `workflow._auto_chain_active: true`; manual E2E smoke (SC#1 cache hit, SC#2 stale + Extend, SC#3 dedup merged sources) deferred to developer for first live stack run.
- 2026-05-12: **Plan 05-03 complete.** SCRAP-08 cross-source dedup + CACH-02 TTL extend landed. New `app/workers/scrapers/dedup.py` exports `compute_dedup_key` (lower(trim(addr))|beds|sqft_bucket_100 per D-12; returns None for opt-out) and `run_dedup_for_job` (groups by dedup_key, retains oldest as canonical, merges into data.sources_list with canonical's own source seeded first per Pattern 3, DELETEs duplicates via `id = ANY($1::uuid[])` parameter binding). Both scrapers stamp dedup_key on INSERT; Craigslist parser now persists `sqft` (Pitfall 8) and a Rule-1 bug fix on the sqft regex (selectolax flattens `<b>850</b>ft<sup>2</sup>` to "850ft2"; old `re.sub('[^\\d]', '')` would have yielded 8502). `mark_done` invokes `run_dedup_for_job` exactly once on terminal='completed', wrapped in try/except so a dedup error never blocks the status flip (T-05-16). New PATCH `/api/listings/{id}/extend` (Pydantic UUID4 path → 422; 404 missing; 200 returns ISO expires_at ≈ now()+28d). Four task commits: bd5accc, 65e1f36, 7e69e9c, 9f27364, 52c979e. Suite-wide: 64 passed, 33 skipped (DB-required tests skip locally without SUPABASE_DB_URL).
- 2026-05-12: **Plan 05-02 complete.** CACH-01 cache-hit fast-path implemented end-to-end. New `app/workers/cache.py` exports `compute_filter_hash` (SHA-256 over canonical chips; drops `flex`/`id`; sorted by `(type, str(value))`) and `copy_cached_listings` (INSERT-from-SELECT with explicit `expires_at`+`dedup_key` carryover per Pitfall 4, `LIMIT 100` per D-04). POST /api/jobs now persists `filter_hash` + `chips` (JSONB cast via `$N::jsonb`, Pitfall 1); GET /api/jobs/{id} exposes `chips` on the job and `expires_at` on each listing. `run_search_coordinator` reads `filter_hash` and short-circuits BEFORE counter SETs / fan-out when `copy_cached_listings` returns > 0 (Pitfall 6 option a — direct `pending → completed` flip, no `mark_done` call, no Redis counter primes). 3 task commits: bcee461 (cache.py), 3a89074 (jobs.py), 5e2eb1b (coordinator.py). Suite-wide: 82 passed, 5 deselected (still-RED 05-03 scaffolds). Only `test_dedup_runs_once` remains RED for plan 05-03.
- 2026-05-12: **Plan 05-01 complete.** Task 2 closed — user ran `npx supabase db push` successfully; `supabase migration list` confirms Local = Remote for migration `20260512000002_cache_dedup_freshness`. Required `supabase/config.toml` + `supabase/migrations/` scaffold committed at 33c6686. Resume signal `migration-0002-pushed` received. Schema diff (expires_at NOT NULL/default 28d, dedup_key, filter_hash, chips, 3 indexes) live on dev project. Plan 05-02 unblocked.
- 2026-05-12: Completed Phase 4 — llm-extraction-multi-source. Plan 04-01: CR-01/CR-02 hardened (Field max_length, safeUrl suffix fix), isAllowedApartmentsUrl added, ANTHROPIC_API_KEY enforced at import, 6 RED scaffolds. Plan 04-02: prefilter.py (≥5× reduction), llm_extract.py (Haiku 4.5 forced tool-use + prompt caching + Sonnet escalation), rate_limit.py (Redis SET NX PX + jitter). Plan 04-03: run_search_coordinator fan-out, mark_done atomic counter, Craigslist renamed + rate-limited. Plan 04-04: run_search_apartments (Playwright + stealth + prefilter + LLM), ENABLED_SOURCES=["craigslist","apartments"]. phase-4-smoke verified (SC#1–SC#4). 55 tests passing. **Phase 4 complete.**

## Decisions Accumulated

- Supabase dev project at ref `ebxglaywpuynshplrtys` (aws-1-us-east-2 pooler, port 6543) per D-04.
- asyncpg pool uses `statement_cache_size=0` (REQUIRED for Supabase transaction pooler).
- `supabase_realtime` publication includes BOTH `listings` and `search_jobs` (single channel for incremental results + status transitions).
- Next.js pinned to `^15` (NOT 16); `@supabase/supabase-js ^2.105`.
- pgcrypto enabled for `gen_random_uuid()` (Pitfall 8).
- RLS deferred to Phase 6 with explicit TODO marker in migration 0001.
- HAIKU_INPUT_USD_PER_TOKEN = 1e-6 (Haiku 4.5 input $1/M) — resolves Plan 02 cost-per-call open question; verified by test_daily_spend_upsert.
- CORS lock for backend dev: exact `["http://localhost:3000"]` allow-list, methods `GET/POST/OPTIONS`, headers `Content-Type` (Pitfall 6).
- ARQ WorkerSettings.max_tries=1 (T-02-07 — avoid duplicate fake-data inserts on retry).
- GET /api/jobs/{id} uses `pydantic.UUID4` so malformed paths return 422, not 500 (ASVS V5).
- Phase 3 Plan 01: RobotsCache uses structlog default (JSON to stdout) — SC#3 verification is "grep worker stdout for `robots.fetched` / `robots.disallow`" (tests use `capsys`, not `caplog`).
- Phase 3 Plan 01: photo URL host whitelist enforced server-side in parse_listing (craigslist.org + craigslistimages.org); non-matching URLs persisted as None (T-03-05 defence in depth).
- Phase 3 Plan 01: httpx promoted to runtime dependency (scraper imports it directly); previously was dev-only.
- Phase 3 Plan 01: `chips`/`global_flex` validated at the API boundary (Pydantic ChipModel with Literal type enum) but not yet persisted — Phase 4 will add `query_chips` JSONB column to search_jobs and use chips in the scraper.
- Phase 3 Plan 02: MapLibre source uses `promoteId:'id'` so `setFeatureState({source, id: listing.id})` targets feature.id directly — without this the hover/select halo silently no-ops.
- Phase 3 Plan 02: vitest mocks for maplibre-gl must use `vi.hoisted` for shared state and ES class constructors (not `vi.fn(() => instance)`); `new maplibregl.Map(...)` requires a real constructor.
- Phase 3 Plan 02: `safeUrl.ts` host-whitelist module (`isAllowedCraigslistUrl`, `isAllowedCraigslistImage`, `formatPostedDate`) gates every rendered `<a href>` and `<img src>` — Phase 4 extends with per-source helpers as scrapers are added.
- Phase 3 Plan 02: ListingDrawer is always mounted in the DOM; closed state slides off-screen with `translate-x-full` + `aria-hidden=true` so AT navigation skips it.
- Phase 5 Plan 01: migration 0002 uses the Pitfall-10 two-step ALTER pattern (nullable → UPDATE per-row → SET NOT NULL → SET DEFAULT) so existing listing rows backfill from their own `created_at + 28d`, never migration-time `now() + 28d`.
- Phase 5 Plan 01: `red_phase_05` marker is intentionally NOT registered in pyproject — plans 05-02/05-03 remove the marker as each test turns GREEN (Wave-0 pattern inherited from Phase 4 Plan 04-01).
- Phase 5 Plan 02: `compute_filter_hash` is polymorphic (accepts Pydantic `ChipModel` or raw dicts via `hasattr(chip, "model_dump")`) — single helper covers both API and worker callsites without forcing a model import into `app/workers/cache.py`.
- Phase 5 Plan 02: cache-hit short-circuit uses Pitfall 6 option (a): flips `pending → completed` directly with `WHERE status='pending'` guard; never calls `mark_done` and never primes the Redis counter keys, since there are no sub-tasks to wait on.
- Phase 5 Plan 02: `copy_cached_listings` SQL explicitly lists `expires_at` and `dedup_key` in both INSERT and SELECT clauses (Pitfall 4) so the column DEFAULT (`now() + 28 days`) never overrides the source row's TTL on cache hit.
- Phase 5 Plan 03: `compute_dedup_key` returns `None` (opt-out) when address or beds missing — those rows insert with `dedup_key=NULL` and `run_dedup_for_job` ignores them entirely (preserves D-12 opt-out semantics).
- Phase 5 Plan 03: sources_list seeded with the canonical row's own (source_name, source_url) FIRST, then duplicates appended in created_at order — resolves Open Question 1 (Pattern 3).
- Phase 5 Plan 03: dedup invoked inside `mark_done` is wrapped in try/except — a dedup exception logs `coordinator.dedup_failed` and the status UPDATE still runs (T-05-16: dedup never blocks status flip).
- Phase 5 Plan 03: Rule-1 bug fix in `craigslist._parse_attrgroup` sqft regex — selectolax flattens `<b>850</b>ft<sup>2</sup>` to "850ft2", which the old `re.sub('[^\\d]', '', text)` would have parsed as 8502. New regex `(\\d+)\\s*ft(?:[²]|2)?\\b` captures the leading digit run before "ft". Latent bug; never observed because sqft was discarded pre-05-03.
- Phase 5 Plan 03: `dup_ids` are defensively cast to `uuid.UUID` Python objects before passing to `ANY($1::uuid[])` so the asyncpg uuid codec works regardless of whether the SELECT returned `uuid.UUID` or `str` for the id column.
- Phase 5 Plan 04: `ListingCard` React.memo comparator extended with `prev.listing.expires_at === next.listing.expires_at` and `prev.listing.data.sources_list === next.listing.data.sources_list` — without these the Extend success-path (state replacement with the new ISO) would never re-render the row (Pitfall 8 / T-05-23).
- Phase 5 Plan 04: `safeUrl.isAllowedSourceUrl(source_name, url)` is a single dispatcher that lower-trims `source_name` and routes to the existing per-source helpers (`isAllowedCraigslistUrl`, `isAllowedApartmentsUrl`); unknown sources return `false` — defence-in-depth gate for every sources_list anchor (T-05-18).
- Phase 5 Plan 04: `handleResearch` reloads the page after the new job_id is written to localStorage, so the existing `reattach()` path picks up the new job cleanly — avoids re-implementing the subscribe + catchup choreography inline.
- Phase 5 Plan 04: Test fixture default `expires_at = now + 24h` keeps all 6 pre-existing ListingCard tests GREEN unchanged after `Listing.expires_at` became required.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260511-pvo | fix scraper payload guard — check_payload on raw HTML (25-43KB) vs 8KB limit | 2026-05-12 | ae87cb1 | [260511-pvo-fix-scraper-payload-guard-check-payload-](./quick/260511-pvo-fix-scraper-payload-guard-check-payload-/) |

## Session Continuity

Last session: 2026-05-12T07:54:31.505Z
Stopped at: Plan 05-03 complete — SCRAP-08 dedup + CACH-02 TTL extend landed; dedup.py + listings.py + scraper INSERTs + mark_done hook GREEN
Resume file: None

## Blockers / Concerns

- ⚠ Phase 4 code review CR-01: `mark_done` uses 5 non-atomic Redis commands — race can write wrong terminal status. Fix with Lua script or MULTI/EXEC in Phase 5.
- ⚠ Phase 4 code review CR-02: `asyncio.get_event_loop()` in rate_limit.py — deprecated since Python 3.10. Fix: `asyncio.get_running_loop()`.
- ⚠ Phase 4 code review CR-03: LLM-supplied source_url can override authoritative URL in llm_extract.py — always use authoritative source_url unconditionally.
- ⚠ Phase 4 code review WR-04: Backend photo-host check uses bare `endswith` (craigslist.py, apartments.py) — same issue as frontend CR-02 was; fix to dotted-subdomain check.
