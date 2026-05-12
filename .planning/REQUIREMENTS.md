# Requirements: Property Helper

**Defined:** 2026-05-10
**Core Value:** Non-technical users say what they want once in natural language and get consolidated, map-visualized apartment results without being asked anything else.

## v1 Requirements

### Authentication

- [ ] **AUTH-01**: User can sign up with email address and receive a magic link to log in
- [ ] **AUTH-02**: User can log in via email + magic link (no password required)
- [ ] **AUTH-03**: User session persists across browser refresh and tab reopening
- [ ] **AUTH-04**: User can log out from any page

### Search Input

- [ ] **SRCH-01**: User can type a natural language apartment query (e.g., "2BR in SF Bay Area under $3k, in-unit W/D") and the system parses it into structured, editable chips (price range, beds, baths, location, amenities)
- [ ] **SRCH-02**: User can edit or remove individual parsed chips before submitting a search
- [ ] **SRCH-03**: User can set an overall flexibility mode per query ("willing to flex" — signals to the LLM that soft constraints should be relaxed when results are sparse)
- [ ] **SRCH-04**: User can toggle flex on or off per individual chip (e.g., "hard limit on price, flex on baths")
- [ ] **SRCH-05**: User can submit a search and immediately see a "searching" state; the system never pauses to ask clarifying questions mid-run

### Map & Results

- [x] **MAP-01**: User sees search results displayed on an interactive map with listing pins showing price labels; pins cluster when zoomed out
- [x] **MAP-02**: Hovering a listing card highlights the corresponding pin on the map; hovering a pin highlights the corresponding card in the list
- [x] **MAP-03**: Each listing shows: address, price, beds/baths, key amenities, source name, source link, and a "data from X date" freshness label
- [x] **MAP-04**: User can click a listing pin or card to expand a detail view with photo preview and direct link to the original listing source

### Caching & Freshness

- [x] **CACH-01**: New searches check the shared listing cache first; cached listings matching the query's geographic bounding box and filters are returned instantly without re-scraping
- [ ] **CACH-02**: Listings expire after 3–4 weeks (TTL); expired listings are labeled "data from X date" and the user is offered a "re-search" option to scrape fresh data
- [ ] **CACH-03**: Search job persists in Supabase so the user can close the tab and return later to find completed results (fire-and-forget)
- [ ] **CACH-04**: Each listing is stored at ~300–500 characters of structured data to stay within Supabase 500MB free tier; photos are stored as URLs only

### Scraping & Orchestration

- [ ] **SCRAP-01**: System uses Playwright browser automation (with playwright-stealth) for major aggregators (Zillow, Apartments.com, Realtor.com) that prohibit HTML scraping in their ToS
- [x] **SCRAP-02**: System uses traditional HTML scraping (httpx + selectolax) for Craigslist and smaller property management sites where robots.txt permits
- [ ] **SCRAP-03**: Multiple scraper sessions run in parallel per search query (not sequentially)
- [ ] **SCRAP-04**: Rate limiting enforced per-domain at max 1 req/sec with 0.1–0.5s random jitter, coordinated across parallel workers via Redis distributed token bucket
- [x] **SCRAP-05**: robots.txt is checked and respected for every target domain before scraping
- [ ] **SCRAP-06**: LLM (Claude Haiku 4.5) extracts structured listing data from pre-filtered HTML using forced tool-use schema; raw HTML is never sent to the LLM
- [ ] **SCRAP-07**: HTML is pre-filtered (selectolax + trafilatura) to extract only listing regions before passing to LLM — target 5–10× token reduction vs raw DOM
- [ ] **SCRAP-08**: Scraped listings from multiple sources are deduplicated using normalized address + beds + sqft range composite key; duplicate sources are merged into a single listing with a `sources[]` array

### Cost Controls

- [ ] **COST-01**: LLM orchestration enforces hard loop limits: max 8–12 iterations per search, per-search token budget cap, and loop detection on repeated tool signatures
- [ ] **COST-02**: Daily LLM API spend is logged to the database for observability and future budget enforcement features
- [ ] **COST-03**: Tool-result payloads passed to Claude are capped at 8KB per result to prevent context bloat

### Observability & Debugging

- [ ] **OBS-01**: Every scraper run produces a structured log entry: source domain, listings found, duration, errors encountered, token cost for that run
- [ ] **OBS-02**: Admin/owner dashboard view shows scraper health per source: last run time, success rate, average listings found, recent errors
- [ ] **OBS-03**: Each search result page shows the token cost of that search (opt-in debug display for the owner/admin)

### User Dashboard

- [ ] **DASH-01**: User can save a search (stores the NL query and parsed chips) to re-run later from their dashboard
- [ ] **DASH-02**: User can bookmark/heart individual listings to a personal saved shortlist
- [ ] **DASH-03**: User can view search history (past searches with result count) and re-open results

## v2 Requirements

### Voice Input

- **VOICE-01**: User can press and hold a mic button to dictate a search query; browser transcribes via Web Speech API and auto-populates the input field
- **VOICE-02**: Users on Firefox (where Web Speech API is disabled) are routed to a server-side Whisper transcription fallback

### Map Enhancements

- **MAP-V2-01**: Zone analytics overlay on map: neighborhoods and H3 hex zones are shaded by median rent, listing count, and key metrics — computed on-the-fly from listing coordinates using PostGIS
- **MAP-V2-02**: Streaming results: listing pins drop onto the map in real-time as scrapers finish, with a live "Searching… X matches so far" counter (Supabase Realtime Broadcast)
- **MAP-V2-03**: Walk Score / Transit Score badges per listing zone

### Cost & BYOK

- **COST-V2-01**: Per-user LLM budget cap ($1–3 of shared Anthropic API budget); once cap is reached, user is prompted to add their own Anthropic API key (BYOK)
- **COST-V2-02**: BYOK: users enter their own Anthropic API key in account settings; key is stored encrypted (app-layer encryption), never logged in plaintext
- **COST-V2-03**: Daily spend alarm: alert owner/admin when daily API cost exceeds 2× expected baseline

### Notifications & Alerts

- **NOTF-01**: User can enable email alerts for saved searches (notify when new listings match criteria)
- **NOTF-02**: User can set alert cadence (daily digest vs instant)

### Scraping Expansion

- **SCRAP-V2-01**: Stagehand fallback for scrapers where CSS selectors have rotted — LLM-assisted selector repair
- **SCRAP-V2-02**: Scheduled per-metro pre-scraping background job (makes live searches instant; major cost reduction)
- **SCRAP-V2-03**: Residential/mobile proxy rotation for hardened anti-bot sites (Zillow, Realtor.com)

### OAuth & Social

- **AUTH-V2-01**: User can sign up / log in with Google OAuth
- **AUTH-V2-02**: User can share a search results URL (public permalink to a search)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Chat-style turn-taking / follow-up questions | Core non-negotiable: user gets results, not a conversation |
| In-app tour scheduling or CRM | Too vertical; deep-link to source for scheduling |
| Comparison tables | Research shows low actual usage; link-out covers the need |
| Mortgage / affordability calculators | Out of domain for rental search |
| AI-generated property descriptions | Adds cost, no user trust benefit; show source data |
| Push / browser notifications | v2 email alerts cover the use case; don't add notification fatigue |
| Mobile app (iOS/Android) | Web-responsive only for v1; native app is v3+ |
| Using claude.ai subscription accounts as API | Violates Anthropic ToS; risk of account bans; official API only |
| Gamification (streaks, scores) | Anti-feature; alienates the non-technical target user |
| Agent-style agentic browser tools (browser-use, Skyvern) | LLM call per browser action = cost explosion; Playwright + deterministic selectors instead |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| COST-01 | Phase 1 | Pending |
| COST-02 | Phase 1 | Pending |
| COST-03 | Phase 1 | Pending |
| CACH-03 | Phase 1 | Pending |
| CACH-04 | Phase 1 | Pending |
| SRCH-01 | Phase 2 | Pending |
| SRCH-02 | Phase 2 | Pending |
| SRCH-03 | Phase 2 | Pending |
| SRCH-04 | Phase 2 | Pending |
| SRCH-05 | Phase 2 | Pending |
| SCRAP-02 | Phase 3 | Complete |
| SCRAP-05 | Phase 3 | Complete |
| MAP-01 | Phase 3 | Complete |
| MAP-02 | Phase 3 | Complete |
| MAP-03 | Phase 3 | Complete |
| MAP-04 | Phase 3 | Complete |
| SCRAP-01 | Phase 4 | Pending |
| SCRAP-03 | Phase 4 | Pending |
| SCRAP-04 | Phase 4 | Pending |
| SCRAP-06 | Phase 4 | Pending |
| SCRAP-07 | Phase 4 | Pending |
| CACH-01 | Phase 5 | Complete (05-02) |
| CACH-02 | Phase 5 | Pending |
| SCRAP-08 | Phase 5 | Pending |
| AUTH-01 | Phase 6 | Pending |
| AUTH-02 | Phase 6 | Pending |
| AUTH-03 | Phase 6 | Pending |
| AUTH-04 | Phase 6 | Pending |
| DASH-01 | Phase 7 | Pending |
| DASH-02 | Phase 7 | Pending |
| DASH-03 | Phase 7 | Pending |
| OBS-01 | Phase 8 | Pending |
| OBS-02 | Phase 8 | Pending |
| OBS-03 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-10*
*Last updated: 2026-05-10 after roadmap revision (5 → 8 atomic phases)*
