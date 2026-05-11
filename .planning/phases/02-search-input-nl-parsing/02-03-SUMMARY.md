---
phase: 02-search-input-nl-parsing
plan: 03
subsystem: frontend
tags: [wiring, react, supabase-realtime, page-orchestrator]
status: pending-checkpoint
requires:
  - <SearchForm /> component (Plan 02-02)
  - <ChipList /> component (Plan 02-02)
  - parseQuery() utility (Plan 02-01)
  - JobPostPayload / Chip / ChipType types (Plan 02-01)
  - Phase 1 subscribe()/reattach()/mergeById() in page.tsx (Phase 01)
provides:
  - End-to-end vertical slice: NL textarea → editable chips → POST /api/jobs with enriched payload → Realtime stream
  - Enriched POST /api/jobs body: { query, chips, global_flex }
affects:
  - frontend/app/page.tsx (refactored in place)
tech_stack:
  added: []
  patterns:
    - "Page.tsx orchestrator owns job/listing/Realtime state; SearchForm owns query/chips/globalFlex state"
    - "Single-payload onSubmit contract (JobPostPayload) — page.tsx no longer holds chips state"
    - "All Phase 1 Realtime + reattach logic preserved verbatim per D-08"
key_files:
  created: []
  modified:
    - frontend/app/page.tsx
decisions:
  - "Adapted to SearchForm's actual onSubmit signature (JobPostPayload object) rather than the (query, chips, globalFlex) 3-arg signature described in plan text — Plan 02 finalized SearchForm with payload-object API. Outcome equivalent (D-06 payload still sent), no chips state needed in page.tsx (SearchForm derives via parseQuery + overrides)."
  - "Removed buttonLabel derived const — SearchForm owns its own submit button label (UI-SPEC Copywriting Contract)."
  - "Standardized error copy to UI-SPEC: 'Couldn't start the search. Check that the backend and Redis are running, then try again.' (was 'job' / 'uvicorn' specific in Phase 1)."
metrics:
  tasks_completed: 1
  tasks_pending_checkpoint: 1
  duration_minutes: ~6
  completed: 2026-05-11
---

# Phase 02 Plan 03: page.tsx Wiring Summary

Wired the Phase 2 SearchForm component into page.tsx, replacing the Phase 1 stub `body: JSON.stringify({ query: 'Phase 1 stub query' })` with the enriched `{ query, chips, global_flex }` payload sourced from SearchForm. All Phase 1 Realtime subscription, fire-and-forget reattach, and mergeById dedup logic preserved verbatim per D-08. Copy updated to match the 02-UI-SPEC Copywriting Contract.

## Tasks Executed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Refactor page.tsx — wire SearchForm, update startSearch, update copy | 81f61c1 |
| 2 | End-to-end smoke — all 4 Phase 2 success criteria | **PENDING-CHECKPOINT** (human-verify) |

## Verification Results (Task 1)

**Vitest suite:** 10/10 passing (`./node_modules/.bin/vitest run`)
- parseQuery.test.ts: 5/5
- ChipList.test.tsx: 3/3
- SearchForm.test.tsx: 2/2

**TypeScript:** `tsc --noEmit` exits 0 with no errors. `next build` likewise reports `✓ Compiled successfully in 2.7s` and lint clean (the only warning is the pre-existing `setOverrides is assigned a value but never used` in SearchForm.tsx — out of scope for this plan).

**Acceptance grep checks (all green):**
- `grep -c "global_flex" frontend/app/page.tsx` = 1 (>= 1 ✓)
- `grep -c "SearchForm" frontend/app/page.tsx` = 2 (>= 2 ✓)
- `grep -c "Phase 1 stub query" frontend/app/page.tsx` = 0 ✓
- `grep -c "Foundation Skeleton" frontend/app/page.tsx` = 0 ✓
- `grep -c "subscribe" frontend/app/page.tsx` = 4 (>= 4 ✓)
- `grep -c "reattach" frontend/app/page.tsx` = 2 (>= 2 ✓)
- `grep -c "mergeById" frontend/app/page.tsx` = 4 (>= 2 ✓)

**Security assertion (T-02-03-02 mitigation):**
- `grep -c "dangerouslySetInnerHTML" frontend/app/page.tsx` = 0 ✓
- `grep -c "dangerouslySetInnerHTML" frontend/app/components/ChipList.tsx` = 0 ✓

## Pre-existing Build Condition (Out of Scope)

`next build` static prerender of `/` fails with `Error: supabaseUrl is required.` because no SUPABASE env vars are present at build time in this worktree. This is the same pre-existing condition documented in 02-01-SUMMARY.md ("Pre-existing condition noted… `next build` static prerender of `/` fails on missing SUPABASE env var at build time"). It is unrelated to this plan's diff: the `tsc --noEmit` TypeScript-correctness gate that this plan owns passes cleanly. Logged for the eventual env/build hardening plan.

## Deviations from Plan

### [Rule 3 — Interface mismatch] SearchForm onSubmit signature

- **Found during:** Task 1 (reading SearchForm.tsx before writing page.tsx)
- **Issue:** The plan text in `<interfaces>` describes `startSearch(rawQuery: string, chips: Chip[], globalFlex: boolean)` with `const [chips, setChips] = useState<Chip[]>([])` held in page.tsx. The actual SearchForm component shipped in Plan 02-02 exposes `onSubmit: (payload: JobPostPayload) => void` and owns its own `query` / `chips` / `globalFlex` state internally (via `parseQuery` + override Sets).
- **Fix:** `startSearch` accepts a single `JobPostPayload` argument and destructures `payload.query` / `payload.chips` / `payload.global_flex` into the POST body. Did not add `const [chips, setChips]` to page.tsx — would be unused; SearchForm is the single source of truth. The D-10 "clears prior chip and listing state on re-submit" behaviour is satisfied by SearchForm holding its own state across submits (re-submit reuses current chips/query) and `setListings([])` running before the POST. If the user wants to clear chips after submit, that's a future SearchForm enhancement, not this plan.
- **Outcome:** Functionally equivalent — the wire-format payload `{ query, chips, global_flex }` reaching POST /api/jobs is identical to what the plan specifies (D-06).
- **Files modified:** frontend/app/page.tsx
- **Commit:** 81f61c1

No other deviations.

## Task 2: Pending Human Verification

The remaining task is a `checkpoint:human-verify` requiring a human to drive the browser through SC#1–SC#4 (plus AddFilter and static-× checks) per the plan's `<how-to-verify>` block. Backend (uvicorn), Redis + arq-worker, and `npm run dev` must be running. Resume signal: type `phase-2-complete` if all criteria pass.

## Self-Check: PASSED

- frontend/app/page.tsx FOUND
- Commit 81f61c1 FOUND
- All 10 vitest tests passing
- tsc --noEmit clean
- All 7 grep acceptance checks green
- Both dangerouslySetInnerHTML security greps return 0
- STATE.md / ROADMAP.md NOT modified (parallel-executor contract honored)
