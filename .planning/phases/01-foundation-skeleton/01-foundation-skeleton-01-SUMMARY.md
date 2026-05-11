---
phase: 01-foundation-skeleton
plan: 01
subsystem: infra
tags: [docker, redis, fastapi, uv, asyncpg, pydantic-settings, structlog, supabase, postgis, nextjs, tailwind, supabase-js, pytest]

requires: []
provides:
  - Repo-root scaffolding (docker-compose Redis 7-alpine, .env.example contract, extended .gitignore)
  - Backend Python project (uv + pyproject.toml + uv.lock, pytest with asyncio_mode=auto)
  - Backend settings/db/logging modules (pydantic-settings, asyncpg pool with statement_cache_size=0, structlog JSON)
  - Supabase migration 0001_init.sql (search_jobs, listings, daily_spend, supabase_realtime publication on both listings + search_jobs)
  - Pytest scaffold (conftest with pg_pool/clean_db/arq_redis fixtures; 7 skip-marked stubs matching VALIDATION.md)
  - Frontend Next.js 15 + Tailwind 3.4 + @supabase/supabase-js client singleton
  - Applied schema in Supabase dev project (ebxglaywpuynshplrtys) — listings + search_jobs in supabase_realtime
affects: [01-02 backend behavior, 01-03 frontend slice, all downstream phases]

tech-stack:
  added:
    - "Backend: fastapi>=0.136, uvicorn[standard]>=0.46, arq>=0.28, asyncpg>=0.31, pydantic>=2.10, pydantic-settings>=2.14, structlog>=25.5, python-dotenv>=1.0"
    - "Backend dev: pytest>=8, pytest-asyncio>=0.24, httpx>=0.28, fakeredis>=2.26, ruff>=0.8"
    - "Frontend: next ^15, react ^18, @supabase/supabase-js ^2.105, tailwindcss ^3.4, typescript ^5"
    - "Infra: redis:7-alpine via docker-compose"
  patterns:
    - "Single .env.example as canonical env-var contract; backend/.env + frontend/.env.local gitignored"
    - "asyncpg pool with statement_cache_size=0 for Supabase transaction pooler (port 6543)"
    - "structlog JSON renderer with ISO timestamp + log level"
    - "Migration idempotency via IF NOT EXISTS + DO $$ guards for ALTER PUBLICATION"
    - "Realtime publication includes both search_jobs (job-status changes) and listings (incremental results)"

key-files:
  created:
    - "docker-compose.yml"
    - ".env.example"
    - ".gitignore (extended)"
    - "backend/pyproject.toml, backend/uv.lock"
    - "backend/app/__init__.py, backend/app/settings.py, backend/app/db.py, backend/app/logging.py"
    - "backend/migrations/0001_init.sql"
    - "backend/tests/__init__.py, backend/tests/conftest.py"
    - "backend/tests/test_budget_guard.py, backend/tests/test_stub_scraper.py, backend/tests/test_jobs_api.py"
    - "frontend/package.json, frontend/tsconfig.json, frontend/tailwind.config.ts, frontend/next.config.js, frontend/postcss.config.js"
    - "frontend/app/layout.tsx, frontend/app/page.tsx, frontend/app/globals.css"
    - "frontend/lib/supabase.ts"
    - "backend/.env (gitignored, populated with live Supabase creds)"
    - "frontend/.env.local (gitignored, populated with NEXT_PUBLIC_* + API_URL)"
  modified: []

key-decisions:
  - "Supabase dev project provisioned at ref ebxglaywpuynshplrtys (us-east-2 pooler) per D-04"
  - "supabase_realtime publication includes both `listings` and `search_jobs` per UI-SPEC interaction contract"
  - "asyncpg pool sized min=1/max=5 with statement_cache_size=0 (Pitfall 2 mitigation for pooler)"
  - "Pinned Next.js 15.x per CLAUDE.md (NOT 16) and @supabase/supabase-js ^2.105"
  - "pgcrypto extension enabled up front for gen_random_uuid() (Pitfall 8)"
  - "RLS deferred to Phase 6 with explicit TODO(Phase 6) marker in migration"

patterns-established:
  - "Atomic per-task git commits following conventional-commit (type(phase-plan): subject)"
  - "Skip-marked test scaffold matching VALIDATION.md row-for-row so Plan 02 just removes pytestmark"
  - "Single .env.example contract with section dividers — copied selectively into backend/.env and frontend/.env.local"

requirements-completed: [COST-01, COST-02, COST-03, CACH-03, CACH-04]

duration: ~70min (across two sessions, including human checkpoints)
completed: 2026-05-11
---

# Phase 01 Plan 01: Foundation Skeleton Summary

**Full monorepo scaffold + Supabase 0001 migration applied to live dev project, with asyncpg pool, structlog, pytest 7-stub scaffold, and Next.js 15 + supabase-js client all green.**

## Performance

- **Duration:** ~70 minutes (across two sessions including human checkpoints Task 0 and Task 7)
- **Started:** 2026-05-10T23:53Z
- **Completed:** 2026-05-11T06:55Z
- **Tasks:** 7 (2 human-action checkpoints + 5 auto)
- **Files created:** 25 (backend 12, frontend 9, root 4)

## Accomplishments

- `docker compose config` validates Redis 7-alpine service on 6379
- `cd backend && uv sync` resolves all runtime + dev deps from lockfile
- `cd backend && uv run pytest tests/` reports `7 skipped` (zero failures)
- `cd frontend && npm run build` exits 0 with stub env vars
- Supabase migration 0001_init.sql applied — 3 tables present, both `listings` and `search_jobs` listed in `supabase_realtime` publication
- Step E smoke test `cd backend && uv run python -c "..."` prints **`schema-push-verified`** against the live pooler URI

## Task Commits

1. **Task 1: Repo-root scaffolding (docker-compose, .env.example, .gitignore)** — `a95c6e3` (feat)
2. **Task 2: Backend project — uv init + dependencies + pytest config** — `16dbd60` (feat)
3. **Task 3: Backend settings + asyncpg pool + structlog config** — `c38dbf7` (feat)
4. **Task 4: Supabase migration 0001_init.sql** — `5c62232` (feat)
5. **Task 5: Pytest scaffold (conftest + empty test files)** — `af57f9b` (test)
6. **Task 6: Frontend Next.js 15 scaffold + Tailwind + supabase-js client** — `d3b4875` (feat)

Tasks 0 and 7 were `checkpoint:human-action` gates with no associated code commit. Task 7 produced two non-committed gitignored files: `backend/.env` and `frontend/.env.local`.

## Files Created/Modified

- `docker-compose.yml` — Redis 7-alpine, port 6379, no version key, no volume
- `.env.example` — 11-variable contract split into backend/frontend sections
- `.gitignore` — extended with `backend/.env`, `backend/.venv/`, `frontend/.env.local`, `frontend/.next/`, `frontend/node_modules/`, `**/__pycache__/`, `**/.pytest_cache/`
- `backend/pyproject.toml` + `backend/uv.lock` — locked Python 3.12 environment with pytest asyncio_mode=auto
- `backend/app/settings.py` — `Settings(BaseSettings)` reading `.env`, defaults match D-10 exactly
- `backend/app/db.py` — asyncpg pool factory with `statement_cache_size=0`, `min_size=1`, `max_size=5`, `command_timeout=30`
- `backend/app/logging.py` — structlog JSON renderer with ISO timestamp + log level
- `backend/migrations/0001_init.sql` — 3 tables, pgcrypto, idempotent publication adds, RLS TODO marker
- `backend/tests/conftest.py` — `pg_pool` (skips if `SUPABASE_DB_URL` unset), `clean_db`, `arq_redis` fixtures
- `backend/tests/test_budget_guard.py` — 4 skip-marked stubs (`test_iter_cap`, `test_token_cap`, `test_daily_spend_upsert`, `test_payload_cap`)
- `backend/tests/test_stub_scraper.py` — 2 skip-marked stubs (`test_payload_size`, `test_run_search`)
- `backend/tests/test_jobs_api.py` — 1 skip-marked stub (`test_fire_and_forget`)
- `frontend/package.json` — Next.js `^15`, `@supabase/supabase-js` `^2.105`, Tailwind `^3.4`
- `frontend/lib/supabase.ts` — `createClient(NEXT_PUBLIC_SUPABASE_URL!, NEXT_PUBLIC_SUPABASE_ANON_KEY!)` singleton
- `frontend/app/layout.tsx` — system-font stack per UI-SPEC; `<html lang="en">`, `font-sans antialiased text-zinc-900 bg-white` body
- `frontend/app/page.tsx` — null-rendering placeholder for Plan 03 to replace
- `backend/.env` (gitignored) — live Supabase pooler URL + anon/service-role keys + REDIS_URL + cost-guard defaults
- `frontend/.env.local` (gitignored) — NEXT_PUBLIC_SUPABASE_URL/ANON_KEY + NEXT_PUBLIC_API_URL

## Decisions Made

- Supabase dev project provisioned at ref `ebxglaywpuynshplrtys` in `aws-1-us-east-2` (pooler URI on port 6543).
- Realtime publication includes BOTH `listings` (incremental results) and `search_jobs` (job-status transitions) so the frontend can observe completion via a single Postgres-changes channel.
- `statement_cache_size=0` set on the asyncpg pool (RESEARCH Pitfall 2) — required for Supabase transaction-mode pooler; verified by literal-substring grep in Task 3 acceptance.
- Migration uses idempotent guards (`IF NOT EXISTS`, `DO $$ ... pg_publication_tables` check) so re-applying the file is a no-op.
- RLS intentionally NOT enabled (assumption A2); explicit `TODO(Phase 6)` comment in the SQL file records the deferral.
- shadcn intentionally NOT initialized in Phase 1 (UI-SPEC defers to Phase 2).

## Deviations from Plan

None — plan executed exactly as written. Task 7's two-checkpoint structure (user provisions Supabase + applies schema; agent writes env files + runs smoke test) was honored. Both gitignored env files were populated by the agent after the user signaled `schema-pushed`, and the Step E smoke test passed on first run.

## Issues Encountered

None.

## User Setup Required

External Supabase project required and provisioned during Task 0. Credentials live in `backend/.env` and `frontend/.env.local` (both gitignored). The frontmatter `user_setup` block in `01-01-PLAN.md` and the Task 0 / Task 7 checkpoint instructions are the canonical guide for re-provisioning if needed.

## Next Phase Readiness

- **Plan 01-02 (backend behavior):** Ready to begin. Plan 02 can `from app.db import get_pool` and `from app.settings import settings` directly. The 7 pytest stubs in `backend/tests/` need their `pytestmark = pytest.mark.skip` removed and bodies filled in per VALIDATION.md.
- **Plan 01-03 (frontend slice):** Ready to begin. `frontend/lib/supabase.ts` singleton and Tailwind config are in place; Plan 03 replaces `app/page.tsx` per UI-SPEC.
- **Schema state:** Live in the Supabase dev project. Any DB-touching test from Plan 02 onward can rely on the 3 tables + Realtime publication being present.
- **No blockers.**

## Self-Check: PASSED

- FOUND: docker-compose.yml, .env.example, backend/pyproject.toml, backend/uv.lock, backend/app/settings.py, backend/app/db.py, backend/app/logging.py, backend/migrations/0001_init.sql, backend/tests/conftest.py, backend/tests/test_budget_guard.py, backend/tests/test_stub_scraper.py, backend/tests/test_jobs_api.py, frontend/package.json, frontend/lib/supabase.ts, frontend/app/layout.tsx, frontend/app/page.tsx, backend/.env, frontend/.env.local
- FOUND commits: a95c6e3, 16dbd60, c38dbf7, 5c62232, af57f9b, d3b4875
- Step E smoke output: `schema-push-verified`

---
*Phase: 01-foundation-skeleton*
*Completed: 2026-05-11*
