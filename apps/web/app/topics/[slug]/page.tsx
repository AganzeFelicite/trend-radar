import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AreaChart, Flags, Growth, Movement, Skeleton, Updated, VideoCard, card, fmt, label } from "@/components/ui";
import { getTopic } from "@/lib/api";

function Stat({ name, value, hint }: { name: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className={`${card} p-4`}>
      <div className="text-xs text-neutral-500">{name}</div>
      <div className="mt-1 font-mono text-xl font-bold">{value}</div>
      {hint && <div className="mt-0.5 text-[11px] text-neutral-400">{hint}</div>}
    </div>
  );
}

async function TopicDetails({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await getTopic(slug);
  if (!data) notFound();
  const { topic: t, videos, posts, news, keywords } = data;
  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {t.rank && <span className="rounded-full bg-emerald-600 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">#{t.rank} right now</span>}
          <Movement t={t} />
          <Flags t={t} />
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{t.name}</h1>
          <p className="leading-none">
            <span className="font-mono text-6xl font-bold tracking-tighter text-emerald-600 dark:text-emerald-400">{Math.round(t.score)}</span>
            <span className="font-mono text-base text-neutral-400">/100</span>
          </p>
        </div>
        <Updated at={data.updated_at} />
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat name="Share of conversation" value={t.attention != null ? `${(t.attention * 100).toFixed(1)}%` : "–"} hint="of all GTA 6 activity, 24h" />
        <Stat name="vs yesterday" value={t.growth != null ? <Growth g={t.growth} /> : "–"} hint={t.growth == null ? "measurable from Nov 5" : undefined} />
        <Stat name="Posts & videos" value={t.items ?? 0} hint="last 24h" />
        <Stat name="Channels" value={t.channels ?? 0} hint="different creators" />
      </section>

      {t.series.length > 1 && (
        <section className={`${card} space-y-3 p-4 sm:p-5`}>
          <h2 className={label}>Score, hour by hour (UTC)</h2>
          <AreaChart series={t.series} start={t.series_start} axes className="h-48" />
        </section>
      )}

      {keywords.length > 0 && (
        <section className="space-y-3">
          <h2 className={label}>What people call it</h2>
          <div className="flex flex-wrap gap-2">
            {keywords.map((k) => (
              <span key={k.keyword} className="rounded-full border border-neutral-300 bg-white px-3 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900">
                {k.keyword} <span className="font-mono text-xs text-neutral-400">{k.items}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {videos.length > 0 && (
        <section className="space-y-1">
          <h2 className={label}>Top videos · 24h</h2>
          <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {videos.map((v, i) => <VideoCard key={v.item_id} v={{ ...v, topics: [] }} rank={i + 1} />)}
          </ol>
        </section>
      )}

      {posts.length > 0 && (
        <section className="space-y-3">
          <h2 className={label}>Top posts on Bluesky · 24h</h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {posts.map((p) => (
              <li key={p.url}>
                <a href={p.url} target="_blank" rel="noopener noreferrer"
                   className={`${card} flex h-full flex-col justify-between gap-3 p-4 transition hover:border-emerald-500`}>
                  <p className="line-clamp-4 text-sm">{p.title}</p>
                  <p className="flex items-center justify-between gap-2 text-xs text-neutral-500">
                    <span className="truncate">@{p.author}</span>
                    <span className="shrink-0 font-mono">♥ {fmt(p.engagement_24h)}</span>
                  </p>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}

      {news.length > 0 && (
        <section className="space-y-3">
          <h2 className={label}>In the news</h2>
          <ul className={`${card} divide-y divide-neutral-200 dark:divide-neutral-800`}>
            {news.map((n) => (
              <li key={n.url}>
                <a href={n.url} target="_blank" rel="noopener noreferrer" className="flex items-baseline justify-between gap-3 px-4 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-800/50">
                  <span className="font-medium">{n.title}</span>
                  <span className="shrink-0 text-xs text-neutral-500">{n.outlet}</span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export default function TopicPage(props: PageProps<"/topics/[slug]">) {
  return (
    <div className="space-y-6 pt-4">
      <Link href="/" className="text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-400">← All topics</Link>
      <Suspense fallback={<Skeleton rows={3} className="h-28" />}>
        <TopicDetails params={props.params} />
      </Suspense>
    </div>
  );
}
