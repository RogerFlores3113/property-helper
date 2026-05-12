# Phase 6: Auth - Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Add Supabase magic-link authentication to the existing Next.js + Supabase app so users can:
1. Enter their email and receive a magic link (AUTH-01)
2. Click the link and land in an authenticated session (AUTH-02)
3. Refresh or reopen the tab and remain logged in (AUTH-03)
4. Log out from any page and be returned to anonymous state with no leaked session (AUTH-04)

**In scope:** `@supabase/ssr` client setup, Next.js middleware for session refresh, `/login` page (email input), `/auth/callback` route handler, header login/logout UI on main page, environment variable `NEXT_PUBLIC_SITE_URL` for magic link redirect, no RLS changes.

**Out of scope:** RLS row-level policies (Phase 7), user_id on existing tables (Phase 7), saved searches/listings per user (Phase 7), BYOK (v2), Google OAuth (v2), password auth.

</domain>

<decisions>
## Implementation Decisions

### Auth Client Setup (AUTH-01, AUTH-02, AUTH-03)

- **D-01:** Migrate the Supabase client to `@supabase/ssr`. Add `createBrowserClient` in `lib/supabase-browser.ts` for client components and `createServerClient` in `lib/supabase-server.ts` for Server Components / Route Handlers. Keep `lib/supabase.ts` (bare client) only for Realtime subscriptions — Realtime does not use the SSR client.
- **D-02:** Add `middleware.ts` at the Next.js root to call `supabase.auth.getSession()` on every request, refresh the session cookie if needed, and forward the response. This satisfies SC#3 (session survives refresh) via cookie storage rather than localStorage.
- **D-03:** Magic link `emailRedirectTo` is set to `${NEXT_PUBLIC_SITE_URL}/auth/callback`. Add `NEXT_PUBLIC_SITE_URL=http://localhost:3000` to `.env.local` (and to Fly.io/Vercel env for prod). Supabase dashboard must whitelist this URL under Auth → URL Configuration → Redirect URLs.

### Auth UI (AUTH-01, AUTH-04)

- **D-04:** Add a minimal header bar to `app/layout.tsx`. When no session: shows a "Sign in" link to `/login`. When session is active: shows the user's email truncated + a "Sign out" button. The layout reads the session server-side via `createServerClient` so it renders correctly on first paint with no flash.
- **D-05:** `/login` page (`app/login/page.tsx`) is a Client Component with a single email input and "Send magic link" button. It calls `supabase.auth.signInWithOtp({ email, options: { emailRedirectTo } })` and shows a "Check your inbox" confirmation message. No password field.
- **D-06:** Sign out uses `supabase.auth.signOut()` from a Client Component button in the header. After sign-out, redirect to `/` (main search page) in anonymous state. No server action needed — client-side sign-out is sufficient.

### Callback Route (AUTH-02, AUTH-03)

- **D-07:** Add `app/auth/callback/route.ts` (Next.js Route Handler). It reads the `code` query param from the magic link URL, calls `supabase.auth.exchangeCodeForSession(code)`, and redirects to `/`. If `code` is missing or exchange fails, redirect to `/login?error=auth_failed`. This is the official Supabase Next.js App Router pattern.

### RLS (intentionally deferred)

- **D-08:** Do NOT enable RLS or add user_id columns in Phase 6. Existing `search_jobs`, `listings`, and `daily_spend` tables remain anon-accessible. RLS + user-scoping (so each user only sees their own jobs) is Phase 7's concern, when we need per-user saved searches and history. Adding it now would break the existing anonymous search flow without the dashboard to benefit from it.

### Claude's Discretion

- Loading/error states on the login form (spinner, disabled button during OTP request)
- Exact header layout/styling — should match the existing Tailwind/zinc-900 design system
- Whether the header is sticky or static

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Auth Requirements
- `.planning/REQUIREMENTS.md` §Authentication — AUTH-01 through AUTH-04 (4 requirements, all pending)

### Existing Schema
- `supabase/migrations/20250101000001_init.sql` — Current table schema; note the `-- TODO(Phase 6): Enable RLS` comment (intentionally deferred to Phase 7 per D-08)
- `supabase/migrations/20260512000002_cache_dedup_freshness.sql` — Phase 5 additions (expires_at, dedup_key, filter_hash)

### Existing Frontend Patterns
- `frontend/lib/supabase.ts` — Bare supabase-js client used for Realtime; this is NOT the SSR auth client. Keep for Realtime subscriptions only.
- `frontend/app/layout.tsx` — Root layout to extend with session-aware header
- `frontend/app/page.tsx` — Main search page; uses `supabase` from `lib/supabase.ts` for Realtime subscriptions (not affected by auth client migration)

### Official Supabase Patterns
- Supabase Next.js App Router Auth guide: https://supabase.com/docs/guides/auth/server-side/nextjs (reference for @supabase/ssr setup, middleware, callback route)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/lib/supabase.ts` (`createClient`): Keep for Realtime subscriptions in `page.tsx`. The new SSR-aware browser client (`createBrowserClient`) lives in a separate file to avoid conflicts.
- `frontend/app/layout.tsx`: Already a Server Component — extend it to read the session server-side via `createServerClient` without adding `'use client'`.
- Tailwind + zinc-900 design system: Header should use `bg-white border-b border-zinc-200` or similar to match the existing page aesthetic.

### Established Patterns
- Client Components are marked `'use client'` at the top (e.g., `page.tsx`, `SearchForm.tsx`). The `/login` page and auth header button follow this pattern.
- Environment variables: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are already wired in `.env.local`. Add `NEXT_PUBLIC_SITE_URL`.
- Supabase client import path: `@/lib/supabase` (alias already configured in `tsconfig.json`). New SSR clients follow the same alias pattern.

### Integration Points
- `app/layout.tsx` wraps all pages — the auth header lives here. It reads the session using `createServerClient` (SSR) so no flicker on load.
- `/auth/callback/route.ts` is a new Route Handler only — no UI component.
- The `/login` page is a standalone route; the existing `page.tsx` (main search) is NOT gated behind auth in Phase 6 (auth is additive, not a gate).

</code_context>

<specifics>
## Specific Ideas

- Magic link flow only — no password, no OAuth in Phase 6 (per REQUIREMENTS.md AUTH-01/02 and phase scope)
- Session must survive full browser refresh (AUTH-03) — this is why `@supabase/ssr` + cookie storage is required over the default localStorage approach
- Logout must produce zero leaked session state (AUTH-04) — `signOut()` clears both the cookie and any in-memory state

</specifics>

<deferred>
## Deferred Ideas

- **RLS + user_id on existing tables** — Phase 7. When saved searches and per-user listing shortcuts require per-user isolation, add `user_id uuid REFERENCES auth.users(id)` to `search_jobs` and enable RLS. Do NOT do this in Phase 6.
- **Google OAuth** — v2 (AUTH-V2-01). Magic link is sufficient for v1.
- **BYOK (Anthropic key per user)** — v2 (COST-V2-02). Requires encrypted key storage, not planned until post-v1.
- **Protected search page** — Keeping the main search page anonymous in Phase 6. Phase 7 Dashboard is where user identity becomes load-bearing.

</deferred>

---

*Phase: 6-Auth*
*Context gathered: 2026-05-12*
