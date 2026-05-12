"""Phase 3+ scrapers package — per-source ARQ-friendly modules.

Currently houses:
    - robots.py   (RobotsCache: per-job robots.txt enforcement, SCRAP-05)
    - location.py (location chip → Craigslist subdomain mapping, SSRF whitelist)
    - craigslist.py (run_search ARQ task + parse_search_results / parse_listing)
    - base.py     (BaseScraper Protocol for future Phase 4 multi-source reuse)
"""
