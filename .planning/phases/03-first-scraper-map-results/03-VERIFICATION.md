---
phase: 03-first-scraper-map-results
verified: 2026-05-11T21:55:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Live end-to-end smoke: submit a real search and visually confirm SC#1-SC#4"
    expected: "Map shows priced pins that cluster; hovering card highlights pin and vice versa; drawer opens with full fields; robots.fetched in worker log; freshness label and craigslist source link present"
    why_human: "03-03-PLAN.md is a checkpoint:human-verify plan requiring live stack validation. The resume signal 'phase-3-complete' was documented in 03-03-SUMMARY.md frontmatter but was not independently verifiable from code artifacts alone. The SUMMARY.md is a claim, not evidence; the automated verifier cannot reproduce a live Craigslist scrape, a running MapLibre browser render, or the ARQ worker stdout."
---

# Phase 3: First Scraper + Map Results — Verification Report

**Phase Goal:** End-to-end vertical slice — real Craigslist listings stream into Supabase and render on an interactive map with clustered priced pins, a scrollable result list, and a slide-out detail drawer. All Phase 3 success criteria verified by human tester.
**Verified:** 2026-05-11T21:55:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Submitting a search results in real Craigslist apartment listings inserted into the listings table | VERIFIED | `craigslist.py` implements `run_search` with `parse_search_results` + `parse_listing`, calls `INSERT INTO listings` (line 246, 345); `WorkerSettings.functions = [run_search]` confirmed via `from .scrapers.craigslist import run_search` in `backend/app/workers/settings.py` line 14 |
| 2 | robots.txt is fetched and parsed before any scraping; disallowed paths are skipped (SCRAP-05) | VERIFIED | `RobotsCache.allow()` called before both search URL (line 278) and each detail URL (line 316) in `craigslist.py`; `RobotsCache` backed by protego in `robots.py` line 23; structlog events `robots.fetched`/`robots.disallow` emitted; fixture `craigslist_robots.txt` exists with `User-agent: *` |
| 3 | robots.txt cached per origin for one job run; outcome logged via structlog | VERIFIED | `RobotsCache` stores parsed object by origin (structural caching in class); `structlog.get_logger()` used; `robots.fetched`/`robots.disallow`/`robots.fetch_failed` events confirmed in test output and SUMMARY |
| 4 | Each inserted listing's data JSONB contains lat, lng, source_name, posted_date, source_url, address, price, beds, baths, amenities | VERIFIED | `craigslist.py` lines 229-232 confirm `source_name: "craigslist"`, `posted_date`, `lat`, `lng`; lines 159-164 extract lat/lng from `data-latitude`/`data-longitude`; fixture `craigslist_detail.html` line 467 has `data-latitude="37.578738" data-longitude="-122.330092"` |
| 5 | User sees interactive MapLibre map with priced pins clustering when zoomed out (MAP-01) | VERIFIED | `MapView.tsx` line 18: `STYLE_URL = 'https://tiles.openfreemap.org/styles/positron'`; lines 46-51: `cluster: true, clusterRadius: 50, promoteId: 'id'`; automated `MapView.test.tsx` test `addSource_called_with_cluster_true` passes (7 test files / 28 tests green) |
| 6 | Hovering card highlights map pin and vice versa via setFeatureState (MAP-02); hovering pin scrolls card into view (D-14) | VERIFIED (automated) / UNCERTAIN (D-14 scroll behavior — human only) | `MapView.tsx` lines 219-260: `map.setFeatureState` called for hover/select in dedicated effect with lastHoveredRef/lastSelectedRef; `MapView.test.tsx` line 153 `setFeatureState_called_on_hover_and_select` asserts call shape including clear-previous; `ListingList.tsx` lines 24-36: `cardRefs` Map + `scrollIntoView({ block: 'nearest', behavior: 'smooth' })` in `useEffect([hoveredId])`; scroll behavior is visual-only |
| 7 | Each card shows address, price, beds/baths, amenities, source name, source link, freshness label (MAP-03); detail drawer shows photo, full fields, source link (MAP-04) | VERIFIED | `ListingCard.test.tsx` `test_renders_MAP-03_fields` passes; `ListingDrawer.test.tsx` `test_open_renders_fields` passes; `safeUrl.ts` `isAllowedCraigslistUrl`/`isAllowedCraigslistImage`/`formatPostedDate` exported (lines 9, 20, 40) and consumed in `ListingDrawer.tsx` lines 6-7, 45-46; drawer `role="dialog"` + slide classes `translate-x-full`/`translate-x-0` confirmed |
| 8 | Submitting a new search resets selectedId and hoveredId to null; listings without lat/lng appear in list only with inline notice | VERIFIED | `page.tsx` lines 136-137: `setSelectedId(null); setHoveredId(null)` in `startSearch`; `ListingList.tsx` renders `noCoordsCount` notice when any listing lacks lat/lng; `ListingList.test.tsx` `test_no_coords_notice` passes |

**Score:** 8/8 truths verified (D-14 scroll behavior is the single human-verification item; all other truths have automated evidence)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/workers/scrapers/robots.py` | RobotsCache with protego + structlog | VERIFIED | `class RobotsCache` line 23; `protego>=0.6` in `pyproject.toml` runtime deps |
| `backend/app/workers/scrapers/craigslist.py` | `run_search` + `parse_search_results` + `parse_listing` | VERIFIED | All three functions present at lines 51, 155, 239 |
| `backend/app/workers/scrapers/location.py` | `location_to_search_url` whitelist | VERIFIED | File exists; function present |
| `backend/app/workers/scrapers/base.py` | `BaseScraper` Protocol | VERIFIED | `class BaseScraper(Protocol)` confirmed; `from typing import Any, Protocol` line 9 |
| `backend/tests/fixtures/craigslist_detail.html` | Contains `data-latitude`/`data-longitude` | VERIFIED | Line 467: `data-latitude="37.578738" data-longitude="-122.330092"` |
| `backend/tests/fixtures/craigslist_search.html` | >5KB search results page | VERIFIED | 363,872 bytes |
| `backend/tests/fixtures/craigslist_robots.txt` | Contains `User-agent: *` | VERIFIED | 1 match for `User-agent: *` confirmed |
| `frontend/app/components/MapView.tsx` | MapLibre wrapper with cluster + setFeatureState | VERIFIED | 270 lines; cluster source line 46; setFeatureState lines 219-260; positron style line 18 |
| `frontend/app/components/ListingList.tsx` | cardRefs + scrollIntoView | VERIFIED | `cardRefs` line 24; `scrollIntoView` line 31 |
| `frontend/app/components/ListingCard.tsx` | React.memo with hover/select ring, registerRef | VERIFIED | `React.memo` line 121; `registerRef` lines 17, 26, 60 |
| `frontend/app/components/ListingDrawer.tsx` | Slide-out detail panel | VERIFIED | `role="dialog"` line 34; `translate-x-full`/`translate-x-0` lines 29, 50 |
| `frontend/app/components/safeUrl.ts` | URL whitelist helpers | VERIFIED | `isAllowedCraigslistUrl`, `isAllowedCraigslistImage`, `formatPostedDate` at lines 9, 20, 40 |
| `frontend/vitest.config.ts` | Vitest jsdom config | VERIFIED | `environment: 'jsdom'` line 7; `"test": "vitest"` in `package.json` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/app/workers/settings.py` | `scrapers/craigslist.py::run_search` | `from .scrapers.craigslist import run_search` | WIRED | Confirmed line 14 |
| `craigslist.py` | `robots.py::RobotsCache.allow()` | `await robots.allow(url)` before every fetch | WIRED | Lines 278, 316 confirmed |
| `craigslist.py` | Supabase listings table | `INSERT INTO listings ... $3::jsonb` | WIRED | Lines 246, 345 confirmed |
| `backend/app/routes/jobs.py::CreateJobBody` | Phase 2 frontend payload | `class ChipModel` + `chips: list[ChipModel]` + `global_flex: bool` | WIRED | Lines 18, 42, 43 confirmed |
| `frontend/app/page.tsx` | `MapView.tsx` | `<MapView listings={listings} hoveredId selectedId onHover onSelect />` | WIRED | `page.tsx` line 255 confirmed |
| `frontend/app/page.tsx` | `ListingList.tsx` | `<ListingList listings={listings} ... />` | WIRED | `page.tsx` line 264 confirmed |
| `frontend/app/page.tsx` | `ListingDrawer.tsx` | `<ListingDrawer listing={selectedListing} onClose />` | WIRED | `page.tsx` line 286 confirmed |
| `MapView.tsx` | MapLibre GeoJSON source 'listings' | `map.addSource('listings', { type:'geojson', cluster:true, ... })` | WIRED | Lines 46-51 confirmed |
| `MapView.tsx` | MapLibre feature-state hover/select | `map.setFeatureState({source:'listings', id}, {hovered/selected:true/false})` | WIRED | Lines 219-260; lastHoveredRef/lastSelectedRef tracking confirmed |
| `MapView.tsx` | OpenFreeMap CDN | `style: 'https://tiles.openfreemap.org/styles/positron'` | WIRED | Line 18 confirmed |
| `ListingList.tsx` | DOM scroll-into-view | `cardRefs.get(hoveredId)?.scrollIntoView({block:'nearest', behavior:'smooth'})` | WIRED | Lines 30-31 confirmed |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `MapView.tsx` | `listings` prop | `page.tsx` Supabase Realtime INSERT subscription (`mergeById` on `payload.new`) | Yes — Supabase Realtime channel fires on real DB inserts from `craigslist.run_search` | FLOWING |
| `ListingList.tsx` | `listings` prop | Same Realtime path | Yes | FLOWING |
| `ListingDrawer.tsx` | `listing` prop | `listings.find(l => l.id === selectedId)` from same source | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend test suite green | `cd backend && uv run pytest -q` | `10 passed, 7 skipped` (DB-integration skipped without `SUPABASE_DB_URL`) | PASS |
| Frontend test suite green | `cd frontend && npm run test -- --run` | `7 test files / 28 tests passed` | PASS |
| Frontend build clean | `cd frontend && npm run build` | Exit 0; no `window is not defined`; page 339 kB (+275 kB maplibre-gl expected) | PASS |
| No XSS vector via dangerouslySetInnerHTML | `grep -r dangerouslySetInnerHTML frontend/app/` | 0 matches | PASS |

### Probe Execution

Step 7c: SKIPPED — Phase 03 has no `scripts/*/tests/probe-*.sh` probes. Verification uses automated pytest + vitest suites (Step 7b) and a human checkpoint plan (03-03).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCRAP-02 | 03-01 | HTML scraping with httpx + selectolax for Craigslist | SATISFIED | `craigslist.py` uses httpx + selectolax; fixture-tested via `test_craigslist_parser.py` (3 tests) + `test_craigslist_scraper_integration.py` (3 tests) |
| SCRAP-05 | 03-01 | robots.txt checked and respected before scraping | SATISFIED | `RobotsCache` with protego; `allow()` called before search URL and each detail URL; `robots.fetched`/`robots.disallow` structlog events; integration test `test_robots_disallow_skips_url` passes |
| MAP-01 | 03-02 | Interactive map with price-labeled pins; cluster on zoom-out | SATISFIED | `MapView.tsx` with OpenFreeMap positron tiles; `cluster:true` source; `MapView.test.tsx::addSource_called_with_cluster_true` passes |
| MAP-02 | 03-02 | Hover card highlights pin; hover pin highlights card | SATISFIED (automated) / UNCERTAIN (pin-hover scrolls card — human) | `setFeatureState` wiring confirmed; `MapView.test.tsx::setFeatureState_called_on_hover_and_select` passes; `cardRefs.scrollIntoView` confirmed in `ListingList.tsx`; visual scroll behavior is human-only |
| MAP-03 | 03-02 | Card shows address, price, beds/baths, amenities, source, link, freshness | SATISFIED | `ListingCard.test.tsx::test_renders_MAP-03_fields` passes; `safeUrl.ts` helpers gate link + photo |
| MAP-04 | 03-02 | Click opens detail view with photo, fields, source link | SATISFIED | `ListingDrawer.test.tsx::test_open_renders_fields` + `test_source_url_whitelist` + `test_close_button` + `test_escape_key` all pass |

No orphaned requirements found. All 6 requirement IDs from PLAN frontmatter (SCRAP-02, SCRAP-05, MAP-01, MAP-02, MAP-03, MAP-04) are accounted for and marked Complete in `REQUIREMENTS.md` traceability table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None found | — | — | — | No TBD/FIXME/XXX markers; no return null stubs; no hardcoded empty arrays in rendering paths; no dangerouslySetInnerHTML |

No debt markers in phase-modified files. Pre-existing ruff warnings in `tests/test_jobs_api.py` and `tests/test_stub_scraper.py` (unused `pytest` import) are out of scope per SUMMARY.md Executor rule; not introduced by Phase 3.

### Human Verification Required

#### 1. Live End-to-End Smoke (SC#1–SC#4)

**Test:** Run the full stack (backend uvicorn + ARQ worker + frontend dev server), submit a search for "2BR in SF Bay Area under $5000", and visually verify all four success criteria:
- SC#1: Map renders with priced pins; pins cluster on zoom-out; cluster click eases in
- SC#2: Card hover highlights pin; pin hover highlights card and scrolls it into view; click opens drawer with photo, address, price, beds/baths, amenities, source name, "View on craigslist" link, freshness label
- SC#3: `grep -E 'robots.fetched' /tmp/phase3-worker.log` returns at least one line for craigslist.org
- SC#4: "data from {Mon DD}" label visible on cards and drawer; source link opens craigslist.org in new tab with `rel=noreferrer`

**Expected:** All four criteria pass; no browser console errors; no SSR errors in dev output.

**Why human:** MapLibre rendering, real Craigslist HTML content (fixture-tested but live HTML may drift), ARQ worker stdout (SC#3), and D-14 pin-hover-scrolls-card behavior are not testable without a live browser and running stack. The 03-03-SUMMARY.md documents `phase-3-complete` was received, but that document is a claim; independent human confirmation is the only dispositive evidence for a checkpoint:human-verify plan.

Note: The resume signal `phase-3-complete` from 03-03-SUMMARY.md is consistent with the codebase evidence. All automated indicators are green. This human verification item is a process gate, not a code gap.

### Gaps Summary

No code gaps identified. All 8 must-have truths are VERIFIED by codebase evidence. All 6 requirement IDs are satisfied. All key links are wired. No stub patterns, debt markers, or disconnected data flows found.

The `human_needed` status reflects that Phase 3's Plan 03-03 was explicitly designed as a blocking human checkpoint (`gate="blocking"`). The 03-03-SUMMARY.md records the resume signal `phase-3-complete` from the human verifier on 2026-05-11. If the project owner considers that signal sufficient, the phase may be marked complete without a repeat live run — this is a process decision, not a code quality decision.

---

_Verified: 2026-05-11T21:55:00Z_
_Verifier: Claude (gsd-verifier)_
