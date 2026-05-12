import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

/**
 * Refresh the Supabase auth session cookie on every request.
 *
 * CRITICAL: do NOT place any code between createServerClient(...) and
 * supabase.auth.getUser(). The library relies on getUser() being the
 * first call so it can detect a stale refresh token and rotate it
 * before any downstream handler reads request.cookies.
 *
 * Phase 6 contract: session refresh only. No redirect logic, no
 * "if (!user) redirect" branching — that lives in route-level guards
 * added in later phases.
 */
export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options),
          );
        },
      },
    },
  );

  // IMPORTANT: do NOT run code between createServerClient and getUser().
  await supabase.auth.getUser();

  return supabaseResponse;
}
