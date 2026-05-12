# Phase 6: Auth - Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 14 (8 new source + 6 test)
**Analogs found:** 12 / 14 (2 have no in-repo analog; RESEARCH.md Patterns 1–7 are the canonical source)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/lib/supabase-browser.ts` | utility (client factory) | request-response | `frontend/lib/supabase.ts` | role-match (same lib, different API surface) |
| `frontend/lib/supabase-server.ts` | utility (client factory, async) | request-response | `frontend/lib/supabase.ts` | role-match |
| `frontend/middleware.ts` | middleware | request-response | none in repo (greenfield) | none — use RESEARCH Pattern 3 |
| `frontend/app/login/page.tsx` | component (Client, page route) | request-response (form submit) | `frontend/app/components/SearchForm.tsx` | exact (Client Component, form + submit + disabled-while-loading) |
| `frontend/app/auth/callback/route.ts` | route handler | request-response | none in repo (greenfield, no existing Route Handlers) | none — use RESEARCH Pattern 4 |
| `frontend/app/layout.tsx` (MODIFY) | component (Server, root layout) | request-response (SSR read) | `frontend/app/layout.tsx` (self, current shape) | exact (extend existing) |
| `frontend/app/components/SignOutButton.tsx` | component (Client) | event-driven (click → signOut + router.refresh) | `frontend/app/components/SearchForm.tsx` | role-match (Client Component pattern + button + async handler) |
| `frontend/lib/supabase.ts` (MODIFY) | utility | streaming (Realtime) | self | exact (only add TODO comment) |
| `frontend/__tests__/_mocks/supabase.ts` | test helper (factory) | n/a | `frontend/__tests__/ListingCard.test.tsx` `makeListing()` factory | role-match (test factory convention) |
| `frontend/__tests__/LoginPage.test.tsx` | test (component) | n/a | `frontend/__tests__/SearchForm.test.tsx` | exact |
| `frontend/__tests__/authCallback.test.ts` | test (route handler) | n/a | none in repo | none — see RESEARCH §Validation Architecture |
| `frontend/__tests__/middleware.test.ts` | test (middleware) | n/a | none in repo | none — see RESEARCH §Validation Architecture |
| `frontend/__tests__/SignOutButton.test.tsx` | test (component) | n/a | `frontend/__tests__/SearchForm.test.tsx` | exact |
| `frontend/__tests__/layout.test.tsx` | test (Server Component) | n/a | `frontend/__tests__/ListingCard.test.tsx` | role-match (RTL render; mocks server module) |

## Pattern Assignments

### `frontend/lib/supabase-browser.ts` (utility, client factory)

**Analog:** `frontend/lib/supabase.ts` (lines 1–7)

**Imports + factory pattern to mirror:**
```ts
// frontend/lib/supabase.ts (current)
import { createClient } from '@supabase/supabase-js';

export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);
```

**Difference from analog:** Existing file uses module-level singleton `export const`. The browser SSR client MUST be a function (no module caching) per RESEARCH §Anti-Patterns. Match the env-var access style (`process.env.NEXT_PUBLIC_SUPABASE_URL!` non-null assertion) and the alias-based import. New body comes verbatim from RESEARCH §Pattern 1.

---

### `frontend/lib/supabase-server.ts` (utility, async server factory)

**Analog:** `frontend/lib/supabase.ts` (env-var access only)

**Pattern:** Same env-var access (`process.env.NEXT_PUBLIC_SUPABASE_URL!`, non-null bang). New body comes from RESEARCH §Pattern 2 verbatim. Critical: `async function createClient()` + `await cookies()` (Next.js 15 — see RESEARCH Pitfall 5) and the `try { ... } catch {}` around `cookieStore.set` is mandatory.

---

### `frontend/middleware.ts` + `frontend/lib/supabase-middleware.ts` (middleware)

**Analog:** none in repo.

**Source:** RESEARCH §Pattern 3 verbatim. Two files:
1. `lib/supabase-middleware.ts` — `updateSession(request)` helper. Critical contract: NO code between `createServerClient(...)` and `await supabase.auth.getUser()`. Return `supabaseResponse` as-is.
2. `middleware.ts` at frontend root — thin shim that calls `updateSession`, plus `export const config = { matcher: [...] }` excluding static assets.

**Phase-6 constraint (RESEARCH Pitfall 2):** Do NOT add `if (!user) redirect('/login')`. Middleware is session-refresh-only this phase.

---

### `frontend/app/login/page.tsx` (component, Client)

**Analog:** `frontend/app/components/SearchForm.tsx`

**'use client' + useState pattern** (lines 1–17):
```tsx
'use client';

import { useRef, useState } from 'react';
// ... typed props ...
export function SearchForm({ inFlight, onSubmit }: SearchFormProps) {
  const [query, setQuery] = useState<string>('');
```
Copy the `'use client'` directive placement and the `useState<string>('')` typing convention.

**Async submit + disabled-while-inflight pattern** (lines 44–48, 51–61, 90–96):
```tsx
function handleSubmit(e: React.FormEvent) {
  e.preventDefault();
  if (inFlight || !query.trim()) return;
  onSubmit({ ... });
}
// ...
<form onSubmit={handleSubmit} className="flex flex-col gap-3">
  <textarea
    value={query}
    onChange={handleChange}
    disabled={inFlight}
    autoFocus
    aria-label="..."
    className="w-full rounded border border-zinc-300 p-2 text-sm disabled:bg-zinc-100 disabled:cursor-not-allowed"
  />
  ...
  <button
    type="submit"
    disabled={inFlight || !query.trim()}
    className="self-start rounded bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed"
  >
    {inFlight ? 'Searching…' : 'Search apartments'}
  </button>
</form>
```
**Copy:** `e.preventDefault()` guard, `disabled={loading || !email}` style, Tailwind zinc-900/zinc-300 design tokens, `aria-label` on inputs, the `{loading ? 'Sending…' : 'Send magic link'}` ternary on submit-button text.

**Body (auth-specific) from RESEARCH §Pattern 5** — `signInWithOtp({ email, options: { emailRedirectTo } })`, `sent`/`error`/`loading` state triad.

**Error state pattern from `frontend/app/page.tsx`** (lines 293–297):
```tsx
{error && (
  <div className="mt-6 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-700" role="alert">
    {error}
  </div>
)}
```
Reuse this exact error-banner styling for `signInWithOtp` errors.

---

### `frontend/app/auth/callback/route.ts` (route handler)

**Analog:** none in repo.

**Source:** RESEARCH §Pattern 4 verbatim. Additional security ask (RESEARCH §Security Domain): if `next` is read from query, validate it starts with `/` and doesn't contain `://` before using in redirect. Use `origin` from `new URL(request.url)` for the redirect base (handles preview deploys + localhost).

---

### `frontend/app/layout.tsx` (MODIFY — Server Component)

**Analog:** self (current file, lines 1–22).

**Current shape to preserve:**
```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Property Helper", description: "AI-powered apartment finder" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className='font-sans antialiased text-zinc-900 bg-white'
        style={{ fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
```

**Modifications (from RESEARCH §Pattern 6):**
1. Make the function `async` and add `const supabase = await createClient()` + `const { data: { user } } = await supabase.auth.getUser()`.
2. Insert a `<header>` element ABOVE `{children}`, preserving body classes/font.
3. Header styling per CONTEXT D-04 + matching `frontend/app/page.tsx` line 278 (`bg-white`) and ListingCard borders (`border-zinc-200`): `<header className="border-b border-zinc-200 bg-white px-6 py-3 flex items-center justify-between">`.
4. Authenticated: show truncated `user.email` + `<SignOutButton />`. Anonymous: `<Link href="/login" className="text-sm font-semibold">Sign in</Link>`.
5. Keep `metadata` export and `<html lang="en">` unchanged.

---

### `frontend/app/components/SignOutButton.tsx` (component, Client)

**Analog:** `frontend/app/components/SearchForm.tsx` (Client Component shape) + RESEARCH §Pattern 7 (auth body).

**Pattern to copy from SearchForm.tsx:**
- `'use client';` at top
- Named export: `export function SignOutButton() { ... }`
- Tailwind zinc-900 button styling from SearchForm line 91–95: `className="rounded bg-zinc-900 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"` (size-adjusted for header).

**Body from RESEARCH §Pattern 7:** `useRouter` from `next/navigation`, `await signOut()`, then BOTH `router.push('/')` and `router.refresh()` (Pitfall 7 mandate).

---

### `frontend/lib/supabase.ts` (MODIFY — keep + TODO)

**Analog:** self (no behavior change).

**Action:** Add a TODO comment block above `createClient(...)` per RESEARCH §Open Questions #2:
```ts
// TODO(Phase 7): Once RLS lands and Realtime channels become user-scoped,
// migrate this bare client to the SSR browser client from supabase-browser.ts
// so subscriptions carry the authenticated user's JWT. Phase 6 keeps the
// anon client because tables are still anon-accessible (D-08).
```
No code changes.

---

### `frontend/__tests__/_mocks/supabase.ts` (test helper)

**Analog:** `frontend/__tests__/ListingCard.test.tsx` lines 7–37 (`makeListing()` factory convention).

**Pattern to mirror — factory with override:**
```ts
function makeListing(overrides: Partial<Listing['data']> & { ... } = {}): Listing {
  const { id = 'l1', ... } = overrides;
  return { id, job_id: 'job-1', data: { address: '123 Main St', ..., ...data }, ... };
}
```
Copy: default-arg pattern, single `overrides` object, sensible defaults so most callers pass nothing.

**Body from RESEARCH §Validation Architecture (Vitest mocking pattern):**
```ts
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
```

---

### `frontend/__tests__/LoginPage.test.tsx` (test)

**Analog:** `frontend/__tests__/SearchForm.test.tsx`

**Imports + describe/it shape (lines 1–6):**
```ts
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchForm } from '../app/components/SearchForm';

describe('SearchForm (SRCH-03)', () => {
```
Copy: requirement tag in describe name (`'LoginPage (AUTH-01)'`), `userEvent.setup()` per test, `screen.getByRole(...)` queries.

**Interaction pattern (lines 7–14):**
```ts
it('GlobalFlexToggle toggles aria-checked', async () => {
  const user = userEvent.setup();
  render(<SearchForm inFlight={false} onSubmit={vi.fn()} />);
  const toggle = screen.getByRole('switch', { name: /willing to flex/i });
  await user.click(toggle);
  expect(toggle).toHaveAttribute('aria-checked', 'true');
});
```
Copy: `getByRole` + accessible-name regex, `await user.click(...)`, single-assertion-per-it style.

**Disabled-state pattern (lines 16–19):**
```ts
it('textarea is disabled when inFlight=true', () => {
  render(<SearchForm inFlight={true} onSubmit={vi.fn()} />);
  expect(screen.getByRole('textbox')).toBeDisabled();
});
```
Copy directly for the loading-state assertion on email input + submit button.

**Mock injection** — use `vi.mock('@/lib/supabase-browser', () => ({ createClient: () => mockSupabaseClient(...) }))` per RESEARCH §Validation Architecture.

---

### `frontend/__tests__/SignOutButton.test.tsx` (test)

**Analog:** `frontend/__tests__/SearchForm.test.tsx` + Vitest mocking pattern from RESEARCH.

Pattern identical to LoginPage.test.tsx above. Additional mocks:
- `vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }))`
- Assert both `push('/')` and `refresh()` are called (Pitfall 7 contract).

---

### `frontend/__tests__/layout.test.tsx` (test, Server Component)

**Analog:** `frontend/__tests__/ListingCard.test.tsx` (RTL render-and-assert shape).

**Pattern:**
- Mock `@/lib/supabase-server` `createClient` to return `{ auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null } }) } }` for the anon case, and a populated user for the authed case.
- Render `await RootLayout({ children: <div data-testid="kid" /> })` (Server Components are async — call as a function, await, then `render(result)`).
- Anon: assert `screen.getByRole('link', { name: /sign in/i })` exists.
- Authed: assert email text + sign-out button render.

---

### `frontend/__tests__/authCallback.test.ts` (test, route handler)

**Analog:** none in repo. Use RESEARCH §Validation Architecture.

Test the `GET(request)` export as a plain async function. Construct `new NextRequest('http://localhost/auth/callback?code=abc')`, mock `createClient` from `@/lib/supabase-server`, assert `exchangeCodeForSession('abc')` is called and `NextResponse.redirect` returns the expected URL. Three cases per CONTEXT D-07 / RESEARCH §Phase Requirements → Test Map: success, missing code, exchange error.

---

### `frontend/__tests__/middleware.test.ts` (test, middleware)

**Analog:** none in repo. Use RESEARCH §Validation Architecture.

Mock `@supabase/ssr` `createServerClient` to return `{ auth: { getUser: vi.fn().mockResolvedValue({ data: { user: null } }) } }`. Build a `NextRequest` with a cookie jar; call `updateSession(request)`; assert `getUser` was called and the returned response is a `NextResponse` (cookie-refresh contract).

---

## Shared Patterns

### Supabase env-var access
**Source:** `frontend/lib/supabase.ts` lines 4–5
**Apply to:** `lib/supabase-browser.ts`, `lib/supabase-server.ts`, `lib/supabase-middleware.ts`
```ts
process.env.NEXT_PUBLIC_SUPABASE_URL!,
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
```
Use the non-null `!` assertion. Do not add runtime null-checks; Next.js inlines these at build.

### Path alias `@/`
**Source:** `frontend/tsconfig.json` `"paths": { "@/*": ["./*"] }` + usage in `frontend/app/page.tsx` line 5 (`import { supabase } from '@/lib/supabase';`)
**Apply to:** every new import that crosses directories.
```ts
import { createClient } from '@/lib/supabase-browser';
import { createClient } from '@/lib/supabase-server';
import { updateSession } from '@/lib/supabase-middleware';
import { SignOutButton } from '@/app/components/SignOutButton';
```

### Client Component declaration
**Source:** `frontend/app/components/SearchForm.tsx` line 1, `frontend/app/page.tsx` line 1
**Apply to:** `app/login/page.tsx`, `app/components/SignOutButton.tsx`
```tsx
'use client';
```
Single-quoted, top of file, blank line before imports.

### Tailwind design tokens (zinc-900 / zinc-200 / zinc-500)
**Source:** `frontend/app/components/SearchForm.tsx` lines 60, 82–84, 91–95; `frontend/app/page.tsx` lines 278–283
**Apply to:** `app/login/page.tsx`, `app/components/SignOutButton.tsx`, header in `app/layout.tsx`
- Primary button: `bg-zinc-900 text-white px-4 py-2 text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed`
- Border: `border border-zinc-300` (inputs), `border-b border-zinc-200` (separators)
- Muted text: `text-zinc-500`
- Background: `bg-white` for page body, `bg-zinc-100` for muted banners

### Error banner
**Source:** `frontend/app/page.tsx` lines 293–297
**Apply to:** `app/login/page.tsx` (auth_failed messages, signInWithOtp errors)
```tsx
<div className="mt-6 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-700" role="alert">
  {error}
</div>
```
Note the `role="alert"` for screen readers.

### Vitest test file shape
**Source:** `frontend/__tests__/SearchForm.test.tsx` lines 1–6, 8–14
**Apply to:** all five new test files.
- Imports: `import { describe, it, expect, vi } from 'vitest';` + `render, screen` from RTL + `userEvent` default.
- Describe name includes requirement tag: `describe('LoginPage (AUTH-01)', ...)`.
- `userEvent.setup()` inside each `it`, never module-scope.
- Prefer `getByRole` with accessible-name regex over `getByTestId`.

### Test factory convention
**Source:** `frontend/__tests__/ListingCard.test.tsx` lines 7–37 (`makeListing(overrides)`)
**Apply to:** `__tests__/_mocks/supabase.ts` (`mockSupabaseClient(overrides)`)
- Single `overrides` parameter with default `= {}`
- Sensible defaults so most callers pass nothing
- Spread overrides last so caller can replace any default

## No Analog Found

Files with no close in-repo match — planner uses RESEARCH.md patterns instead:

| File | Role | Reason |
|------|------|--------|
| `frontend/middleware.ts` + `lib/supabase-middleware.ts` | middleware | Next.js middleware is brand-new to this codebase. Use RESEARCH §Pattern 3 verbatim. |
| `frontend/app/auth/callback/route.ts` | route handler | No Route Handlers exist in repo yet. Use RESEARCH §Pattern 4 verbatim, with the `next`-param hardening from §Security Domain. |
| `frontend/__tests__/authCallback.test.ts` | route-handler test | No existing test of a Next.js Route Handler. Use RESEARCH §Validation Architecture mock pattern. |
| `frontend/__tests__/middleware.test.ts` | middleware test | No existing middleware test. Same as above. |

## Metadata

**Analog search scope:** `frontend/lib/`, `frontend/app/`, `frontend/app/components/`, `frontend/__tests__/`
**Files scanned:** 22 TS/TSX files (full frontend tree, excluding `node_modules` and `.next`)
**Pattern extraction date:** 2026-05-12
