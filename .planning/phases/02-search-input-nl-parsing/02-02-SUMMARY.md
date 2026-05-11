---
phase: 02-search-input-nl-parsing
plan: 02
subsystem: frontend
tags: [tdd, vitest, react, components]
requires:
  - parseQuery() (Plan 02-01)
  - Chip / ChipType / JobPostPayload types (Plan 02-01)
  - Vitest + jsdom + @testing-library/react infrastructure (Plan 02-01)
  - RED component test stubs (Plan 02-01)
provides:
  - <ChipList /> component (edit-in-place, per-chip flex toggle, remove)
  - <SearchForm /> component (textarea + GlobalFlexToggle + live chip preview)
  - jest-dom matcher integration for vitest
affects:
  - frontend/vitest.config.ts (setupFiles)
  - frontend/package.json (devDependencies: @testing-library/jest-dom)
tech_stack:
  added:
    - "@testing-library/jest-dom@latest"
  patterns:
    - "Controlled inline edit: local draft state inside ChipList, commit on Enter/blur"
    - "GlobalFlexToggle as button with role=switch + aria-checked (a11y-first)"
    - "SearchForm composes parseQuery output with per-chip overrides (edits/removed/flexed) layered via useMemo"
key_files:
  created:
    - frontend/app/components/ChipList.tsx
    - frontend/app/components/SearchForm.tsx
    - frontend/vitest.setup.ts
  modified:
    - frontend/vitest.config.ts
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "Chip label text comes from a chipLabel(chip) helper inside ChipList — keeps the test contract ('2BR') colocated with rendering"
  - "Per-chip flex toggled via Set<id> override on top of parser-emitted chip.flex — preserves parser as source of truth"
  - "SearchForm passes value as string from edit input (matches test expectation { value: '3' }); coercion to number is a future concern at submit time"
metrics:
  tasks_completed: 2
  duration_minutes: ~6
  completed: 2026-05-11
---

# Phase 02 Plan 02: ChipList + SearchForm Components Summary

Turned the RED component stubs from Plan 02-01 GREEN by implementing `<ChipList />` (chip pills with click-to-edit, ~ flex toggle, × remove) and `<SearchForm />` (textarea + role=switch GlobalFlexToggle + live chip preview wired to `parseQuery`). All 10 vitest tests in the frontend now pass (5 parseQuery + 3 ChipList + 2 SearchForm).

## Tasks Executed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Implement ChipList.tsx + wire jest-dom matchers | 6a1e325 |
| 2 | Implement SearchForm.tsx with GlobalFlexToggle | 43b9d29 |

## Verification Results

**Full vitest suite:** 10/10 passing (`./node_modules/.bin/vitest run`)
- parseQuery.test.ts: 5/5
- ChipList.test.tsx: 3/3 (click-to-edit, Enter commits via onUpdate, ~ button calls onToggleFlex)
- SearchForm.test.tsx: 2/2 (GlobalFlexToggle aria-checked toggles, textarea disabled when inFlight)

**TypeScript:** `tsc --noEmit` clean — no errors introduced by new components or imports.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking dep] Added @testing-library/jest-dom**
- **Found during:** Task 1 (first attempt at ChipList tests)
- **Issue:** Plan 02-01 left tests using `expect(...).toBeInTheDocument()` but did not install jest-dom or wire it via setupFiles. Vitest threw `Invalid Chai property: toBeInTheDocument`.
- **Fix:** `npm install --save-dev @testing-library/jest-dom`, created `frontend/vitest.setup.ts` importing `'@testing-library/jest-dom/vitest'`, and updated `vitest.config.ts` `setupFiles` to load it.
- **Files modified:** frontend/package.json, frontend/package-lock.json, frontend/vitest.config.ts; frontend/vitest.setup.ts (new)
- **Commit:** 6a1e325

No other deviations — components match the test contract exactly.

## Self-Check: PASSED

- frontend/app/components/ChipList.tsx FOUND
- frontend/app/components/SearchForm.tsx FOUND
- frontend/vitest.setup.ts FOUND
- Commit 6a1e325 FOUND
- Commit 43b9d29 FOUND
- All 10 vitest tests passing
- STATE.md / ROADMAP.md NOT modified (parallel-executor contract honored)
