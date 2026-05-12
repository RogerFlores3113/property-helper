import { createBrowserClient } from '@supabase/ssr';

/**
 * Browser-scoped Supabase SSR client factory.
 *
 * Call this INSIDE each Client Component render path. Do NOT cache the
 * resulting client at module scope — that risks leaking identity across
 * requests in dev/HMR and across tab-switches.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
