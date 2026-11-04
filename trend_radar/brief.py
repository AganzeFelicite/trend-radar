"""Daily Brief (P9.1): one structured, verified snapshot of the day's data, built after the morning dbt build.
Everything downstream (digest, Telegram, website "Today", Content Packages) is written from an approved brief only,
so every fact in them traces back to a field here. No AI in this step.
"""

from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import func, select, text

from trend_radar import api
from trend_radar.db import DailyBrief, connector_run, engine

# Same trust rule as the public top 5 (dbt var top5_min_sources): one platform's in-joke isn't the day's news.
MIN_SOURCES = 2
# A source counts as stale when its last good run is older than this (Wikipedia is daily and published a day late).
STALE_AFTER = {"youtube": timedelta(hours=2), "bluesky": timedelta(hours=2), "rss": timedelta(hours=2),
               "twitch": timedelta(hours=2), "wikipedia": timedelta(hours=30)}


class TopicFact(BaseModel):
    slug: str
    name: str
    rank: int | None  # public rank (top 5 rule, off-topic flags)
    rank_6h_ago: int | None
    score: float  # 0-100
    share: float  # of all GTA 6 activity in the last 24h, 0-1
    growth: float | None  # x vs the previous 24h; None until measurable
    sources: int
    items: int
    channels: int


class VideoFact(BaseModel):
    """For the email and site only: never shown in videos (third-party media)."""
    title: str
    channel: str | None
    url: str
    views_24h: int
    times_subscribers: float  # views in 24h / channel subscribers


class Lead(BaseModel):
    """A research starting point: read it (and its comments), cite it, never show it in a video."""
    title: str
    url: str
    by: str | None
    metric: str


class Evidence(BaseModel):
    keywords: list[str] = []  # what people call the topic (alias matches, 7 days)
    videos: list[Lead] = []
    posts: list[Lead] = []
    news: list[Lead] = []


class Freshness(BaseModel):
    source: str
    last_success: datetime | None
    stale: bool


class Brief(BaseModel):
    date: date
    generated_at: datetime
    scores_at: datetime  # the scored hour every number comes from
    window_hours: int  # topic numbers cover the 24h ending at scores_at
    top5: list[TopicFact]
    biggest_riser: TopicFact | None  # largest public-rank gain in 6h
    make_this_now: TopicFact | None  # rising, talked about, few videos yet; None until growth is measurable
    breakout_videos: list[VideoFact]
    off_topic: list[TopicFact]
    freshness: list[Freshness]
    notes: list[str]
    evidence: dict[str, Evidence] = {}  # topic slug -> research leads (briefs before Nov 4 v3 have none)


def _fact(r: dict) -> TopicFact:
    r = api.topic_view(r)
    return TopicFact(slug=r["slug"], name=r["name"], rank=r["rank"], rank_6h_ago=r["rank_6h_ago"], score=r["score"],
                     share=r["attention"] or 0, growth=r["growth"], sources=r["sources"] or 0, items=r["items"] or 0,
                     channels=r["channels"] or 0)


def _evidence(slug: str) -> Evidence:
    page = api.topic(slug)  # same data as the public topic page
    return Evidence(
        keywords=[k["keyword"] for k in page["keywords"]],
        videos=[Lead(title=v["title"], url=v["url"], by=v["channel_title"], metric=f"{int(v['views_24h']):,} views in 24h")
                for v in page["videos"][:5]],
        posts=[Lead(title=" ".join(p["title"].split())[:280], url=p["url"], by=p["author"],
                    metric=f"{int(p['engagement_24h']):,} likes, reposts and replies in 24h") for p in page["posts"][:3]],
        news=[Lead(title=n["title"], url=n["url"], by=n["outlet"], metric=f"seen {n['seen_at']:%b %d, %H:%M} UTC")
              for n in page["news"][:3]],
    )


def _make_this_now(topics: list[TopicFact]) -> TopicFact | None:
    # ponytail: heuristic: rising (growth >= 1.2) on 2+ sources, most momentum per YouTube video already made.
    # Tune on release-week data (P7.3).
    rising = [t for t in topics if t.growth is not None and t.growth >= 1.2 and t.sources >= MIN_SOURCES]
    if not rising:
        return None
    videos = {r["t"]: r["n"] for r in api.rows("""select t, count(*) as n from analytics.rising_items, unnest(topics) t
                                                  where source = 'youtube' group by 1""")}
    return max(rising, key=lambda t: t.share * t.growth / (1 + videos.get(t.slug, 0)))


def assemble(now: datetime | None = None) -> Brief:
    now = now or datetime.now(timezone.utc)
    ranked = [_fact(r) for r in api.rows(api.TOPICS + " where not s.is_off_topic order by s.public_rank limit 20")]
    in_top5 = {r["slug"] for r in api.rows(api.TOPICS + " where s.in_top5")}
    top5 = [t for t in ranked if t.slug in in_top5][:5]
    gains = [t for t in ranked if t.rank and t.rank_6h_ago and t.rank_6h_ago > t.rank and t.sources >= MIN_SOURCES]
    riser = max(gains, key=lambda t: (t.rank_6h_ago - t.rank, t.score), default=None)

    last_ok = {r["source"]: r["t"] for r in api.rows("""select source, max(finished_at) as t from connector_runs
                                                        where status in ('ok', 'partial') group by 1""")}
    freshness = [Freshness(source=s, last_success=last_ok.get(s), stale=not last_ok.get(s) or now - last_ok[s] > age)
                 for s, age in STALE_AFTER.items()]

    notes = [f"{f.source}: no successful run yet" if not f.last_success else f"{f.source}: last data {f.last_success:%H:%M} UTC, stale"
             for f in freshness if f.stale]
    if all(t.growth is None for t in ranked):
        notes.append("Growth vs yesterday is not measurable yet (needs 48h of collection): no 'make this now' pick, scores rank by share.")
    with engine.connect() as c:
        scores_at = c.scalar(text("select max(scored_at) from analytics.topic_scores"))

    pick = _make_this_now(ranked)
    return Brief(
        date=now.date(), generated_at=now, scores_at=scores_at, window_hours=24, top5=top5, biggest_riser=riser,
        make_this_now=pick,
        breakout_videos=[VideoFact(title=v["title"], channel=v["channel_title"], url=v["url"], views_24h=v["views_24h"],
                                   times_subscribers=round(v["per_1k_subs"] / 1000, 1))
                         for v in api.rising_videos(limit=3)["videos"]],
        off_topic=[_fact(r) for r in api.rows(api.TOPICS + " where s.is_off_topic order by s.score desc limit 3")],
        freshness=freshness, notes=notes,
        evidence={t.slug: _evidence(t.slug) for t in top5 + [riser, pick] if t},
    )


def build() -> None:
    """Scheduled after the morning dbt build. Each run of the same day adds a new draft version."""
    with connector_run("brief", "build") as (s, run):
        b = assemble()
        version = (s.scalar(select(func.max(DailyBrief.version)).where(DailyBrief.brief_date == b.date)) or 0) + 1
        s.add(DailyBrief(brief_date=b.date, version=version, json=b.model_dump(mode="json"), status="draft"))
        s.commit()
        run.items_count = len(b.top5)
