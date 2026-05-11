-- Phase 1 Foundation Skeleton — initial schema
--
-- References:
--   D-06: Three tables — search_jobs, listings, daily_spend
--   D-07: Photos stored as URL strings only (no binary)
--   D-08: Supabase Realtime subscribed on listings (filtered by job_id);
--         search_jobs also published so the frontend can observe status updates
--   RESEARCH Pitfall 3: tables created post-init are NOT auto-published —
--         must ALTER PUBLICATION supabase_realtime ADD TABLE ...
--   RESEARCH Pitfall 8: gen_random_uuid() lives in pgcrypto; enable explicitly
--
-- This file is idempotent — re-applying it must not error.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS search_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  query text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

CREATE TABLE IF NOT EXISTS listings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES search_jobs(id) ON DELETE CASCADE,
  data jsonb NOT NULL,
  photo_url text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS listings_job_id_idx ON listings(job_id);

CREATE TABLE IF NOT EXISTS daily_spend (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  date date NOT NULL UNIQUE,
  estimated_tokens int NOT NULL DEFAULT 0,
  estimated_cost_usd numeric(10, 6) NOT NULL DEFAULT 0
);

-- Realtime publication setup (idempotent — guard each ADD TABLE).
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'listings'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE listings;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'search_jobs'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE search_jobs;
  END IF;
END $$;

-- TODO(Phase 6): Enable RLS on all 3 tables and author policies. Currently OPEN.
