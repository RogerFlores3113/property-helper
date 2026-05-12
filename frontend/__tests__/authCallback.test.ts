import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest } from 'next/server';
import { mockSupabaseClient } from './_mocks/supabase';

const client = mockSupabaseClient();

vi.mock('@/lib/supabase-server', () => ({
  createClient: async () => client,
}));

// The route handler will be created in Plan 02; this import is RED until then.
import { GET } from '../app/auth/callback/route';

describe('auth/callback route handler (AUTH-02)', () => {
  beforeEach(() => {
    client.auth.exchangeCodeForSession.mockReset();
    client.auth.exchangeCodeForSession.mockResolvedValue({ data: {}, error: null });
  });

  it('exchanges code and redirects to origin root on success', async () => {
    const req = new NextRequest('http://localhost:3000/auth/callback?code=abc');
    const res = await GET(req);

    expect(client.auth.exchangeCodeForSession).toHaveBeenCalledWith('abc');
    expect(res.headers.get('location')).toBe('http://localhost:3000/');
  });

  it('redirects to /login?error=auth_failed when code is missing', async () => {
    const req = new NextRequest('http://localhost:3000/auth/callback');
    const res = await GET(req);

    expect(client.auth.exchangeCodeForSession).not.toHaveBeenCalled();
    expect(res.headers.get('location')).toBe('http://localhost:3000/login?error=auth_failed');
  });

  it('redirects to /login?error=auth_failed when exchange returns an error', async () => {
    client.auth.exchangeCodeForSession.mockResolvedValueOnce({
      data: {},
      error: { message: 'invalid', name: 'AuthError' },
    });
    const req = new NextRequest('http://localhost:3000/auth/callback?code=bad');
    const res = await GET(req);

    expect(client.auth.exchangeCodeForSession).toHaveBeenCalledWith('bad');
    expect(res.headers.get('location')).toBe('http://localhost:3000/login?error=auth_failed');
  });
});
