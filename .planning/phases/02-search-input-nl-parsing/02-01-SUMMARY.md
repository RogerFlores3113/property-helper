---
phase: 02-search-input-nl-parsing
plan: 01
subsystem: frontend
tags: [tdd, vitest, parser, types]
requires:
  - frontend Next.js 15 + TypeScript scaffold (Phase 01)
provides:
  - parseQuery() pure NL-to-chip parser
  - Chip / ChipType / JobPostPayload type definitions
  - Vitest test infrastructure (jsdom + react-plugin)
  - RED component stubs for ChipList + SearchForm (await Plan 02)
affects:
  - frontend/package.json devDependencies
  - frontend/app/types.ts (extended in place)
tech_stack:
  added:
    - vitest@4.1.6
    - "@testing-library/react@16.3.2"
    - "@testing-library/user-event@14.6.1"
    - "@vitejs/plugin-react@6.0.1"
    - jsdom@29.1.1
  patterns:
    - "Pure function parser (no React deps), named exports only"
    - "Regex order load-bearing (PRICE_RANGE_RE before MAX_PRICE_RE)"
    - "Strip-and-collect: replace consumed substrings with spaces, then derive location from remainder"
key_files:
  created:
    - frontend/vitest.config.ts
    - frontend/lib/parseQuery.ts
    - frontend/__tests__/parseQuery.test.ts
    - frontend/__tests__/ChipList.test.tsx
    - frontend/__tests__/SearchForm.test.tsx
  modified:
    - frontend/app/types.ts
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "Use crypto.randomUUID() for chip ids (Node 24 + Chromium 92+ + Firefox 95+ — meets project browser support)"
  - "Replace consumed regex substrings with spaces, not empty strings, to avoid word collisions when computing location remainder"
  - "Component test stubs left in RED state intentionally (Plan 02 will add ChipList.tsx and SearchForm.tsx)"
metrics:
  tasks_completed: 3
  duration_minutes: ~6
  completed: 2026-05-11
---

# Phase 02 Plan 01: NL Parser + Vitest Foundation Summary

Established Vitest + jsdom test infrastructure, wrote five TDD unit tests for parseQuery() and implemented the pure NL-to-chip parser with the regex-ordering / stop-word-stripping / numeric-coercion mitigations called for in 02-RESEARCH.md (Pitfalls 1, 2, 5). Component test stubs for ChipList and SearchForm intentionally left RED — Plan 02 will turn them green when the components are built.

## Tasks Executed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | Install Vitest + configure jsdom + react plugin + @/ alias | 1faa3a8 |
| 2a (RED) | Add failing parseQuery unit tests + Chip types | 16852d4 |
| 2b (GREEN) | Implement parseQuery NL parser | 63d8bdf |
| 3 | Add RED component stubs (ChipList, SearchForm) | d77c31d |

## TDD Gate Compliance

- RED gate: `test(02-01): add failing parseQuery unit tests` (16852d4) — confirmed failing on missing module before GREEN.
- GREEN gate: `feat(02-01): implement parseQuery NL parser` (63d8bdf) — five tests pass.
- REFACTOR gate: not needed; implementation went green on first pass and is already factored (helper functions for newId / toNumber / consume / stripConsumed).

## Verification Results

**parseQuery test suite:** 5/5 passing (`npx vitest run __tests__/parseQuery.test.ts`)
- canonical SRCH-01: beds=2, max_price=1500, location='Champaign', amenity present
- short query (<5 chars) → []
- price range $1000-$2000 → both min_price=1000 and max_price=2000
- stop-word strip: location value is 'Champaign' not 'in Champaign'
- numeric type coercion: typeof beds.value === 'number'

**Component stubs:** RED as designed — both fail with `Failed to resolve import "../app/components/{ChipList|SearchForm}"`. Stub files exist and parse; only the missing module prevents them from running. Plan 02 will fix.

**TypeScript compilation:** `npm run build` compiles successfully (`✓ Compiled successfully in 2.7s`). Three new type exports (ChipType, Chip, JobPostPayload) introduce no errors.

## Pitfall Mitigations

| Pitfall (RESEARCH.md) | Mitigation in Code |
|-----------------------|--------------------|
| Pitfall 1 — MAX_PRICE_RE swallowing range numbers | PRICE_RANGE_RE declared and executed before MAX_PRICE_RE; range branch consumes substring before fallback runs |
| Pitfall 2 — "in Champaign" leaking into location chip | STOP_WORDS regex strips `in/at/near/with/and/for` from remainder before location chip emission |
| Pitfall 5 — Chip.value being string instead of number | parseInt(., 10) for beds/baths; parseFloat(.replace(',', '')) for prices |

## Deviations from Plan

None — plan executed exactly as written.

Pre-existing condition noted (out of scope for this plan, not a deviation): `next build` static prerender of `/` fails on missing SUPABASE env var at build time. Verified this fails identically against the unmodified Plan-01-base commit (no local changes to stash). TypeScript compilation, which is what success_criteria asks for, passes cleanly. Logged here for the eventual env/build hardening plan.

## Self-Check: PASSED

- frontend/vitest.config.ts FOUND
- frontend/lib/parseQuery.ts FOUND
- frontend/__tests__/parseQuery.test.ts FOUND
- frontend/__tests__/ChipList.test.tsx FOUND
- frontend/__tests__/SearchForm.test.tsx FOUND
- Commit 1faa3a8 FOUND
- Commit 16852d4 FOUND
- Commit 63d8bdf FOUND
- Commit d77c31d FOUND
