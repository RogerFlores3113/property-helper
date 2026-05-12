'use client';

import { useRouter } from 'next/navigation';
import { createClient } from '@/lib/supabase-browser';

export function SignOutButton() {
  const router = useRouter();

  async function onClick() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push('/');
    router.refresh();
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className="text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline"
    >
      Sign out
    </button>
  );
}
