import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { mockSupabaseClient } from './_mocks/supabase';

const client = mockSupabaseClient();

vi.mock('@/lib/supabase-browser', () => ({
  createClient: () => client,
}));

// LoginPage will be created in Plan 02; this import is RED until then.
import LoginPage from '../app/login/page';

describe('LoginPage (AUTH-01)', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_SITE_URL', 'http://localhost:3000');
    client.auth.signInWithOtp.mockReset();
    client.auth.signInWithOtp.mockResolvedValue({ data: {}, error: null });
  });

  it('submits email and calls signInWithOtp with emailRedirectTo /auth/callback', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    const emailInput = screen.getByRole('textbox', { name: /email/i });
    await user.type(emailInput, 'user@example.com');
    await user.click(screen.getByRole('button', { name: /send magic link/i }));

    expect(client.auth.signInWithOtp).toHaveBeenCalledTimes(1);
    const callArg = client.auth.signInWithOtp.mock.calls[0][0];
    expect(callArg.email).toBe('user@example.com');
    expect(callArg.options.emailRedirectTo).toMatch(/\/auth\/callback$/);
  });

  it('shows the "Check your inbox" success block on successful submit', async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByRole('textbox', { name: /email/i }), 'a@b.com');
    await user.click(screen.getByRole('button', { name: /send magic link/i }));

    expect(await screen.findByText(/check your inbox/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send magic link/i })).toBeNull();
  });

  it('shows the error banner with role="alert" when signInWithOtp errors', async () => {
    client.auth.signInWithOtp.mockResolvedValueOnce({
      data: {},
      error: { message: 'send failed', name: 'AuthError' },
    });
    const user = userEvent.setup();
    render(<LoginPage />);
    await user.type(screen.getByRole('textbox', { name: /email/i }), 'a@b.com');
    await user.click(screen.getByRole('button', { name: /send magic link/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/Couldn't send the link\. Check the email address and try again\./);
    // Form remains mounted so user can retry.
    expect(screen.getByRole('button', { name: /send magic link/i })).toBeInTheDocument();
  });
});
