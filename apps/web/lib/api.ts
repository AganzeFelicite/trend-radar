import { cacheLife } from "next/cache";
import { connection } from "next/server";

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export type TopicRef = { slug: string; name: string };

export type Topic = {
  slug: string;
  name: string;
  origin: "curated" | "ai";
  rank: number | null;
  rank_6h_ago?: number | null; // null: not ranked (or no data) 6 hours ago
  score: number;
  attention?: number;
  growth: number | null; // null until the previous 24h is covered
  items?: number;
  channels?: number;
  sources?: number;
  is_new?: boolean;
  is_spiking?: boolean;
  is_confirmed?: boolean;
  in_top5?: boolean; // the public top 5: unflagged topics with activity on 2+ sources
  is_off_topic?: boolean; // owner-flagged meme / non-game topic: no rank, listed apart
  series: number[]; // score per hour, oldest first
  series_start?: string;
};

export type Video = {
  item_id: string;
  title: string;
  url: string;
  channel_title: string | null;
  views_24h: number;
  per_hour: number;
  subscribers?: number;
  per_1k_subs?: number;
  topics: TopicRef[];
};

export type TopicPage = {
  updated_at: string | null;
  topic: Topic;
  videos: Video[];
  news: { title: string; url: string; outlet: string; seen_at: string }[];
  posts: { title: string; url: string; author: string; engagement_24h: number }[];
  keywords: { keyword: string; items: number }[];
};

// Scores change once an hour: request time (never baked in at build, so the site builds without the API),
// cached in memory for a minute so busy minutes don't each hit the API.
async function cached<T>(path: string): Promise<T | null> {
  "use cache";
  cacheLife({ stale: 30, revalidate: 60, expire: 300 });
  const res = await fetch(`${API_URL}${path}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${path}: ${res.status}`);
  return res.json();
}

async function get<T>(path: string): Promise<T | null> {
  await connection();
  return cached<T>(path);
}

export type Stats = { items_24h: number; sources: number; topics: number };
export const getTopTopics = () =>
  get<{ updated_at: string | null; stats: Stats; topics: Topic[]; off_topic: Topic[] }>("/api/topics/top?limit=10");
export const getTopic = (slug: string) => get<TopicPage>(`/api/topics/${encodeURIComponent(slug)}`);
export const getRisingVideos = () => get<{ updated_at: string | null; videos: Video[] }>("/api/videos/rising");
