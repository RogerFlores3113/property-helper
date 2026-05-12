import { describe, it, expect, vi, beforeEach } from 'vitest';
import { NextRequest, NextResponse } from 'next/server';
import { mockSupabaseClient } from './_mocks/supabase';

const client = mockSupabaseClient();

vi.mock('@supabase/ssr', () => ({
  createServerClient: () => client,
}));

import { updateSession } from '../lib/supabase-middleware';

describe('updateSession (AUTH-03)', () => {
  beforeEach(() => {
    client.auth.getUser.mockClear();
  });

  it('calls supabase.auth.getUser() at least once', async () => {
    const req = new NextRequest('http://localhost:3000/');
    await updateSession(req);
    expect(client.auth.getUser).toHaveBeenCalled();
  });

  it('returns a NextResponse (the supabaseResponse passthrough)', async () => {
    const req = new NextRequest('http://localhost:3000/');
    const res = await updateSession(req);
    expect(res).toBeInstanceOf(NextResponse);
  });
});
