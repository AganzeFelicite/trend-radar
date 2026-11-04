import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { Flags, Growth, Skeleton, Updated, VideoRow, fmt } from "@/components/ui";
import { getTopic, type Topic } from "@/lib/api";

function Chart({ t }: { t: Topic }) {
  if (t.series.length < 2 || !t.series_start) return null;
  const n = t.series.length;
  const pts = t.series.map((v, i) => `${(i / (n - 1)) * 100},${100 - v}`).join(" ");
  const day = (d: Date) => d.toLocaleDateString("en", { month: "short", day: "numeric", timeZone: "UTC" });
  return (
    <figure className="space-y-1">
      <div className="relative h-44 rounded-2xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full text-emerald-500" role="img"
             aria-label={`Score over the last ${n} hours, now ${Math.round(t.score)}`}>
          {[0, 50, 100].map((y) => (
            <line key={y} x1="0" x2="100" y1={100 - y} y2={100 - y} className="stroke-neutral-200 dark:stroke-neutral-800"
                  strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          <polygon points={`0,100 ${pts} 100,100`} className="fill-emerald-500/10" />
          <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke"
                    strokeLinejoin="round" />
        </svg>
        <span className="absolute left-4 top-2 text-[10px] text-neutral-400">100</span>
      </div>
      <figcaption className="flex justify-between text-xs text-neutral-500">
        <span>{day(new Date(t.series_start))}</span>
        <span>Score per hour (UTC)</span>
        <span>now</span>
      </figcaption>
    </figure>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="mt-1 font-semibold tabular-nums">{value}</div>
    </div>
  );
}

async function TopicDetails({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const data = await getTopic(slug);
  if (!data) notFound();
  const { topic: t, videos, posts, news, keywords } = data;
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-2"><Flags t={t} /></div>
        <h1 className="text-3xl font-bold tracking-tight">{t.name}</h1>
        <div className="flex items-baseline gap-3">
          <span className="text-5xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">{Math.round(t.score)}</span>
          <span className="text-neutral-500">/ 100{t.rank ? ` · #${t.rank} right now` : ""}</span>
        </div>
        <Updated at={data.updated_at} />
      </section>

      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Share of conversation" value={t.attention != null ? `${(t.attention * 100).toFixed(1)}%` : "–"} />
        <Stat label="vs yesterday" value={t.growth != null ? <Growth g={t.growth} /> : "from Nov 5"} />
        <Stat label="Posts (24h)" value={t.items ?? 0} />
        <Stat label="Channels" value={t.channels ?? 0} />
      </section>

      <Chart t={t} />

      {keywords.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">What people call it</h2>
          <div className="flex flex-wrap gap-2">
            {keywords.map((k) => (
              <span key={k.keyword} className="rounded-full border border-neutral-300 px-3 py-1 text-sm dark:border-neutral-700">
                {k.keyword} <span className="text-neutral-400">{k.items}</span>
              </span>
            ))}
          </div>
        </section>
      )}

      {videos.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Top videos (24h)</h2>
          <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {videos.map((v) => <VideoRow key={v.item_id} v={{ ...v, topics: [] }} />)}
          </ol>
        </section>
      )}

      {posts.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Top posts on Bluesky (24h)</h2>
          <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {posts.map((p) => (
              <li key={p.url} className="py-3">
                <a href={p.url} target="_blank" rel="noopener noreferrer" className="line-clamp-3 hover:underline">{p.title}</a>
                <p className="mt-1 text-xs text-neutral-500">@{p.author} · {fmt(p.engagement_24h)} likes, reposts and replies</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {news.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">In the news</h2>
          <ul className="space-y-2">
            {news.map((n) => (
              <li key={n.url}>
                <a href={n.url} target="_blank" rel="noopener noreferrer" className="font-medium hover:underline">{n.title}</a>
                <span className="text-xs text-neutral-500"> · {n.outlet}</span>
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
    <div className="space-y-4 pt-4">
      <Link href="/" className="text-sm text-emerald-700 hover:underline dark:text-emerald-400">← Top topics</Link>
      <Suspense fallback={<Skeleton rows={3} />}>
        <TopicDetails params={props.params} />
      </Suspense>
    </div>
  );
}
