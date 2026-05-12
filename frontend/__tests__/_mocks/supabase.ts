import { vi } from 'vitest';

/**
 * Shared Supabase auth-client test factory. Returns a minimal stand-in
 * exposing the four auth methods we exercise in Phase 6. Callers may pass
 * an `overrides.auth` object to swap any default with a custom vi.fn().
 *
 * Defaults:
 *   signInWithOtp        → { data: {}, error: null }
 *   exchangeCodeForSession → { data: {}, error: null }
 *   signOut              → { data: {}, error: null }
 *   getUser              → { data: { user: null }, error: null }
 */
export function mockSupabaseClient(overrides: { auth?: Record<string, ReturnType<typeof vi.fn>> } = {}) {
  const defaultAuth = {
    signInWithOtp: vi.fn().mockResolvedValue({ data: {}, error: null }),
    exchangeCodeForSession: vi.fn().mockResolvedValue({ data: {}, error: null }),
    signOut: vi.fn().mockResolvedValue({ data: {}, error: null }),
    getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
  };

  return {
    auth: {
      ...defaultAuth,
      ...(overrides.auth ?? {}),
    },
  };
}
