import Link from "next/link";
import { Suspense } from "react";
import { FeaturedTopic, Radar, Skeleton, TopicRow, Updated, VideoCard, card, fmt, label } from "@/components/ui";
import { WaitlistForm } from "@/components/waitlist-form";
import { getRisingVideos, getTopic, getTopTopics } from "@/lib/api";

async function LiveStats() {
  const data = await getTopTopics();
  if (!data) return null;
  const { stats } = data;
  return (
    <div className="space-y-4">
      <Updated at={data.updated_at} />
      <dl className="grid max-w-md grid-cols-3 gap-4">
        {[[fmt(stats.items_24h), "posts & videos read in 24h"], [stats.topics, "topics tracked"], [stats.sources, "sources, hourly"]].map(([n, text]) => (
          <div key={text}>
            <dt className="sr-only">{text}</dt>
            <dd className="font-mono text-2xl font-bold">{n}</dd>
            <dd className="text-xs leading-tight text-neutral-500">{text}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

async function HeroRadar() {
  const data = await getTopTopics();
  return <Radar topics={data?.topics ?? []} className="w-full" />;
}

async function TopTopics() {
  const data = await getTopTopics();
  if (!data?.topics.length) return <p className="text-neutral-500">No scores yet. Check back in an hour.</p>;
  const [first, ...rest] = data.topics;
  const detail = await getTopic(first.slug);
  const v = detail?.videos[0], p = detail?.posts[0];
  const evidence = v ? { text: v.title, by: `${v.channel_title} · ${fmt(v.views_24h)} views in 24h` }
    : p ? { text: p.title, by: `@${p.author} on Bluesky · ${fmt(p.engagement_24h)} likes, reposts and replies` } : undefined;
  return (
    <div className="space-y-3">
      <FeaturedTopic t={first} evidence={evidence} />
      <div className={`${card} divide-y divide-neutral-200 overflow-hidden dark:divide-neutral-800`}>
        {rest.map((t) => <TopicRow key={t.slug} t={t} />)}
      </div>
    </div>
  );
}

async function RisingPreview() {
  const data = await getRisingVideos();
  if (!data?.videos.length) return null;
  return (
    <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
      {data.videos.slice(0, 3).map((v, i) => <VideoCard key={v.item_id} v={v} rank={i + 1} />)}
    </ol>
  );
}

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="relative">
        <div className="grid-bg pointer-events-none absolute -inset-x-4 -top-24 bottom-0 -z-10" />
        <div className="grid items-center gap-8 pt-6 sm:grid-cols-[1fr_15rem]">
          <div className="space-y-5">
            <h1 className="text-4xl font-bold leading-[1.05] tracking-tight sm:text-5xl">
              What GTA 6 topics are <span className="text-emerald-600 dark:text-emerald-400">rising</span> right now
            </h1>
            <p className="max-w-lg text-neutral-600 dark:text-neutral-400">
              We read every new GTA 6 video, post and headline each hour and rank topics by momentum, so you know what
              your next video should be about.
            </p>
            <Suspense fallback={<div className="h-20" />}>
              <LiveStats />
            </Suspense>
          </div>
          <div className="hidden sm:block">
            <Suspense fallback={<Radar topics={[]} className="w-full" />}>
              <HeroRadar />
            </Suspense>
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className={label}>Top 5 today</h2>
        <Suspense fallback={<><Skeleton rows={1} className="h-80" /><Skeleton rows={1} className="mt-3 h-72" /></>}>
          <TopTopics />
        </Suspense>
        <details className="group rounded-2xl border border-neutral-200 px-4 py-3 text-sm dark:border-neutral-800">
          <summary className="flex cursor-pointer list-none items-center justify-between font-medium">
            How the score works
            <span className="text-neutral-400 transition group-open:rotate-45">+</span>
          </summary>
          <div className="mt-3 space-y-2 text-neutral-600 dark:text-neutral-400">
            <p><b>Score out of 100.</b> 100 is the strongest moment any topic had in the past 7 days.</p>
            <p>It multiplies how much of the GTA 6 conversation a topic holds (its share of views, likes and headlines
              on YouTube, Bluesky, Twitch and gaming news) by how fast that share is growing compared with the day before.</p>
            <p><b>▲▼ 6h</b> rank change in the last 6 hours · <b>Spiking</b> accelerating in the last 3 hours ·{" "}
              <b>Found by AI</b> a topic our AI spotted that no keyword list covered.</p>
          </div>
        </details>
      </section>

      <section className="relative overflow-hidden rounded-3xl bg-emerald-600 p-6 text-white sm:p-8 dark:bg-emerald-700">
        <div className="pointer-events-none absolute -right-20 -top-20 w-72 opacity-40 [&_*]:border-white/50">
          <Radar topics={[]} />
        </div>
        <div className="relative space-y-3">
          <h2 className="text-2xl font-bold tracking-tight">Know what&apos;s rising before you plan your next video</h2>
          <p className="max-w-md text-emerald-50">A short email every morning with the 5 topics that moved overnight. Free. Unsubscribe anytime.</p>
          <WaitlistForm />
        </div>
      </section>

      <section className="space-y-2">
        <div className="flex items-baseline justify-between">
          <h2 className={label}>Breakout videos</h2>
          <Link href="/videos" className="text-sm font-medium text-emerald-700 hover:underline dark:text-emerald-400">All 10 →</Link>
        </div>
        <p className="text-sm text-neutral-500">Small channels getting far more views than they have subscribers.</p>
        <Suspense fallback={<Skeleton rows={3} className="h-24" />}>
          <RisingPreview />
        </Suspense>
      </section>
    </div>
  );
}
