import type { Metadata } from "next";
import Link from "next/link";
import { createClient } from "@/lib/supabase-server";
import { SignOutButton } from "@/app/components/SignOutButton";
import "./globals.css";

export const metadata: Metadata = {
  title: "Property Helper",
  description: "AI-powered apartment finder",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <html lang="en">
      <body className='font-sans antialiased text-zinc-900 bg-white'
        style={{ fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' }}>
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto max-w-[1280px] px-6 py-3 flex items-center justify-between">
            <Link href="/" className="text-[20px] font-semibold leading-tight">
              Property Helper
            </Link>
            {user ? (
              <div className="flex items-center gap-3">
                <span className="truncate max-w-[200px] text-sm">{user.email}</span>
                <SignOutButton />
              </div>
            ) : (
              <Link
                href="/login"
                className="text-sm text-zinc-500 hover:text-zinc-900 underline-offset-2 hover:underline"
              >
                Sign in
              </Link>
            )}
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
