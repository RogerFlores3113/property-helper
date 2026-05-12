---
phase: 6
slug: auth
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.6 + @testing-library/react 16.3 + jsdom 29.1 |
| **Config file** | `frontend/vitest.config.ts` (exists; jsdom + setupFiles `./vitest.setup.ts`) |
| **Quick run command** | `cd frontend && npm test -- --run <pattern>` |
| **Full suite command** | `cd frontend && npm test -- --run` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd frontend && npm test -- --run <touched file pattern>`
- **After every plan wave:** Run `cd frontend && npm test -- --run`
- **Before `/gsd-verify-work`:** Full suite must be green + manual smoke checklist (AUTH-03 reload + AUTH-02 real magic link flow)
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | AUTH-01 | T-06-01 | signInWithOtp uses PKCE emailRedirectTo, never leaks token in URL fragment | unit | `npm test -- --run LoginPage.test.tsx` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | AUTH-02 | T-06-01 | exchangeCodeForSession not called without valid code param | unit | `npm test -- --run authCallback.test.ts` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | AUTH-03 | T-06-02 | middleware calls getUser() (not getSession()) and returns supabaseResponse | unit | `npm test -- --run middleware.test.ts` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 0 | AUTH-04 | T-06-02 | signOut clears session; layout shows anonymous state post-logout | unit | `npm test -- --run SignOutButton.test.tsx` | ❌ W0 | ⬜ pending |
| 06-01-05 | 01 | 0 | AUTH-04 | — | Layout renders sign-in link when no user; email+signout when user present | unit | `npm test -- --run layout.test.tsx` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/__tests__/_mocks/supabase.ts` — shared mock factory for createBrowserClient / createServerClient with auth stubs (signInWithOtp, exchangeCodeForSession, signOut, getUser). Reused across all test files.
- [ ] `frontend/__tests__/LoginPage.test.tsx` — covers AUTH-01 (OTP submission, success state, error state)
- [ ] `frontend/__tests__/authCallback.test.ts` — covers AUTH-02 (code→session exchange, missing code redirect, error redirect)
- [ ] `frontend/__tests__/middleware.test.ts` — covers AUTH-03 cookie-refresh contract (getUser call, supabaseResponse passthrough)
- [ ] `frontend/__tests__/SignOutButton.test.tsx` — covers AUTH-04 (signOut + router.push + router.refresh)
- [ ] `frontend/__tests__/layout.test.tsx` — covers session-aware header (anonymous state + authenticated state)
- [ ] `frontend/vitest.setup.ts` additions — mock `next/headers` cookies() (async in Next.js 15), `next/navigation` useRouter/redirect so server-side modules import cleanly under jsdom

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Session persists across browser refresh | AUTH-03 | Cannot test browser cookie jar in Vitest/jsdom | Open app, login via magic link, F5, confirm still logged in |
| Magic link end-to-end (send email, click, land logged in) | AUTH-01, AUTH-02 | Requires live Supabase email delivery | Enter test email, receive link, click, confirm session established |
| Logout from any page clears session | AUTH-04 | Requires live session | Log in, click sign out, confirm anonymous state, confirm no session on refresh |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
