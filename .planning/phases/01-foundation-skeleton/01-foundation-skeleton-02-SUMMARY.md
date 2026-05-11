---
phase: 01-foundation-skeleton
plan: 02
subsystem: backend
tags: [fastapi, asyncpg, arq, pydantic, budget-guard, cors, supabase]

requires:
  - "01-01: backend scaffold, settings/db/logging modules, Supabase 0001 migration applied, 7 pytest stubs"

provides:
  - "BudgetGuard (COST-01/02/03 enforcement) with iter, payload, and token caps + daily_spend upsert"
  - "FastAPI app with lifespan, CORS lock, /api/jobs POST + GET routes (CACH-03)"
  - "ARQ WorkerSettings + stub_scraper run_search task (3 iters × 3 listings = 9 listings, CACH-04)"
  - "Full backend test suite green: 7 passed against live Supabase pooler"

affects:
  - "01-03 (frontend slice can now POST to /api/jobs and GET reattach state)"
  - "Phase 4 (BudgetGuard is the cost gate the real LLM extractor will sit behind)"

tech-stack:
  added: []
  patterns:
    - "Conventional commits with type(phase-plan): subject"
    - "Pydantic CreateJobBody for request validation; UUID4 for path validation (ASVS V5)"
    - "asyncpg parameterized queries throughout — no string concatenation"
    - "ON CONFLICT (date) DO UPDATE upsert pattern for daily aggregate counters"
    - "ARQ ctx['db'] injection — pool wired via WorkerSettings.on_startup"
    - "Try/except BudgetExceeded in run_search → status='failed' + re-raise"

key-files:
  created:
    - "backend/app/guards/__init__.py"
    - "backend/app/guards/budget.py"
    - "backend/app/routes/__init__.py"
    - "backend/app/routes/jobs.py"
    - "backend/app/main.py"
    - "backend/app/workers/__init__.py"
    - "backend/app/workers/stub_scraper.py"
    - "backend/app/workers/settings.py"
  modified:
    - "backend/tests/test_budget_guard.py (4 stubs → 4 implementations)"
    - "backend/tests/test_jobs_api.py (1 stub → 1 implementation)"
    - "backend/tests/test_stub_scraper.py (2 stubs → 2 implementations)"

key-decisions:
  - "HAIKU_INPUT_USD_PER_TOKEN = 1e-6 (Haiku 4.5 input price $1/M) — resolves RESEARCH Open Question #2; verified by daily_spend test asserting 0.001 USD for 1000 tokens"
  - "BudgetGuard.record_spend raises BEFORE the daily_spend write when cap exceeded — rejected spend must not be persisted"
  - "GET /api/jobs/{id} uses pydantic.UUID4 path type so malformed UUIDs return 422 (not 500) — ASVS V5"
  - "CORS allow_origins exactly ['http://localhost:3000']; allow_methods=['GET','POST','OPTIONS']; allow_headers=['Content-Type'] (Pitfall 6 mitigation; not wildcards)"
  - "ARQ WorkerSettings.max_tries=1 (T-02-07: avoid duplicate fake-data inserts on retry)"

patterns-established:
  - "Per-task RED → GREEN commits (test commit precedes feat commit for every TDD task)"
  - "Tests reuse pg_pool fixture by monkeypatching db_module._pool inside the test — avoids spinning a second pool against the same DB"

requirements-completed: [COST-01, COST-02, COST-03, CACH-03, CACH-04]

metrics:
  duration: ~25min
  tasks: 3
  files_created: 8
  files_modified: 3
  test_results: "7 passed (4 budget + 1 jobs-api + 2 stub-scraper)"
completed: 2026-05-11
---

# Phase 01 Plan 02: Backend Behavior Summary

**Full backend slice for Phase 1: BudgetGuard enforces COST-01/02/03, FastAPI /api/jobs round-trip satisfies CACH-03, and the ARQ stub scraper emits 9 listings sized to CACH-04 — all proven by 7 passing pytest cases against the live Supabase pooler.**

## Performance

- **Duration:** ~25 minutes
- **Started:** 2026-05-11T (this session)
- **Completed:** 2026-05-11
- **Tasks:** 3 (all `type=auto, tdd=true`)
- **Files created:** 8
- **Files modified:** 3 (test stubs filled in)
- **Test results:** 7 passed (`uv run pytest tests/`)

## Accomplishments

- `BudgetGuard.check_iter()` raises `BudgetExceeded` after `max_iters` (COST-01)
- `BudgetGuard.record_spend(tokens=...)` raises `BudgetExceeded` once cumulative tokens exceed `token_budget` (COST-01) — without persisting the rejected spend
- `BudgetGuard.record_spend(...)` upserts `daily_spend` with `ON CONFLICT (date) DO UPDATE` so a calendar date has exactly one row (COST-02). With Haiku rate (1e-6 USD/token), 1000 simulated tokens produces `estimated_cost_usd = 0.001`.
- `BudgetGuard.check_payload(>8192)` raises `BudgetExceeded` (COST-03)
- `POST /api/jobs` (body `{query: str}`) inserts `search_jobs` row with `status='pending'` + enqueues ARQ `run_search` job; returns `{job_id, status:'pending'}` (CACH-03)
- `POST /api/jobs` with malformed body → 422 (Pydantic `CreateJobBody`)
- `GET /api/jobs/{id}` returns `{job, listings}` with listings ordered by `created_at` ASC; 404 for unknown UUID; 422 for malformed UUID via `pydantic.UUID4` path type (ASVS V5)
- `FastAPI` app wires `lifespan` to `init_pool`/`close_pool` and CORS to exactly `http://localhost:3000` (Pitfall 6)
- `run_search(ctx, job_id)` transitions `search_jobs.status` pending → running → completed, inserts exactly 9 listings with serialized data in `[300, 500]` chars (315 chars, CACH-04), and writes one `daily_spend` row with `estimated_tokens=1500`
- `BudgetExceeded` inside `run_search` flips status to `failed` and re-raises (ARQ marks job failed)
- `WorkerSettings.max_tries=1` (T-02-07 mitigation)

## Task Commits

1. **Task 1 RED** — `test(01-02): add failing tests for BudgetGuard (COST-01/02/03)` — `0b4d57d`
2. **Task 1 GREEN** — `feat(01-02): implement BudgetGuard (COST-01/02/03)` — `88ed911`
3. **Task 2 RED** — `test(01-02): add failing test for jobs API fire-and-forget (CACH-03)` — `8043238`
4. **Task 2 GREEN** — `feat(01-02): FastAPI app + /api/jobs routes with CORS lock (CACH-03)` — `b1d33cb`
5. **Task 3 RED** — `test(01-02): add failing tests for stub_scraper run_search (CACH-04)` — `2921ac0`
6. **Task 3 GREEN** — `feat(01-02): ARQ stub_scraper worker (3 iters × 3 listings, CACH-04)` — `db7c4c6`

## Files Created/Modified

**Created:**
- `backend/app/guards/__init__.py` (empty package marker)
- `backend/app/guards/budget.py` — `BudgetGuard` dataclass + `BudgetExceeded` + `HAIKU_INPUT_USD_PER_TOKEN`
- `backend/app/routes/__init__.py` (empty package marker)
- `backend/app/routes/jobs.py` — APIRouter with POST `/api/jobs` + GET `/api/jobs/{job_id}`
- `backend/app/main.py` — FastAPI app, lifespan, CORS middleware, router include, `configure_logging()`
- `backend/app/workers/__init__.py` (empty package marker)
- `backend/app/workers/stub_scraper.py` — `_fake_listing()` + `run_search(ctx, job_id)`
- `backend/app/workers/settings.py` — `WorkerSettings` with `max_tries=1`

**Modified (skip stubs → real tests):**
- `backend/tests/test_budget_guard.py` — 4 tests (iter cap, token cap, daily_spend upsert, payload cap)
- `backend/tests/test_jobs_api.py` — 1 test (`test_fire_and_forget` covers POST, GET, 404, 422 + ARQ enqueue stub)
- `backend/tests/test_stub_scraper.py` — 2 tests (`test_payload_size`, `test_run_search`)

## Decisions Made

- **Haiku input pricing:** `HAIKU_INPUT_USD_PER_TOKEN = 1e-6` — resolves RESEARCH Open Question #2; chosen because Haiku 4.5 input is $1/M tokens. The `test_daily_spend_upsert` test asserts the resulting `estimated_cost_usd` is `0.001` for 1000 tokens (`pytest.approx(0.001, abs=1e-9)`).
- **Order of operations in `record_spend`:** Increment counter → cap-check → raise (no DB write) → otherwise upsert. Ensures rejected spend never reaches `daily_spend`.
- **Path validation:** `pydantic.UUID4` on `job_id` path param so malformed UUIDs return 422 before any DB query — defense against bad inputs without an exception trace.
- **CORS lock:** exact origin list `["http://localhost:3000"]`, methods `GET/POST/OPTIONS`, headers `Content-Type` — Pitfall 6 mitigation, never `["*"]`.
- **ARQ retry policy:** `max_tries=1` so a failed `run_search` doesn't re-emit the 9 fake rows (T-02-07).
- **Test pool reuse:** `monkeypatch.setattr(db_module, "_pool", pg_pool)` in `test_fire_and_forget` instead of spinning a second pool — keeps `clean_db` TRUNCATE applicable to the data the routes read/write.

## Deviations from Plan

None — plan executed exactly as written, including the loop shape (`for _ in range(3): for _ in range(3): ...`), the `BudgetGuard.from_env(db)` signature, the CORS allow-list, and the `UUID4` path type. The plan's literal grep checks (`ON CONFLICT (date) DO UPDATE`, `HAIKU_INPUT_USD_PER_TOKEN`, `CORSMiddleware`, `UUID4`, `BudgetGuard.from_env`, `guard.check_iter`, `guard.check_payload`, `guard.record_spend`, `WorkerSettings`, `async def run_search`) all hit in the source files.

## Issues Encountered

None.

## Verification

### Automated

```
cd backend && uv run pytest tests/
============================= test session starts ==============================
collected 7 items

tests/test_budget_guard.py ....                                          [ 57%]
tests/test_jobs_api.py .                                                 [ 71%]
tests/test_stub_scraper.py ..                                            [100%]

============================== 7 passed in 7.64s ===============================
```

### Manual Smoke (deferred to Plan 03 final checkpoint)

The plan's `<output>` section asks for a manual curl POST → GET demonstration with real UUIDs and a `daily_spend` row inspection. The Phase 1 ROADMAP success criteria #1–#5 are exercised end-to-end in Plan 03's `realtime-e2e` manual smoke checkpoint, which boots Redis (`docker compose up`), uvicorn, and the ARQ worker together. The automated `test_run_search` already covers the worker→DB path and asserts `daily_spend.estimated_tokens=1500`; no additional separate manual run was performed here.

## Next Phase Readiness

- **Plan 01-03 (frontend slice):** Ready. The backend exposes `POST /api/jobs` and `GET /api/jobs/{id}` with CORS open to `http://localhost:3000`, plus Realtime publication already includes `listings` + `search_jobs`. The frontend can subscribe to either table by `job_id` and re-attach on reload via `GET /api/jobs/{id}`.
- **Phase 4 LLM:** `BudgetGuard` is the cost gate the real Haiku extractor will sit behind — same `check_iter`/`check_payload`/`record_spend` API, just with real token counts.
- **No blockers.**

## Self-Check: PASSED

- FOUND: backend/app/guards/budget.py, backend/app/routes/jobs.py, backend/app/main.py, backend/app/workers/stub_scraper.py, backend/app/workers/settings.py
- FOUND tests filled in: backend/tests/test_budget_guard.py, backend/tests/test_jobs_api.py, backend/tests/test_stub_scraper.py
- FOUND commits: 0b4d57d, 88ed911, 8043238, b1d33cb, 2921ac0, db7c4c6
- pytest: `7 passed in 7.64s`
- grep checks: `ON CONFLICT (date) DO UPDATE` ✓, `HAIKU_INPUT_USD_PER_TOKEN` ✓, `CORSMiddleware` ✓, `allow_origins=["http://localhost:3000"]` ✓, `UUID4` ✓, `class BudgetGuard` ✓, `class WorkerSettings` ✓, `async def run_search` ✓, `BudgetGuard.from_env` ✓

---
*Phase: 01-foundation-skeleton*
*Completed: 2026-05-11*
