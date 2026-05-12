import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockSupabaseClient } from './_mocks/supabase';

const client = mockSupabaseClient();
const push = vi.fn();
const refresh = vi.fn();

vi.mock('@/lib/supabase-browser', () => ({
  createClient: () => client,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, refresh, replace: vi.fn() }),
  redirect: vi.fn(),
}));

// SignOutButton will be created in Plan 03; this import is RED until then.
import { SignOutButton } from '../app/components/SignOutButton';

describe('SignOutButton (AUTH-04)', () => {
  beforeEach(() => {
    client.auth.signOut.mockReset();
    client.auth.signOut.mockResolvedValue({ data: {}, error: null });
    push.mockReset();
    refresh.mockReset();
  });

  it('calls signOut() when the button is clicked', async () => {
    const user = userEvent.setup();
    render(<SignOutButton />);
    await user.click(screen.getByRole('button', { name: /sign out/i }));
    expect(client.auth.signOut).toHaveBeenCalledTimes(1);
  });

  it('navigates to / and refreshes the router after signOut resolves', async () => {
    const user = userEvent.setup();
    render(<SignOutButton />);
    await user.click(screen.getByRole('button', { name: /sign out/i }));
    expect(push).toHaveBeenCalledWith('/');
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
