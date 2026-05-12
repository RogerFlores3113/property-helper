---
phase: 03-first-scraper-map-results
reviewed: 2026-05-11T00:00:00Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - backend/app/workers/scrapers/__init__.py
  - backend/app/workers/scrapers/base.py
  - backend/app/workers/scrapers/robots.py
  - backend/app/workers/scrapers/location.py
  - backend/app/workers/scrapers/craigslist.py
  - backend/tests/test_robots_cache.py
  - backend/tests/test_craigslist_parser.py
  - backend/tests/test_craigslist_scraper_integration.py
  - backend/app/settings.py
  - backend/app/workers/settings.py
  - backend/app/routes/jobs.py
  - frontend/app/components/MapView.tsx
  - frontend/app/components/ListingList.tsx
  - frontend/app/components/ListingCard.tsx
  - frontend/app/components/ListingDrawer.tsx
  - frontend/app/components/safeUrl.ts
  - frontend/__tests__/MapView.test.tsx
  - frontend/__tests__/ListingCard.test.tsx
  - frontend/__tests__/ListingList.test.tsx
  - frontend/__tests__/ListingDrawer.test.tsx
  - frontend/app/types.ts
  - frontend/app/globals.css
  - frontend/app/page.tsx
findings:
  critical: 2
  warning: 4
  info: 4
  total: 10
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-11
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Phase 3 delivers a working Craigslist scraper (httpx + selectolax + protego), robots.txt compliance, and a MapLibre/Supabase-Realtime frontend. The implementation is generally solid — SSRF is properly mitigated via construction of URLs from a whitelist rather than passing user input through, robots.txt is checked before every fetch, budget guard semantics are preserved, and the frontend URL safety helpers block open-redirect / XSS vectors.

Two critical findings require attention before shipping: an unbounded `query` string that allows unlimited database writes and worker CPU consumption; and an imprecise image host suffix check in the frontend that, while unlikely to be exploitable today, contradicts the stated security contract and diverges from the backend's own whitelist.

Four warnings cover: a `map.once('load', ...)` accumulation bug that can fire stale data handlers at map load, a missing `status='running'` update before the job transitions directly to `completed` in early-exit paths, a `check_iter` counter that is shared with the future LLM iteration budget (causing silent early termination in Phase 4), and a `ListingDrawer` that declares `role="dialog"` without a focus trap.

---

## Critical Issues

### CR-01: Unbounded `query` string stored in Postgres and consumed by worker

**File:** `backend/app/routes/jobs.py:41`

**Issue:** `CreateJobBody.query` is declared as bare `str` with no maximum length constraint. A caller can POST a request with a query string of arbitrary size (megabytes), which is then written verbatim into `search_jobs.query` (TEXT column, unlimited by Postgres). The ARQ worker subsequently reads the full string, calls `location.lower().strip()` on it (linear in length), and runs a substring scan over the city dict. Beyond the storage abuse against the 500 MB Supabase free tier, this is a straightforward denial-of-service vector against the worker.

**Fix:**
```python
from pydantic import Field

class CreateJobBody(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    chips: list[ChipModel] = []
    global_flex: bool = False
```
512 chars comfortably covers any natural-language apartment description. Callers receive a Pydantic 422 on oversized input, consistent with the existing chip validation contract (ASVS V5).

---

### CR-02: `isAllowedCraigslistImage` suffix check is imprecise and diverges from backend whitelist

**File:** `frontend/app/components/safeUrl.ts:29`

**Issue:** The image whitelist check includes `host.endsWith('craigslistimages')` (no leading dot, no `.org`). This matches any hostname whose suffix is the literal string `craigslistimages`, including `evilcraigslistimages` (single label, no TLD) or `x.craigslistimages` (a hypothetical TLD that doesn't exist today but could be registered). The backend's `_PHOTO_HOST_SUFFIXES` tuple only lists `"craigslistimages.org"` — the frontend check is therefore wider than the backend enforces, contradicting the defense-in-depth the comments describe. The already-present `host.endsWith('craigslistimages.org')` covers every legitimate Craigslist image host; the bare suffix check is both redundant and imprecise.

**Fix:**
```typescript
export function isAllowedCraigslistImage(url: string): boolean {
  try {
    const u = new URL(url);
    const host = u.hostname;
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    return (
      host === 'craigslist.org' ||
      host.endsWith('.craigslist.org') ||
      host === 'craigslistimages.org' ||
      host.endsWith('.craigslistimages.org')
    );
  } catch {
    return false;
  }
}
```
This matches the backend `_PHOTO_HOST_SUFFIXES` exactly and removes the imprecise bare-suffix path.

---

## Warnings

### WR-01: `map.once('load', apply)` accumulates stale handlers when listings arrive before map load

**File:** `frontend/app/components/MapView.tsx:207`

**Issue:** The listings `useEffect` (line 169) branches on `map.isStyleLoaded()`. If the style is not yet loaded it calls `map.once('load', apply)`. In the streaming-results UX, multiple Supabase Realtime INSERTs arrive while the map is still initializing, triggering this effect several times before load fires. `map.once` registers a new one-time listener on each call; all registered listeners fire when the `load` event emits. This means `apply()` executes multiple times in registration order at load time, calling `src.setData(...)` and `map.fitBounds(...)` with progressively stale feature collections. The last call wins on data, but intermediate calls emit redundant `fitBounds` transitions and flicker. The same accumulation pattern appears in the hover (line 239) and select (line 268) effects.

**Fix:** Track whether a pending `once` callback is already registered and cancel it before registering a new one, or use a cleanup-based approach:

```typescript
// At the top of the component (add ref):
const pendingListingsApplyRef = useRef<(() => void) | null>(null);

// Inside the listings useEffect, replace the else branch:
} else {
  if (pendingListingsApplyRef.current) {
    map.off('load', pendingListingsApplyRef.current);
  }
  pendingListingsApplyRef.current = apply;
  map.once('load', apply);
}
```
Apply the same pattern to the hover and select effects.

---

### WR-02: Early-exit paths in `run_search` skip the `status='running'` UPDATE

**File:** `backend/app/workers/scrapers/craigslist.py:253` and exit paths at lines 267-270, 280-285, 293-298

**Issue:** `run_search` sets `status='running'` at line 253, then immediately checks `location_to_search_url` (line 263) and the robots.txt gate (line 277), and the search-page fetch error (line 289). All three early-exit paths UPDATE the job to `status='completed'` without first setting `status='running'`. This means the frontend observes the transition `pending -> completed` (skipping `running`) for no-location-match and robots-disallowed cases. The status badge text and the Realtime channel both key on `running` to show "Searching — listings will appear below". Users who submit a query for an unsupported city see a split-second `completed` badge without ever seeing the in-progress state — confusing but not data-corrupting.

More critically: the `status='running'` UPDATE at line 253 runs before the early-exit guard, so for the `search_url is None` case, the job transitions `pending -> running -> completed` in the DB but the frontend Realtime subscription may only observe `pending -> completed` depending on timing.

**Fix:** Move the `status='running'` UPDATE to after `search_url` and robots resolution, or keep it where it is but document that early-exit `completed` transitions intentionally skip the `running` state. The simplest clean fix:

```python
# After line 263, before the early-exit return:
search_url = location_to_search_url(query)
if search_url is None:
    # Never set running — go directly to completed.
    await guard.record_spend(tokens=0, cost_usd=0.0)
    await db.execute(
        "UPDATE search_jobs SET status='completed', completed_at=NOW() WHERE id=$1",
        job_id,
    )
    return

# Only set running once we know we'll actually scrape.
await db.execute(
    "UPDATE search_jobs SET status='running' WHERE id=$1", job_id
)
```

---

### WR-03: `check_iter` counter is shared with the future LLM iteration budget

**File:** `backend/app/workers/scrapers/craigslist.py:312`

**Issue:** `BudgetGuard.check_iter()` increments `_iters` and enforces `max_iters` (default 10 from settings). In Phase 3 this is repurposed as a per-listing-page iteration counter. The Phase 3 default `scraper_max_listings=10` aligns with `max_iters=10`, so the guard never trips in normal operation. However `BudgetGuard` is instantiated fresh per `run_search` call (`BudgetGuard.from_env(db=db)` at line 249), so there is no cross-job sharing.

The problem arises in Phase 4 when LLM tool calls are added to the same `run_search` flow: the single `_iters` counter will count both scrape iterations and LLM tool invocations against the same `max_iters` cap. Scraping 10 pages exhausts the budget before any LLM call can run. The guard's docstring describes `check_iter` as the "LLM agentic loop" limiter (COST-01); reusing it for HTTP page fetches conflates two distinct resource axes.

**Fix:** Add a separate `scrape_iters` counter to `BudgetGuard`, or simply remove the `check_iter` call from the scraper loop and rely solely on the `scraper_max_listings` slice at line 300 (which already hard-caps the list length before the loop).

```python
# Line 300 already limits the iteration count:
detail_urls = parse_search_results(resp.text)[: settings.scraper_max_listings]
# Remove lines 311-314 (the guard.check_iter() block):
# The max_listings slice is the correct guard here.
```

---

### WR-04: `ListingDrawer` declares `role="dialog"` without a focus trap

**File:** `frontend/app/components/ListingDrawer.tsx:49`

**Issue:** The open drawer renders `role="dialog"` (correct for a modal-adjacent panel) but does not trap keyboard focus inside it. Tab/Shift-Tab freely leaves the drawer and reaches the map, list, and search form behind it. For sighted keyboard users this is functional; for screen reader users, `role="dialog"` signals that focus should remain within the dialog until it is dismissed. The Escape key handler is correctly wired (lines 20-25). The missing focus trap is the only gap.

`aria-modal="false"` is intentional (it is not a blocking modal) but the `role="dialog"` label still carries the focus-containment expectation per ARIA authoring practices.

**Fix:** On drawer open, move focus to the first focusable element inside the drawer (the close button or the image area). On close, restore focus to the element that triggered the selection. A minimal implementation:

```tsx
// Add ref to the close button:
const closeButtonRef = useRef<HTMLButtonElement>(null);

useEffect(() => {
  if (open && closeButtonRef.current) {
    closeButtonRef.current.focus();
  }
}, [open]);

// Attach ref to the close button element.
```
A full focus trap (preventing Tab from leaving) requires either a library (`focus-trap-react`) or manual sentinel logic, and may be deferred if the product accepts keyboard-exits-drawer behavior.

---

## Info

### IN-01: Redundant `import re as _re` inside `parse_listing` function body

**File:** `backend/app/workers/scrapers/craigslist.py:192`

**Issue:** `re` is imported at module level on line 15. Inside `parse_listing`, line 192 re-imports it as a local alias `_re` and uses it for one `_re.sub(...)` call. The local alias adds confusion and is unnecessary.

**Fix:** Replace `import re as _re` + `_re.sub(...)` with `re.sub(...)` using the existing module-level import.

---

### IN-02: Stale comment in `workers/settings.py` references Phase 1 stub

**File:** `backend/app/workers/settings.py:5` and line 31

**Issue:** Both the module docstring and the inline comment still say "avoid duplicate fake-data inserts on retry". Phase 3 ships real Craigslist data. The `max_tries=1` policy is still correct but the justification is wrong.

**Fix:**
```python
# max_tries=1 — prevents duplicate real listings on ARQ retry if the worker crashes.
```

---

### IN-03: Dead `safeHostname` function retained in `page.tsx`

**File:** `frontend/app/page.tsx:194`

**Issue:** `safeHostname` is defined at line 194 and immediately suppressed with `void safeHostname` at line 215. The comment says it is kept "for future use". Dead code with a suppression comment is a maintenance liability and confuses readers about whether the function is active.

**Fix:** Remove `safeHostname` and the `void safeHostname` suppression. If it is genuinely needed in a future phase, add it then.

---

### IN-04: `isAllowedCraigslistUrl` accepts `http:` scheme for listing links

**File:** `frontend/app/components/safeUrl.ts:13`

**Issue:** Both `isAllowedCraigslistUrl` and `isAllowedCraigslistImage` accept `http:` as a valid protocol (line 13, line 24). Craigslist has enforced HTTPS since 2019. Accepting `http:` means a scraped listing with a downgraded URL is rendered as a link, potentially enabling a mixed-content warning or a cleartext leak. This is low risk in practice since the scraper always fetches via HTTPS and the resulting `source_url` will always be HTTPS, but the defense is incomplete.

**Fix:**
```typescript
if (u.protocol !== 'https:') return false;
```

---

_Reviewed: 2026-05-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
