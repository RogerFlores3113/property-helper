-- Phase 5 Cache, Dedup & Freshness — schema diff
--
-- References:
--   D-07 (Phase 5 CONTEXT): listings.expires_at NOT NULL DEFAULT now()+28d,
--         backfill existing rows with created_at+28d (per-row), not migration-time now()+28d.
--   D-12 (Phase 5 CONTEXT): listings.dedup_key text, nullable (NULL = opt-out of dedup).
--   D-16 (Phase 5 CONTEXT): schema diff is additive only — no new tables, no FK changes,
--         no ALTER PUBLICATION needed (Pitfall 3 of 05-RESEARCH.md).
--   Pitfall 10 (05-RESEARCH.md): two-step ALTER for the NOT NULL backfill so existing
--         rows are populated based on each row's created_at, not a single migration timestamp.
--
-- This file is idempotent — re-applying it must not error.
-- The RLS TODO marker remains in 0001_init.sql; we do not duplicate it here.

-- 1. Add expires_at nullable so existing rows can be backfilled per-row.
ALTER TABLE listings ADD COLUMN IF NOT EXISTS expires_at timestamptz;

-- 2. Backfill existing rows with their own created_at + 28d (Pitfall 10).
--    Re-running this is safe — only rows still NULL are updated.
UPDATE listings
   SET expires_at = created_at + interval '28 days'
 WHERE expires_at IS NULL;

-- 3. Now that every row has a value, promote the column to NOT NULL.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_name = 'listings'
       AND column_name = 'expires_at'
       AND is_nullable = 'YES'
  ) THEN
    ALTER TABLE listings ALTER COLUMN expires_at SET NOT NULL;
  END IF;
END $$;

-- 4. Set the default for future inserts (now + 28d).
ALTER TABLE listings ALTER COLUMN expires_at SET DEFAULT (now() + interval '28 days');

-- 5. Add dedup_key (text, nullable — NULL means opt-out, no backfill per D-12).
ALTER TABLE listings ADD COLUMN IF NOT EXISTS dedup_key text;

-- 6. Add filter_hash to search_jobs (text, nullable — set on POST /api/jobs).
ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS filter_hash text;

-- 7. Add chips to search_jobs (jsonb, nullable — persisted Phase-2 ChipModel list).
ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS chips jsonb;

-- 8. Index expires_at for fast freshness sweeps and TTL filtering.
CREATE INDEX IF NOT EXISTS listings_expires_at_idx ON listings(expires_at);

-- 9. Index dedup_key for grouping duplicate listings across sources.
CREATE INDEX IF NOT EXISTS listings_dedup_key_idx ON listings(dedup_key);

-- 10. Index filter_hash for cache-hit lookups on search_jobs.
CREATE INDEX IF NOT EXISTS search_jobs_filter_hash_idx ON search_jobs(filter_hash);
