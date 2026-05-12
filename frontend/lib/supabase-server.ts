import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

/**
 * Server-scoped Supabase SSR client factory.
 *
 * Awaits next/headers cookies() (Next.js 15 async-cookies API). The setAll
 * callback is wrapped in try/catch to tolerate the read-only Server
 * Component cookie store — when called from a Server Component (vs. a
 * Server Action or Route Handler), set() throws and we silently swallow
 * because the middleware refresh path will rewrite the cookies anyway.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) => {
              cookieStore.set(name, value, options);
            });
          } catch {
            // Called from a Server Component (read-only cookie store).
            // Safe to ignore — the middleware updateSession() helper will
            // refresh cookies on the next request.
          }
        },
      },
    },
  );
}
