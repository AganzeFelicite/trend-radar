import Link from "next/link";
import { Suspense } from "react";
import { Skeleton, TopicCard, Updated, VideoRow } from "@/components/ui";
import { WaitlistForm } from "@/components/waitlist-form";
import { getRisingVideos, getTopTopics } from "@/lib/api";

async function TopTopics() {
  const data = await getTopTopics();
  if (!data?.topics.length) return <p className="text-neutral-500">No scores yet. Check back in an hour.</p>;
  return (
    <div className="space-y-3">
      <Updated at={data.updated_at} />
      {data.topics.map((t) => <TopicCard key={t.slug} t={t} />)}
      <p className="text-xs text-neutral-500">
        Score out of 100: 100 is the strongest moment of any topic in the past 7 days. It combines how much of the
        GTA 6 conversation a topic holds with how fast that share is growing.
      </p>
    </div>
  );
}

async function RisingPreview() {
  const data = await getRisingVideos();
  if (!data?.videos.length) return null;
  return (
    <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
      {data.videos.slice(0, 3).map((v, i) => <VideoRow key={v.item_id} v={v} rank={i + 1} />)}
    </ol>
  );
}

export default function Home() {
  return (
    <div className="space-y-10">
      <section className="space-y-3 pt-4">
        <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">What GTA 6 topics are rising right now</h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Every hour we read new videos, posts and headlines about GTA 6 and rank topics by momentum, so you know
          what to make your next video about.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Top 5 today</h2>
        <Suspense fallback={<Skeleton />}>
          <TopTopics />
        </Suspense>
      </section>

      <section className="space-y-3 rounded-2xl bg-emerald-50 p-5 dark:bg-emerald-950/40">
        <h2 className="text-lg font-semibold">Get the top 5 in your inbox every morning</h2>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">One short email a day until launch week. Unsubscribe anytime.</p>
        <WaitlistForm />
      </section>

      <section className="space-y-1">
        <div className="flex items-baseline justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-neutral-500">Breakout videos</h2>
          <Link href="/videos" className="text-sm text-emerald-700 hover:underline dark:text-emerald-400">All 10 →</Link>
        </div>
        <Suspense fallback={<Skeleton rows={3} />}>
          <RisingPreview />
        </Suspense>
      </section>
    </div>
  );
}
