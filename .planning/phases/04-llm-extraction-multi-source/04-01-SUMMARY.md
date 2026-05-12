---
phase: 04-llm-extraction-multi-source
plan: 01
subsystem: security-baseline+test-scaffolding
tags: [security, code-review, debt, wave-0, scaffolding, tdd-red]
requires:
  - Phase 3 complete (Craigslist scraper, safeUrl.ts apex-allowlist pattern)
provides:
  - CR-01 closed (POST /api/jobs query length cap 1–512)
  - CR-02 closed (craigslistimages.org apex + dotted-suffix allowlist)
  - isAllowedApartmentsUrl exported for Plan 04 source-link rendering
  - Settings.anthropic_api_key required field (D-09 / ASVS V14)
  - backend/.env.example with ANTHROPIC_API_KEY placeholder
  - 6 Wave-0 RED scaffolds targeting Plans 02/03/04 modules
affects:
  - backend/app/routes/jobs.py (CreateJobBody.query Field bounds)
  - backend/app/settings.py (anthropic_api_key + env_file test hook)
  - backend/.env.example (new file mirroring backend section)
  - .env.example (root canonical contract — appended ANTHROPIC_API_KEY)
  - frontend/app/components/safeUrl.ts (CR-02 fix + new helper)
tech-stack:
  added: []
  patterns:
    - "pydantic Field(..., min_length=1, max_length=512) on CreateJobBody.query"
    - "BaseSettings env_file test-disable hook via PH_DISABLE_ENV_FILE env"
    - "Apex-equality + dotted-suffix host allowlist (no bare endsWith)"
    - "RED test scaffold pattern: import target module before implementation exists"
key-files:
  created:
    - backend/.env.example
    - backend/tests/test_settings.py
    - backend/tests/test_llm_extract.py
    - backend/tests/test_prefilter.py
    - backend/tests/test_rate_limit.py
    - backend/tests/test_coordinator.py
    - backend/tests/test_apartments_parser.py
    - backend/tests/test_apartments_scraper.py
    - backend/tests/fixtures/apartments/search.html
    - frontend/__tests__/safeUrl.test.ts
  modified:
    - backend/app/routes/jobs.py
    - backend/app/settings.py
    - backend/tests/test_jobs_api.py
    - .env.example
    - frontend/app/components/safeUrl.ts
decisions:
  - "Settings.env_file becomes None when PH_DISABLE_ENV_FILE=1 so the fail-fast Anthropic key test can verify ValidationError without an on-disk .env masking the missing var."
  - "backend/.env.example created in addition to root .env.example (D-02 canonical contract) — root file also extended with ANTHROPIC_API_KEY to keep contracts consistent."
  - "RED scaffolds import target modules that do not exist; pytest collection ERRORs are the intentional Wave-0 state."
metrics:
  duration_minutes: ~12
  tasks_completed: 3
  files_created: 10
  files_modified: 5
  tests_added: 14
completed: 2026-05-12
---

# Phase 4 Plan 01: Wave-0 Security Baseline + RED Scaffolding Summary

CR-01 (query length cap) and CR-02 (craigslistimages suffix-fool) closed; ANTHROPIC_API_KEY wired into Settings as a required, fail-fast field; six RED test scaffolds in place so Plans 02–04 land test-first.

## Tasks Completed

| Task | Name                                                             | Commit  | Files                                                                                                                                                   |
| ---- | ---------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1    | CR-01 query length cap + Settings.anthropic_api_key + .env.example | 9002444 | backend/app/routes/jobs.py, backend/app/settings.py, backend/.env.example, .env.example, backend/tests/test_jobs_api.py, backend/tests/test_settings.py |
| 2    | CR-02 craigslistimages suffix fix + isAllowedApartmentsUrl       | add5b30 | frontend/app/components/safeUrl.ts, frontend/__tests__/safeUrl.test.ts                                                                                  |
| 3    | Wave-0 RED test scaffolds for Plans 02–04                        | 66f79ee | backend/tests/test_{llm_extract,prefilter,rate_limit,coordinator,apartments_parser,apartments_scraper}.py + backend/tests/fixtures/apartments/search.html |

## Behavior Verified

- POST /api/jobs returns 200 for `query="x"*512` and 422 for `query="x"*513` (T-04-05).
- POST /api/jobs returns 422 for empty query.
- `Settings()` raises pydantic.ValidationError when ANTHROPIC_API_KEY is unset (D-09 / ASVS V14).
- `isAllowedCraigslistImage('https://evilcraigslistimages.org/...')` → false (CR-02 regression).
- `isAllowedCraigslistImage('https://craigslistimages.org/...')` → true (apex apex match).
- `isAllowedCraigslistImage('https://images.craigslistimages.org/...')` → true (dotted suffix).
- `isAllowedApartmentsUrl` accepts apex + `*.apartments.com`; rejects `evilapartments.com`, javascript:, and unparseable input.
- Six new test modules error on import with ModuleNotFoundError targeting `app.workers.scrapers.llm_extract`, `app.workers.scrapers.prefilter`, `app.workers.rate_limit`, `app.workers.coordinator`, `app.workers.scrapers.apartments` (RED — intentional).

## Test Results

- Backend: 20 passed (previously 17 — added 2 query-length + 1 settings).
- Frontend: 39 passed (previously 28 — added 11 safeUrl assertions).
- RED scaffolds: 6 files error on collection as designed; existing 20 backend tests still pass when scaffolds are `--ignore`d (verified per acceptance criteria).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Critical Functionality] Test hook for Settings env_file**
- **Found during:** Task 1 RED phase.
- **Issue:** The plan's `test_settings_requires_anthropic_key` design (delete env var, reload module) cannot work as written because `BaseSettings` reads `.env` from disk and on the development machine `backend/.env` contains `ANTHROPIC_API_KEY=...` after we copy it for the rest of the suite.
- **Fix:** Added a single-line `_ENV_FILE = None if os.environ.get("PH_DISABLE_ENV_FILE") == "1" else ".env"` toggle in `backend/app/settings.py`, used by the test to force a clean missing-key state.
- **Files modified:** `backend/app/settings.py`, `backend/tests/test_settings.py`
- **Commit:** `9002444`

**2. [Rule 2 — Critical Functionality] Root .env.example also updated**
- **Found during:** Task 1.
- **Issue:** Plan specifies adding `ANTHROPIC_API_KEY=` to `backend/.env.example`, but the project's canonical env contract per D-02 is the root `.env.example`. Updating only the backend file would leave the canonical contract incomplete.
- **Fix:** Appended `ANTHROPIC_API_KEY=<your-anthropic-api-key>` to the root `.env.example` backend section so both files stay in sync.
- **Files modified:** `.env.example`
- **Commit:** `9002444`

### Authentication Gates

None.

## Threat Surface Notes

All mitigations land where the plan's `<threat_model>` requires:

| Threat ID | Status |
| --------- | ------ |
| T-04-05 (DoS via unbounded query) | mitigated — `Field(min_length=1, max_length=512)` + test coverage |
| T-04-03 (Tampering: craigslistimages bare-suffix) | mitigated — apex eq + dotted suffix |
| T-04-03 (Tampering: apartments host allowlist) | mitigated — apex eq + dotted suffix; rejects javascript: |
| T-04-04 (Info Disclosure: ANTHROPIC_API_KEY) | mitigated — required field, fail-fast import; never serialized by structlog; backend-only Settings (no Next.js bundle leak path) |

No new threat surface introduced.

## Known Stubs

- `backend/tests/fixtures/apartments/search.html` is a **placeholder** fixture sized so the `test_prefilter_reduces_token_count` assertion can exercise the ≤20% compression ratio meaningfully. Plan 04-04 will replace it with a real Apartments.com search capture.

## TDD Gate Compliance

This plan was written as `type: execute` (not `type: tdd`), but Tasks 1 and 2 carried `tdd="true"`. Per-task gates:

- Task 1 RED→GREEN performed inline (single commit `9002444`) — new tests (`test_query_max_length`, `test_query_min_length`, `test_settings_requires_anthropic_key`) were written and verified RED before the Field/Settings edits made them GREEN. Combined commit chosen because the plan's `<action>` block instructs landing tests and code together for this hardening task.
- Task 2 RED→GREEN performed inline (single commit `add5b30`) — `frontend/__tests__/safeUrl.test.ts` written and verified RED (7 failures) before the safeUrl.ts edits flipped all 11 assertions GREEN.
- Task 3 is pure RED scaffolding by design — `test(04-01): ...` commit `66f79ee` matches the test-only convention.

## Self-Check: PASSED

Verified files exist:

- `backend/app/routes/jobs.py` — FOUND
- `backend/app/settings.py` — FOUND
- `backend/.env.example` — FOUND
- `.env.example` — FOUND
- `frontend/app/components/safeUrl.ts` — FOUND
- `frontend/__tests__/safeUrl.test.ts` — FOUND
- `backend/tests/test_settings.py` — FOUND
- `backend/tests/test_llm_extract.py` — FOUND
- `backend/tests/test_prefilter.py` — FOUND
- `backend/tests/test_rate_limit.py` — FOUND
- `backend/tests/test_coordinator.py` — FOUND
- `backend/tests/test_apartments_parser.py` — FOUND
- `backend/tests/test_apartments_scraper.py` — FOUND
- `backend/tests/fixtures/apartments/search.html` — FOUND

Verified commits exist on `worktree-agent-a2f815c0f2fd45111`:

- `9002444` — FOUND (Task 1)
- `add5b30` — FOUND (Task 2)
- `66f79ee` — FOUND (Task 3)
