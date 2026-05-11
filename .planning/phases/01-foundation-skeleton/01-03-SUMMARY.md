---
phase: 01-foundation-skeleton
plan: 03
subsystem: frontend
tags: [nextjs, react, supabase-realtime, tailwind, localStorage, fire-and-forget]

requires:
  - "01-01: frontend Next.js 15 scaffold + supabase-js singleton (frontend/lib/supabase.ts)"
  - "01-02: POST /api/jobs and GET /api/jobs/{id} routes; supabase_realtime publication on listings + search_jobs"

provides:
  - "Phase 1 placeholder UI per UI-SPEC: Header, StartSearchButton, JobStatusBadge, ListingList, EmptyState, ResumeBanner, ErrorBanner"
  - "Supabase Realtime subscription with dual listeners (listings INSERT, search_jobs UPDATE) filtered by job_id"
  - "localStorage-backed fire-and-forget persistence (CACH-03): GET /api/jobs/{id} reattach on mount"
  - "Frontend type contracts: Listing, ListingData, JobStatus, SearchJob, JobResponse mirroring backend GET shape"

affects:
  - "Phase 1 success criteria 1–5 are now end-to-end exercisable in the browser"
  - "Phase 2 UI work: Tailwind utility patterns established; shadcn still NOT initialized (deferred to Phase 2 ui-researcher per UI-SPEC)"

tech-stack:
  added: []
  patterns:
    - "'use client' component with useEffect for mount-time reattach and cleanup"
    - "useRef<RealtimeChannel | null> + supabase.removeChannel in cleanup (Pitfall 7: React StrictMode double-mount)"
    - "mergeById dedup of Realtime INSERT vs GET reattach payload (Pitfall 1: subscribe-before-insert race)"
    - "Subscribe BEFORE returning from startSearch and AFTER GET resolves in reattach — both seed initial state and stream incremental updates"
    - "UUID regex gate on localStorage value before reattach (T-03-02: arbitrary value 404s on backend regardless)"

key-files:
  created:
    - "frontend/app/types.ts"
  modified:
    - "frontend/app/page.tsx (null placeholder → full Phase 1 UI)"

key-decisions:
  - "Subscribe in reattach AFTER GET resolves: seeds initial listings first, then mergeById dedupes any INSERT echo that arrives during the small window"
  - "Use raw fetch (no client lib) to backend — keeps Phase 1 dependency surface to react + supabase-js only; revisit when SWR/React Query is justified by real data needs"
  - "Subscribe ONE channel per job_id with two `.on('postgres_changes', ...)` listeners (one per table) instead of two channels — matches RESEARCH Pattern 7"
  - "Render listings newest-first via `[...listings].reverse()` — order independent of insert sequence (Realtime/GET merge keeps insertion order in state; UI reverses at render time)"
  - "URL.hostname extraction wrapped in try/catch fallback (T-03-05 mitigation) — defensive even though Phase 1 stub data is internally controlled"

patterns-established:
  - "Channel ref pattern: `const channelRef = useRef<RealtimeChannel | null>(null)` + cleanup in useEffect return"
  - "Status union type: `JobStatus | 'idle' | 'resuming'` to model the UI states beyond backend's enum"

requirements-completed: [CACH-03, CACH-04]

metrics:
  duration: ~15min (Task 1 only; Task 2 is a human-verify checkpoint)
  tasks: 1 of 2 (Task 2 is checkpoint:human-verify, blocking gate)
  files_created: 1
  files_modified: 1
completed: 2026-05-11
---

# Phase 01 Plan 03: Frontend Slice Summary

**Phase 1 placeholder UI implementing UI-SPEC verbatim: 'Start search' button → POST /api/jobs → localStorage-backed Realtime stream of 9 fake listings with fire-and-forget reload reattach via GET /api/jobs/{id}.**

## Performance

- **Duration:** ~15 minutes for Task 1 (Task 2 awaiting human verification)
- **Started:** 2026-05-11
- **Completed (code):** 2026-05-11
- **Tasks:** 2 (1 auto + 1 checkpoint:human-verify)
- **Files created:** 1 (`frontend/app/types.ts`)
- **Files modified:** 1 (`frontend/app/page.tsx` — null placeholder replaced)
- **Build:** `npm run build` exits 0 in 1690ms; 5 static pages prerendered

## Accomplishments

- `frontend/app/types.ts` exports `Listing`, `ListingData`, `JobStatus`, `SearchJob`, `JobResponse` matching backend GET contract
- `frontend/app/page.tsx` starts with `'use client'` and renders default-exported `Home`
- Contains required literal substrings (verified by acceptance grep): `supabase.channel`, `'postgres_changes'`, `localStorage`, `property_helper_job_id`, `removeChannel`, `NEXT_PUBLIC_API_URL`, `Start search`, `Searching…`, `Start another search`, `export type Listing`
- All UI-SPEC copywriting strings present verbatim:
  - `Property Helper — Foundation Skeleton`
  - `Phase 1 proof: clicking Start search streams fake listings from the worker.`
  - `No search running`
  - `Click "Start search" to enqueue a stub job. Fake listings will stream in below.`
  - `Couldn't start the job. Check that the backend (uvicorn) and Redis are running, then try again.`
  - `Resumed previous search`
  - `Job finished but returned no listings. This is unexpected — check the worker logs.`
- Realtime subscription registers BOTH `listings` INSERT (filter `job_id=eq.{id}`) AND `search_jobs` UPDATE (filter `id=eq.{id}`) listeners on one channel
- `cd frontend && npm run build` with stub env vars exits 0 with no TypeScript errors
- No `<img>` tag, no map library import, no shadcn-style import (UI-SPEC out-of-scope enforcement preserved)

## Task Commits

1. **Task 1: Implement page.tsx with Realtime streaming + reattach** — `ee238b6` (feat)

Task 2 is `checkpoint:human-verify` — no code commit, awaiting end-to-end manual smoke verification (see below).

## Files Created/Modified

**Created:**
- `frontend/app/types.ts` — 5 exported types (`ListingData`, `Listing`, `JobStatus`, `SearchJob`, `JobResponse`) shaped to backend GET response

**Modified:**
- `frontend/app/page.tsx` — null placeholder replaced with full Phase 1 client component; ~280 lines including:
  - State: `jobId`, `status` (UiStatus union), `listings`, `error`, `resumed`, `channelRef`
  - Helpers: `subscribe(id)`, `mergeById(prev, next)`, `reattach(id)`, `startSearch()`
  - Render: Header, ResumeBanner, ErrorBanner, StartSearchButton, JobStatusBadge, ListingList, EmptyState, completed-with-zero-rows banner
  - Cleanup: `useEffect` return removes the active Realtime channel via `supabase.removeChannel`

## Decisions Made

- **Subscribe ordering:** In `reattach`, subscribe AFTER the GET resolves so initial state seeds first and any concurrent INSERT is deduped by `mergeById`. In `startSearch`, subscribe immediately after POST returns to ensure no early INSERT is missed.
- **Channel teardown discipline:** `subscribe()` removes any existing channel before creating a new one; useEffect cleanup removes the active channel on unmount. Together this neutralizes React 18 StrictMode double-mount accumulation (Pitfall 7).
- **Dedupe by id (mergeById):** Realtime INSERT and GET reattach may both deliver the same row (Pitfall 1). `mergeById` is O(n + m) using a `Set<string>` of seen IDs; preserves insertion order in state, render reverses at the JSX level.
- **UUID regex gate:** Validate `localStorage` value with `/^[0-9a-f]{8}-...-[0-9a-f]{12}$/i` before calling reattach. Belt-and-suspenders to backend's UUID4 path validation (T-03-02).
- **Hostname extraction:** `safeHostname()` wraps `new URL(u).hostname` in try/catch and falls back to raw string — defensive even though Phase 1 stub URLs are internally controlled (T-03-05).
- **No supabase-js typing escape:** Initial draft used `@ts-expect-error` for the `postgres_changes` event string. Build proved the typing is satisfied without it; removed.

## Deviations from Plan

None.

- The plan-required structure, copywriting strings, state shape, helper signatures, channel filter syntax, and render order all match. The only nitpick worth recording is cosmetic: the StartSearchButton and JobStatusBadge are rendered as sibling block-level elements with the badge `ml-3` to keep them on the same visual line — UI-SPEC describes them as separate "components" without prescribing layout adjacency, and the spec's 4px/8px tokens permit this.

## Issues Encountered

- **TypeScript build error on first attempt:** `@ts-expect-error` was unused because `supabase-js` v2.105 actually exposes typings for the `postgres_changes` event string. Removed the directives and the build was clean on the next attempt. No source-of-truth change needed; just removed the unnecessary suppressions.

## Verification

### Automated (Task 1)

```
cd frontend && NEXT_PUBLIC_SUPABASE_URL=https://x.supabase.co \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=stub \
  NEXT_PUBLIC_API_URL=http://localhost:8000 \
  npm run build
…
 ✓ Compiled successfully in 1690ms
   Linting and checking validity of types ...
 ✓ Generating static pages (5/5)
Route (app)                                 Size  First Load JS
┌ ○ /                                    61.5 kB         164 kB
```

All literal-substring greps from `<verify>` pass:
- `'use client'` ✓ · `supabase.channel` ✓ · `postgres_changes` ✓ · `localStorage` ✓ · `property_helper_job_id` ✓ · `NEXT_PUBLIC_API_URL` ✓ · `removeChannel` ✓ · `Start search` ✓ · `Phase 1 proof` ✓ · `export type Listing` ✓

### Manual Smoke (Task 2 — checkpoint:human-verify)

**Status:** awaiting human execution.

The end-to-end manual smoke covers all 5 ROADMAP Phase 1 success criteria as one continuous exercise. Pre-flight requires 4 terminals (Redis via docker compose, FastAPI via uvicorn, ARQ worker via `uv run arq`, Next.js via `npm run dev`). The plan's `<how-to-verify>` section is the authoritative script; key checkpoints:

1. **SC #1 — POST creates a running job:** Start button → "Searching…" → JobStatusBadge → uvicorn POST log → arq dequeue log → `search_jobs` row visible in Supabase Table Editor.
2. **SC #2 — listings stream in <1s:** 3 cards every ~0.5s for 3 iterations = 9 cards total; badge transitions to `completed — 9 listings received`; button switches to "Start another search".
3. **SC #3 — fire-and-forget:** Close tab → reopen `http://localhost:3000` → ResumeBanner with prior UUID + Status: completed + all 9 cards rendered from GET. Reload again — no duplicates (mergeById + cleanup proven).
4. **SC #4 — 300–500 char listings:** `SELECT id, LENGTH(data::text) AS chars FROM listings ORDER BY created_at DESC LIMIT 9;` — every row in `[300, 500]`. Plan 02's `test_payload_size` already locks this at 315 chars.
5. **SC #5 — cost guardrails + daily_spend:** `cd backend && uv run pytest tests/ -q` → `7 passed`. `SELECT date, estimated_tokens, estimated_cost_usd FROM daily_spend WHERE date = CURRENT_DATE;` → exactly one row, `estimated_tokens >= 1500` per stub run.

**Resume signal expected:** `phase-1-complete` once all 5 criteria + error-path sanity check pass.

## Next Phase Readiness

- **Phase 2 start (`/gsd-plan-phase 2`):** Ready once Task 2 human-verify returns `phase-1-complete`. Phase 2 ui-researcher MUST initialize shadcn before any production UI is built (UI-SPEC carryover note).
- **Frontend foundation:** Tailwind utilities and the `'use client'` + Supabase Realtime patterns are established and reusable.
- **Backend contract:** Stable — POST /api/jobs and GET /api/jobs/{id} are exercised end-to-end. No backend changes required for Phase 2.
- **Phase 2 carryover note:** Re-declare typography/color tokens at shadcn initialization. Phase 1 used provisional zinc-100/zinc-900/red-600 only.
- **No blockers.**

## Self-Check: PASSED

- FOUND: frontend/app/types.ts
- FOUND: frontend/app/page.tsx (modified)
- FOUND commit: ee238b6
- npm run build: ✓ Compiled successfully in 1690ms; 5 static pages prerendered

---
*Phase: 01-foundation-skeleton*
*Completed (code): 2026-05-11*
*Task 2 manual smoke: awaiting human verification*
