import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { mockSupabaseClient } from './_mocks/supabase';

const client = mockSupabaseClient();

vi.mock('@/lib/supabase-server', () => ({
  createClient: async () => client,
}));

import RootLayout from '../app/layout';

describe('RootLayout header (AUTH-04)', () => {
  beforeEach(() => {
    client.auth.getUser.mockReset();
  });

  it('renders a "Sign in" link when no user is signed in', async () => {
    client.auth.getUser.mockResolvedValueOnce({
      data: { user: null },
      error: null,
    });
    const tree = await RootLayout({ children: <div data-testid="kid" /> });
    render(tree);
    expect(
      screen.getByRole('link', { name: /sign in/i }),
    ).toBeInTheDocument();
  });

  it('renders the user email and a "Sign out" button when authed', async () => {
    client.auth.getUser.mockResolvedValueOnce({
      data: { user: { id: 'u1', email: 'a@b.com' } },
      error: null,
    });
    const tree = await RootLayout({ children: <div data-testid="kid" /> });
    render(tree);
    expect(screen.getByText('a@b.com')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /sign out/i }),
    ).toBeInTheDocument();
  });
});
