# Phase 6: Auth - Research

**Researched:** 2026-05-12
**Domain:** Supabase magic-link authentication on Next.js 15 App Router (`@supabase/ssr` cookie-based sessions)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Migrate to `@supabase/ssr`. Add `createBrowserClient` in `lib/supabase-browser.ts` for client components and `createServerClient` in `lib/supabase-server.ts` for Server Components / Route Handlers. Keep `lib/supabase.ts` (bare client) only for Realtime subscriptions.
- **D-02:** Add `middleware.ts` at Next.js root to refresh session cookie on every request, forward the response.
- **D-03:** Magic link `emailRedirectTo = ${NEXT_PUBLIC_SITE_URL}/auth/callback`. Add `NEXT_PUBLIC_SITE_URL=http://localhost:3000` to `.env.local`. Supabase dashboard whitelist required under Auth → URL Configuration → Redirect URLs.
- **D-04:** Session-aware header in `app/layout.tsx` (Server Component reads session via `createServerClient`, shows login/logout, no flash).
- **D-05:** `/login` page (`app/login/page.tsx`) is a Client Component — single email input + "Send magic link" button → `signInWithOtp({ email, options: { emailRedirectTo } })`. Shows "Check your inbox" confirmation.
- **D-06:** Sign out via `supabase.auth.signOut()` from a Client Component button, then redirect to `/`.
- **D-07:** `/auth/callback/route.ts` reads `code` query param, calls `supabase.auth.exchangeCodeForSession(code)`, redirects to `/`. On failure → `/login?error=auth_failed`.
- **D-08:** NO RLS changes. Tables remain anon-accessible. Deferred to Phase 7.

### Claude's Discretion

- Loading/error states on the login form (spinner, disabled button during OTP request)
- Exact header layout/styling — match existing Tailwind/zinc-900 design system
- Whether the header is sticky or static

### Deferred Ideas (OUT OF SCOPE)

- RLS + `user_id` on existing tables → Phase 7
- Google OAuth → v2 (AUTH-V2-01)
- BYOK → v2 (COST-V2-02)
- Gating the main search page behind auth → Phase 7 (Dashboard)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AUTH-01 | User can sign up with email and receive magic link | `signInWithOtp({ email, options: { emailRedirectTo, shouldCreateUser: true } })` (default `shouldCreateUser=true`). Supabase auto-creates `auth.users` row on first send. |
| AUTH-02 | User can log in via magic link, no password | Magic link click hits `/auth/callback?code=...`; route handler runs `exchangeCodeForSession(code)`; cookie is set; redirect to `/`. |
| AUTH-03 | Session persists across refresh and tab reopen | `@supabase/ssr` stores session in **HTTP cookies** (not localStorage). Middleware refreshes the token on every request via `supabase.auth.getUser()`. Cookies survive refresh and reopen by definition. |
| AUTH-04 | User can log out from any page | `supabase.auth.signOut()` from a Client Component button (header lives in `app/layout.tsx`, so it's available on every page). `signOut()` clears cookies on all configured scopes (local + global server-side revoke). |
</phase_requirements>

## Summary

`@supabase/ssr` (v0.10.3, published 2026-05-07) is the current and only supported way to do server-rendered Supabase auth in Next.js. It replaced `@supabase/auth-helpers-nextjs`, which is deprecated. The package ships PKCE flow as the **default** for cookie-stored sessions — `signInWithOtp` automatically uses PKCE when called from a `createBrowserClient`. The browser sets a PKCE code verifier cookie before redirecting to the email provider; the magic-link URL contains a `?code=...` parameter; the `/auth/callback` route handler exchanges that code for a session cookie via `exchangeCodeForSession`. **D-07 is therefore correct as written.**

The canonical Next.js + Supabase example (vercel/next.js `examples/with-supabase`) defines the exact patterns this phase needs: a `lib/supabase/client.ts` browser factory, a `lib/supabase/server.ts` async server factory using `cookies()` from `next/headers`, and a middleware helper that calls `supabase.auth.getUser()` (or `getClaims()`) inside `updateSession()` to refresh the cookie. The strict contract is: **use ONLY `getAll`/`setAll` — never `get`/`set`/`remove`** — and **return the exact `supabaseResponse` object** the middleware created, copying cookies if you must wrap it.

There is one easily-misread subtlety worth flagging up front: the rest of the Supabase docs increasingly show `verifyOtp({ token_hash, type })` against an `/auth/confirm` route. That pattern requires customizing the magic-link email template to use `{{ .TokenHash }}`. The default Supabase email template uses `{{ .ConfirmationURL }}`, which produces a `?code=` URL and works directly with `exchangeCodeForSession` — matching D-07. The plan should keep the default template; no Supabase dashboard email-template edit is required.

**Primary recommendation:** Follow the vercel/next.js `examples/with-supabase` skeleton verbatim for client/server factories and the middleware helper. Use `exchangeCodeForSession` against the default `{{ .ConfirmationURL }}` template per D-07. Do NOT introduce `verifyOtp`/`token_hash` unless the user later asks for OTP codes instead of links.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Magic-link email sending | Supabase Auth service (backend SaaS) | Frontend Server (calls `signInWithOtp`) | Supabase handles SMTP, token signing, email template. Client only triggers it. |
| Session cookie storage | Browser (HTTP cookies) | Frontend Server (sets via `Set-Cookie`) | Cookies are written by middleware/route handlers and read by both browser and server. |
| Session refresh on every request | Frontend Server (Next.js middleware) | — | Middleware is the only layer that can rewrite `Set-Cookie` on every navigation before the page renders. |
| PKCE code-verifier handling | `@supabase/ssr` library | Browser (cookie) | The lib stores `code_verifier` in a cookie automatically when `signInWithOtp` runs in the browser; the callback route reads it via the same cookie store. |
| Auth code → session exchange | Frontend Server (`/auth/callback` route handler) | — | Must be server-side because the route sets the session cookie; client-side exchange would not persist to SSR reads. |
| Session-aware header rendering | Frontend Server (Server Component in layout) | Browser (sign-out button is Client Component) | Server-side read avoids flash-of-unauth UI on first paint. |
| Sign-out | Browser (Client Component button) | Supabase Auth service (revokes refresh token) | `signOut()` runs in the browser, clears local cookies, and calls Supabase to revoke server-side. |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@supabase/ssr` | 0.10.3 (2026-05-07) | Cookie-aware Supabase client for Next.js App Router | Official replacement for deprecated `@supabase/auth-helpers-nextjs`. Sole supported SSR path. `[VERIFIED: npm view @supabase/ssr]` |
| `@supabase/supabase-js` | 2.105.4 (already installed: ^2.105) | Underlying auth + Realtime APIs | Peer dep of `@supabase/ssr` (`^2.105.3`). Already in `frontend/package.json`. `[VERIFIED: npm view]` |
| `next` | ^15 (already installed) | App Router framework | Locked by project. middleware.ts is the standard cookie-refresh hook in Next.js 15. `[VERIFIED: frontend/package.json]` |

**Note on Next.js 16:** The vercel example uses Next.js 16 canary, which renamed `middleware.ts` → `proxy.ts`. **This project is on Next.js 15**, so the file MUST be `middleware.ts`. The internal helper name (`updateSession`) and content are identical. `[CITED: nextjs.org/docs/15/pages/api-reference/file-conventions/middleware]`

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@testing-library/react` | ^16.3 (installed) | Component tests | Login page form behavior, header session states |
| `@testing-library/user-event` | ^14.6 (installed) | User interaction simulation | "type email + click send" flow |
| `vitest` | ^4.1 (installed) | Test runner | Already wired in `vitest.config.ts` with jsdom |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@supabase/ssr` | `@supabase/auth-helpers-nextjs` | **Deprecated.** Do not use. `[CITED: supabase troubleshooting migration guide]` |
| `exchangeCodeForSession` (D-07) | `verifyOtp({ token_hash, type })` against `/auth/confirm` | Requires editing Supabase email template to use `{{ .TokenHash }}`. More moving parts. D-07's choice is simpler and matches the default template. `[CITED: supabase.com/docs/guides/auth/auth-email-passwordless]` |
| Cookie storage (default in `@supabase/ssr`) | localStorage (bare `@supabase/supabase-js` default) | localStorage cannot be read server-side → can't render the layout's auth-aware header without a client-side hydration flash. Cookies fix this. `[CITED: vercel example]` |

**Installation:**
```bash
cd frontend
npm install @supabase/ssr@^0.10.3
```

`@supabase/supabase-js` is already installed and satisfies the peer dependency.

**Version verification (2026-05-12):**
- `@supabase/ssr` 0.10.3, published 2026-05-07 (5 days ago — current) `[VERIFIED: npm view]`
- `@supabase/supabase-js` 2.105.4 (peer-satisfying version installed: ^2.105) `[VERIFIED: npm view]`

## Architecture Patterns

### System Architecture Diagram

```
                            ┌────────────────────────┐
                            │ Supabase Auth (SaaS)   │
                            │  - sends magic email   │
                            │  - signs JWT           │
                            │  - revokes on signOut  │
                            └─────────┬──────────────┘
                                      │
              signInWithOtp           │ magic link in email
                  (HTTPS)             │ → user clicks
                      │               ▼
   ┌──────────────────┴───────────────────────────────────┐
   │ Browser                                              │
   │  ┌───────────────┐    ┌──────────────────────────┐  │
   │  │ /login        │    │ Session-aware header     │  │
   │  │ (Client Comp) │    │ (rendered by layout SSR) │  │
   │  │   uses        │    │   shows email + sign-out │  │
   │  │ createBrowser │    │   sign-out button uses   │  │
   │  │   Client      │    │   createBrowserClient    │  │
   │  └───────────────┘    └──────────────────────────┘  │
   │       │                              │              │
   │       │ writes pkce code_verifier    │ reads        │
   │       │ cookie + sb-* session cookies│ session      │
   │       ▼                              │ cookie       │
   └──────────────┬───────────────────────┴──────────────┘
                  │ all HTTP requests
                  ▼
   ┌──────────────────────────────────────────────────────┐
   │ Next.js Frontend Server (Vercel)                     │
   │                                                      │
   │  ┌──────────────────────────────────────────────┐    │
   │  │ middleware.ts (root)                         │    │
   │  │   updateSession(request):                    │    │
   │  │     - createServerClient w/ request cookies  │    │
   │  │     - supabase.auth.getUser()  ← refreshes   │    │
   │  │     - returns response w/ refreshed cookies  │    │
   │  └──────────────────────────────────────────────┘    │
   │                                                      │
   │  ┌──────────────────────────────────────────────┐    │
   │  │ app/auth/callback/route.ts                   │    │
   │  │   GET: code = searchParams.code              │    │
   │  │     exchangeCodeForSession(code)             │    │
   │  │     redirect("/")                            │    │
   │  └──────────────────────────────────────────────┘    │
   │                                                      │
   │  ┌──────────────────────────────────────────────┐    │
   │  │ app/layout.tsx (Server Component)            │    │
   │  │   const supabase = await createClient()      │    │
   │  │   const { data: { user } } = await           │    │
   │  │     supabase.auth.getUser()                  │    │
   │  │   <Header user={user} />                     │    │
   │  └──────────────────────────────────────────────┘    │
   └──────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
frontend/
├── middleware.ts                       # NEW — root middleware (calls updateSession)
├── lib/
│   ├── supabase.ts                     # KEEP — bare client for Realtime only
│   └── supabase/
│       ├── client.ts                   # NEW — createBrowserClient factory
│       ├── server.ts                   # NEW — createServerClient factory (uses cookies())
│       └── middleware.ts               # NEW — updateSession helper (imported by root middleware.ts)
├── app/
│   ├── layout.tsx                      # MODIFY — Server Component reads session, renders header
│   ├── login/
│   │   └── page.tsx                    # NEW — Client Component with signInWithOtp
│   ├── auth/
│   │   └── callback/
│   │       └── route.ts                # NEW — Route Handler, exchangeCodeForSession
│   └── components/
│       └── SignOutButton.tsx           # NEW — Client Component, calls signOut() then router.push('/')
```

CONTEXT.md D-01 names the files as `lib/supabase-browser.ts` and `lib/supabase-server.ts` (flat). The vercel example uses `lib/supabase/{client,server,middleware}.ts` (nested). Either works; pick one and be consistent. The flat naming in D-01 is fine and arguably clearer alongside the existing `lib/supabase.ts`.

### Pattern 1: Browser Client Factory

```typescript
// lib/supabase-browser.ts (or lib/supabase/client.ts)
// Source: github.com/vercel/next.js examples/with-supabase/lib/supabase/client.ts
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
```

Call as `const supabase = createClient()` inside Client Components. Do NOT cache at module scope across renders.

### Pattern 2: Server Client Factory

```typescript
// lib/supabase-server.ts (or lib/supabase/server.ts)
// Source: github.com/vercel/next.js examples/with-supabase/lib/supabase/server.ts
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // setAll called from a Server Component (read-only context).
            // Safe to ignore because middleware refreshes the cookie.
          }
        },
      },
    },
  );
}
```

The `try/catch` is **mandatory**. Server Components have a read-only cookie store; without the catch, layout.tsx will throw whenever it reads the session.

### Pattern 3: Middleware Helper

```typescript
// lib/supabase-middleware.ts (or lib/supabase/middleware.ts)
// Source: adapted from github.com/vercel/next.js examples/with-supabase/lib/supabase/proxy.ts
import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // CRITICAL: do not place ANY code between createServerClient and getUser().
  // The library uses this call to detect whether a token refresh is needed.
  await supabase.auth.getUser();

  // CRITICAL: must return the supabaseResponse object as-is. If you wrap it,
  // copy cookies via myNewResponse.cookies.setAll(supabaseResponse.cookies.getAll()).
  return supabaseResponse;
}
```

```typescript
// middleware.ts (root of frontend/)
import { updateSession } from "@/lib/supabase-middleware";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    // Run on everything except static assets
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
```

The plan-checker should reject any task that adds redirect logic between `createServerClient` and `getUser()`, or that returns a freshly-constructed `NextResponse` without copying cookies.

### Pattern 4: /auth/callback Route Handler

```typescript
// app/auth/callback/route.ts
import { createClient } from "@/lib/supabase-server";
import { NextResponse, type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (!code) {
    return NextResponse.redirect(`${origin}/login?error=auth_failed`);
  }

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(`${origin}/login?error=auth_failed`);
  }

  return NextResponse.redirect(`${origin}${next}`);
}
```

The `origin` from the parsed URL is preferred over `NEXT_PUBLIC_SITE_URL` here — it correctly handles preview deploys and localhost without re-reading env. `[CITED: supabase.com/docs/guides/auth/server-side/nextjs sample]`

### Pattern 5: Login Page (Client Component)

```typescript
// app/login/page.tsx
'use client';

import { useState } from "react";
import { createClient } from "@/lib/supabase-browser";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
      },
    });
    setLoading(false);
    if (error) setError(error.message);
    else setSent(true);
  }

  if (sent) return <p>Check your inbox for a magic link.</p>;
  return (
    <form onSubmit={onSubmit}>
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        disabled={loading}
      />
      <button type="submit" disabled={loading || !email}>
        {loading ? "Sending…" : "Send magic link"}
      </button>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}
```

### Pattern 6: Session-Aware Header in Layout

```typescript
// app/layout.tsx (Server Component — no 'use client')
import { createClient } from "@/lib/supabase-server";
import { SignOutButton } from "@/app/components/SignOutButton";
import Link from "next/link";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  return (
    <html lang="en">
      <body>
        <header className="border-b border-zinc-200">
          {user
            ? <><span>{user.email}</span><SignOutButton /></>
            : <Link href="/login">Sign in</Link>}
        </header>
        {children}
      </body>
    </html>
  );
}
```

### Pattern 7: Sign-Out Button (Client Component)

```typescript
// app/components/SignOutButton.tsx
'use client';
import { createClient } from "@/lib/supabase-browser";
import { useRouter } from "next/navigation";

export function SignOutButton() {
  const router = useRouter();
  async function onClick() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh(); // re-renders layout server-side so header flips to anon state
  }
  return <button onClick={onClick}>Sign out</button>;
}
```

The `router.refresh()` is the non-obvious correct touch: without it, the Server Component layout will still show the cached user email until the next navigation, leaking the impression of a stale session even though the cookie is cleared.

### Anti-Patterns to Avoid

- **Using `get`/`set`/`remove` instead of `getAll`/`setAll`** — `@supabase/ssr` requires only the array forms. The single-cookie forms break refresh-token rotation. `[CITED: supabase docs]`
- **Putting code between `createServerClient` and `getUser()` in middleware** — Documented as a cause of "users randomly logged out" bugs. `[CITED: vercel example proxy.ts comments]`
- **Returning a new `NextResponse` from middleware without copying `supabaseResponse.cookies`** — Same bug as above, surfaced differently.
- **Reading `auth.getSession()` in middleware/server code without validation** — `getSession()` reads the cookie without verifying the JWT signature. Use `getUser()` (which contacts the auth server) or `getClaims()` (which validates locally) for any branching decision. `[CITED: supabase.com/docs/guides/auth/server-side/creating-a-client]`
- **Caching the SSR client across requests in a module-scope variable** — Documented warning in the vercel example: "Especially important if using Fluid compute: Don't put this client in a global variable. Always create a new client within each function." `[CITED: vercel example server.ts]`
- **Using `localStorage` for the session (the bare `@supabase/supabase-js` default)** — Server cannot read it; SSR header will flash anonymous before hydrating.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cookie name management for refresh tokens | Custom cookie parsing | `@supabase/ssr` `getAll`/`setAll` | Cookie names contain hashes of the project ref; getting them wrong breaks silently. |
| Session refresh on token expiry | Manual refresh-token call in a `useEffect` | `middleware.ts` + `getUser()` | The library coordinates the refresh, sets new cookies, and avoids race conditions across tabs. |
| PKCE code verifier storage | Manual `localStorage` write | Trust `@supabase/ssr` default | The library writes/reads the verifier cookie automatically; manual handling breaks the flow. |
| Magic-link URL parsing | Regex on the email URL | `exchangeCodeForSession(code)` | Supabase signs codes; only the SDK validates them correctly. |
| "Am I logged in?" client-side polling | `setInterval` + `getSession` | Layout SSR read + `router.refresh()` after sign-out | Polling wastes requests; SSR is the source of truth and Next.js cache invalidation propagates correctly. |

**Key insight:** Auth is exactly the area where hand-rolling silently produces "works in dev, breaks in prod" bugs. Use the vercel/next.js skeleton verbatim.

## Common Pitfalls

### Pitfall 1: Supabase Redirect URL Not Whitelisted

**What goes wrong:** User clicks magic link → redirects to a Supabase error page or a wrong host.
**Why it happens:** Supabase enforces an allowlist on every redirect target.
**How to avoid:** In Supabase Dashboard → **Authentication → URL Configuration**, add **all** of:
- `http://localhost:3000/auth/callback` (local dev)
- `http://localhost:3000/**` (local wildcard, helps in dev)
- The Vercel production URL: `https://<prod-host>/auth/callback`
- Any preview-deploy patterns if Vercel branch previews are in use (e.g., `https://<project>-*.vercel.app/auth/callback`)

Also set the **Site URL** to the production URL. `[CITED: supabase.com/docs/guides/auth/redirect-urls]`
**Warning signs:** Magic link works locally but fails in prod with `?error=...` in URL.

### Pitfall 2: Middleware Infinite Loop / Redirect Loop

**What goes wrong:** Browser shows "ERR_TOO_MANY_REDIRECTS" when navigating.
**Why it happens:** Middleware redirects unauthenticated users to `/login`, but `/login` itself also runs through middleware. If the middleware also redirects `/auth/callback` away when unauthenticated, the magic-link callback never lands.
**How to avoid:** In Phase 6 the plan is **NOT** to redirect-protect any route (no D-08 RLS, no gated pages). Keep the middleware purely as a session-refresh layer: call `getUser()` and return. Do NOT add redirect logic in this phase. The vercel example's redirect-to-login logic is **out of scope** for Phase 6.
**Warning signs:** Adding any `if (!user) redirect(...)` block in middleware before the search page is ready for it.

### Pitfall 3: NEXT_PUBLIC_SITE_URL Mismatch

**What goes wrong:** Magic link points to `localhost:3000` in production, or to `127.0.0.1` when the dashboard whitelist has `localhost`.
**Why it happens:** `NEXT_PUBLIC_SITE_URL` is read at build time on Vercel. If unset on Vercel, it falls back to `undefined` → emailRedirectTo is `undefined/auth/callback`.
**How to avoid:**
- Set `NEXT_PUBLIC_SITE_URL` in Vercel project env vars (Production + Preview + Development).
- Use `http://localhost:3000` (not `127.0.0.1`) locally, matching what dev servers print.
- Consider using `origin` from `headers()` server-side as a runtime fallback if the constant is missing.

### Pitfall 4: Cookie Name Conflicts with Existing `lib/supabase.ts`

**What goes wrong:** Two Supabase clients (the bare one and the SSR one) both run in the same browser tab; the bare client's default localStorage session and the SSR cookie session diverge; Realtime subscriptions auth differently than the rest of the app.
**Why it happens:** Both clients use the same project ref by default.
**How to avoid:**
- Keep `lib/supabase.ts` (bare) ONLY for `supabase.from('listings').on('postgres_changes', ...)` Realtime subscriptions. Do NOT call `auth.*` methods on it.
- In Phase 6, Realtime is anon-scoped (no RLS yet — D-08), so the bare client's lack of session is fine.
- Phase 7 (when RLS arrives) will need to migrate Realtime subscriptions to receive an authenticated client, but that's out of scope here. Note this in the deferred section of PLAN.md.

**Warning signs:** Realtime subscription stops working after sign-in (would only happen if RLS is enabled later — N/A for Phase 6).

### Pitfall 5: `'next/headers' cookies()` is Async in Next.js 15

**What goes wrong:** `TypeError: cookieStore.getAll is not a function` in tests or runtime.
**Why it happens:** Next.js 15 made `cookies()` from `next/headers` return a Promise. Older snippets call it synchronously.
**How to avoid:** Always `const cookieStore = await cookies();` (note the `await`). The factory function must be `async`. `[CITED: nextjs.org/docs/15 — dynamic API change]`
**Warning signs:** `.getAll` undefined errors in `lib/supabase-server.ts`.

### Pitfall 6: Magic Link URL Strips the `code` Param

**What goes wrong:** `/auth/callback?error=auth_failed` every time.
**Why it happens:**
1. The default email template uses `{{ .ConfirmationURL }}` which produces `?code=...`. Some custom templates have stripped or renamed it.
2. The `code` parameter is single-use and expires in 5 minutes — re-clicking an old link fails.
3. PKCE requires the same browser instance that called `signInWithOtp` to also handle the callback (the `code_verifier` cookie is browser-scoped). Opening the email link in a different browser or in incognito fails the exchange.

**How to avoid:**
- Keep the default email template (no edit needed for D-07's flow).
- On failure, route to `/login?error=auth_failed` and tell the user to request a fresh link.
- Document the "same browser" constraint in the inbox-confirmation message: *"Open the link in the same browser you used here."*

### Pitfall 7: `signOut()` Doesn't Clear Cookies Synchronously

**What goes wrong:** After clicking sign-out, the header still shows the user's email until navigation.
**Why it happens:** `signOut()` clears local storage and calls the server, but the Server Component layout was already rendered with the old cookie value. The browser's cookie deletion happens before SSR-cached HTML is replaced.
**How to avoid:** After `signOut()`, call BOTH `router.push("/")` AND `router.refresh()` to force the Server Component to re-render with no user. Shown in Pattern 7 above.

## Runtime State Inventory

This is a greenfield phase (new files, no rename/migration of existing data). Inventory still completed for diligence:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `auth.users` rows created automatically by Supabase on first `signInWithOtp` — no manual migration. Existing `search_jobs`, `listings`, `daily_spend` tables have NO `user_id` column (D-08 defers). | None in Phase 6. |
| Live service config | Supabase project's **Auth → URL Configuration** must add `${NEXT_PUBLIC_SITE_URL}/auth/callback` to Redirect URLs. Set Site URL to the prod host. This is a **dashboard change**, not git. | Document in PLAN as a one-time manual step with a verification screenshot. |
| OS-registered state | None. | — |
| Secrets / env vars | New: `NEXT_PUBLIC_SITE_URL` in `.env.local` (=`http://localhost:3000`) and Vercel env (=prod URL). Existing `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` reused. | Add to `.env.local.example` if it exists; add to Vercel dashboard. |
| Build artifacts | None — no installed CLI binaries are renamed. New `node_modules/@supabase/ssr` after `npm install`. | Standard `npm install`. |

**The canonical question:** *After every file is updated, what runtime systems still need configuration?* → **Only the Supabase Dashboard Redirect URLs.** That's the single non-code change.

## Code Examples

All verified patterns are inlined in **Architecture Patterns** above (Patterns 1–7). Sources:
- `lib/supabase/client.ts` and `lib/supabase/server.ts` — verbatim from [vercel/next.js examples/with-supabase](https://github.com/vercel/next.js/tree/canary/examples/with-supabase/lib/supabase)
- Middleware helper — adapted from `examples/with-supabase/lib/supabase/proxy.ts` (renamed `proxy.ts` → `middleware.ts` for Next.js 15)
- `/auth/callback` route handler — pattern from [supabase.com/docs/guides/auth/server-side/nextjs](https://supabase.com/docs/guides/auth/server-side/nextjs)
- `signInWithOtp` call — official API reference

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@supabase/auth-helpers-nextjs` | `@supabase/ssr` | Deprecated 2024; SSR is the only supported path on App Router | Plans using auth-helpers patterns are obsolete |
| Cookie shape: `get`/`set`/`remove` | `getAll`/`setAll` | `@supabase/ssr` 0.x → required form | Older snippets break refresh-token rotation if mixed |
| `verifyOtp({ token, type })` with `{{ .Token }}` numeric OTP code | Default magic-link `{{ .ConfirmationURL }}` + `exchangeCodeForSession(code)` for PKCE | PKCE became default in `@supabase/ssr` | Plan D-07 is on the modern path |
| `middleware.ts` | `proxy.ts` (Next.js 16 only) | Next.js 16 canary rename | **Not applicable** — project is on Next.js 15, keep `middleware.ts` |
| `auth.getSession()` for branching | `auth.getUser()` (server-validated) or `auth.getClaims()` (locally validated, faster, available `@supabase/ssr` 0.10+) | 2025 | Use `getUser()` in middleware/layout; never trust `getSession()` for auth decisions |

**Deprecated / outdated:**
- `@supabase/auth-helpers-nextjs` — **do not import**.
- Any pattern that reads `session` from `getSession()` and trusts it for access control.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `lib/supabase.ts` (bare client) used for Realtime continues to work without the SSR session (anon-only, no RLS in Phase 6 per D-08) | Pitfall 4 | Low — D-08 explicitly defers RLS; bare client + anon Realtime is the current working state |
| A2 | `.env.local.example` may not exist; only `.env.local` was inspected (which is gitignored) | Runtime State Inventory | Low — planner should check for `.env.example` / `.env.local.example` during planning |
| A3 | The Supabase project's default email template still uses `{{ .ConfirmationURL }}` (the Supabase default, never edited in this project) | Pitfall 6 | Medium — if someone previously edited the template to use `{{ .TokenHash }}`, D-07's `exchangeCodeForSession` will fail and `verifyOtp` would be needed. Verifiable by inspecting the dashboard's **Auth → Email Templates → Magic Link** body. |

## Open Questions

1. **Vercel production URL for `NEXT_PUBLIC_SITE_URL`**
   - What we know: Frontend hosts on Vercel Hobby (per CLAUDE.md).
   - What's unclear: The actual production domain isn't recorded in `.planning/`.
   - Recommendation: Plan should include "human action: confirm Vercel production URL and add to (a) Vercel env vars, (b) Supabase dashboard Redirect URLs" as an explicit gated step. Until then, local dev (`http://localhost:3000`) is fully testable.

2. **Should the Realtime subscription on the home page be migrated to the SSR browser client?**
   - What we know: D-01 says keep `lib/supabase.ts` for Realtime only.
   - What's unclear: Once a user is signed in, should Realtime subscriptions present their identity (e.g., for future RLS-scoped channels)? Phase 7 will need to address this.
   - Recommendation: Stay on the bare client in Phase 6. Add a TODO comment in `lib/supabase.ts` pointing to Phase 7.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js + npm | Install `@supabase/ssr` | ✓ (project already runs Next.js) | — | — |
| Supabase project (dashboard access) | Whitelist Redirect URLs | ✓ (project active, migrations applied) | — | — |
| Supabase SMTP (built-in, free tier) | Sending magic-link emails | ✓ (built-in) | — | Configure custom SMTP only if rate limits hit (4 emails/hour on free tier — likely sufficient for v1) |
| Email inbox for testing | Magic-link click-through | ✓ (developer email) | — | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — but flag that **Supabase free-tier built-in SMTP is rate-limited to ~2–4 emails/hour per recipient**. Friends-and-family launch is fine; if testing burns through limits, plan a fallback to a free SMTP provider (Resend free tier, etc.). `[CITED: supabase.com/docs/guides/auth/auth-smtp]`

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.6 + @testing-library/react 16.3 + jsdom 29.1 |
| Config file | `frontend/vitest.config.ts` (exists; jsdom + setupFiles `./vitest.setup.ts`) |
| Quick run command | `cd frontend && npm test -- --run <pattern>` |
| Full suite command | `cd frontend && npm test -- --run` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AUTH-01 | LoginPage submits email and calls `signInWithOtp` with correct `emailRedirectTo` | unit (component) | `npm test -- --run LoginPage.test.tsx` | ❌ Wave 0 |
| AUTH-01 | LoginPage shows "Check your inbox" after successful OTP send | unit (component) | same file | ❌ Wave 0 |
| AUTH-01 | LoginPage shows error message when `signInWithOtp` returns an error | unit (component) | same file | ❌ Wave 0 |
| AUTH-02 | `/auth/callback` route handler calls `exchangeCodeForSession` with `code` query param and redirects to `/` | unit (route handler) | `npm test -- --run authCallback.test.ts` | ❌ Wave 0 |
| AUTH-02 | `/auth/callback` redirects to `/login?error=auth_failed` when `code` is missing | unit | same | ❌ Wave 0 |
| AUTH-02 | `/auth/callback` redirects to `/login?error=auth_failed` when `exchangeCodeForSession` errors | unit | same | ❌ Wave 0 |
| AUTH-03 | `middleware.updateSession` calls `getUser()` and returns the same response object (cookie-refresh contract) | unit | `npm test -- --run middleware.test.ts` | ❌ Wave 0 |
| AUTH-03 | Browser-cookie persistence across reload | **manual smoke** | dev-server flow; cannot Vitest the browser cookie jar | manual checklist |
| AUTH-04 | SignOutButton calls `signOut()` then `router.push('/')` and `router.refresh()` | unit (component) | `npm test -- --run SignOutButton.test.tsx` | ❌ Wave 0 |
| AUTH-04 | Layout renders sign-in link when `getUser()` returns no user | unit (Server Component test via render with mocked module) | `npm test -- --run layout.test.tsx` | ❌ Wave 0 |
| AUTH-04 | Layout renders user email + sign-out button when `getUser()` returns a user | unit | same | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd frontend && npm test -- --run <touched file pattern>`
- **Per wave merge:** `cd frontend && npm test -- --run`
- **Phase gate:** Full Vitest suite green + manual smoke checklist (AUTH-03 reload + AUTH-02 end-to-end via real magic link in dev)

### Wave 0 Gaps

- [ ] `frontend/__tests__/LoginPage.test.tsx` — covers AUTH-01
- [ ] `frontend/__tests__/authCallback.test.ts` — covers AUTH-02 (mock `next/server` + supabase server client)
- [ ] `frontend/__tests__/middleware.test.ts` — covers AUTH-03 cookie-refresh contract
- [ ] `frontend/__tests__/SignOutButton.test.tsx` — covers AUTH-04
- [ ] `frontend/__tests__/layout.test.tsx` — covers session-aware header (both states)
- [ ] **Shared mock helper** `frontend/__tests__/_mocks/supabase.ts` — factory that returns a Vitest-mocked Supabase client with `auth.signInWithOtp`, `auth.exchangeCodeForSession`, `auth.signOut`, `auth.getUser` stubs. Reused across all five test files.
- [ ] **`vitest.setup.ts` addition** — mock `next/headers` `cookies()` and `next/navigation` `useRouter` / `redirect` so server-side modules import cleanly under jsdom.

**Vitest mocking pattern for `@supabase/ssr`:**

```typescript
// frontend/__tests__/_mocks/supabase.ts
import { vi } from "vitest";

export function mockSupabaseClient(overrides = {}) {
  return {
    auth: {
      signInWithOtp: vi.fn().mockResolvedValue({ data: {}, error: null }),
      exchangeCodeForSession: vi.fn().mockResolvedValue({ data: {}, error: null }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
      ...overrides,
    },
  };
}

// In a test file:
vi.mock("@/lib/supabase-browser", () => ({
  createClient: () => mockSupabaseClient({
    getUser: vi.fn().mockResolvedValue({ data: { user: { id: "u1", email: "a@b.com" } } }),
  }),
}));
```

This keeps tests pure unit tests — no network, no real Supabase. Integration testing of the actual magic-link round-trip is a **manual smoke step**, not Vitest.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Supabase Auth (passwordless OTP via PKCE) — do not hand-roll |
| V3 Session Management | yes | `@supabase/ssr` cookie store; middleware refresh; `signOut()` for revocation |
| V4 Access Control | partial | No RLS in Phase 6 (D-08 defers). Tables remain anon-accessible. Phase 7 must enable RLS before any user-scoped data lands. |
| V5 Input Validation | yes (light) | Email input: HTML5 `type="email" required` + Supabase server-side validation. `code` query param: trust Supabase signature validation in `exchangeCodeForSession`. |
| V6 Cryptography | yes | Delegated entirely to Supabase (JWT signing, PKCE code verifier). Do not implement crypto. |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Open redirect via `next` param on `/auth/callback` | Tampering | Validate `next` is a relative path (starts with `/`, no `//`, no `://`). The vercel example doesn't validate — **add this check** in the route handler. |
| Magic-link replay | Spoofing | Codes are single-use and expire in 5 min (Supabase-enforced) |
| Session hijacking via XSS reading cookie | Tampering | Cookies are HttpOnly by default in `@supabase/ssr` |
| CSRF on sign-out | Tampering | Sign-out via fetch from the same origin; same-site cookies prevent cross-origin POSTs by default |
| Magic-link sent to attacker (account takeover via typo) | Spoofing | Acceptable risk for v1 with friends-and-family scope; rate-limited by Supabase |
| Redirect-URL allowlist bypass | Spoofing | Supabase enforces server-side Redirect URL allowlist (dashboard config). Plan must include this step. |

**Concrete additional security ask for the planner:** Have the `/auth/callback` route handler reject any `next` parameter that doesn't start with `/` and doesn't contain `://`. Even though Phase 6 doesn't put a user-controlled `next` into the link, defensive coding now prevents a future bug.

## Sources

### Primary (HIGH confidence)

- [vercel/next.js examples/with-supabase (lib/supabase/client.ts, server.ts, proxy.ts)](https://github.com/vercel/next.js/tree/canary/examples/with-supabase/lib/supabase) — verbatim factory and middleware code
- [Supabase docs: Server-side auth for Next.js](https://supabase.com/docs/guides/auth/server-side/nextjs) — canonical patterns
- [Supabase docs: Creating a Supabase client for SSR](https://supabase.com/docs/guides/auth/server-side/creating-a-client) — `getAll`/`setAll` contract
- [Supabase docs: Advanced guide (server-side)](https://supabase.com/docs/guides/auth/server-side/advanced-guide) — cache-header semantics and refresh requirements
- [Supabase docs: Passwordless email logins](https://supabase.com/docs/guides/auth/auth-email-passwordless) — magic-link vs OTP, template variables
- [Supabase docs: PKCE flow](https://supabase.com/docs/guides/auth/sessions/pkce-flow) — auth code and `exchangeCodeForSession`
- [Supabase docs: signInWithOtp JS reference](https://supabase.com/docs/reference/javascript/auth-signinwithotp) — API signature
- [Supabase docs: exchangeCodeForSession JS reference](https://supabase.com/docs/reference/javascript/auth-exchangecodeforsession)
- [Next.js 15 middleware docs](https://nextjs.org/docs/15/pages/api-reference/file-conventions/middleware) — matcher and file location
- `npm view @supabase/ssr` → 0.10.3 published 2026-05-07 (verified 2026-05-12)

### Secondary (MEDIUM confidence)

- [Supabase community discussion: middleware function recommendations](https://github.com/orgs/supabase/discussions/34842) — context on the deprecated `auth-helpers` patterns
- [Supabase troubleshooting: PKCE flow errors](https://supabase.com/docs/guides/troubleshooting/pkce-flow-errors-cannot-parse-response-or-zgotmplz-in-magic-link-emails-433665) — email-template pitfalls

### Tertiary (LOW confidence)

- None used for prescriptive guidance.

## Project Constraints (from CLAUDE.md)

- **Stack:** Next.js 15 App Router, TypeScript, Tailwind, Supabase. `@supabase/supabase-js ^2.105` already pinned. Add `@supabase/ssr ^0.10.3`.
- **Frontend host:** Vercel Hobby — `NEXT_PUBLIC_SITE_URL` env var must be set in Vercel project (Production, Preview, Development).
- **Auth scope (v1):** Magic-link only. NO Google OAuth (v2), NO password, NO BYOK (v2).
- **No mid-task questions:** The login flow itself is the only blocking interaction; once authenticated, no further prompts.
- **Storage budget:** `auth.users` rows are tiny; well within the 500MB Supabase free tier.
- **GSD workflow enforcement:** All file changes flow through the GSD command set; this research feeds `/gsd-plan-phase`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — npm registry confirms versions; vercel example provides verbatim code.
- Architecture: HIGH — official patterns cross-verified across vercel example + Supabase docs.
- Pitfalls: HIGH — pitfalls drawn from documented "important" callouts in the vercel example comments and Supabase troubleshooting pages.
- D-07 (`exchangeCodeForSession` vs `verifyOtp`): HIGH — both are valid, D-07 matches the default email template, no template edit needed.

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (`@supabase/ssr` is on a roughly monthly cadence; refresh if a 0.11+ ships)
