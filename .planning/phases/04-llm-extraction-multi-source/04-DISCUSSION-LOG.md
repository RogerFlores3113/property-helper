# Phase 4: LLM Extraction & Multi-Source - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-11
**Phase:** 4-LLM Extraction & Multi-Source
**Mode:** --auto (all gray areas auto-resolved with recommended defaults)
**Areas discussed:** LLM Extraction Call Pattern, HTML Pre-Filtering Pipeline, Playwright Integration, Parallel Coordinator Architecture, Redis Rate Limiting, Code Review Debt

---

## LLM Extraction Call Pattern

| Option | Description | Selected |
|--------|-------------|----------|
| Forced tool-use (extract_listings) | Single tool call per page, prose prevented, prompt-cached system+tool defs | ✓ |
| Free-form extraction + prose parsing | Lower reliability, no cache savings, more fragile | |

**Selected:** Forced tool-use via `extract_listings` tool with Haiku 4.5 + prompt caching
**Notes:** Auto-selected per CLAUDE.md LLM Strategy which explicitly specifies this pattern. Escalation to Sonnet on empty/parse failure only.

---

## HTML Pre-Filtering Pipeline

| Option | Description | Selected |
|--------|-------------|----------|
| selectolax + trafilatura (two-pass) | Strip structure first, then extract main content. 5–10× token reduction | ✓ |
| selectolax only | Faster but less content extraction quality | |
| Raw HTML to LLM | Against project constraints (CLAUDE.md: "Don't. Always pre-filter.") | |

**Selected:** selectolax (strip nav/footer/ads) → trafilatura (main content extraction)
**Notes:** SCRAP-07 requires 5–10× token reduction. CLAUDE.md explicitly forbids raw HTML to LLM.

---

## Playwright Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Inline in ARQ worker (same Fly.io machine) | Simpler — no extra service. Add Playwright base image to Dockerfile | ✓ |
| Separate Playwright microservice | Better isolation but adds ops complexity for v1 | |
| Playwright on Browserbase | Managed but adds cost and vendor dependency | |

**Selected:** Inline Playwright in ARQ worker using `mcr.microsoft.com/playwright/python` base image
**Notes:** Recommended in CLAUDE.md §Decision Analysis. Revisit for v2 if resource contention emerges.

---

## Parallel Coordinator Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| Coordinator ARQ task fans out sub-tasks | Clean separation, Realtime streams from both sources in parallel | ✓ |
| Single task, sequential scrapers | Simpler but slow — user waits for both sources to finish before seeing anything | |
| One ARQ task per search (no coordinator) | Doesn't support per-source parallelism | |

**Selected:** Coordinator task (`run_search_coordinator`) fans out one ARQ sub-task per source
**Notes:** Aligns with SCRAP-03 requirement for parallel sessions. Coordinator tracks completion via Redis counter.

---

## Redis Rate Limiting

| Option | Description | Selected |
|--------|-------------|----------|
| Redis sliding window per domain | Coordinates all ARQ workers; correct by construction | ✓ |
| In-memory per-worker limit | No cross-worker coordination — violates SCRAP-04 for multi-worker deploys | |
| External rate-limit service (e.g., Upstash) | Adds vendor dependency; same Redis already available | |

**Selected:** Redis sliding window with key `rate_limit:{domain}`
**Notes:** SCRAP-04 explicitly requires Redis-coordinated rate limiting. Same Redis instance as ARQ.

---

## Code Review Debt (CR-01, CR-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Fix in Phase 4 first tasks | Clears critical findings before new code builds on top | ✓ |
| Defer to separate quick-task | Creates debt drift; minor effort | |

**Selected:** Fix CR-01 (query max_length) and CR-02 (safeUrl suffix) at start of Phase 4
**Notes:** Both are quick fixes. Building Phase 4 on top of CR-01 (unbounded query) is a security risk.

---

## Claude's Discretion

- Specific CSS selectors for Apartments.com listing regions (researcher identifies from live HTML)
- ARQ job dependencies vs Redis counter for coordinator completion detection
- Exact trafilatura configuration flags

## Deferred Ideas

- Realtor.com as a third source — scoped out of Phase 4 (only Craigslist + Apartments.com required)
- Deduplication across sources — Phase 5
- BYOK user API key for LLM calls — Phase 6+
- Stagehand caching for selector resilience — only if Playwright selectors break in production
