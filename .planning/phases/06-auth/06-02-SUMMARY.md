---
phase: 06-auth
plan: 02
subsystem: frontend-auth
tags: [auth, supabase, ssr, login, magic-link, pkce, vertical-slice]
requires:
  - "frontend/lib/supabase-browser.ts (Plan 01)"
  - "frontend/lib/supabase-server.ts (Plan 01)"
  - "frontend/middleware.ts (Plan 01)"
provides:
  - "/login Client Component page rendering the magic-link form, sent state, error banner, and callback-error banner"
  - "/auth/callback Route Handler exchanging PKCE codes for a session cookie and redirecting"
  - "T-06-03 open-redirect mitigation (validated `next` query param) baked into the callback handler"
affects:
  - "frontend/vitest.setup.ts (added useSearchParams to the global next/navigation mock)"
tech-stack:
  added: []
  patterns:
    - "Client Component + Suspense wrapper around useSearchParams (Next 15 static-prerender requirement)"
    - "Server-side origin extraction via new URL(request.url) — preview-deploy safe (no NEXT_PUBLIC_SITE_URL read in the callback)"
    - "Validated `next` predicate inline in source: startsWith('/') && !startsWith('//') && !includes('://')"
    - "Canned UI-SPEC error copy (never error.message) — defense-in-depth against information disclosure"
key-files:
  created:
    - frontend/app/login/page.tsx
    - frontend/app/auth/callback/route.ts
  modified:
    - frontend/vitest.setup.ts
decisions:
  - "Use Suspense to wrap LoginForm so useSearchParams works at static prerender time (Next 15 requirement); the Suspense fallback is null because /login is below-the-fold for a Suspense boundary anyway"
  - "Extract redirect origin from new URL(request.url) in the callback (not process.env.NEXT_PUBLIC_SITE_URL) — RESEARCH Pattern 4 — works on preview deploys without env-var churn"
  - "Map signInWithOtp error → canned UI-SPEC copy; never render error.message (T-06-06)"
  - "Open-redirect predicate is three positive AND-conjuncts (startsWith('/') AND !startsWith('//') AND !includes('://')), inlined in the source so the threat-model checker can grep it"
metrics:
  completed: "2026-05-12"
  tasks: 2
  files_created: 2
  files_modified: 1
  source_loc: 135
---

# Phase 6 Plan 02: Magic-Link Vertical Slice Summary

End-to-end magic-link round-trip wired: `/login` collects an email and calls `signInWithOtp` with `emailRedirectTo=${NEXT_PUBLIC_SITE_URL}/auth/callback`; the new `/auth/callback` Route Handler exchanges the returned PKCE code via `supabase.auth.exchangeCodeForSession` and redirects to `/`. AUTH-01 and AUTH-02 delivered as a single vertical slice. Turns three RED Wave-0 tests (LoginPage 3 + authCallback 3) GREEN; the header flip awaits Plan 03.

## What Shipped

### Source (2 files, 135 LOC)

| File | Lines | Role |
| --- | --- | --- |
| `frontend/app/login/page.tsx` | 105 | Client Component: email form + sent block + inline error banner + `?error=auth_failed` callback-error banner (wrapped in Suspense for useSearchParams) |
| `frontend/app/auth/callback/route.ts` | 30 | Route Handler `GET`: PKCE code exchange + origin-relative redirect with hardened `next` param |

### Tests turned GREEN

| File | Tests | Previously |
| --- | --- | --- |
| `frontend/__tests__/LoginPage.test.tsx` | 3 | RED (Plan 01 import-only failure) |
| `frontend/__tests__/authCallback.test.ts` | 3 | RED (Plan 01 import-only failure) |

Final `npm test -- --run` snapshot: **53 passed / 2 failed (55 total)** — the 2 remaining failures are `__tests__/layout.test.tsx` (Plan 03 RED — layout has no auth content yet) and the file-collection failure on `__tests__/SignOutButton.test.tsx` (Plan 03 RED — component does not exist).

## Exact Copy Strings Used (UI-SPEC §Copywriting Contract — verbatim)

| Element | String |
| --- | --- |
| Page heading | `Sign in to Property Helper` |
| Helper text | `Enter your email and we'll send a one-time link.` |
| Email aria-label | `Email address` |
| Email placeholder | `you@example.com` |
| CTA idle | `Send magic link` |
| CTA loading | `Sending…` |
| Success heading | `Check your inbox` |
| Success body | `We sent a sign-in link to {email}. Open it in this same browser to finish signing in.` |
| Inline error | `Couldn't send the link. Check the email address and try again.` |
| Callback-error banner | `That sign-in link didn't work. Request a fresh one below.` |
| Callback-error redirect target | `/login?error=auth_failed` |

The "Open it in this same browser" sentence is preserved verbatim per Pitfall 6 — it is the user-facing reinforcement of the PKCE code-verifier cookie-scope contract.

## `next`-param validator predicate (T-06-03)

Located in `frontend/app/auth/callback/route.ts`:

```ts
const rawNext = searchParams.get('next');
const next =
  rawNext &&
  rawNext.startsWith('/') &&
  !rawNext.startsWith('//') &&
  !rawNext.includes('://')
    ? rawNext
    : '/';
```

Three positive AND-conjuncts; all three must be true for the user-supplied value to be honored. Failing values silently default to `/`. The predicate is inlined (not extracted into a helper) so the threat-model grep finds all three checks in close proximity in the source file.

## Threat Model Disposition

| Threat | Mitigation Landed |
| --- | --- |
| T-06-01 (PKCE code interception) | `signInWithOtp` runs in the browser → sets the code_verifier cookie; the matching `exchangeCodeForSession` only succeeds in the same browser. User-facing reinforcement: "Open it in this same browser…" sentence in the sent block. |
| T-06-03 (Open redirect via `next`) | Inline predicate enforces `startsWith('/') && !startsWith('//') && !includes('://')`. Failing values default to `/`. |
| T-06-06 (Token / error-message disclosure) | (a) raw `code` query param never logged; (b) `signInWithOtp` errors mapped to canned UI-SPEC copy — `error.message` is never rendered. |
| T-06-07 (Phishing via misdirected magic link) | `emailRedirectTo` is the env-derived `${NEXT_PUBLIC_SITE_URL}/auth/callback`; redirect-URL whitelist is the Supabase dashboard upstream control (accepted, per CONTEXT). |

## Deviations from Plan

**1. [Rule 3 — Blocking issue] Wrapped LoginForm in `<Suspense>` and extended the global `next/navigation` mock**

- **Found during:** Task 1 (initial test/build attempts)
- **Issue:** The plan instructs `LoginPage` to call `useSearchParams()` directly. Next 15 fails the static prerender of any Client Component that calls `useSearchParams()` unless it is inside a `<Suspense>` boundary, and the existing `vitest.setup.ts` global `next/navigation` mock did not export `useSearchParams`, so `render(<LoginPage />)` would throw in jsdom.
- **Fix:** (1) Split the page into `LoginPage` (default export) that wraps `LoginForm` in `<Suspense fallback={null}>`; `LoginForm` is the component that calls `useSearchParams()`. (2) Added `useSearchParams: () => new URLSearchParams()` to the `vi.mock('next/navigation', ...)` block in `frontend/vitest.setup.ts` — this matches the established Plan-01 pattern for that file (it already mocks `useRouter` and `redirect` for the same jsdom-import-cleanliness reason).
- **Files modified:** `frontend/app/login/page.tsx` (Suspense split), `frontend/vitest.setup.ts` (useSearchParams added).
- **Commit:** `00753ac` (Task 1).

No other deviations.

## Verification

| Gate | Result |
| --- | --- |
| `npm test -- --run LoginPage` | 3/3 passed |
| `npm test -- --run authCallback` | 3/3 passed |
| `npm test -- --run` (full suite) | 53 passed, 2 failed (failures = Plan 03 RED: layout 2 + SignOutButton collection) |
| `NEXT_PUBLIC_SUPABASE_URL=stub NEXT_PUBLIC_SUPABASE_ANON_KEY=stub NEXT_PUBLIC_SITE_URL=http://localhost:3000 npm run build` | Compiled successfully; `/login` prerendered as Static (5.9 kB), `/auth/callback` registered as Dynamic (122 B). |
| `npx tsc --noEmit` | No errors in the two new files. Pre-existing errors persist in `__tests__/{ListingDrawer,ListingList,MapView}.test.tsx` (the `expires_at` literal-shape mismatch flagged in Plan 01 SUMMARY) and in `__tests__/SignOutButton.test.tsx` (Plan 03 RED). All four are out-of-scope (SCOPE BOUNDARY) — they touch files this plan did NOT modify. |

## Pre-existing Out-of-Scope Issues

Same three `expires_at` tsc errors flagged in Plan 01 still exist on `main`; this plan did not modify those test files. Confirmed by `git stash && npm run build && git stash pop` — the pre-existing Next.js build prerender error (`Error: supabaseUrl is required.` when env vars are absent) is unrelated to this plan and reproducible before our changes. The build is reliably green when `NEXT_PUBLIC_SUPABASE_*` envs are provided.

## Manual Smoke (deferred to integration)

The output spec asks for a DevTools cookie snippet after a successful magic-link click. This is a parallel-worktree execution and a real Supabase project + email round-trip is not available here. The smoke is intentionally deferred to the integration verifier when the wave merges. Expected behavior on a real `npm run dev`:

1. Visit `http://localhost:3000/login` → form renders with `Sign in to Property Helper` heading.
2. Type a real email + click `Send magic link` → button flips to `Sending…`, then the form is replaced by `Check your inbox` naming the email and instructing same-browser open.
3. Open the magic link in the same browser → `/auth/callback?code=…` → 302 redirect to `/`; DevTools → Application → Cookies should show `sb-*-auth-token` (HttpOnly).
4. Visit `http://localhost:3000/auth/callback` directly (no params) → 302 redirect to `/login?error=auth_failed`; banner `That sign-in link didn't work. Request a fresh one below.` renders.
5. Visit `http://localhost:3000/auth/callback?code=xxx&next=https://evil.com` → 302 redirect to `/` (NOT to `evil.com`).

## Commits

| Hash | Task | Summary |
| --- | --- | --- |
| `00753ac` | Task 1 | /login Client Component with magic-link form (+ useSearchParams mock added globally) |
| `d7b435b` | Task 2 | /auth/callback Route Handler with PKCE exchange and T-06-03 open-redirect mitigation |

## Self-Check: PASSED

- `frontend/app/login/page.tsx` — exists (105 LOC, line 1 is `'use client';`).
- `frontend/app/auth/callback/route.ts` — exists (30 LOC, exports `async function GET`).
- `frontend/vitest.setup.ts` — modified (useSearchParams added to the global `next/navigation` mock).
- Both task commits present in `git log` (`00753ac`, `d7b435b`).
- All six previously-RED tests (3 LoginPage + 3 authCallback) now GREEN.
- `npm run build` green with envs set; `/login` static, `/auth/callback` dynamic.
- Grep-verified literal UI-SPEC strings all present in `frontend/app/login/page.tsx`.
- Grep-verified open-redirect predicate (`startsWith('/')`, `startsWith('//')`, `includes('://')` in close proximity) present in `frontend/app/auth/callback/route.ts`.
- No `error.message` rendering in source (verified by grep: zero matches in `frontend/app/login/page.tsx`).
