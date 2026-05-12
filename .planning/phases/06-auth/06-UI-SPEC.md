---
phase: 6
slug: auth
status: draft
shadcn_initialized: false
preset: none
created: 2026-05-12
---

# Phase 6 — UI Design Contract

> Visual and interaction contract for the auth surface (header bar, /login page, sign-out button). Extends the existing zinc-900 / white / system-ui design system already established in `app/page.tsx` and `app/components/SearchForm.tsx`. No new design system introduced.

---

## Design System

| Property | Value |
|----------|-------|
| Tool | none (Tailwind v3 utility classes, no shadcn — `components.json` not present) |
| Preset | not applicable |
| Component library | none (hand-built Tailwind components matching existing `SearchForm.tsx` aesthetic) |
| Icon library | none — Phase 6 uses zero icons (text-only buttons and links, consistent with current UI) |
| Font | `system-ui, -apple-system, "Segoe UI", Roboto, sans-serif` (inherited from `app/layout.tsx` body style — must not be changed in Phase 6) |

**Inherited globals** (verified in code):
- Body classes: `font-sans antialiased text-zinc-900 bg-white`
- Tailwind config: defaults only (no theme extensions in `tailwind.config.ts`)
- Global CSS: `globals.css` imports `maplibre-gl/dist/maplibre-gl.css` + Tailwind directives — do not modify

---

## Spacing Scale

Declared values (all multiples of 4 — matches Tailwind defaults; mirrors values already in use in `page.tsx`/`SearchForm.tsx`):

| Token | Value | Tailwind class | Usage in Phase 6 |
|-------|-------|----------------|------------------|
| xs | 4px | `gap-1`, `p-1` | Inline gaps between header text and button |
| sm | 8px | `gap-2`, `py-2`, `p-2` | Input padding (matches `SearchForm` textarea `p-2`); button vertical padding |
| xs-plus | 12px | `gap-3`, `py-3` | Header vertical padding (`py-3`); inter-element gap inside `/login` form stack (`gap-3`); gap between email label and sign-out in header. **Justification:** already used consistently in the existing codebase (`SearchForm.tsx` gap pattern; header height target). Tailwind-native (`space-3 = 0.75rem`). Listed explicitly so component specs that use `gap-3`/`py-3` are in-contract. |
| md | 16px | `px-4`, `gap-4` | Primary button horizontal padding (matches `SearchForm` submit `px-4 py-2`); form field gaps |
| lg | 24px | `px-6`, `pt-6` | Header horizontal padding inside max-w container (matches `page.tsx` `px-6`) |
| xl | 32px | `pt-8`, `mt-8` | `/login` page top spacing (matches `page.tsx` `pt-8`) |
| 2xl | 48px | `py-12` | `/login` vertical centering padding |
| 3xl | 64px | `mt-16` | Reserved — not used in Phase 6 |

**Container width:** `max-w-[1280px]` (matches `page.tsx`) for the header; `max-w-[420px]` for the `/login` form card (narrow, focused single-purpose page).

**Exceptions:** none. All spacing is a multiple of 4. Header height is not declared as a fixed value — let content + `py-3` (12px, the `xs-plus` token) drive it.

---

## Typography

Four type roles. Two weights total (`font-normal` = 400 and `font-semibold` = 600), matching the existing app. Sizes are explicit Tailwind utilities already used in `page.tsx`.

| Role | Size | Weight | Line Height | Tailwind | Used For |
|------|------|--------|-------------|----------|----------|
| Body | 14px | 400 (`font-normal`) | 1.5 (`leading-normal`) | `text-sm` | Header email label; helper copy under `/login` form; "Check your inbox" body |
| Label | 14px | 600 (`font-semibold`) | 1.5 (`leading-normal`) | `text-sm font-semibold` | Buttons ("Send magic link", "Sign out", "Sign in") |
| Heading | 20px | 600 (`font-semibold`) | 1.2 (`leading-tight`) | `text-[20px] font-semibold leading-tight` | `/login` page heading ("Sign in to Property Helper"); matches the `h1` in `page.tsx` exactly |
| Display | not used | — | — | — | Phase 6 has no display-scale type |

**Rules:**
- Only `font-normal` (400) and `font-semibold` (600). No medium, no bold, no light.
- Body line-height defaults to Tailwind `leading-normal` (1.5).
- Headings use `leading-tight` (1.25 effective with `text-[20px]` — the existing `h1` reference).
- No font-style italic anywhere in Phase 6.

---

## Color

Strict adherence to the existing dual-tone palette in `page.tsx`. No new hues introduced.

| Role | Value | Tailwind | Usage |
|------|-------|----------|-------|
| Dominant (60%) | `#ffffff` | `bg-white` | All page backgrounds (header, login page, body) |
| Secondary (30%) | `#18181b` (zinc-900) | `text-zinc-900`, `bg-zinc-900` | Default text color; primary button surface |
| Accent (10%) | `#71717a` (zinc-500) | `text-zinc-500`, `border-zinc-300`, `bg-zinc-100` | Subdued helper text; input borders; resumed-state info chip background |
| Destructive | `#b91c1c` (red-700) on `#fef2f2` (red-50) with `border-red-600` | `text-red-700 bg-red-50 border-red-600` | Login error message ("Couldn't send magic link…") — matches the existing error pattern in `page.tsx` line 294 |

**Accent reserved for** (explicit list — never "all interactive elements"):
1. Helper text under the email input (`text-zinc-500` — "We'll email you a one-time sign-in link.")
2. Email-input border at rest (`border-zinc-300`)
3. The resumed-search info chip styling pattern (`bg-zinc-100` + body weight) — reused for the "Check your inbox" confirmation block

**Primary button:** zinc-900 surface, white text, semibold — identical to the existing "Search apartments" button (`SearchForm.tsx` line 93). The "Send magic link" button MUST use this exact class string:
`rounded bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed`

**Sign-out button** (header, secondary action): text-only link styled as `text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline`. Reason: it must not compete visually with the primary search CTA on the main page; subdued treatment is correct.

**Sign-in link** (header, anonymous state): same subdued treatment as sign-out: `text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline`.

**No new colors.** No green/blue/yellow. No gradients. No shadows beyond Tailwind defaults (none used in Phase 6).

---

## Copywriting Contract

Every literal string the user reads in Phase 6. Tone: declarative, friendly, no jargon. Matches the existing voice in `page.tsx` ("Describe what you're looking for. Results stream in automatically.").

### Header bar (in `app/layout.tsx`)

| State | Element | Copy |
|-------|---------|------|
| Anonymous | Right-side link | `Sign in` |
| Authenticated | Email label | `{user.email}` (truncate visually with `truncate max-w-[200px]` so long emails don't break header) |
| Authenticated | Sign-out button | `Sign out` |

### `/login` page

| Element | Copy |
|---------|------|
| Page heading (`h1`) | `Sign in to Property Helper` |
| Helper text under heading | `Enter your email and we'll send a one-time link.` |
| Email input label (sr-only) | `Email address` |
| Email input placeholder | `you@example.com` |
| Primary CTA (idle) | `Send magic link` |
| Primary CTA (loading) | `Sending…` |
| Success heading (after OTP sent) | `Check your inbox` |
| Success body | `We sent a sign-in link to {email}. Open it in this same browser to finish signing in.` (the "same browser" sentence is non-negotiable — required by Pitfall 6 in RESEARCH.md re: PKCE code-verifier cookie scope) |
| Inline error (signInWithOtp returns error) | `Couldn't send the link. Check the email address and try again.` |
| Callback error redirect query string | `/login?error=auth_failed` (D-07) |
| Callback-error banner copy (when `?error=auth_failed` is present) | `That sign-in link didn't work. Request a fresh one below.` |

### Empty / loading states

| State | Where | Copy |
|-------|-------|------|
| Empty (no email typed yet) | `/login` form | No empty-state message — the helper text under the heading covers it |
| Loading (OTP request in flight) | Button label flips to `Sending…`; input is `disabled`; button is `disabled` |
| Resumed (returning to a sent state — refresh of `/login` while `sent=true` in memory only) | not applicable — page is stateless on refresh; user just re-requests if needed |

### Destructive actions

| Action | Confirmation approach |
|--------|----------------------|
| Sign out | **No confirmation dialog.** Sign-out is one click. Rationale: this is a low-cost, easily-reversed action (user can sign back in with another magic link in <30s). Adding a confirm modal would be friction-for-friction's-sake. Inline behavior: click → header flips to "Sign in" within ~200ms (driven by `router.refresh()`). |

No other destructive actions in Phase 6. No account deletion, no email change, no session-revocation-all-devices (all deferred).

---

## Component Inventory

Six concrete components/files. Each maps to a single responsibility from CONTEXT.md decisions D-04 through D-07.

| Component | File | Type | Responsibility |
|-----------|------|------|----------------|
| Header | inline in `app/layout.tsx` | Server Component (no `'use client'`) | Reads session via `createServerClient`; renders anonymous OR authenticated state |
| SignOutButton | `app/components/SignOutButton.tsx` | Client Component (`'use client'`) | Calls `signOut()` + `router.push('/')` + `router.refresh()` |
| LoginPage | `app/login/page.tsx` | Client Component (`'use client'`) | Email input + send-link button + sent/error states |
| AuthCallback | `app/auth/callback/route.ts` | Route Handler (no UI) | Exchanges code for session; redirects |
| (existing) `app/page.tsx` | unchanged | — | Search page remains anonymous-accessible per CONTEXT D-08 |
| (existing) `app/layout.tsx` | extended | — | Adds header above `{children}` |

### Header layout (visual contract)

```
+--------------------------------------------------------------+
| Property Helper                              you@example.com  |  ← authenticated
|                                              Sign out         |
+--------------------------------------------------------------+

+--------------------------------------------------------------+
| Property Helper                                    Sign in    |  ← anonymous
+--------------------------------------------------------------+
```

- Left side: plain text `Property Helper` (no logo image). Same `text-[20px] font-semibold` as the page `h1` — except on the home page the `h1` already says this; the header text can be wrapped in a `<Link href="/">` styled identically. The visual duplication on `/` is acceptable (header is global; page `h1` is page-local).
- Right side: anonymous → single `Sign in` link. Authenticated → email + sign-out, separated by `gap-3` (12px, `xs-plus` token), email first.
- Border: `border-b border-zinc-200` (light hairline). NOT sticky in Phase 6 — `position: static`. Sticky behavior is Claude's-discretion deferred; default to static for v1 simplicity.
- Inner container: `mx-auto max-w-[1280px] px-6 py-3 flex items-center justify-between` — matches the page's max-w + horizontal padding so left edges align with the page heading below.

### `/login` page layout

```
                                                                
              Sign in to Property Helper                        
              Enter your email and we'll send a one-time link.  
                                                                
              [ you@example.com                              ]  
                                                                
              [ Send magic link ]                               
                                                                
```

- Outer: `min-h-screen bg-white flex items-start justify-center pt-16 px-6`.
- Inner card: `w-full max-w-[420px]` — no border, no shadow (consistent with the borderless, surface-minimal aesthetic of `page.tsx`).
- Stack direction: vertical `flex flex-col gap-3` (12px, `xs-plus` token, between heading, helper, input, button) — matches the `SearchForm` gap pattern.
- Email input: same class string as the existing textarea but single-line:
  `w-full rounded border border-zinc-300 p-2 text-sm disabled:bg-zinc-100 disabled:cursor-not-allowed` with `type="email" required autoFocus`.
- Button: `self-start` so it doesn't stretch full-width — matches `SearchForm.tsx` line 93 exactly.
- Sent state: replaces the form entirely with a two-line block — heading (`Check your inbox`) + body (`We sent a sign-in link to {email}…`). No button to dismiss. User either clicks the link in email or navigates away.
- Error state: red banner ABOVE the form (same pattern as `page.tsx` error banner at line 293–297). Form stays visible so the user can retry.

---

## Interaction Contract

| Trigger | Outcome | Latency target |
|---------|---------|---------------|
| Type into email input | No-op until submit (no live validation beyond HTML5 `type="email"`) | — |
| Click `Send magic link` with valid email | Button label flips to `Sending…`, button + input disabled, await `signInWithOtp` | <500ms perceived |
| `signInWithOtp` resolves OK | Form swaps to "Check your inbox" success block | immediate |
| `signInWithOtp` returns error | Red error banner appears above form; button + input re-enabled | immediate |
| Click magic link in email | Browser navigates to `/auth/callback?code=…`; route handler runs exchange; redirect to `/`; layout re-renders with email in header | <1s |
| Click `Sign out` in header | `signOut()` runs; `router.push('/')`; `router.refresh()`; header flips to anonymous within ~200ms | <300ms |
| Refresh tab while signed in | Cookie persists; SSR header renders authenticated state on first paint (no flash) | first paint |

**Accessibility:**
- All buttons have either explicit text labels or `aria-label`.
- Email input has an `sr-only` `<label htmlFor>` of `Email address`.
- Error banner uses `role="alert"` (matches existing pattern in `page.tsx`).
- Focus order on `/login`: heading is non-focusable → email input (`autoFocus`) → send button. Tab order is natural document order.
- Color contrast: zinc-900 on white = 16.6:1 (AAA); zinc-500 on white = 4.8:1 (AA — used only for helper text, never for interactive labels except the underlined sign-in/sign-out links which also expose `:hover` text-zinc-900).

---

## Registry Safety

| Registry | Blocks Used | Safety Gate |
|----------|-------------|-------------|
| shadcn official | none — shadcn not initialized for this project | not applicable |
| third-party | none | not applicable |

No registry-installed blocks of any kind. All Phase 6 components are hand-rolled Tailwind utility composition, identical in style to the existing `SearchForm.tsx` / `page.tsx` patterns. Zero third-party UI dependencies introduced in Phase 6 (the only new npm package is `@supabase/ssr`, which is non-UI infrastructure — see 06-RESEARCH.md).

---

## Checker Sign-Off

- [ ] Dimension 1 Copywriting: PASS
- [ ] Dimension 2 Visuals: PASS
- [ ] Dimension 3 Color: PASS
- [ ] Dimension 4 Typography: PASS
- [ ] Dimension 5 Spacing: PASS
- [ ] Dimension 6 Registry Safety: PASS

**Approval:** pending
