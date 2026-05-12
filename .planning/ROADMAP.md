# Roadmap: Property Helper

**Generated:** 2026-05-10
**Revised:** 2026-05-10
**Phases:** 8 | **Requirements:** 34 | **Mode:** Vertical MVP

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | Foundation Skeleton | End-to-end infra (Next.js + FastAPI + Supabase + Redis + ARQ + Realtime) with cost guardrails wired and fake data flowing from worker to UI. | COST-01, COST-02, COST-03, CACH-03, CACH-04 | 5 |
| 2 | Search Input & NL Parsing | A non-technical user can compose a natural-language query, see it parsed into editable chips, toggle flex, and submit — backed by mock data. | SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05 | 4 |
| 3 | First Scraper + Map Results | Real Craigslist listings (robots.txt-respecting) appear on an interactive map with hover/click sync to the result list. | SCRAP-02, SCRAP-05, MAP-01, MAP-02, MAP-03, MAP-04 | 4 |
| 4 | LLM Extraction & Multi-Source | Claude Haiku extracts listings via forced tool-use over pre-filtered HTML, Playwright unlocks Apartments.com, and parallel sessions run with proper rate limiting. | SCRAP-01, SCRAP-03, SCRAP-04, SCRAP-06, SCRAP-07 | 4 |
| 5 | Cache, Dedup & Freshness | Overlapping searches return instantly from the shared cache, duplicate listings are merged across sources, and freshness/TTL is visible to the user. | CACH-01, CACH-02, SCRAP-08 | 3 |
| 6 | Auth | Supabase magic-link login with persistent sessions and clean logout from any page. | AUTH-01, AUTH-02, AUTH-03, AUTH-04 | 4 |
| 7 | Dashboard | Logged-in users save searches, save listings, and re-open past search history. | DASH-01, DASH-02, DASH-03 | 3 |
| 8 | Observability | Structured scraper logs, an admin health view per source, and per-search token cost display. | OBS-01, OBS-02, OBS-03 | 3 |

## Phase Details

### Phase 1: Foundation Skeleton
**Goal:** Stand up the end-to-end stack (Next.js, FastAPI, Supabase Postgres + Realtime, Redis, ARQ worker) with cost guardrails wired before any real LLM calls. A fake/stub scraper writes rows that stream to a placeholder UI via Supabase Realtime.
**Mode:** mvp
**Requirements:** COST-01, COST-02, COST-03, CACH-03, CACH-04
**Success Criteria:**
1. Clicking "Start search" in the web UI enqueues an ARQ job and creates a Supabase row with status "running".
2. Fake listings written by the worker appear in the browser within ~1 second via Supabase Realtime with no manual refresh.
3. Closing the tab and reopening the search URL still shows the in-progress or completed job (fire-and-forget persistence).
4. Listing rows in Supabase are stored at ~300–500 chars of structured data per listing, with photos as URLs only.
5. The orchestration scaffold refuses to exceed configured per-search caps (8–12 iters, token budget, 8KB per tool result) and writes a daily spend row for every simulated LLM call.
**Plans:** 3 plans
- [x] 01-01-PLAN.md — Repo scaffolding: docker-compose, .env.example, backend uv project, Supabase migration 0001_init.sql, frontend Next.js 15 + Tailwind + supabase-js, pytest scaffold. Includes [BLOCKING] schema-push checkpoint. (Completed 2026-05-11)
- [x] 01-02-PLAN.md — Backend behavior: BudgetGuard (COST-01/02/03), FastAPI POST/GET /api/jobs (CACH-03), ARQ worker + stub_scraper (CACH-04), and complete test suite (7 tests). (Completed 2026-05-11)
- [x] 01-03-PLAN.md — Frontend slice: Next.js page implementing UI-SPEC with Supabase Realtime streaming, localStorage reattach, and end-to-end manual smoke checkpoint covering all 5 ROADMAP success criteria. (Completed 2026-05-11; all 5 success criteria verified — `phase-1-complete`. Two post-execution bug fixes in 28c5d20.)

### Phase 2: Search Input & NL Parsing
**Goal:** Build the search-entry experience: a user types a natural-language apartment query, sees it parsed into structured editable chips with flex toggles, and submits to a "searching" state. Frontend-only, backed by mock data.
**Mode:** mvp
**Requirements:** SRCH-01, SRCH-02, SRCH-03, SRCH-04, SRCH-05
**Success Criteria:**
1. Typing "2BR in Champaign under $1500 with in-unit W/D" produces editable chips (beds=2, max_price=1500, location=Champaign, amenities=[w/d]) before submit.
2. User can edit or remove individual chips and see the change reflected in the parsed query state.
3. User can toggle an overall "willing to flex" mode and toggle flex on individual chips independently.
4. Submitting the search immediately enters a "searching" state and never prompts a clarifying question mid-run.
**Plans:** 3 plans
- [x] 02-01-PLAN.md — Test scaffold + NL parser: Vitest config + jsdom, parseQuery() pure function (TDD red→green), ChipType/Chip/JobPostPayload types, RED component test stubs for ChipList and SearchForm. (SRCH-01)
- [x] 02-02-PLAN.md — Chip UI components: ChipList.tsx (ChipPill static/edit + AddFilter) and SearchForm.tsx (textarea + debounce + GlobalFlexToggle). Turns Plan 01 RED stubs GREEN. (SRCH-01, SRCH-02, SRCH-03, SRCH-04)
- [ ] 02-03-PLAN.md — Page wiring + smoke: refactor page.tsx to mount SearchForm, enrich POST /api/jobs payload (chips + global_flex), update copy per UI-SPEC, end-to-end manual smoke verifying all 4 success criteria. (SRCH-01–05)
**UI hint**: yes

### Phase 3: First Scraper + Map Results
**Goal:** Replace mock data with a real Craigslist HTML scraper (httpx + selectolax) that respects robots.txt, and render real listings on an interactive map synced with a result list.
**Mode:** mvp
**Requirements:** SCRAP-02, SCRAP-05, MAP-01, MAP-02, MAP-03, MAP-04
**Success Criteria:**
1. A submitted search returns real Craigslist listings that render on an interactive map with priced pins that cluster when zoomed out.
2. Hovering a result card highlights its map pin and vice versa; clicking a pin or card opens a detail view with address, price, beds/baths, amenities, source name, source link, photo preview, and a "data from X date" label.
3. Before scraping any domain, the worker fetches and respects robots.txt and skips disallowed paths (verifiable in the job's scraper log).
4. Each listing displays a freshness label and a direct link back to its original Craigslist source.
**Plans:** 3 plans
- [x] 03-01-PLAN.md — Backend: capture Craigslist fixtures, RobotsCache (protego), Craigslist parser/scraper replacing stub_scraper, CreateJobBody chips/global_flex; full backend test suite green (SCRAP-02, SCRAP-05).
- [x] 03-02-PLAN.md — Frontend: vitest config + types lat/lng/source_name; MapView (MapLibre + OpenFreeMap positron + clustering), ListingList, ListingCard, ListingDrawer, safeUrl helpers; page.tsx D-11 side-by-side layout (MAP-01–04). (Completed 2026-05-12; 7 test files / 28 tests passing; build clean.)
- [x] 03-03-PLAN.md — End-to-end manual smoke checkpoint verifying SC#1–#4 on live stack (resume signal phase-3-complete).
**UI hint**: yes

### Phase 4: LLM Extraction & Multi-Source
**Goal:** Introduce Claude Haiku 4.5 as the structured extractor over pre-filtered HTML, add Playwright (with stealth) for Apartments.com, and fan out parallel scraper sessions per search under Redis-coordinated rate limits.
**Mode:** mvp
**Requirements:** SCRAP-01, SCRAP-03, SCRAP-04, SCRAP-06, SCRAP-07
**Success Criteria:**
1. A single user search triggers parallel scraper sessions against at least two sources (Craigslist + Apartments.com) and results from both appear on the same map.
2. Listings are extracted by Claude Haiku via forced tool-use over HTML pre-filtered with selectolax + trafilatura; raw, unfiltered DOM is never sent to the LLM (logs show 5–10× token reduction vs raw).
3. Apartments.com pages load via Playwright with stealth configuration and yield extracted listings on a typical run.
4. Sustained scraping against any one domain never exceeds 1 req/sec (with 0.1–0.5s jitter) across concurrent workers, enforced by a Redis distributed token bucket.
**Plans:** 4 plans
- [x] 04-01-PLAN.md — CR-01/CR-02 debt fixes, isAllowedApartmentsUrl, ANTHROPIC_API_KEY Settings field, and six Wave-0 RED test scaffolds for downstream plans.
- [x] 04-02-PLAN.md — Shared utilities: prefilter (selectolax+trafilatura), llm_extract (Claude Haiku forced tool-use + cache + Sonnet escalation), rate_limit (Redis SET NX PX). SCRAP-04, SCRAP-06, SCRAP-07.
- [x] 04-03-PLAN.md — Coordinator (fan-out + completion counter + D-16 partial failure), Craigslist rename to run_search_craigslist + acquire_domain_slot wrapping, WorkerSettings + jobs.py rewire. SCRAP-03 + SCRAP-04.
- [x] 04-04-PLAN.md — Dockerfile to Playwright base image, location_to_apartments_url allowlist, apartments.py (Playwright + stealth + prefilter + llm_extract + rate_limit), ENABLED_SOURCES append, [BLOCKING] manual E2E smoke. SCRAP-01 + SC#1–#4.

### Phase 5: Cache, Dedup & Freshness
**Goal:** Make repeat/overlapping searches feel instant via a shared bbox+filter-hash cache, merge duplicate listings across sources, and surface TTL/freshness state clearly to the user.
**Mode:** mvp
**Requirements:** CACH-01, CACH-02, SCRAP-08
**Success Criteria:**
1. A search whose geographic bounding box + filter hash overlaps a recent search returns matching cached listings sub-second without invoking any scraper.
2. Listings older than the 3–4 week TTL render with a "data from X date" label and a visible "re-search" / "extend" action that triggers a fresh scrape.
3. The same property surfaced from two sources appears as one card with a `sources[]` array of links, deduplicated by normalized address + beds + sqft range.
**Plans:** 4 plans
- [x] 05-01-PLAN.md — Migration 0002 (idempotent two-step ALTER for expires_at NOT NULL, dedup_key, filter_hash, chips, 3 indexes), [BLOCKING] supabase db push, and Wave-0 RED test scaffolds covering CACH-01/02 + SCRAP-08.
- [x] 05-02-PLAN.md — app/workers/cache.py (compute_filter_hash + copy_cached_listings), jobs.py persists filter_hash+chips and exposes expires_at+chips, coordinator cache-hit fast-path (CACH-01).
- [x] 05-03-PLAN.md — scrapers/dedup.py (compute_dedup_key + run_dedup_for_job), Craigslist sqft fix + dedup_key stamp, Apartments dedup_key stamp, mark_done dedup hook, PATCH /api/listings/{id}/extend (CACH-02, SCRAP-08).
- [ ] 05-04-PLAN.md — Frontend types + safeUrl multi-source helper, ListingCard stale-state + Extend/Re-search + sources_list rendering, page.tsx handler wiring, [BLOCKING] E2E smoke for SC#1–#3.

### Phase 6: Auth
**Goal:** Add Supabase magic-link authentication so users can claim sessions, with persistence across refresh and a clean logout flow from any page.
**Mode:** mvp
**Requirements:** AUTH-01, AUTH-02, AUTH-03, AUTH-04
**Success Criteria:**
1. A new user can enter their email, receive a magic link, and land logged in after clicking it.
2. A returning user can log in via magic link with no password prompt.
3. A logged-in session survives full browser refresh and tab reopen.
4. A logged-in user can log out from any page and is returned to an anonymous state with no leaked session.
**Plans:** TBD
**UI hint**: yes

### Phase 7: Dashboard
**Goal:** Give logged-in users a personal dashboard for saved searches, saved listings, and search history — all re-openable in one click.
**Mode:** mvp
**Requirements:** DASH-01, DASH-02, DASH-03
**Success Criteria:**
1. A logged-in user can save the current search (NL query + parsed chips) and re-run it from their dashboard with one click, producing fresh results.
2. A logged-in user can heart/bookmark individual listings to a personal shortlist and view that shortlist from the dashboard.
3. A logged-in user can see a list of past searches with result counts and re-open each one to view the original results.
**Plans:** TBD
**UI hint**: yes

### Phase 8: Observability
**Goal:** Give the owner/admin structured visibility into scraper health and LLM cost: per-run logs, per-source dashboard, and per-search token cost.
**Mode:** mvp
**Requirements:** OBS-01, OBS-02, OBS-03
**Success Criteria:**
1. Every scraper run writes a structured log row (source domain, listings found, duration, errors, token cost) viewable per job.
2. The owner admin view shows per-source health: last run time, success rate, average listing count, and recent errors.
3. With debug display enabled, the owner can see the total token cost of a given search on its results page.
**Plans:** TBD
**UI hint**: yes

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation Skeleton | 3/3 | Complete | 2026-05-11 |
| 2. Search Input & NL Parsing | 3/3 | Complete | 2026-05-11 |
| 3. First Scraper + Map Results | 3/3 | Complete | 2026-05-12 |
| 4. LLM Extraction & Multi-Source | 4/4 | Complete | 2026-05-12 |
| 5. Cache, Dedup & Freshness | 2/4 | In progress | - |
| 6. Auth | 0/0 | Not started | - |
| 7. Dashboard | 0/0 | Not started | - |
| 8. Observability | 0/0 | Not started | - |
