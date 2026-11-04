import Link from "next/link";
import { connection } from "next/server";
import type { Topic, Video } from "@/lib/api";

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
export const fmt = (n: number) => compact.format(n);

export const label = "text-xs font-semibold uppercase tracking-[0.12em] text-neutral-500";
export const card = "rounded-2xl border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900";

export async function Updated({ at }: { at: string | null }) {
  await connection();
  if (!at) return null;
  // eslint-disable-next-line react-hooks/purity -- server component rendered once per request (after connection())
  const min = Math.max(0, Math.round((Date.now() - new Date(at).getTime()) / 60000));
  const ago = min < 1 ? "just now" : min < 60 ? `${min} min ago` : `${Math.round(min / 60)} h ago`;
  return (
    <p className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-800 dark:text-emerald-300">
      <span className="relative flex size-2">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
      </span>
      Live · updated <time dateTime={at}>{ago}</time>
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
  return flags.map(([text, cls]) => (
    <span key={text} className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {text}
    </span>
  ));
}

/** Rank change over the last 6 hours. */
export function Movement({ t }: { t: Topic }) {
  if (t.rank == null || t.rank_6h_ago == null) return null;
  const d = t.rank_6h_ago - t.rank;
  const [text, cls] = d > 0 ? [`▲ ${d}`, "text-emerald-700 dark:text-emerald-400"]
    : d < 0 ? [`▼ ${-d}`, "text-rose-700 dark:text-rose-400"] : ["–", "text-neutral-400"];
  return (
    <span title="Rank change in the last 6 hours" className={`font-mono text-xs font-semibold ${cls}`}>
      {text}<span className="ml-1 font-sans font-normal text-neutral-400">6h</span>
    </span>
  );
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
  const pts = series.map((v, i) => `${(i / (series.length - 1)) * 100},${31 - (v / 100) * 30}`).join(" ");
  return (
    <svg viewBox="0 0 100 32" preserveAspectRatio="none" className={className} aria-hidden>
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke"
                strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Score per hour as an area chart. axes = 0/50/100 gridlines with labels and a tick at each UTC midnight. */
export function AreaChart({ series, start, axes = false, className = "" }:
  { series: number[]; start?: string; axes?: boolean; className?: string }) {
  if (series.length < 2) return null;
  const n = series.length;
  const pts = series.map((v, i) => `${(i / (n - 1)) * 100},${100 - v}`).join(" ");
  const t0 = start ? new Date(start).getTime() : 0;
  const days = start
    ? series.map((_, i) => new Date(t0 + i * 3600e3)).flatMap((d, i) => (d.getUTCHours() === 0 ? [{ i, d }] : []))
    : [];
  return (
    <div className={`relative ${axes ? "pb-5 pl-7" : ""} ${className}`}>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full overflow-visible text-emerald-500" aria-hidden>
        <defs>
          <linearGradient id="fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor="currentColor" stopOpacity="0.28" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        {axes && [0, 50, 100].map((y) => (
          <line key={y} x1="0" x2="100" y1={100 - y} y2={100 - y} strokeDasharray={y ? "3 3" : undefined}
                className="stroke-neutral-300 dark:stroke-neutral-700" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        ))}
        <polygon points={`0,100 ${pts} 100,100`} fill="url(#fill)" />
        <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2.5" vectorEffect="non-scaling-stroke"
                  strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      {axes && (
        <>
          {[0, 50, 100].map((y) => (
            <span key={y} className="absolute left-0 -translate-y-1/2 font-mono text-[10px] text-neutral-400"
                  style={{ top: `calc(${100 - y}% - ${(100 - y) * 0.2}px)` }}>{y}</span>
          ))}
          {days.map(({ i, d }) => (
            <span key={i} className="absolute bottom-0 -translate-x-1/2 text-[10px] text-neutral-400"
                  style={{ left: `calc(1.75rem + ${(i / (n - 1)) * 100}% - ${(i / (n - 1)) * 1.75}rem)` }}>
              {d.toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" })}
            </span>
          ))}
        </>
      )}
    </div>
  );
}

/** Radar: the top topics as blips. Closer to the centre = higher score. Decorative; the list below has the data. */
export function Radar({ topics, className = "" }: { topics: Topic[]; className?: string }) {
  return (
    <div className={`relative aspect-square ${className}`} aria-hidden>
      {["inset-0", "inset-[17%]", "inset-[34%]"].map((c) => (
        <div key={c} className={`absolute ${c} rounded-full border border-emerald-500/25`} />
      ))}
      <div className="absolute inset-x-0 top-1/2 h-px bg-emerald-500/15" />
      <div className="absolute inset-y-0 left-1/2 w-px bg-emerald-500/15" />
      <div className="absolute inset-0 animate-sweep rounded-full motion-reduce:hidden"
           style={{ background: "conic-gradient(from 0deg, rgb(16 185 129 / 0.32), rgb(16 185 129 / 0) 22%)" }} />
      {topics.map((t, i) => {
        const r = 8 + (1 - t.score / 100) * 34; // % of width from the centre
        const a = (-60 + i * 72) * (Math.PI / 180);
        return (
          <div key={t.slug} className="absolute -translate-x-1/2 -translate-y-1/2"
               style={{ left: `${50 + r * Math.cos(a)}%`, top: `${50 + r * Math.sin(a)}%` }}>
            <span className="relative flex size-2.5">
              {i === 0 && <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-70" />}
              <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500 ring-4 ring-emerald-500/20" />
            </span>
            <span className="absolute left-4 top-1/2 -translate-y-1/2 whitespace-nowrap text-[11px] font-medium text-neutral-600 dark:text-neutral-300">
              {t.name}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function ScoreBar({ score }: { score: number }) {
  return (
    <div className="h-1 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800" aria-hidden>
      <div className="h-full rounded-full bg-gradient-to-r from-emerald-600 to-emerald-400" style={{ width: `${Math.max(2, score)}%` }} />
    </div>
  );
}

function Meta({ t }: { t: Topic }) {
  return (
    <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-neutral-500">
      {t.attention != null && <span><b className="font-mono font-semibold text-neutral-700 dark:text-neutral-300">{(t.attention * 100).toFixed(1)}%</b> of the conversation</span>}
      <Growth g={t.growth} />
      {t.items != null && <span>{t.items} posts · {t.channels} channels</span>}
    </p>
  );
}

export function FeaturedTopic({ t, evidence }: { t: Topic; evidence?: { text: string; by: string } }) {
  return (
    <Link href={`/topics/${t.slug}`} prefetch
          className={`${card} group relative block overflow-hidden p-5 transition hover:border-emerald-500 sm:p-6`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">#1 right now</span>
        <Movement t={t} />
        <Flags t={t} />
      </div>
      <div className="mt-3 flex items-end justify-between gap-4">
        <h3 className="text-2xl font-bold tracking-tight group-hover:text-emerald-700 sm:text-3xl dark:group-hover:text-emerald-400">{t.name}</h3>
        <p className="shrink-0 text-right leading-none">
          <span className="font-mono text-5xl font-bold tracking-tighter text-emerald-600 dark:text-emerald-400">{Math.round(t.score)}</span>
          <span className="font-mono text-sm text-neutral-400">/100</span>
        </p>
      </div>
      <div className="mt-2"><Meta t={t} /></div>
      <AreaChart series={t.series} className="mt-4 h-24" />
      {evidence && (
        <blockquote className="mt-4 border-l-2 border-emerald-500 pl-3">
          <p className="line-clamp-2 text-sm font-medium">“{evidence.text}”</p>
          <footer className="mt-1 text-xs text-neutral-500">{evidence.by}</footer>
        </blockquote>
      )}
      <p className="mt-4 text-sm font-semibold text-emerald-700 dark:text-emerald-400">See what&apos;s driving it →</p>
    </Link>
  );
}

export function TopicRow({ t }: { t: Topic }) {
  return (
    <Link href={`/topics/${t.slug}`} prefetch
          className="group grid grid-cols-[1.75rem_1fr_auto] items-center gap-3 px-4 py-3.5 transition hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
      <span className="font-mono text-lg font-bold text-neutral-400">{t.rank}</span>
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <h3 className="font-semibold leading-snug group-hover:text-emerald-700 dark:group-hover:text-emerald-400">{t.name}</h3>
          <Movement t={t} />
          <Flags t={t} />
        </div>
        <Meta t={t} />
      </div>
      <div className="flex items-center gap-3">
        <Sparkline series={t.series} className="h-8 w-14 text-emerald-500 sm:w-20" />
        <div className="w-10 space-y-1 text-right">
          <span className="font-mono text-xl font-bold">{Math.round(t.score)}</span>
          <ScoreBar score={t.score} />
        </div>
      </div>
    </Link>
  );
}

export function VideoCard({ v, rank }: { v: Video; rank?: number }) {
  return (
    <li className="flex gap-3 py-3 sm:gap-4">
      <a href={v.url} target="_blank" rel="noopener noreferrer"
         className="group relative aspect-video w-36 shrink-0 overflow-hidden rounded-xl bg-neutral-200 sm:w-48 dark:bg-neutral-800">
        {/* eslint-disable-next-line @next/next/no-img-element -- YouTube's own thumbnail, served by YouTube, never proxied or stored */}
        <img src={`https://i.ytimg.com/vi/${v.item_id}/mqdefault.jpg`} alt="" loading="lazy"
             className="size-full object-cover transition duration-300 group-hover:scale-105" />
        {rank != null && (
          <span className="absolute left-1.5 top-1.5 rounded-md bg-black/75 px-1.5 py-0.5 font-mono text-xs font-bold text-white">#{rank}</span>
        )}
      </a>
      <div className="min-w-0 flex-1">
        <a href={v.url} target="_blank" rel="noopener noreferrer" className="line-clamp-2 font-medium leading-snug hover:underline">
          {v.title}
        </a>
        <p className="mt-1 truncate text-xs text-neutral-500">{v.channel_title}</p>
        <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="font-mono text-neutral-600 dark:text-neutral-400">{fmt(v.views_24h)} views · 24h</span>
          {v.per_1k_subs != null && v.per_1k_subs >= 1000 && (
            <span title="Views in the last 24h divided by the channel's subscribers"
                  className="rounded-md bg-emerald-100 px-1.5 py-0.5 font-mono font-semibold text-emerald-800 dark:bg-emerald-400/15 dark:text-emerald-300">
              {fmt(v.per_1k_subs / 1000)}× subs
            </span>
          )}
          {v.topics.map((t) => (
            <Link key={t.slug} href={`/topics/${t.slug}`} className="text-neutral-500 underline decoration-dotted hover:text-emerald-700 dark:hover:text-emerald-400">
              {t.name}
            </Link>
          ))}
        </p>
      </div>
    </li>
  );
}

export function Skeleton({ rows = 5, className = "h-20" }: { rows?: number; className?: string }) {
  return (
    <div className="space-y-3" aria-busy>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className={`animate-pulse rounded-2xl bg-neutral-200/70 dark:bg-neutral-800/70 ${className}`} />
      ))}
    </div>
  );
}
