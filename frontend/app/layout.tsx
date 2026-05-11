import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Property Helper",
  description: "AI-powered apartment finder",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className='font-sans antialiased text-zinc-900 bg-white'
        style={{ fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' }}>
        {children}
      </body>
    </html>
  );
}
