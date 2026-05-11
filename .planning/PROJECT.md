# Property Helper

## What This Is

An AI-powered apartment finder for non-technical users. You describe what you want in plain language — "2BR in SF Bay Area, $3k–5k, in-unit W/D, walkable" — and the system searches multiple listing sources in parallel, returning consolidated results on an interactive map with zone analytics. No follow-up questions. You come back to a finished job.

## Core Value

Non-technical users say what they want once in natural language, and get consolidated, map-visualized apartment results without being asked anything else.

## Requirements

### Validated

(None yet — ship to validate)

### Active

**Search & Input**
- [ ] Natural language query input (freeform text + optional structured fields for price, beds, baths)
- [ ] Per-criterion flexibility parameters ("willing to flex on bathrooms", "hard limit on price")
- [ ] Push-to-talk voice input: hold button → browser transcribes via Web Speech API → auto-populates query field
- [ ] Geographic radius search: user says "SF Bay Area" → system searches within 25–50 mile radius, no city lock-in

**Scraping & Orchestration**
- [ ] LLM (Claude) orchestrates tool calls to scrape listings from multiple sources
- [ ] Playwright browser automation for major aggregators (Zillow, Apartments.com, Realtor.com) that prohibit HTML scraping
- [ ] Traditional HTML scraping for smaller property management sites and Google results (where robots.txt permits)
- [ ] Rate limiting: max 1 req/sec per domain with 0.1–0.5s random jitter, coordinated across parallel sessions
- [ ] robots.txt compliance on every target domain
- [ ] Parallel browser sessions (not sequential screenshot loops) for throughput
- [ ] Prefer HTML parsing + LLM-on-text; reserve vision/screenshot parsing only where HTML is not usable
- [ ] Aggressively pre-filter HTML before sending to LLM (crop to listing regions, strip boilerplate)
- [ ] Resilient execution: never pause mid-run for clarifications; retry, fall back, move on

**Results & Map**
- [ ] Interactive map with each listing pinned
- [ ] Zone analytics layer: KNN/radius clustering of listings into areas, each zone shows median rent, avg sqft, listing count, and other key metrics computed on-the-fly
- [ ] Results stream to UI in real-time via Supabase Realtime (cached hits appear instantly; new scrapes trickle in)
- [ ] Fire-and-forget: user can close tab, results persist in Supabase, available on return
- [ ] Each result shows: address, price, beds/baths, key amenities, source link, preview image, timestamp of when data was fetched

**Caching & Freshness**
- [ ] Shared global listing cache: searches populate a common Supabase DB so overlapping queries get instant results
- [ ] Listing TTL: 3–4 weeks; expired listings shown with "data from X date" label and option to re-search or extend
- [ ] Search results labeled with "search performed on X date"
- [ ] Compact listing storage: ~300–500 chars per listing to stay within Supabase 500MB free tier

**Auth & Users**
- [ ] Lightweight auth via Supabase Auth (email/password or magic link)
- [ ] Per-user dashboard: saved searches, preferences, search history
- [ ] Usage-capped shared LLM key: user gets $1–3 of hosted API budget, then prompted to add their own Anthropic API key (BYOK)
- [ ] BYOK: users enter their own Anthropic API key in settings; it is stored encrypted, never logged

**Observability**
- [ ] Structured logging for all scraper runs: domain, result count, duration, errors, fallback triggers
- [ ] Scraper failure visibility in dashboard so failing scrapers can be diagnosed and fixed quickly

### Out of Scope

- Using claude.ai subscription accounts as an unofficial API — against ToS, risk of account bans; use official Anthropic API only
- OpenAI subscription workaround — same reasoning
- Aggressive scraping of any site that explicitly prohibits it (HTML scraping major aggregators) — use Playwright only
- Email/push notifications for v1 — fire-and-forget with persistent results covers the use case; notifications are v2
- Commute time scoring for v1 — zone analytics covers proximity; routing-API-based commute scores are v2
- Mobile app — web-responsive only for v1

## Context

- **Launch market**: Champaign, IL — limited data, good for testing scraper coverage
- **Expansion markets**: SF Bay Area, Boston, NYC, Austin
- **Target users**: Friends and family, non-technical. They will not tolerate being asked follow-up questions after submitting a search.
- **LLM cost target**: Cents per search, not dollars. ~$5/month personal-use budget. Token minimization is a first-class concern.
- **Vercel serverless constraint**: Playwright cannot run inside Vercel serverless functions (no Chromium binary, execution time limits). Scraping workers must run on a persistent container host (Railway, Fly.io, or similar).
- **Supabase Realtime**: Free tier includes Realtime subscriptions — used for streaming results to the UI without a separate WebSocket server.
- **Voice input**: Web Speech API (browser-native, free). Falls back gracefully if browser doesn't support it.
- **Zone analytics**: Computed on-the-fly using KNN or radius clustering on listing lat/lng stored in Supabase. No third-party neighborhood data dependency for v1.

## Constraints

- **Budget**: LLM API costs ~$5/month; Supabase free tier (500MB Postgres, unlimited API requests); Vercel Hobby for frontend
- **Legal**: No scraping of sites that prohibit it via ToS without using browser automation that mimics human behavior; robots.txt respected everywhere
- **Storage**: Listings stored at 300–500 chars each; must stay under Supabase 500MB free tier
- **Latency**: Full search result (fire-and-forget) is acceptable; streaming UX for perceived responsiveness
- **No mid-task questions**: The orchestration layer must never stop to ask the user something during a search run

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Playwright over Stagehand/Skyvern/browser-use | Playwright is mature, well-documented, has full browser control. Stagehand/browser-use add LLM overhead per interaction. Evaluate Stagehand if visual parsing complexity grows. | — Pending |
| FastAPI over Node/Express | Python ecosystem has better scraping/parsing libraries (BeautifulSoup, httpx); async-friendly; Claude SDK is Python-native | — Pending |
| Supabase Realtime for streaming | Free tier includes it; avoids a separate WebSocket server; frontend subscribes to DB writes directly | — Pending |
| Official Anthropic API only (BYOK) | claude.ai subscription workaround violates ToS and risks account bans; official API is stable and billable | ✓ Locked |
| KNN clustering for zone analytics | On-the-fly computation from listing coordinates, no third-party neighborhood data dependency | — Pending |
| Web Speech API for voice | Free, browser-native, no backend round-trip. Falls back gracefully. | — Pending |
| Next.js on Vercel + FastAPI on Railway/Fly | Playwright requires persistent containers — cannot run on Vercel serverless; split is necessary | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-10 after initialization*
