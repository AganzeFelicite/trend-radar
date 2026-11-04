import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton, Updated, VideoRow } from "@/components/ui";
import { getRisingVideos } from "@/lib/api";

export const metadata: Metadata = { title: "Rising GTA 6 videos" };

async function Videos() {
  const data = await getRisingVideos();
  if (!data?.videos.length) return <p className="text-neutral-500">No videos yet. Check back in an hour.</p>;
  return (
    <>
      <Updated at={data.updated_at} />
      <ol className="divide-y divide-neutral-200 dark:divide-neutral-800">
        {data.videos.map((v, i) => <VideoRow key={v.item_id} v={v} rank={i + 1} />)}
      </ol>
    </>
  );
}

export default function VideosPage() {
  return (
    <div className="space-y-4 pt-4">
      <h1 className="text-3xl font-bold tracking-tight">Breakout videos</h1>
      <p className="text-neutral-600 dark:text-neutral-400">
        GTA 6 videos getting the most views in the last 24 hours compared with their channel&apos;s size. A small
        channel beating its subscriber count is a format worth studying.
      </p>
      <Suspense fallback={<Skeleton rows={6} />}>
        <Videos />
      </Suspense>
    </div>
  );
}
