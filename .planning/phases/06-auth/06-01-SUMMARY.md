---
phase: 06-auth
plan: 01
subsystem: frontend-auth
tags: [auth, supabase, ssr, nextjs, middleware, tdd, wave-0]
requires: []
provides:
  - "@supabase/ssr@0.10.3 installed in frontend dependencies"
  - "createClient() browser factory (lib/supabase-browser.ts)"
  - "async createClient() server factory (lib/supabase-server.ts)"
  - "updateSession(request) middleware helper (lib/supabase-middleware.ts)"
  - "Root middleware.ts wired to refresh session cookies on every non-static request"
  - "mockSupabaseClient(overrides) shared test factory"
  - "5 Wave-0 test files (4 RED, 1 GREEN)"
affects:
  - "frontend/lib/supabase.ts (legacy bare client retained; Phase 7 TODO added)"
tech-stack:
  added:
    - "@supabase/ssr ^0.10.3"
  patterns:
    - "Browser/Server/Middleware SSR client triplet"
    - "getAll/setAll cookie adapter (no get/set/remove single-cookie callbacks)"
    - "getUser() (not getSession) for server-validated session refresh"
key-files:
  created:
    - frontend/lib/supabase-browser.ts
    - frontend/lib/supabase-server.ts
    - frontend/lib/supabase-middleware.ts
    - frontend/middleware.ts
    - frontend/.env.local.example
    - frontend/__tests__/_mocks/supabase.ts
    - frontend/__tests__/LoginPage.test.tsx
    - frontend/__tests__/authCallback.test.ts
    - frontend/__tests__/middleware.test.ts
    - frontend/__tests__/SignOutButton.test.tsx
    - frontend/__tests__/layout.test.tsx
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/vitest.setup.ts
    - frontend/lib/supabase.ts
decisions:
  - "Use getUser() in middleware (not getSession) — server-validates JWT against Supabase to mitigate T-06-02 cookie tampering"
  - "createClient() returns a fresh client per call in supabase-browser.ts (no module-scope cache) — mitigates T-06-05 identity leak"
  - "Phase 6 middleware has zero redirect logic — session refresh only (per Pitfall 2)"
  - "Legacy lib/supabase.ts kept for Realtime; Phase 7 TODO scheduled for SSR migration"
metrics:
  completed: "2026-05-12"
  tasks: 3
  files_created: 11
  files_modified: 4
  source_loc: 116
  test_loc: 251
---

# Phase 6 Plan 01: Supabase SSR Foundation Summary

Installed @supabase/ssr 0.10.3 and laid the full Wave-0 auth foundation: three SSR client factories (browser, server, middleware), root Next.js middleware wired to refresh session cookies on every non-static request, a shared Vitest mock factory, and five RED/GREEN test files enforcing the AUTH-01..04 contracts that Plans 02 and 03 will turn green.

## What Shipped

### Source (4 files, 116 LOC)

| File | Lines | Role |
| --- | --- | --- |
| `frontend/lib/supabase-browser.ts` | 15 | `createClient()` per-render browser factory |
| `frontend/lib/supabase-server.ts` | 38 | `async createClient()` with try/catch-wrapped setAll |
| `frontend/lib/supabase-middleware.ts` | 44 | `updateSession()` — zero code between createServerClient and getUser() |
| `frontend/middleware.ts` | 19 | Next.js root middleware delegating to updateSession + static-asset matcher |

### Tests (6 files, 251 LOC)

| File | Lines | State | Notes |
| --- | --- | --- | --- |
| `__tests__/_mocks/supabase.ts` | 28 | n/a | Shared mock factory; defaults `getUser → { user: null }` |
| `__tests__/LoginPage.test.tsx` | 61 | RED | Fails on `import LoginPage from '../app/login/page'` — Plan 02 will create source |
| `__tests__/authCallback.test.ts` | 47 | RED | Fails on `import { GET } from '../app/auth/callback/route'` — Plan 02 |
| `__tests__/middleware.test.ts` | 29 | **GREEN** | Contract enforcement against Task 2's helper — passes immediately |
| `__tests__/SignOutButton.test.tsx` | 44 | RED | Fails on `import { SignOutButton } from '../app/components/SignOutButton'` — Plan 03 |
| `__tests__/layout.test.tsx` | 42 | RED | Layout has no auth content yet; both assertions fail — Plan 03 |

### Config / Infra

- `frontend/package.json` — `"@supabase/ssr": "^0.10.3"` added under `dependencies` (resolved as 0.10.3). `npm install` ran clean; no peer-dep warnings.
- `frontend/.env.local.example` — created with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `NEXT_PUBLIC_SITE_URL=http://localhost:3000`. Committed with `git add -f` because `frontend/.gitignore`'s `.env*` rule covers `.example` too — this is the standard exception for example files.
- `frontend/vitest.setup.ts` — `import { vi } from 'vitest'` + global `vi.mock('next/headers', ...)` and `vi.mock('next/navigation', ...)` so server-only modules import cleanly under jsdom. Existing 45 tests remain GREEN.
- `frontend/lib/supabase.ts` — added 4-line `TODO(Phase 7)` block above the bare client export; behavior unchanged.

## Test State Snapshot

```
Test Files  4 failed | 9 passed (13)
Tests       2 failed | 47 passed (49)
```

- The previous 45 tests still pass.
- `middleware.test` (2 tests) passes — GREEN contract enforcement on the helper Task 2 just landed.
- 4 RED test files fail on missing source imports / missing layout auth content. Their actual failure messages:
  - LoginPage / authCallback / SignOutButton: `Failed to load url ../app/<…>` (collection-time, "0 test" reported by Vitest — expected RED signal until Plan 02/03 create the source files).
  - layout: `Unable to find an element with the text: a@b.com` and the `Sign in` assertion fails because the current `app/layout.tsx` renders neither a sign-in link nor any auth-aware header.

## Threat Model Disposition

| Threat | Mitigation Landed |
| --- | --- |
| T-06-02 (session cookie tampering) | `getUser()` is the call used in middleware — verified by middleware.test asserting `client.auth.getUser` is called |
| T-06-04 (cookie-adapter misuse) | Source uses `getAll`/`setAll` only; no `get(`/`set(`/`remove(` single-cookie callbacks anywhere in the new files |
| T-06-05 (module-scope identity leak) | `createClient()` in `lib/supabase-browser.ts` is a function call, NOT a module-scope const |

T-06-01 (PKCE) and T-06-03 (open redirect on /auth/callback) land in Plan 02 where the callback handler is implemented.

## Deviations from Plan

None of substance. One operational note:

**1. `.env.local.example` required `git add -f`**
- **Found during:** Task 1 commit
- **Issue:** `frontend/.gitignore` line 34 (`.env*`) blocks `.env.local.example` as well as real env files. This is intentional Next.js default behavior.
- **Fix:** Staged with `git add -f frontend/.env.local.example`. Standard practice for committing `.env.local.example` next to a `.env*`-ignored project.
- **Files modified:** None beyond the staging command.

## Pre-existing Out-of-Scope Issues

`npx tsc --noEmit` reports three errors in `__tests__/ListingDrawer.test.tsx`, `__tests__/ListingList.test.tsx`, and `__tests__/MapView.test.tsx` complaining that `expires_at` is missing on the `Listing` literals those tests construct. These errors:

- Exist on `main` prior to this plan (see `git diff` — none of the three files were modified here).
- Do not block `npm test -- --run` (Vitest does not run tsc; all 45 prior tests still pass).
- Touch files this plan did NOT modify.

Per executor SCOPE BOUNDARY they are NOT in scope for this plan. Flagged here for a future cleanup plan.

## User Setup Reminder (frontmatter mirror)

After merge, the operator must add `http://localhost:3000/auth/callback` to Supabase Dashboard → Authentication → URL Configuration → Redirect URLs before Plan 02's magic-link round-trip can complete. The redirect-URL whitelist is a Supabase-side dashboard config; this plan added the env-var scaffolding (`NEXT_PUBLIC_SITE_URL`) but the dashboard step is intentionally not automated.

## Commits

| Hash | Task | Summary |
| --- | --- | --- |
| `4d97cab` | Task 1 | Install @supabase/ssr 0.10.3, add .env.local.example, vitest.setup mocks |
| `793fcbb` | Task 2 | Add SSR client factories + root middleware.ts + Phase 7 TODO on legacy client |
| `2210c63` | Task 3 | Shared Supabase mock + 5 Wave-0 test files (4 RED, 1 GREEN) |

## Self-Check: PASSED

- All 11 created files exist on disk (verified via `wc -l`).
- All 3 task commits present in `git log` (verified: 4d97cab, 793fcbb, 2210c63).
- `npm ls @supabase/ssr` → 0.10.3.
- `npm test -- --run` end state: 47 passed, 2 failed (layout RED) + 3 test files RED on missing source imports — matches the plan's success criteria precisely.
- `getAll`/`setAll`-only contract verified across both server and middleware adapters (no `get(`/`set(`/`remove(` single-cookie callbacks).
- `updateSession` body: zero statements between `createServerClient(...)` and `await supabase.auth.getUser()` (visual + grep verified).
