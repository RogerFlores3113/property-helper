---
phase: 05-cache-dedup-freshness
plan: 05
subsystem: phase-5-cleanup (CORS preflight + ROADMAP SC realignment)
tags: [backend, cors, docs, roadmap, mvp-scope, deferred-v2]
requires:
  - 05-03 (PATCH /api/listings/{id}/extend endpoint exists)
  - 05-04 (frontend Extend button issues PATCH from browser)
provides:
  - CORS preflight permission for PATCH (Extend button now reaches backend)
  - ROADMAP Phase-5 SC#1 wording aligned with shipped MVP (filter_hash-only cache)
affects:
  - backend/app/main.py (CORSMiddleware allow_methods)
  - .planning/ROADMAP.md (Phase 5 SC#1 narrative)
tech-stack:
  added: []
  patterns:
    - "CORS allow_methods extended explicitly per HTTP verb; no wildcards (preserves Pitfall-6 mitigation)."
    - "Scope-drift documentation: deferred-v2 features (bbox-overlap cache) called out inline in SC wording so future planners do not re-introduce them as bugs."
key-files:
  created:
    - .planning/phases/05-cache-dedup-freshness/05-05-SUMMARY.md
  modified:
    - backend/app/main.py
    - .planning/ROADMAP.md
decisions:
  - "Phase 5 ships with filter_hash-only cache (no bbox overlap). 05-02 implemented compute_filter_hash + copy_cached_listings without a geographic component. The original ROADMAP SC#1 referenced 'bounding box + filter hash' — that wording is now corrected to match shipped behavior and explicitly marks bbox-overlap as v2 scope."
  - "PATCH was missing from CORS allow_methods because 05-01/05-03 added PATCH /api/listings/{id}/extend without updating the existing CORSMiddleware allow-list (originally GET/POST/OPTIONS for Phase 1). Browser preflight (OPTIONS) was returning 400 with 'Method PATCH is not allowed', blocking the 05-04 Extend button despite end-to-end backend tests passing (tests bypass CORS)."
metrics:
  duration: "~5 min (Tasks 1+2 only; Task 3 checkpoint deferred to orchestrator)"
  completed: 2026-05-12T16:11Z
  tasks_completed: 2  # Task 3 (checkpoint:human-verify, blocking gate) deferred
  files_changed: 2
  commits: 2
---

# Phase 5 Plan 05: Cleanup (CORS PATCH + ROADMAP SC realignment) Summary

One-liner: Add PATCH to backend CORS allow_methods so the 05-04 Extend button
actually reaches `/api/listings/{id}/extend`, and rewrite Phase 5 SC#1 to match
the shipped filter_hash-only cache (bbox-overlap deferred to v2).

## Task Diff Summary

### Task 1 — `fix(05-05)`: CORS PATCH allowance

**File:** `backend/app/main.py`

```diff
-    allow_methods=["GET", "POST", "OPTIONS"],
+    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
```

**Why:** Plan 05-03 added `PATCH /api/listings/{id}/extend`. Plan 05-04 wired
the frontend Extend button to call it from the browser. The CORSMiddleware
allow-list was originally written in Phase 1 (Pitfall-6 hardening) with only
the verbs Phase-1 needed, and was never updated when PATCH was introduced.
Browser preflight `OPTIONS /api/listings/{id}/extend` was responding with
`400 Disallowed CORS method`, so the actual PATCH never fired — silently
breaking the freshness UX even though the backend endpoint + tests are green.

**Commit:** `c48fd64`

### Task 2 — `docs(05-05)`: ROADMAP Phase-5 SC#1 wording

**File:** `.planning/ROADMAP.md` (line 87)

```diff
-1. A search whose geographic bounding box + filter hash overlaps a recent search returns matching cached listings sub-second without invoking any scraper.
+1. A search whose filter hash matches a recent search returns matching cached listings sub-second without invoking any scraper. (Geographic bounding-box overlap was descoped from MVP and deferred to v2; v1 caches on filter_hash alone.)
```

**Why:** Plan 05-02 shipped `compute_filter_hash` + `copy_cached_listings`
keyed on filter_hash alone. There is no bbox component to the cache lookup in
the MVP — the v1 scope is "same filters, same results, reuse them". Bbox
overlap (a search that geographically *overlaps* an older search and wants to
splice in those listings) is a richer v2 feature that requires PostGIS
predicates over `search_jobs.bbox`. The ROADMAP wording is now reality-aligned
and the v2 deferral is documented inline so a future planner does not file
this as a missing-feature bug.

The Phase-5 goal sentence on line 84 still mentions "bbox+filter-hash" — left
intentionally untouched because (a) it is descriptive of the original *intent*,
(b) editing it is out-of-scope for this surgical cleanup plan, and (c) the
authoritative success criteria (the numbered list) now carry the correct
deferral note.

**Commit:** `4419b38`

## Verification

Both commits are present on the worktree branch:

```
4419b38 docs(05-05): drop bbox from Phase 5 SC#1; reference v2 deferral
c48fd64 fix(05-05): add PATCH to CORS allow_methods for /extend endpoint
```

No automated tests run for this plan — Task 1 is a single CORSMiddleware
constructor argument (backend test suite uses TestClient which bypasses CORS),
and Task 2 is a documentation edit. Functional verification is gated on
Task 3 (checkpoint:human-verify, blocking).

## Deviations from Plan

None — both tasks executed exactly as specified by the orchestrator.

## Deferred / Out-of-Scope

- **Task 3 — `checkpoint:human-verify` (blocking):** Deferred to the
  orchestrator/developer. Per the worktree-agent instructions, this checkpoint
  must NOT be auto-approved; a human must physically:
  1. Reload the frontend, click Extend on a stale listing, and confirm the
     PATCH request returns 200 (no CORS error in DevTools console).
  2. Visually re-read Phase 5 SC#1 in ROADMAP.md and confirm the new wording
     accurately reflects shipped behavior.
- The Phase-5 **goal** sentence (line 84) still references "bbox+filter-hash";
  intentionally left as-is per the scope analysis above.

## Self-Check: PASSED

- [x] `backend/app/main.py` contains `"GET", "POST", "PATCH", "OPTIONS"` (verified)
- [x] `.planning/ROADMAP.md` SC#1 contains "filter hash matches" and "deferred to v2" (verified)
- [x] commit `c48fd64` present in `git log` (verified)
- [x] commit `4419b38` present in `git log` (verified)
- [x] No modifications to STATE.md or ROADMAP.md progress-tracking fields (only the SC#1 wording on line 87 was touched; the progress table on lines 130-141 is untouched)
