---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 03
status: ready_to_plan
last_updated: "2026-05-12T01:25:00.000Z"
progress:
  total_phases: 8
  completed_phases: 2
  total_plans: 9
  completed_plans: 7
  percent: 78
---

# Project State

## Project Reference

See: .planning/PROJECT.md

**Core value:** Non-technical users say what they want once in natural language and get consolidated, map-visualized apartment results without being asked anything else.
**Current phase:** 03

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 1 | Foundation Skeleton | ✅ Complete |
| 2 | Search Input & NL Parsing | ⏳ Pending |
| 3 | First Scraper + Map Results | 🚧 In Progress (Plan 01/3 complete) |
| 4 | LLM Extraction & Multi-Source | ⏳ Pending |
| 5 | Cache, Dedup & Freshness | ⏳ Pending |
| 6 | Auth | ⏳ Pending |
| 7 | Dashboard | ⏳ Pending |
| 8 | Observability | ⏳ Pending |

## Active Phase

**Phase 1: Foundation Skeleton**
Goal: End-to-end infra (Next.js + FastAPI + Supabase + Redis + ARQ + Realtime) with cost guardrails wired and fake data flowing from worker to UI.
Started: 2026-05-10

## Log

- 2026-05-10: Project initialized
- 2026-05-10: Roadmap created (5 phases, 34/34 v1 requirements mapped)
- 2026-05-10: Roadmap revised to 8 atomic phases (34/34 v1 requirements mapped); split prior Phase 2 into Search Input + First Scraper/Map, prior Phase 4 into Cache/Dedup + Auth, prior Phase 5 into Dashboard + Observability
- 2026-05-11: Completed Plan 01-01 — repo scaffold, backend uv project, Supabase migration 0001 applied to live dev project (ref ebxglaywpuynshplrtys), Next.js 15 + supabase-js client, pytest 7-stub scaffold green; smoke test prints `schema-push-verified`. Requirements COST-01/02/03 + CACH-03/04 scaffolded (behavior lands in 01-02).
- 2026-05-11: Completed Plan 01-02 — BudgetGuard (COST-01/02/03), FastAPI /api/jobs POST+GET (CACH-03), ARQ stub_scraper (3 iters × 3 listings, CACH-04). Full backend test suite green: `7 passed`. Six per-task commits (3 RED + 3 GREEN TDD pairs).
- 2026-05-11: Completed Plan 01-03 (code) — frontend/app/page.tsx implements UI-SPEC verbatim with Supabase Realtime dual-channel subscription (listings INSERT + search_jobs UPDATE), localStorage fire-and-forget reattach via GET /api/jobs/{id}, mergeById dedup (Pitfall 1), and useEffect cleanup via removeChannel (Pitfall 7). `npm run build` clean. Task 2 manual end-to-end smoke (all 5 ROADMAP success criteria) is a checkpoint:human-verify awaiting execution.
- 2026-05-11: Plan 01-03 fully complete — Task 2 manual smoke PASSED with resume signal `phase-1-complete`. All 5 ROADMAP success criteria verified: SC#1 enqueue+running, SC#2 streaming <1s (after pull-on-connect fix), SC#3 fire-and-forget reload (after jsonb parsing fix), SC#4 listings ~315 chars, SC#5 pytest 7 passed + daily_spend row with estimated_tokens=4500. Two post-execution bug fixes committed in 28c5d20 (jobs.py jsonb parsing + page.tsx pull-on-connect race). **Phase 1 complete.**
- 2026-05-12: Completed Plan 03-01 — replaced stub_scraper with real Craigslist scraper (httpx + selectolax + protego); RobotsCache enforces SCRAP-05 (one-fetch-per-origin, structlog SC#3 audit, fail-open on 5xx); parse_listing extracts lat/lng (D-07, range-validated), price/beds/baths/amenities/posted_date/source_url/source_name; photo URL whitelisted to craigslist.org/craigslistimages.org (T-03-05); SCRAPER_MAX_LISTINGS clamped to ≤30 (T-03-06); CreateJobBody now type-validates Phase 2 chips/global_flex (Pitfall 9, chip persistence deferred to Phase 4). +10 backend tests (17 total). SCRAP-02 + SCRAP-05 marked complete.

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
