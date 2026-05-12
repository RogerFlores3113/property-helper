---
phase: 04-llm-extraction-multi-source
plan: 03
subsystem: coordinator+fanout+rate-limit-wiring
tags: [coordinator, fan-out, arq, redis-counter, rate-limit-wiring, craigslist-rename, tdd-green]
requires:
  - Plan 04-01 (RED scaffold for test_coordinator.py, Settings.anthropic_api_key)
  - Plan 04-02 (acquire_domain_slot async context manager from app.workers.rate_limit)
provides:
  - SCRAP-03 GREEN (coordinator fan-out, completion counter, partial vs full failure, idempotent terminal flip)
  - SCRAP-04 GREEN wired into Craigslist (every fetch via acquire_domain_slot; inline jitter removed)
  - app.workers.coordinator.run_search_coordinator(ctx, job_id) — ARQ entrypoint
  - app.workers.coordinator.mark_done(redis, db, job_id, *, failed) — sub-task completion hook
  - app.workers.coordinator.ENABLED_SOURCES = ["craigslist"]   # Plan 04 appends "apartments"
  - app.workers.scrapers.craigslist.run_search_craigslist (renamed from run_search)
affects:
  - backend/app/workers/coordinator.py (new)
  - backend/app/workers/scrapers/craigslist.py (rename + rate-limit wrapping + mark_done; no direct status writes)
  - backend/app/workers/settings.py (WorkerSettings.functions flipped to [coordinator, craigslist])
  - backend/app/routes/jobs.py (POST enqueues run_search_coordinator)
  - backend/tests/test_coordinator.py (RED scaffold → 6 GREEN behaviors)
  - backend/tests/test_craigslist_scraper_integration.py (rewired to new name + arq_redis + counter priming; +4 new behaviors)
  - backend/tests/test_jobs_api.py (assertion flipped to run_search_coordinator; +1 dedicated test)
tech-stack:
  added: []
  patterns:
    - "Redis-based per-job completion counters (expected/completed/failed:{job_id}) with 1h TTL (Pitfall 8)"
    - "Idempotent terminal flip: UPDATE ... WHERE id=$1 AND status='running' so stale calls are no-ops"
    - "Partial-failure semantics (D-16): job is 'failed' only when failed_n >= expected_n; one success keeps it 'completed'"
    - "Sub-task → mark_done is the only writer of terminal search_jobs.status (D-15 — separation of concerns)"
    - "Per-domain rate limit via `async with acquire_domain_slot(ctx['redis'], url):` around every client.get"
key-files:
  created:
    - backend/app/workers/coordinator.py
    - .planning/phases/04-llm-extraction-multi-source/04-03-SUMMARY.md
  modified:
    - backend/app/workers/scrapers/craigslist.py
    - backend/app/workers/settings.py
    - backend/app/routes/jobs.py
    - backend/tests/test_coordinator.py
    - backend/tests/test_craigslist_scraper_integration.py
    - backend/tests/test_jobs_api.py
decisions:
  - "Replaced the Plan 01 RED scaffold for test_coordinator.py wholesale per Plan 04-03 <action>. The scaffold's design used non-existent search_jobs columns (expected, completed_n, failed_n) and a different mark_done signature (ctx, not redis/db); the plan explicitly redefines the surface around Redis counters with 1h TTL."
  - "Used `async with acquire_domain_slot(...)` (context-manager) — consistent with Plan 02's deviation note. The plan's <action> says 'await acquire_domain_slot(...)' as plain syntax but the implemented surface from Plan 02 ships as `@asynccontextmanager`; the observable contract is identical and the Plan-02 SUMMARY explicitly documents this."
  - "Wrapped both the search-page fetch AND each detail-page fetch — six acquire_domain_slot occurrences total in craigslist.py (the plan minimum is ≥2)."
  - "Removed inline `import asyncio`/`import random` since the only consumer was the now-deleted jitter sleep. acquire_domain_slot owns all per-domain throttling now."
  - "ENABLED_SOURCES kept as a `list[str]` (not tuple) so Plan 04 can `ENABLED_SOURCES.append('apartments')` cleanly or replace the literal in place — matches plan must_have."
metrics:
  duration_minutes: ~9
  tasks_completed: 2
  files_created: 2
  files_modified: 6
  tests_added_or_promoted: 11   # 6 coordinator + 4 craigslist surface + 1 jobs route
completed: 2026-05-11
---

# Phase 4 Plan 03: Parallel Coordinator + Craigslist Rate-Limit Wiring Summary

Coordinator fan-out (SCRAP-03) and per-domain rate-limit serialization (SCRAP-04) now drive the working Craigslist scraper end-to-end. POST /api/jobs enqueues `run_search_coordinator`, which primes three Redis counters with 1h TTL and dispatches one ARQ sub-task per source in `ENABLED_SOURCES = ["craigslist"]`. The sub-task (`run_search_craigslist`, renamed from `run_search`) wraps every outbound HTTP fetch with `acquire_domain_slot` and never writes terminal status itself — `mark_done` owns the flip from `'running'` to `'completed'`/`'failed'` via an idempotent guarded UPDATE.

## Tasks Completed

| Task | Name                                                                                                                | Commit  | Files                                                                                                                                                       |
| ---- | ------------------------------------------------------------------------------------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | coordinator.py (run_search_coordinator + mark_done) — 6 GREEN tests covering fan-out, completion, partial/all-failed, TTLs, idempotency | e32cdbb | backend/app/workers/coordinator.py, backend/tests/test_coordinator.py                                                                                       |
| 2    | Rename Craigslist scraper; wrap fetches with acquire_domain_slot; call mark_done; flip WorkerSettings + POST route  | d4c992b | backend/app/workers/scrapers/craigslist.py, backend/app/workers/settings.py, backend/app/routes/jobs.py, backend/tests/test_craigslist_scraper_integration.py, backend/tests/test_jobs_api.py |

## Behavior Verified

### Coordinator (6 tests, all GREEN)

- `test_fanout_enqueues_all_sources` — coordinator flips `search_jobs.status='running'`, primes `expected:{job_id}=len(ENABLED_SOURCES)`, `completed:{job_id}=0`, `failed:{job_id}=0`, and enqueues exactly one `run_search_{src}` job per source (set equality, no duplicates, no extras).
- `test_mark_done_completes_on_last` — with `expected=2`, the first `mark_done(failed=False)` leaves status `'running'`; the second flips to `'completed'` and stamps `completed_at`.
- `test_partial_failure` — with `expected=2`, one `mark_done(failed=True)` + one `mark_done(failed=False)` → status `'completed'`, `failed:{job_id}=1` (D-16 partial-failure rule).
- `test_all_failed` — two `mark_done(failed=True)` calls → status `'failed'`.
- `test_counter_ttl_set` — after `run_search_coordinator`, all three counter keys have `ttl > 0` (Pitfall 8); after a `mark_done` call, the `completed:` key TTL is refreshed.
- `test_status_not_double_flipped` — a third `mark_done` call after status already flipped to `'completed'` is a no-op (idempotency guard via `WHERE id=$2 AND status='running'`).

### Craigslist (Plan 04-03 surface — 4 new tests + 3 carry-over integration tests)

- `test_craigslist_function_renamed` — `run_search_craigslist` importable; old `run_search` raises `AttributeError`.
- `test_craigslist_calls_acquire_domain_slot_per_fetch` — recorder captures ≥2 slot acquires (search + ≥1 detail), all on craigslist hostnames.
- `test_craigslist_calls_mark_done_on_success` — recorder shows exactly one `mark_done(failed=False)` on a normal run.
- `test_craigslist_calls_mark_done_on_exception` — induced `RuntimeError` → `mark_done(failed=True)` recorded and exception propagates.
- `test_craigslist_does_not_write_status_completed` — source file contains zero literal `status='completed'` SQL (D-15).
- `test_run_search_inserts_real_listing` / `test_robots_disallow_skips_url` / `test_daily_spend_row_written` — pre-existing integration tests rewired to the new function name + arq_redis fixture; all still GREEN.

### Jobs API (1 new + existing)

- `test_jobs_post_enqueues_coordinator` — asserts the recorded enqueue target string is `"run_search_coordinator"`.
- `test_fire_and_forget` — pre-existing test updated to assert the same.

## Test Results

```
$ uv run pytest -x --ignore=tests/test_apartments_scraper.py --ignore=tests/test_apartments_parser.py
50 passed in 40.25s
```

Apartments scaffolds (Plan 04-04 territory) remain RED by design. WorkerSettings boot smoke:

```
$ uv run python -c "from app.workers.settings import WorkerSettings; print([f.__name__ for f in WorkerSettings.functions])"
['run_search_coordinator', 'run_search_craigslist']
```

## Deviations from Plan

### Auto-fixed / In-scope adjustments

**1. [Rule 3 — Blocking issue] `async with acquire_domain_slot(...)` instead of plain `await`**
- **Found during:** Task 2 implementation.
- **Issue:** Plan 04-03's `<action>` writes the rate-limit wrap as `await acquire_domain_slot(ctx["redis"], <url>)` placed immediately before each `client.get(...)`. But `acquire_domain_slot` (delivered by Plan 04-02) is implemented as `@asynccontextmanager` — a plain `await` on it returns the context-manager object, not the slot. The Plan 04-02 SUMMARY documents this trade-off and the public observable contract is identical.
- **Fix:** Use `async with acquire_domain_slot(redis, url): await client.get(url)` at every fetch site. Acceptance grep `acquire_domain_slot` still matches (≥2 hits; we ship 6).
- **Files modified:** `backend/app/workers/scrapers/craigslist.py`
- **Commit:** `d4c992b`

**2. [Rule 3 — Blocking issue] Plan 01 RED scaffold for test_coordinator.py replaced wholesale**
- **Found during:** Task 1.
- **Issue:** The Plan 01 scaffold (`66f79ee`) wrote tests assuming `search_jobs` had `expected`, `completed_n`, `failed_n` columns AND that `mark_done(ctx, job_id, failed=...)` took an ARQ context. The actual schema (`migrations/0001_init.sql`) has none of those columns, and the Plan 04-03 `<must_haves>` redefine `mark_done(redis, db, job_id, *, failed)` with **Redis-based** counters. The scaffold could not be made GREEN as written.
- **Fix:** Plan 04-03 explicitly says "Replace the Plan 01 RED scaffold backend/tests/test_coordinator.py with the GREEN suite covering every behavior bullet." Did that — 6 new tests covering exactly the 6 behavior bullets in the plan.
- **Commit:** `e32cdbb`

**3. [Rule 2 — Critical functionality] Remove unused `import asyncio` and `import random` from craigslist.py**
- **Found during:** Task 2.
- **Issue:** Both modules were imported solely for the inline jitter sleep. After replacing the jitter with `acquire_domain_slot`, both imports became dead. Leaving them in would (a) be misleading for reviewers and (b) lint as unused-import.
- **Fix:** Removed both imports from `craigslist.py`. The test fixture `test_craigslist_scraper_integration.py` no longer monkeypatches `cl.asyncio.sleep` either (it was a no-op because there is no sleep to patch).
- **Commit:** `d4c992b`

**4. [Naming hygiene] Docstring tweak so D-15 grep test passes**
- **Found during:** Task 2 first test run.
- **Issue:** The `test_craigslist_does_not_write_status_completed` grep test asserts the source file contains zero literal `status='completed'` strings. The function's docstring previously included the literal `status='completed'` while *explaining* that mark_done owns the flip — the grep is intentionally strict and caught the docstring.
- **Fix:** Reworded the docstring to describe terminal status without the literal SQL fragment. Behavior unchanged.
- **Commit:** `d4c992b`

### Authentication Gates

None.

## Threat Surface Notes

All mitigations from the plan's `<threat_model>` land in code:

| Threat ID                                | Status                                                                                                                                       |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| T-04-06 (Redis counter key tampering)    | mitigated — keys are `{expected,completed,failed}:{job_id}` where `job_id` is a server-issued UUID; never reflects user input. TTL `ex=3600`. |
| Status race / double-flip                | mitigated — UPDATE guarded by `WHERE id=$1 AND status='running'`; verified by `test_status_not_double_flipped` (third call is a no-op).      |
| Stuck-running on coordinator early-return | mitigated — coordinator does NOT own terminal status (Pitfall 5); sub-tasks drive completion via `mark_done`. Counter TTL bounds Redis growth. |
| Inline jitter race across workers (SCRAP-04 violation) | mitigated — `random.uniform(0.5, 1.5)` literal removed; every craigslist fetch path now goes through `acquire_domain_slot`. Six occurrences in source; zero `random.uniform(0.5, 1.5)` literals. |

No new threat surface introduced.

## Known Stubs

- `ENABLED_SOURCES = ["craigslist"]` — intentionally single-source for Plan 04-03 (purpose: validate the fan-out plumbing against a known-good source before Plan 04-04 plugs in the Apartments.com path). Plan 04-04 will append `"apartments"` to this list and register `run_search_apartments` in `WorkerSettings.functions`.
- No code stubs that flow to the UI; no placeholder data.

## TDD Gate Compliance

Both tasks were `tdd="true"`:

- **Task 1 (e32cdbb)** — Plan 01 RED scaffold for `test_coordinator.py` was already collection-ERROR (`ModuleNotFoundError: No module named 'app.workers.coordinator'`). This commit lands `coordinator.py` AND replaces the scaffold with 6 GREEN tests in a single landing per the plan's `<action>` "Replace the Plan 01 RED scaffold ... with the GREEN suite." `feat(...)` commit matches plan-level TDD pattern (RED was the import-error state in Plan 01).
- **Task 2 (d4c992b)** — production changes + test rewires in a single commit; new tests (`test_craigslist_function_renamed`, `test_craigslist_calls_acquire_domain_slot_per_fetch`, `test_craigslist_calls_mark_done_on_success`, `test_craigslist_calls_mark_done_on_exception`, `test_craigslist_does_not_write_status_completed`, `test_jobs_post_enqueues_coordinator`) verified locally GREEN. Per the plan's `<action>` "Update existing ... rewire any imports of `run_search` to `run_search_craigslist`; ... add the `acquire_domain_slot` recorder test" — code + tests land together because the rename couples them.

## Self-Check: PASSED

Files verified to exist:

- `backend/app/workers/coordinator.py` — FOUND
- `backend/app/workers/scrapers/craigslist.py` — FOUND (run_search_craigslist defined; run_search absent)
- `backend/app/workers/settings.py` — FOUND (functions=[run_search_coordinator, run_search_craigslist])
- `backend/app/routes/jobs.py` — FOUND (enqueue target = run_search_coordinator)
- `backend/tests/test_coordinator.py` — FOUND (6 GREEN tests)
- `backend/tests/test_craigslist_scraper_integration.py` — FOUND (rewired + 4 new tests)
- `backend/tests/test_jobs_api.py` — FOUND (+1 new test)

Commits verified on `worktree-agent-a86e9fe5d600391a1`:

- `e32cdbb` — FOUND (Task 1)
- `d4c992b` — FOUND (Task 2)

Acceptance grep checks (all green):

- `grep -n "async def run_search_craigslist" backend/app/workers/scrapers/craigslist.py` → 1 hit
- `grep -nE "^async def run_search\b" backend/app/workers/scrapers/craigslist.py` → 0 hits
- `grep -c "acquire_domain_slot" backend/app/workers/scrapers/craigslist.py` → 6 (≥2 required)
- `grep -c "random.uniform(0.5, 1.5)" backend/app/workers/scrapers/craigslist.py` → 0
- `grep -cE "status\s*=\s*'completed'" backend/app/workers/scrapers/craigslist.py` → 0
- `grep -c "mark_done" backend/app/workers/scrapers/craigslist.py` → 13 (≥2 required)
- `grep -n 'enqueue_job("run_search_coordinator"' backend/app/routes/jobs.py` → 1 hit
- `grep -n "run_search_coordinator" backend/app/workers/settings.py` → ≥1 hit; `grep -n "run_search_craigslist" backend/app/workers/settings.py` → ≥1 hit; bare `run_search` (not `run_search_`) → 0 hits
- `grep -rnE "\brun_search\b" backend/app/ | grep -v "run_search_"` → 0 hits (no stale references in the app/ tree)
