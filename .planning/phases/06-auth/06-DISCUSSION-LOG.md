# Phase 6: Auth - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** 6-auth
**Mode:** --auto (fully autonomous — no user prompts; all choices are Claude recommended defaults)
**Areas discussed:** Supabase Auth client setup, Auth UI placement, RLS scope, Magic link callback

---

## Supabase Auth Client Setup

| Option | Description | Selected |
|--------|-------------|----------|
| Keep bare `@supabase/supabase-js` | Client-side only; session stored in localStorage. Simple, no middleware. | |
| `@supabase/ssr` + middleware | Cookie-based SSR-aware sessions. Required for SC#3 (session survives refresh). Official Next.js App Router recommendation. | ✓ |

**Auto-selected:** `@supabase/ssr` with middleware  
**Rationale:** SC#3 (session survives browser refresh) cannot be achieved with localStorage — server-rendered layout would show logged-out state until client hydrates. Cookie-based sessions are the only correct approach for Next.js App Router.

---

## Auth UI Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Modal overlay | Login form appears as modal over main page; no route change. | |
| Header button + `/login` page | Header shows "Sign in" / email + "Sign out". Dedicated `/login` page for the magic link form. | ✓ |
| Dedicated route only | Just `/login` and `/logout` routes; no persistent header element. | |

**Auto-selected:** Header button + `/login` page  
**Rationale:** Most intuitive pattern. Login form on a dedicated page avoids modal complexity. Header presence makes auth state visible on every page.

---

## RLS Scope

| Option | Description | Selected |
|--------|-------------|----------|
| Enable RLS now (user-scoped) | Add `user_id` to `search_jobs`, enable RLS, require auth for all job creation. Breaks anonymous search flow. | |
| Keep tables open (Phase 6) | No RLS changes. Auth is additive — existing anonymous flow unchanged. RLS deferred to Phase 7. | ✓ |

**Auto-selected:** Keep tables open in Phase 6  
**Rationale:** The existing search flow is anonymous. Adding RLS now would require changing the job creation API, add user context to the ARQ worker, and break anon search — all Phase 7 scope. The auth gate is additive in Phase 6.

---

## Magic Link Callback

| Option | Description | Selected |
|--------|-------------|----------|
| Client-side session exchange | Use `supabase.auth.signInWithOtp` hash fragment mode; no callback route needed. | |
| `/auth/callback` route handler | Next.js Route Handler exchanges `code` param for session. Official Supabase Next.js App Router pattern. | ✓ |

**Auto-selected:** `/auth/callback` route handler  
**Rationale:** PKCE flow (used by `@supabase/ssr`) requires a server-side code exchange. Hash-fragment mode is incompatible with SSR-aware cookie sessions.

---

## Claude's Discretion

- Loading/error states on the login form (spinner, disabled button during OTP request)
- Exact header layout/styling (should match existing zinc-900 Tailwind design system)
- Whether the header is sticky or static

## Deferred Ideas

- RLS + user_id on existing tables → Phase 7 (user dashboard requires per-user isolation)
- Google OAuth → v2 (AUTH-V2-01)
- BYOK Anthropic key per user → v2 (COST-V2-02)
- Protected search page (require auth to search) → Not planned; search stays anonymous in v1
