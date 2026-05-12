# Phase 4: LLM Extraction & Multi-Source - Context

**Gathered:** 2026-05-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce Claude Haiku 4.5 as the structured listing extractor over pre-filtered HTML (replacing the Phase 3 direct-parse approach for any source that needs it), add Apartments.com via Playwright with stealth, and fan out parallel scraper sessions per search under Redis-coordinated rate limits. Real listings from at least two sources appear on the same map.

**In scope:** LLM forced tool-use extraction, HTML pre-filtering (selectolax + trafilatura), Playwright + playwright-stealth for Apartments.com, parallel ARQ sub-tasks per source, Redis token-bucket rate limiting per domain, CR-01/CR-02 debt fixes, safeUrl.ts extension for Apartments.com URLs.

**Out of scope:** Additional sources beyond Craigslist + Apartments.com, deduplication across sources (Phase 5), caching/TTL (Phase 5), auth (Phase 6).

</domain>

<decisions>
## Implementation Decisions

### LLM Extraction Call Pattern
- **D-01:** Use Claude Haiku 4.5 with forced tool-use via a single `extract_listings(listings: List[Listing])` tool per page — `tool_choice={"type":"tool","name":"extract_listings"}` to prevent prose output.
- **D-02:** System prompt + tool definitions are marked as prompt-cache breakpoints (Anthropic `cache_control` headers) — first call pays full price, subsequent calls within TTL pay ~10% of input cost.
- **D-03:** `Listing` schema is a Pydantic model with: `address`, `price`, `beds`, `baths`, `sqft`, `amenities`, `source_url`, `image_url`, `posted_date`, `lat`, `lng`, `source_name`. Same fields as Phase 3's parsed listing dict.
- **D-04:** Escalation model: if Haiku returns empty `listings[]` or parse error, retry once with Claude Sonnet 4.6 (not on every call — only on failure, to control cost).

### HTML Pre-Filtering Pipeline
- **D-05:** selectolax runs first — strips nav, footer, scripts, ads via CSS selector targeting listing regions (e.g., `li.result-row` for Craigslist, listing card divs for Apartments.com). Removes DOM noise before any LLM sees the text.
- **D-06:** trafilatura runs on the selectolax output for main-content extraction — removes boilerplate prose, keeps listing-specific fields. Target: 5–10× token reduction vs raw DOM (per SCRAP-07).
- **D-07:** The pre-filtered text (not raw HTML) is passed to Claude. Raw HTML is never sent to the LLM.
- **D-08:** Max pre-filtered payload per LLM call: 8KB (existing `check_payload` guard in BudgetGuard — this was the Phase 3 COST-03 fix; keep enforcing it).

### Playwright Integration (Apartments.com)
- **D-09:** Playwright runs inline inside the ARQ worker process — no separate service. The backend Dockerfile switches from a plain Python base to `mcr.microsoft.com/playwright/python:v1.x-jammy` (or installs Chromium via `playwright install chromium` in the Dockerfile).
- **D-10:** playwright-stealth applied via `stealth_async(page)` before any Apartments.com navigation to hide `navigator.webdriver` and fingerprint signals.
- **D-11:** Apartments.com scraper follows the same ARQ task pattern as craigslist.py — a top-level `run_search_apartments(ctx, job_id)` ARQ function. It parses HTML via selectolax + LLM, not by reading DOM state directly.
- **D-12:** Playwright context is created fresh per job (no persistent browser sessions across jobs) to avoid session state leakage.

### Parallel Coordinator Architecture
- **D-13:** A coordinator ARQ task (`run_search_coordinator(ctx, job_id)`) is the new entry point — it replaces the direct `run_search` call in WorkerSettings. It reads the job's query/chips, then fans out one sub-task per enabled source using `ctx.arq.enqueue_job` (or equivalent ARQ defer).
- **D-14:** Sub-tasks (`run_search` for Craigslist, `run_search_apartments` for Apartments.com) run independently and INSERT listings to Supabase as they arrive — Realtime streams both sources to the frontend in parallel.
- **D-15:** Coordinator marks the search_jobs row as `status='completed'` only after ALL sub-tasks finish (use ARQ job dependencies or a Redis counter: `INCR completed:{job_id}`).
- **D-16:** If one source fails, the other's results still appear. Coordinator records partial failure in the job's error field but does not set status='failed' unless all sources fail.

### Redis Rate Limiting
- **D-17:** Sliding window rate limit per domain, key pattern: `rate_limit:{domain}` (e.g., `rate_limit:craigslist.org`). Max 1 request per second, coordinated across all ARQ workers sharing the same Redis instance used by ARQ.
- **D-18:** Add 0.1–0.5s random jitter after acquiring the rate limit token (before each fetch) to avoid thundering herd across parallel workers.
- **D-19:** Implementation: simple Redis `SET NX PX 1000` per-domain mutex or a token bucket using `INCR` + `EXPIRE` — whichever is simpler to implement correctly. Does NOT need a full Redis rate-limit library.
- **D-20:** Rate limit applies to all HTTP fetches (both httpx in craigslist.py and Playwright page navigations for Apartments.com).

### Code Review Debt (carry-forward from CR-01/CR-02)
- **D-21:** Fix CR-01 first thing in Phase 4: add `Field(..., min_length=1, max_length=512)` to `CreateJobBody.query` in `backend/app/routes/jobs.py`.
- **D-22:** Fix CR-02 first thing in Phase 4: replace `host.endsWith('craigslistimages')` with `host.endsWith('.craigslistimages.org') || host === 'craigslistimages.org'` in `frontend/app/components/safeUrl.ts`.
- **D-23:** Extend `safeUrl.ts` with `isAllowedApartmentsUrl(url)` helper for Apartments.com source links — same host-whitelist pattern as craigslist helpers (allow `apartments.com`, `*.apartments.com`).

### Claude's Discretion
- Specific CSS selectors for Apartments.com listing regions (researcher/planner to identify from live HTML samples or existing public docs).
- Whether to use ARQ's native job dependencies or a Redis counter for coordinator completion detection — planner picks the simpler approach.
- Exact trafilatura config flags — default config is fine unless token counts remain too high after testing.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Constraints and Stack
- `.planning/ROADMAP.md` §Phase 4 — Phase goal, success criteria, and requirement IDs
- `.planning/REQUIREMENTS.md` — SCRAP-01, SCRAP-03, SCRAP-04, SCRAP-06, SCRAP-07 full requirement text
- `CLAUDE.md` §LLM Strategy — Claude Haiku 4.5 as default, Sonnet escalation, prompt caching rules, token minimization patterns
- `CLAUDE.md` §Technology Stack — full stack decisions including selectolax, trafilatura, httpx, playwright-stealth, ARQ

### Existing Scraper Infrastructure
- `backend/app/workers/scrapers/base.py` — BaseScraper Protocol (structural interface all scrapers must satisfy)
- `backend/app/workers/scrapers/craigslist.py` — Reference implementation: ARQ task pattern, RobotsCache usage, parse_listing, BudgetGuard integration
- `backend/app/workers/scrapers/robots.py` — RobotsCache (must be used by Apartments.com scraper too)
- `backend/app/guards/budget.py` — BudgetGuard: `check_iter`, `record_spend(tokens, cost_usd)` — LLM calls MUST call `record_spend` with real token counts

### Frontend
- `frontend/app/components/safeUrl.ts` — Host-whitelist module to extend for Apartments.com URLs (CR-02 fix + new helper)
- `frontend/app/types.ts` — Listing type definition (must stay compatible as new source adds fields)

### Phase 3 Code Review
- `.planning/phases/03-first-scraper-map-results/03-REVIEW.md` — CR-01 and CR-02 findings to fix in Phase 4

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/workers/scrapers/robots.py` (`RobotsCache`): Fetch-once-per-origin robots.txt cache with protego — Apartments.com scraper must call this before any page fetch.
- `backend/app/guards/budget.py` (`BudgetGuard`): Already wired for real LLM token accounting via `record_spend`. Phase 4 LLM calls replace the `tokens=0` stub with actual token counts from Anthropic API response.
- `backend/app/workers/scrapers/location.py`: Geocoding helpers for lat/lng extraction — may be reusable if Apartments.com provides address without coordinates.
- `frontend/app/components/safeUrl.ts`: Pattern for per-source URL allowlisting — extend for Apartments.com, do not rewrite.

### Established Patterns
- **ARQ task pattern**: `async def run_search(ctx: dict, job_id: str) -> None` — top-level ARQ function, no class instantiation. New tasks follow this exact signature.
- **Structlog JSON logging**: all scraper events log with `structlog.get_logger()` — follow existing `robots.fetched`, `scraper.listing` event key patterns.
- **BudgetGuard from env**: `guard = BudgetGuard.from_env(db)` — use this constructor, don't instantiate directly.
- **Supabase INSERT pattern**: listings inserted via asyncpg `executemany` with `data JSONB` column — Phase 4 new source uses the same INSERT, same JSONB shape, adds `source_name='apartments'`.

### Integration Points
- `backend/app/workers/settings.py` `WorkerSettings.functions`: add coordinator + new source tasks here. Remove or keep direct `run_search` for Craigslist (coordinator calls it as a sub-task).
- `backend/app/routes/jobs.py` `CreateJobBody`: add `max_length=512` to query field (CR-01 fix).
- Dockerfile: switch to Playwright base image or add `playwright install chromium` step.

</code_context>

<specifics>
## Specific Ideas

- CLAUDE.md specifies: "Force tool use with `tool_choice = {"type": "tool", "name": "extract_listings"}` to avoid wasted prose output" — implement exactly this.
- CLAUDE.md specifies: "The system prompt and tool definitions are stable across every scrape. Mark them as cache-control breakpoints in the SDK." — use Anthropic Python SDK `cache_control={"type":"ephemeral"}` on system + tool definition blocks.
- Per the Phase 3 code review: `check_iter` was consuming the BudgetGuard iteration budget inside the scraper loop (WR-03). Phase 4 coordinator should call `check_iter` once per source, not once per page — reserve iterations for LLM tool calls.
- Apartments.com is an SPA — Playwright must wait for listing cards to render before extracting HTML (`page.wait_for_selector(".placard-container", timeout=15000)` or similar).

</specifics>

<deferred>
## Deferred Ideas

- Realtor.com scraper (Phase 4 success criteria only requires Craigslist + Apartments.com — third source is future)
- Deduplication of listings across sources by normalized address + beds + sqft (Phase 5)
- BYOK (user Anthropic API key) for Phase 4 LLM calls — use the project key for now; BYOK is an auth/dashboard feature (Phase 6+)
- Stagehand caching for selector resilience — only if Playwright selectors break in production; not needed for v1

</deferred>

---

*Phase: 4-LLM Extraction & Multi-Source*
*Context gathered: 2026-05-11*
