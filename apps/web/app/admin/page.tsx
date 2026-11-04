import type { Metadata } from "next";
import { Suspense } from "react";
import { Skeleton, card, fmt, label } from "@/components/ui";
import { getAdminBrief, type TopicFact } from "@/lib/api";

export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false } };

const utc = (iso: string) => new Date(iso).toISOString().slice(11, 16) + " UTC";

function Fact({ t, why }: { t: TopicFact; why?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <div>
        <span className="font-semibold">{t.name}</span>
        {why && <span className="ml-2 text-xs text-neutral-500">{why}</span>}
      </div>
      <span className="shrink-0 font-mono text-sm">{Math.round(t.score)}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className={`${card} space-y-3 p-4`}>
      <h2 className={label}>{title}</h2>
      {children}
    </section>
  );
}

async function BriefView() {
  const row = await getAdminBrief();
  if (!row) return <p className="text-neutral-500">No brief yet. Run <code>scripts/radar.sh brief</code>.</p>;
  const b = row.json;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-sm text-neutral-500">
        <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-amber-900 dark:bg-amber-400/15 dark:text-amber-300">
          {row.status}
        </span>
        <span>{b.date} · version {row.version} · built {utc(b.generated_at)} from scores at {utc(b.scores_at)} · last {b.window_hours}h</span>
      </div>

      {b.notes.length > 0 && (
        <ul className="space-y-1 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-400/30 dark:bg-amber-400/10 dark:text-amber-200">
          {b.notes.map((n) => <li key={n}>⚠ {n}</li>)}
        </ul>
      )}

      <Section title="Top 5 (2+ sources, public ranking)">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-neutral-500 [&_th]:pb-1 [&_th:not(:first-child)]:pl-3">
            <tr><th>#</th><th>Topic</th><th className="text-right">Score</th><th className="hidden text-right sm:table-cell">6h ago</th>
              <th className="text-right">Share</th><th className="hidden text-right sm:table-cell">Sources</th><th className="text-right">Items</th></tr>
          </thead>
          <tbody className="font-mono">
            {b.top5.map((t) => (
              <tr key={t.slug} className="border-t border-neutral-200 dark:border-neutral-800 [&_td]:py-1.5 [&_td:not(:first-child)]:pl-3">
                <td>{t.rank}</td><td className="font-sans font-semibold">{t.name}</td>
                <td className="text-right">{Math.round(t.score)}</td><td className="hidden text-right sm:table-cell">{t.rank_6h_ago ?? "–"}</td>
                <td className="text-right">{(t.share * 100).toFixed(1)}%</td><td className="hidden text-right sm:table-cell">{t.sources}</td>
                <td className="text-right">{t.items}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <div className="grid gap-4 sm:grid-cols-2">
        <Section title="Biggest riser · 6h">
          {b.biggest_riser ? <Fact t={b.biggest_riser} why={`#${b.biggest_riser.rank_6h_ago} → #${b.biggest_riser.rank}`} />
            : <p className="text-sm text-neutral-500">No topic climbed.</p>}
        </Section>
        <Section title="Make this now">
          {b.make_this_now ? <Fact t={b.make_this_now} why={`×${b.make_this_now.growth?.toFixed(1)} vs yesterday, few videos`} />
            : <p className="text-sm text-neutral-500">Empty until growth is measurable.</p>}
        </Section>
      </div>

      <Section title="Breakout videos (email and site only, never in videos)">
        <ol className="space-y-2 text-sm">
          {b.breakout_videos.map((v) => (
            <li key={v.url} className="flex items-baseline justify-between gap-3">
              <a href={v.url} target="_blank" rel="noopener noreferrer" className="hover:underline">{v.title} <span className="text-neutral-500">· {v.channel}</span></a>
              <span className="shrink-0 font-mono text-xs text-neutral-500">{fmt(v.views_24h)} · {v.times_subscribers}× subs</span>
            </li>
          ))}
        </ol>
      </Section>

      {b.off_topic.length > 0 && (
        <Section title="Off-topic buzz">{b.off_topic.map((t) => <Fact key={t.slug} t={t} />)}</Section>
      )}

      <Section title="Freshness">
        <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm">
          {b.freshness.map((f) => (
            <li key={f.source} className={f.stale ? "text-rose-700 dark:text-rose-400" : ""}>
              {f.stale ? "✗" : "✓"} {f.source} <span className="font-mono text-xs text-neutral-500">{f.last_success ? utc(f.last_success) : "never"}</span>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

const DRAFTS = ["Email digest", "Telegram post", "Website “Today” text", "Video script · Daily Radar", "Video script · Myth or Real?"];

export default function AdminPage() {
  return (
    <div className="space-y-8 pt-4">
      <div className="space-y-2">
        <p className={label}>Admin · local preview</p>
        <h1 className="text-3xl font-bold tracking-tight">Today&apos;s Daily Brief</h1>
        <p className="max-w-xl text-sm text-neutral-600 dark:text-neutral-400">
          The verified data every draft, email and content package is written from. Built daily at 06:50 UTC, or now
          with <code>scripts/radar.sh brief</code>.
        </p>
      </div>
      <Suspense fallback={<Skeleton rows={4} className="h-32" />}>
        <BriefView />
      </Suspense>
      <section className="space-y-3">
        <h2 className={label}>Drafts</h2>
        <ul className={`${card} divide-y divide-neutral-200 dark:divide-neutral-800`}>
          {DRAFTS.map((d) => (
            <li key={d} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
              <span className="font-medium">{d}</span>
              <span className="text-xs text-neutral-500">not written yet</span>
            </li>
          ))}
        </ul>
        <p className="text-sm text-neutral-500">
          Drafts appear here once AI writing (P9.2) is switched on, which needs your monthly cost cap. Approve, edit and
          send buttons come with P9.3; nothing can be sent from this page today.
        </p>
      </section>
    </div>
  );
}
