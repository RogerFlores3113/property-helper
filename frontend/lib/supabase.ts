import { createClient } from '@supabase/supabase-js';

// TODO(Phase 7): migrate Realtime subscriptions to the SSR browser client
// (lib/supabase-browser.ts) once RLS lands so Realtime channels carry the
// authenticated user's JWT. This bare supabase-js client is retained for
// Phase 6 because Realtime in app/page.tsx still works against public
// (anon) policies — but auth methods MUST NOT be called on this client.
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);
