import Link from "next/link";
import { connection } from "next/server";
import type { Topic, Video } from "@/lib/api";

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
export const fmt = (n: number) => compact.format(n);

export async function Updated({ at }: { at: string | null }) {
  await connection();
  if (!at) return null;
  // eslint-disable-next-line react-hooks/purity -- server component rendered once per request (after connection())
  const min = Math.max(0, Math.round((Date.now() - new Date(at).getTime()) / 60000));
  const ago = min < 1 ? "just now" : min < 60 ? `${min} min ago` : `${Math.round(min / 60)} h ago`;
  return (
    <p className="text-xs text-neutral-500">
      Updated <time dateTime={at}>{ago}</time> · refreshed hourly
    </p>
  );
}

export function Flags({ t }: { t: Topic }) {
  const flags = [
    t.is_spiking && ["Spiking", "bg-amber-100 text-amber-900 dark:bg-amber-400/15 dark:text-amber-300"],
    t.is_new && ["New", "bg-sky-100 text-sky-900 dark:bg-sky-400/15 dark:text-sky-300"],
    t.is_confirmed && ["Confirmed", "bg-emerald-100 text-emerald-900 dark:bg-emerald-400/15 dark:text-emerald-300"],
    t.origin === "ai" && ["Found by AI", "bg-violet-100 text-violet-900 dark:bg-violet-400/15 dark:text-violet-300"],
  ].filter(Boolean) as [string, string][];
  return flags.map(([label, cls]) => (
    <span key={label} className={`rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${cls}`}>
      {label}
    </span>
  ));
}

export function Growth({ g }: { g: number | null }) {
  if (g == null) return null;
  const up = g >= 1;
  return (
    <span className={up ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
      {up ? "▲" : "▼"} ×{g.toFixed(1)} vs yesterday
    </span>
  );
}

export function Sparkline({ series, className = "" }: { series: number[]; className?: string }) {
  if (series.length < 2) return null;
  const pts = series.map((v, i) => `${(i / (series.length - 1)) * 100},${30 - (v / 100) * 28}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={className} aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke"
                strokeLinejoin="round" />
    </svg>
  );
}

export function ScoreBar({ score }: { score: number }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-neutral-200 dark:bg-neutral-800" aria-hidden>
      <div className="h-full rounded-full bg-emerald-500" style={{ width: `${Math.max(2, score)}%` }} />
    </div>
  );
}

export function TopicCard({ t }: { t: Topic }) {
  return (
    <Link href={`/topics/${t.slug}`} prefetch
          className="group flex items-center gap-4 rounded-2xl border border-neutral-200 bg-white p-4 transition hover:border-emerald-500 dark:border-neutral-800 dark:bg-neutral-900">
      <span className="w-6 text-center text-2xl font-bold tabular-nums text-neutral-400">{t.rank}</span>
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-lg font-semibold group-hover:text-emerald-700 dark:group-hover:text-emerald-400">{t.name}</h3>
          <Flags t={t} />
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold tabular-nums">{Math.round(t.score)}</span>
          <ScoreBar score={t.score} />
        </div>
        <p className="flex flex-wrap gap-x-3 text-xs text-neutral-500">
          {t.attention != null && <span>{(t.attention * 100).toFixed(1)}% of the conversation</span>}
          <Growth g={t.growth} />
          {t.items != null && <span>{t.items} posts from {t.channels} channels</span>}
        </p>
      </div>
      <Sparkline series={t.series} className="hidden h-10 w-24 shrink-0 text-emerald-500 sm:block" />
    </Link>
  );
}

export function VideoRow({ v, rank }: { v: Video; rank?: number }) {
  return (
    <li className="flex gap-3 py-3">
      {rank != null && <span className="w-6 text-center font-bold tabular-nums text-neutral-400">{rank}</span>}
      <div className="min-w-0 flex-1">
        <a href={v.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium hover:underline">
          {v.title}
        </a>
        <p className="mt-1 flex flex-wrap gap-x-3 text-xs text-neutral-500">
          <span>{v.channel_title}</span>
          <span>{fmt(v.views_24h)} views in 24h</span>
          {v.per_1k_subs != null && v.per_1k_subs >= 1000 && (
            <span className="font-semibold text-emerald-700 dark:text-emerald-400">
              {fmt(v.per_1k_subs / 1000)}× the channel&apos;s subscribers
            </span>
          )}
          {v.topics.map((t) => (
            <Link key={t.slug} href={`/topics/${t.slug}`} className="underline decoration-dotted">{t.name}</Link>
          ))}
        </p>
      </div>
    </li>
  );
}

export function Skeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-24 animate-pulse rounded-2xl bg-neutral-200/70 dark:bg-neutral-800/70" />
      ))}
    </div>
  );
}
