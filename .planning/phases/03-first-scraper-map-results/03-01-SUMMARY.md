---
phase: 03-first-scraper-map-results
plan: 01
subsystem: api
tags: [scraper, craigslist, robots.txt, backend, httpx, selectolax, protego, structlog, pydantic]

# Dependency graph
requires:
  - phase: 01-foundation-skeleton
    provides: BudgetGuard contract, search_jobs/listings/daily_spend schema, ARQ WorkerSettings, /api/jobs route
  - phase: 02-search-input-nl-parsing
    provides: Phase 2 frontend POST payload (chips[] + global_flex) — CreateJobBody now accepts it
provides:
  - "Real Craigslist HTML scraper replacing stub_scraper at the ARQ entrypoint"
  - "RobotsCache (protego-backed) with per-job-run one-fetch-per-origin and SC#3 structured logs"
  - "Craigslist parsers: parse_search_results + parse_listing extracting lat/lng/source_name/posted_date/amenities (D-07)"
  - "Location whitelist (SSRF-safe city slug → craigslist subdomain mapping)"
  - "ChipModel + CreateJobBody.chips/.global_flex (Phase 2 frontend payload now type-validated end to end)"
  - "settings.scraper_max_listings env-driven, clamped to ≤30 (T-03-06)"
  - "BaseScraper Protocol for Phase 4 multi-source reuse"
affects: [04-llm-extraction-multi-source, 05-cache-dedup-freshness]

# Tech tracking
tech-stack:
  added: [protego>=0.6, selectolax>=0.4, httpx>=0.28 (runtime)]
  patterns:
    - "Per-job RobotsCache: one Protego.parse() per origin, structlog robots.fetched/robots.disallow events"
    - "Module-level httpx.AsyncClient factory (_make_client) so tests can monkeypatch in MockTransport"
    - "Pure parsers (parse_listing, parse_search_results) decoupled from IO — fixture-testable"
    - "JSONB-friendly source data layout: data['lat'], data['lng'], data['source_name']"

key-files:
  created:
    - backend/app/workers/scrapers/__init__.py
    - backend/app/workers/scrapers/base.py
    - backend/app/workers/scrapers/robots.py
    - backend/app/workers/scrapers/location.py
    - backend/app/workers/scrapers/craigslist.py
    - backend/tests/test_robots_cache.py
    - backend/tests/test_craigslist_parser.py
    - backend/tests/test_craigslist_scraper_integration.py
    - backend/tests/fixtures/craigslist_robots.txt
    - backend/tests/fixtures/craigslist_search.html
    - backend/tests/fixtures/craigslist_detail.html
  modified:
    - backend/pyproject.toml
    - backend/uv.lock
    - backend/app/settings.py
    - backend/app/workers/settings.py
    - backend/app/routes/jobs.py
    - .env.example

key-decisions:
  - "RobotsCache logs via structlog default JSON-to-stdout (SC#3 verifiability: grep worker stdout for 'robots.fetched' / 'robots.disallow')"
  - "Phase 3 forwards CreateJobBody.chips/.global_flex but scraper ignores them; Phase 4 will persist + use chips (Pitfall 9, deferred to avoid schema migration in this plan)"
  - "Photo host whitelist limited to craigslist.org + craigslistimages.org (T-03-05) — non-matching photo URLs dropped to None"
  - "scraper_max_listings clamped server-side via @field_validator('scraper_max_listings') to min(value, 30)"

patterns-established:
  - "Per-source scraper module: pure parsers + module-level _make_client() factory + ARQ run_search(ctx, job_id) — Phase 4 sources copy this shape"
  - "robots.txt fail-open with loud structlog warning — only ever runs against trusted hosts (whitelist enforced upstream)"

requirements-completed: [SCRAP-02, SCRAP-05]

# Metrics
duration: 25min
completed: 2026-05-11
---

# Phase 3 Plan 01: First Scraper Summary

**Real Craigslist HTML scraper (httpx + selectolax + protego) replacing stub_scraper at the ARQ entrypoint, with robots.txt enforcement (SCRAP-05), source-first lat/lng extraction (D-07), and Phase 2 chips/global_flex accepted at the API boundary.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-12T01:00:00Z (approx)
- **Completed:** 2026-05-12T01:25:00Z (approx)
- **Tasks:** 2/2 (both TDD)
- **Files modified:** 17 (11 created, 6 modified)

## Accomplishments

- Live-captured 3 Craigslist fixtures (robots.txt, search results page, single detail page) with verified `data-latitude`/`data-longitude` + `<time datetime>` attributes (locks assumptions A1/A2/A3).
- RobotsCache backed by protego: one robots.txt fetch per origin per job run, fail-open on 5xx, structlog `robots.fetched`/`robots.disallow`/`robots.fetch_failed` events for SC#3 audit.
- Craigslist parsers extract address/price/beds/baths/amenities/posted_date/lat/lng/source_url/source_name plus first photo URL — all fields range-validated (lat ∈ [-90, 90], lng ∈ [-180, 180]) per ASVS V5; out-of-range coords return None (T-03-03).
- `scrapers.craigslist.run_search` wired into `WorkerSettings.functions` — preserves Phase 1 status state machine and BudgetGuard contract; records `daily_spend` with `tokens=0` per Pitfall 7.
- `CreateJobBody` now declares typed `chips: list[ChipModel]` (Literal enum on `type`) and `global_flex: bool` — Phase 2 frontend payload is now validated end to end (was previously silently dropped via Pydantic's `extra='ignore'`).
- `settings.scraper_max_listings` env-driven (default 10), clamped to `min(env, 30)` via `@field_validator` (T-03-06).
- `BaseScraper` Protocol scaffolded for Phase 4 multi-source reuse.

## Task Commits

1. **Task 1a: RED tests + fixtures** — `28f2920` (test)
2. **Task 1b: scraper deps + package skeleton** — `f975dba` (chore)
3. **Task 2a: GREEN — RobotsCache + Craigslist parser + run_search** — `97c9c77` (feat)
4. **Task 2b: CreateJobBody chips/global_flex + ARQ worker swap** — `de6d105` (feat)

## Files Created/Modified

### Backend code
- `backend/app/workers/scrapers/__init__.py` — package marker
- `backend/app/workers/scrapers/base.py` — `BaseScraper` typing.Protocol
- `backend/app/workers/scrapers/robots.py` — `RobotsCache` (protego + httpx + structlog)
- `backend/app/workers/scrapers/location.py` — `location_to_search_url` whitelist (T-03-01)
- `backend/app/workers/scrapers/craigslist.py` — `run_search` ARQ task + `parse_search_results` + `parse_listing` (+ helpers)
- `backend/app/settings.py` — added `scraper_max_listings` with clamping validator
- `backend/app/workers/settings.py` — swap import from `stub_scraper` to `scrapers.craigslist`
- `backend/app/routes/jobs.py` — `ChipModel` + extended `CreateJobBody`
- `backend/pyproject.toml`, `backend/uv.lock` — added `httpx` (promoted to runtime), `selectolax`, `protego`

### Tests + fixtures
- `backend/tests/test_robots_cache.py` — 4 tests (allow/disallow, one-fetch-per-origin, disallow log, fail-open)
- `backend/tests/test_craigslist_parser.py` — 3 tests (detail field shape, search URL extraction, lat/lng range validation)
- `backend/tests/test_craigslist_scraper_integration.py` — 3 DB-integration tests (end-to-end insert, robots-disallow skip, daily_spend row)
- `backend/tests/fixtures/craigslist_robots.txt` — 132 B, includes verified `Disallow: /reply`
- `backend/tests/fixtures/craigslist_search.html` — ~364 KB, modern `cl-static-search-result` markup
- `backend/tests/fixtures/craigslist_detail.html` — ~40 KB, `<div id="map" data-latitude="37.578738" data-longitude="-122.330092">` + `<time datetime="2026-04-17T12:27:54-0700">`

### Config
- `.env.example` — added `SCRAPER_MAX_LISTINGS=10`

## Test Count Delta

| Before | After | Notes |
|--------|-------|-------|
| 7 backend tests (3 runnable + 4 DB-integration skipped without `SUPABASE_DB_URL`) | 17 backend tests (10 runnable + 7 DB-integration skipped) | +10 tests (+4 robots cache, +3 parser, +3 scraper integration) |

Local run (no `SUPABASE_DB_URL`): `10 passed, 7 skipped`. With `SUPABASE_DB_URL` set in CI, all 17 should pass.

Sample log line (proves SCRAP-05, taken from test stdout):

```json
{"origin": "https://sfbay.craigslist.org", "error": "Server error '500 Internal Server Error' for url 'https://sfbay.craigslist.org/robots.txt'", "event": "robots.fetch_failed", "timestamp": "2026-05-12T01:04:23.813870Z", "level": "warning"}
```

And on a normal (allow-list) run the worker emits `{"event": "robots.fetched", "origin": "...", "disallow_count": 7, ...}` once per origin per job (only ever `sfbay.craigslist.org` in Phase 3).

## Decisions Made

- **structlog defaults preserved (JSON to stdout)** — RobotsCache uses `structlog.get_logger()` with library defaults; tests use `capsys` rather than `caplog`. This matches how the ARQ worker process emits logs in production (Fly Machine stdout → log aggregator), so SC#3 verification is "grep worker.log" exactly as planned.
- **Photo URL host whitelist enforced in the parser** — even though the planned check is "before render", doing it server-side prevents persisting attacker-controlled URLs in JSONB. Belt-and-suspenders mitigation for T-03-05.
- **httpx promoted from dev to runtime dep** — the planner had `httpx` only in dev deps (it was previously only used in tests for ASGITransport). The scraper imports it directly, so it must be a runtime dep.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] httpx moved from dev-deps to runtime deps**
- **Found during:** Task 1 (adding scraper deps)
- **Issue:** Plan instructed `uv add httpx selectolax protego` and noted "httpx already present; uv add is idempotent" — but httpx was only in `[dependency-groups].dev`, not runtime. The scraper module imports httpx as production code, so it must be a runtime dep or the worker would fail at import in production.
- **Fix:** Moved `httpx>=0.28` into the `[project].dependencies` array; removed it from the dev group (uv won't double-install).
- **Files modified:** `backend/pyproject.toml`
- **Verification:** `uv sync` clean; full test suite still green.
- **Committed in:** `f975dba` (Task 1b commit)

**2. [Rule 1 - Bug] test_robots_cache log-capture path switched from caplog to capsys**
- **Found during:** Task 2 (verifying GREEN)
- **Issue:** Initial RED tests used `caplog` to assert the `robots.disallow` / `robots.fetch_failed` events were emitted. structlog's default configuration writes JSON directly to stdout (not via stdlib `logging`), so caplog captured nothing and two tests failed.
- **Fix:** Switched both tests to `capsys` and assert the event name appears in captured stdout. This matches how SC#3 verification actually works in production ("grep worker stdout").
- **Files modified:** `backend/tests/test_robots_cache.py`
- **Verification:** `uv run pytest -q tests/test_robots_cache.py` → 4 passed.
- **Committed in:** `97c9c77` (folded into Task 2a since the test file's contract — "the event is observable" — was unchanged; only the observation mechanism switched)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes essential. No scope creep. Plan was otherwise executed verbatim.

## Issues Encountered

- Pre-existing ruff lint warnings (2 unused `pytest` imports in `tests/test_jobs_api.py` and `tests/test_stub_scraper.py`) remain — out of scope per executor scope-boundary rule. Logged as ambient debt; can be cleaned in a separate `chore(lint)` pass.

## Fixture Capture Caveats

Fixtures were captured **2026-05-11 18:00 UTC** by live `curl` against:
- `https://www.craigslist.org/robots.txt`
- `https://sfbay.craigslist.org/search/apa`
- `https://sfbay.craigslist.org/pen/apa/d/san-mateo-penthouse-condo-for-rent-at/7928402854.html` (first listing on the search page)

Per RESEARCH.md A1-A3, re-verify monthly that:
1. Craigslist detail pages still embed `<div id="map" data-latitude data-longitude>` (D-07 source-first geocoding).
2. `<time datetime="...">` still ships on detail pages.
3. Search results still use `<li class="cl-static-search-result">` (parser has `a[href$=".html"]` fallback).

If A1 breaks, falls back to Phase 4 LLM extraction (still embedded in the contract: parser returns None for lat/lng).

## User Setup Required

None — no external service configuration required. The plan adds one optional env var (`SCRAPER_MAX_LISTINGS`) which has a sensible default (10).

## Threat Flags

None — all new surface is covered by the plan's existing `<threat_model>` register (T-03-01 through T-03-08).

## Self-Check: PASSED

Verified (post-write):
- `backend/app/workers/scrapers/{robots,location,craigslist,base}.py` exist
- `backend/tests/fixtures/craigslist_{robots.txt,search.html,detail.html}` exist
- Commits 28f2920, f975dba, 97c9c77, de6d105 all present in git log

## Next Phase Readiness

- Real Craigslist listings now stream to the existing Realtime channel — Phase 3 Plan 02 (MapView + ListingDrawer) can subscribe and render straight away.
- `data.lat`/`data.lng`/`data.source_name` available on every new listing row; old Phase 1 stub rows continue to coexist (frontend must handle missing fields gracefully).
- `chips` and `global_flex` now flow through the API; Phase 4 will add a `query_chips` JSONB column on `search_jobs` and let the scraper use them for query refinement.

---
*Phase: 03-first-scraper-map-results*
*Completed: 2026-05-11*
