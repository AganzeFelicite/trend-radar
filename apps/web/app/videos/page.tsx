import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton, Updated, VideoCard, label } from "@/components/ui";
import { getRisingVideos } from "@/lib/api";

export const metadata: Metadata = { title: "Breakout GTA 6 videos" };

async function Videos() {
  const data = await getRisingVideos();
  if (!data?.videos.length) return <p className="text-neutral-500">No videos yet. Check back in an hour.</p>;
  return (
    <div className="space-y-2">
      <Updated at={data.updated_at} />
      <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {data.videos.map((v, i) => <VideoCard key={v.item_id} v={v} rank={i + 1} />)}
      </ol>
    </div>
  );
}

export default function VideosPage() {
  return (
    <div className="space-y-6 pt-4">
      <div className="space-y-3">
        <p className={label}>Last 24 hours</p>
        <h1 className="text-4xl font-bold tracking-tight">Breakout videos</h1>
        <p className="max-w-xl text-neutral-600 dark:text-neutral-400">
          GTA 6 videos getting the most views compared with their channel&apos;s size. <b>10× subs</b> means the video
          got ten times more views in a day than the channel has subscribers: a format worth studying.
        </p>
      </div>
      <Suspense fallback={<Skeleton rows={6} className="h-24" />}>
        <Videos />
      </Suspense>
    </div>
  );
}
