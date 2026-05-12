'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { createClient } from '@/lib/supabase-browser';

const ERROR_COPY = "Couldn't send the link. Check the email address and try again.";
const CALLBACK_ERROR_COPY = "That sign-in link didn't work. Request a fresh one below.";

function LoginForm() {
  const searchParams = useSearchParams();
  const callbackError = searchParams.get('error') === 'auth_failed';

  const [email, setEmail] = useState<string>('');
  const [sent, setSent] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading || !email) return;
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const { error: sendError } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${process.env.NEXT_PUBLIC_SITE_URL}/auth/callback`,
      },
    });
    setLoading(false);
    if (sendError) {
      // Do NOT surface sendError.message — show canned UI-SPEC copy (T-06-06).
      setError(ERROR_COPY);
      return;
    }
    setSent(true);
  }

  return (
    <main className="min-h-screen bg-white flex items-start justify-center pt-16 px-6">
      <div className="w-full max-w-[420px]">
        {sent ? (
          <>
            <h1 className="text-[20px] font-semibold leading-tight">Check your inbox</h1>
            <p className="text-sm text-zinc-700 mt-2">
              We sent a sign-in link to {email}. Open it in this same browser to finish signing in.
            </p>
          </>
        ) : (
          <>
            {callbackError && (
              <div
                className="mb-6 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-700"
                role="alert"
              >
                {CALLBACK_ERROR_COPY}
              </div>
            )}
            {error && (
              <div
                className="mb-6 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-700"
                role="alert"
              >
                {error}
              </div>
            )}
            <h1 className="text-[20px] font-semibold leading-tight">Sign in to Property Helper</h1>
            <p className="text-sm text-zinc-500 mt-2">
              Enter your email and we&apos;ll send a one-time link.
            </p>
            <form onSubmit={onSubmit} className="flex flex-col gap-3 mt-6">
              <input
                type="email"
                required
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                placeholder="you@example.com"
                aria-label="Email address"
                className="w-full rounded border border-zinc-300 p-2 text-sm disabled:bg-zinc-100 disabled:cursor-not-allowed"
              />
              <button
                type="submit"
                disabled={loading || !email}
                className="self-start rounded bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? 'Sending…' : 'Send magic link'}
              </button>
            </form>
          </>
        )}
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
