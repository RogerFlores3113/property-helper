---
phase: 06-auth
plan: 03
subsystem: frontend-auth
tags: [auth, supabase, ssr, header, logout, layout, vertical-slice, checkpoint]
requires:
  - "frontend/lib/supabase-browser.ts (Plan 01)"
  - "frontend/lib/supabase-server.ts (Plan 01)"
  - "frontend/middleware.ts (Plan 01)"
  - "frontend/app/login/page.tsx (Plan 02)"
  - "frontend/app/auth/callback/route.ts (Plan 02)"
provides:
  - "frontend/app/components/SignOutButton.tsx — Client Component that signs out + push('/') + refresh()"
  - "frontend/app/layout.tsx — async Server Component root layout with auth-aware header"
  - "AUTH-03 SSR session-aware first paint (cookie-persisted)"
  - "AUTH-04 sign-out available on every page (header lives in layout)"
affects:
  - "All routes (header rendered globally; build moved /login from Static to Dynamic because layout now reads cookies)"
tech-stack:
  added: []
  patterns:
    - "Server Component root layout that awaits supabase.auth.getUser() and branches on the user"
    - "Client Component SignOutButton calls signOut → push('/') → refresh() in mandatory order (Pitfall 7)"
    - "UI-SPEC subdued link-style for both 'Sign in' and 'Sign out' (zinc-500 hover:zinc-900 underline)"
key-files:
  created:
    - frontend/app/components/SignOutButton.tsx
  modified:
    - frontend/app/layout.tsx
decisions:
  - "Use getUser() (server-validated) for the layout auth branch — never getSession() (cookie-only, T-06-02)"
  - "SignOutButton calls BOTH router.push('/') AND router.refresh() — refresh alone would not change route; push alone would leave the Server-Component cache showing the stale user email until next nav (T-06-04)"
  - "Sign-out is a one-click action with no confirm dialog (UI-SPEC §Destructive actions)"
  - "Layout reads getUser() unconditionally on every render → all routes become server-rendered on demand; this is the correct trade for first-paint correctness (T-06-09 anti-spoofing)"
metrics:
  completed: "2026-05-12"
  tasks_completed: 2
  tasks_total: 3
  task_3_status: "checkpoint:human-verify — awaiting user E2E smoke against live Supabase"
  files_created: 1
  files_modified: 1
  source_loc: 53
---

# Phase 6 Plan 03: Session-Aware Header + Sign-Out Summary

Wired the auth-aware header into the root layout and shipped a SignOutButton Client Component, completing the Phase 6 vertical slice. The layout is now an async Server Component that reads `getUser()` and renders either a `Sign in` link (anon) or `{email} + Sign out` (authed). SignOutButton calls `signOut()` then `router.push('/')` then `router.refresh()` so the Server-Component layout flips to the anonymous state without leaking the prior user's email. Turns the last two RED tests (`layout.test.tsx` 2 tests) GREEN; full Vitest suite now 57/57 passing.

## What Shipped

### Source (1 new file, 1 modified, 53 LOC)

| File | Lines | Role |
| --- | --- | --- |
| `frontend/app/components/SignOutButton.tsx` (NEW) | 24 | Client Component: `signOut() → push('/') → refresh()` with UI-SPEC subdued styling |
| `frontend/app/layout.tsx` (MOD) | 29 | Server Component root layout with auth-aware header above `{children}`; metadata, html lang, body className + inline fontFamily preserved unchanged |

### Tests turned GREEN

| File | Tests | Previously |
| --- | --- | --- |
| `frontend/__tests__/SignOutButton.test.tsx` | 2 | RED (collection failure — component did not exist) |
| `frontend/__tests__/layout.test.tsx` | 2 | RED (layout rendered no auth content) |

Final `npm test -- --run` snapshot: **57 passed / 0 failed (57 total)**. Plan estimated 56; the extra count is harmless (preexisting test file count drift). 0 failures is the success criterion.

## Exact strings landed (UI-SPEC §Copywriting Contract — verbatim)

| Element | String |
| --- | --- |
| Header brand (left, link to `/`) | `Property Helper` |
| Anon right-side link | `Sign in` |
| Authed email span | `{user.email}` with `truncate max-w-[200px] text-sm` |
| Authed button | `Sign out` |
| Header separator class | `border-b border-zinc-200 bg-white` |
| Header inner container | `mx-auto max-w-[1280px] px-6 py-3 flex items-center justify-between` |
| SignOutButton button class | `text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline` |

## SignOutButton ordering contract (T-06-04 mitigation)

`frontend/app/components/SignOutButton.tsx` body:

```ts
async function onClick() {
  const supabase = createClient();
  await supabase.auth.signOut();
  router.push('/');
  router.refresh();
}
```

Both `router.push('/')` AND `router.refresh()` are present, in that order, after the awaited `signOut()`. Without `refresh()` the Server-Component layout would continue to render the cached user email until the next navigation, leaking the impression of an active session (Pitfall 7).

## Threat Model Disposition

| Threat | Mitigation Landed |
| --- | --- |
| T-06-02 (session cookie theft / fixation) | Layout uses `supabase.auth.getUser()` (server-validated against Supabase) NOT `getSession()` — verified by source grep (1 getUser match, 0 getSession matches). Cookies remain HttpOnly via @supabase/ssr defaults from Plan 01. |
| T-06-04 (auth bypass via stale render after signOut) | SignOutButton calls BOTH `router.push('/')` AND `router.refresh()` in mandatory order — verified by acceptance grep. |
| T-06-08 (long email overflowing header) | Email span uses `truncate max-w-[200px]` — verified by grep. |
| T-06-09 (fake "signed in as X" first paint) | Layout reads getUser() server-side on every request; the first paint reflects the real session. Side-effect: all routes become dynamic (server-rendered on demand) — this is the correct trade and matches the AUTH-09 "no client-side flicker" must-have. |

## Build / Routing Note

Before this plan, `/login` prerendered as Static. After this plan all routes are server-rendered on demand because the root layout reads cookies via `getUser()` on every request. Build output:

```
Route (app)                                 Size  First Load JS
┌ ƒ /                                     280 kB         442 kB
├ ƒ /_not-found                            993 B         103 kB
├ ƒ /auth/callback                         122 B         103 kB
└ ƒ /login                               1.25 kB         168 kB

ƒ Middleware                             89.1 kB
ƒ  (Dynamic)  server-rendered on demand
```

This is intentional and required for AUTH-03 (first paint reflects real session, no flicker).

## Verification

| Gate | Result |
| --- | --- |
| `npm test -- --run SignOutButton.test.tsx` | 2/2 GREEN |
| `npm test -- --run layout.test.tsx` | 2/2 GREEN |
| `npm test -- --run` (full suite) | **57 passed / 0 failed** |
| `NEXT_PUBLIC_SUPABASE_URL=… NEXT_PUBLIC_SUPABASE_ANON_KEY=… NEXT_PUBLIC_SITE_URL=… npm run build` | ✓ Compiled successfully (all 7 pages generated) |

## Task 3 — Manual E2E Smoke: AWAITING USER

Task 3 is a `checkpoint:human-verify` (BLOCKING) and requires the user to:

1. Run `cd frontend && npm run dev` against a live Supabase dev project with a real email inbox.
2. Walk SC#1..SC#9 (anonymous header → login → magic-link send → magic-link click → authed header → refresh persistence → tab-reopen persistence → sign out → bad-callback banner → open-redirect mitigation).
3. Report `phase-6-complete` or list failing SC numbers.

This cannot be executed by the parallel-worktree executor (no browser, no real Supabase project credentials in this environment, no email inbox). Returning the checkpoint state to the orchestrator.

## Deviations from Plan

**1. Plan task-3 SC#9 expected `56 tests pass`; actual is `57 tests pass / 0 fail`**

- **Found during:** Task 2 verification
- **Issue:** The plan's success criterion said `56 tests` (45 prior + 11 new auth). Full suite is 57 GREEN. The off-by-one is preexisting test-file count drift, not a regression: 0 tests fail and all 4 previously-RED auth tests (2 SignOutButton + 2 layout) are now GREEN as required.
- **Fix:** None needed — the substantive criterion (RED → GREEN flips with zero remaining failures) is met. Documented here so SC#9 can be read as "57 GREEN / 0 RED" rather than `=== 56`.
- **Files modified:** None.

No other deviations. Tasks 1 + 2 executed exactly as planned.

## Pre-existing Out-of-Scope Issues

The three `expires_at`-literal tsc errors in `__tests__/{ListingDrawer,ListingList,MapView}.test.tsx` flagged in Plan 01 + Plan 02 SUMMARYs persist. None of those files were modified in this plan. Per executor SCOPE BOUNDARY they remain out of scope for Plan 06-03.

## Phase 6 Closing Notes (deferred to orchestrator)

The plan's `<output>` asks for a "requirements traceability flip in REQUIREMENTS.md AUTH-01..04 → Complete". The orchestrator owns writes to `STATE.md` and `ROADMAP.md`; per the parallel-executor instructions this plan does NOT modify them. AUTH-01..04 traceability flips are deferred to the orchestrator's post-merge step (after the Task 3 manual SC pass).

## Commits

| Hash | Task | Summary |
| --- | --- | --- |
| `e8a12fa` | Task 1 | feat(06-03): add SignOutButton client component (AUTH-04) |
| `b068c91` | Task 2 | feat(06-03): auth-aware header in root layout (AUTH-03, AUTH-04) |
| _pending_ | Task 3 | checkpoint:human-verify — live E2E smoke against real Supabase |

## Self-Check: PASSED

- `frontend/app/components/SignOutButton.tsx` — exists (24 LOC, line 1 is `'use client';`).
- `frontend/app/layout.tsx` — modified (default export now `async function RootLayout`).
- Both task commits present in `git log` (verified: `e8a12fa`, `b068c91`).
- Grep-verified source contracts:
  - SignOutButton: `router.push('/')` ×1, `router.refresh()` ×1, `confirm(` ×0, `bg-zinc-900` ×0.
  - layout: `supabase.auth.getUser` ×1, `supabase.auth.getSession` ×0, `'use client'` ×0, `Property Helper` ×2 (metadata + brand), `truncate max-w-[200px]` ×1.
- `npm test -- --run` end state: 57 passed, 0 failed — matches and exceeds plan success criterion.
- `npm run build` (with stub envs) compiled successfully; all 7 routes generated.
