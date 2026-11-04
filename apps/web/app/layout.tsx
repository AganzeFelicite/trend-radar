import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "Trend Radar: rising GTA 6 topics for creators", template: "%s · Trend Radar" },
  description: "Which GTA 6 topics are rising right now across YouTube, Bluesky and gaming news. Updated hourly. Unofficial fan-made tool.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="mx-auto flex w-full max-w-2xl items-center justify-between px-4 py-5">
          <Link href="/" className="flex items-center gap-2 font-bold tracking-tight">
            {/* eslint-disable-next-line @next/next/no-img-element -- 1 KB svg, nothing to optimise */}
            <img src="/icon.svg" alt="" width={28} height={28} />
            Trend Radar
          </Link>
          <nav className="flex gap-4 text-sm text-neutral-600 dark:text-neutral-400">
            <Link href="/" className="hover:text-neutral-900 dark:hover:text-white">Topics</Link>
            <Link href="/videos" className="hover:text-neutral-900 dark:hover:text-white">Rising videos</Link>
          </nav>
        </header>
        <main className="mx-auto w-full max-w-2xl flex-1 px-4 pb-16">{children}</main>
        <footer className="mx-auto w-full max-w-2xl space-y-2 px-4 py-8 text-xs text-neutral-500">
          <p>
            Unofficial fan-made tool. Not affiliated with or endorsed by Rockstar Games or Take-Two Interactive.
            All trademarks belong to their owners.
          </p>
          <p>
            Data from <a href="https://www.youtube.com" className="underline">YouTube</a>, Bluesky, Twitch and gaming
            news RSS feeds, via their official APIs. Scores are our own analysis.
          </p>
        </footer>
      </body>
    </html>
  );
}
