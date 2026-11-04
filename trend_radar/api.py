"""Read-only API over the gold marts (analytics.*), plus the waitlist. Same image as the worker:
uvicorn trend_radar.api:app. Caddy routes /api here; the Next.js site calls it server-side.
"""

import re
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from trend_radar import config
from trend_radar.db import Waitlist, engine

app = FastAPI(title="Trend Radar API", docs_url="/api/docs", openapi_url="/api/openapi.json")

UPDATED_AT = """select max(finished_at) from connector_runs
                where source = 'dbt' and job = 'build' and status in ('ok', 'partial')"""

# One row per topic in the latest scored hour. series = score for every scored hour of the last 7 days (0 = no activity).
# rank = public_rank: the top 5 rule and off-topic flags are applied in dbt (topic_scores), so every reader agrees.
TOPICS = """
with hours as (select distinct scored_at from analytics.topic_scores),
latest as (select max(scored_at) as t from hours)
select s.topic_slug as slug, t.topic_name as name, t.origin, s.public_rank::int as rank, coalesce(s.score, 0)::float as score,
       s.attention, s.prev_attention, s.growth, s.items, s.channels, s.sources,
       s.is_new, s.is_spiking, s.is_confirmed, s.in_top5, s.is_off_topic,
       array(select coalesce(h2.score, 0)::float
             from hours h left join analytics.topic_scores h2 on h2.scored_at = h.scored_at and h2.topic_slug = s.topic_slug
             order by h.scored_at) as series,
       (select min(scored_at) from hours) as series_start,
       (select p.public_rank::int from analytics.topic_scores p
        where p.topic_slug = s.topic_slug and p.scored_at = latest.t - interval '6 hours') as rank_6h_ago
from analytics.topic_scores s
join analytics.topics t using (topic_slug)
join latest on s.scored_at = latest.t
"""

TOPIC_NAMES = """coalesce((select json_agg(json_build_object('slug', t.topic_slug, 'name', t.topic_name) order by t.topic_name)
                           from analytics.topics t where t.topic_slug = any(r.topics)), '[]')"""


def rows(sql: str, **params) -> list[dict]:
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql), params)]


def topic_view(r: dict) -> dict:
    # growth is 1 by construction until the previous 24h window is covered; null says "not measurable yet"
    return r | {"growth": r["growth"] if r["prev_attention"] is not None else None}


def updated_at():
    with engine.connect() as c:
        return c.scalar(text(UPDATED_AT))


@app.get("/api/health")
def health():
    return {"ok": True, "updated_at": updated_at()}


@app.get("/api/topics/top")
def top_topics(limit: int = Query(5, ge=1, le=10)):
    """topics = public ranking (in_top5 marks the top 5); off_topic = flagged topics, shown apart."""
    topics = rows(TOPICS + " where not s.is_off_topic order by s.public_rank limit :limit", limit=limit)
    off_topic = rows(TOPICS + " where s.is_off_topic order by s.score desc, s.topic_slug limit 3")
    stats = rows("""select (select count(*) from analytics.rising_items) as items_24h,
                           (select count(distinct source) from analytics.rising_items) as sources,
                           (select count(*) from analytics.topics) as topics""")[0]
    return {"updated_at": updated_at(), "stats": stats, "topics": [topic_view(r) for r in topics],
            "off_topic": [topic_view(r) for r in off_topic]}


@app.get("/api/topics/{slug}")
def topic(slug: str):
    found = rows(TOPICS + " where s.topic_slug = :slug", slug=slug)
    if found:
        t = topic_view(found[0])
    else:  # a known topic with no activity in the latest hour
        known = rows("select topic_slug as slug, topic_name as name, origin from analytics.topics where topic_slug = :slug",
                     slug=slug)
        if not known:
            raise HTTPException(404, "unknown topic")
        t = known[0] | {"rank": None, "score": 0, "growth": None, "series": []}
    return {
        "updated_at": updated_at(),
        "topic": t,
        "videos": rows(f"""select item_id, title, url, channel_title, activity_24h as views_24h, per_hour, {TOPIC_NAMES} as topics
                           from analytics.rising_items r where source = 'youtube' and :slug = any(topics)
                           order by activity_24h desc limit 8""", slug=slug),
        "posts": rows("""select title, url, channel_title as author, activity_24h as engagement_24h from analytics.rising_items
                         where source = 'bluesky' and :slug = any(topics) order by activity_24h desc limit 5""", slug=slug),
        "news": rows("""select title, url, channel_title as outlet, seen_at from analytics.rising_items
                        where source = 'rss' and :slug = any(topics) order by seen_at desc limit 5""", slug=slug),
        "keywords": rows("""select matched_alias as keyword, count(*) as items from analytics.topic_items
                            where topic_slug = :slug and match_type = 'alias' and seen_at > now() - interval '7 days'
                            group by 1 order by 2 desc, 1 limit 8""", slug=slug),
    }


@app.get("/api/videos/rising")
def rising_videos(limit: int = Query(10, ge=1, le=10)):
    # Views in the last 24h per 1,000 subscribers: small channels breaking out rank above big channels' normal days.
    # ponytail: channels whose subscriber count isn't fetched yet are left out (they'd look tiny); youtube.channels fills it.
    return {"updated_at": updated_at(), "videos": rows(f"""
        select item_id, title, url, channel_title, activity_24h as views_24h, per_hour, subscribers, per_1k_subs,
               {TOPIC_NAMES} as topics
        from analytics.rising_items r
        where source = 'youtube' and activity_24h >= 1000 and subscribers is not null
        order by per_1k_subs desc limit :limit""", limit=limit)}


# --- admin (read-only for now). ponytail: no auth in the app: Caddy basic_auth guards /admin and /api/admin/* on the
# server (P1.3); locally everything is bound to 127.0.0.1. Approve/send actions (P9.3) need it before they exist.

def _latest_brief() -> dict:
    found = rows("""select brief_date, version, status, created_at, json from daily_briefs
                    order by brief_date desc, version desc limit 1""")
    if not found:
        raise HTTPException(404, "no brief yet: run scripts/radar.sh brief")
    return found[0]


def _studio_prompt(b: dict) -> str:
    from trend_radar import studio
    from trend_radar.brief import Brief

    script = rows("""select text from drafts where brief_date = :d and brief_version = :v and kind = 'script_daily_radar'""",
                  d=b["brief_date"], v=b["version"])
    return studio.daily_radar(Brief.model_validate(b["json"]), script[0]["text"] if script else None, b["version"], b["status"])


@app.get("/api/admin/studio-prompt", response_class=PlainTextResponse)
def studio_prompt(download: bool = False):
    """The Video Studio brief as Markdown (download=1: as a file)."""
    b = _latest_brief()
    headers = {"Content-Disposition": f'attachment; filename="radar-daily-{b["brief_date"]}.md"'} if download else None
    return PlainTextResponse(_studio_prompt(b), media_type="text/markdown; charset=utf-8", headers=headers)


@app.get("/api/admin/brief")
def latest_brief():
    b = _latest_brief()
    drafts = rows("""select kind, text, status, problems, created_at from drafts
                     where brief_date = :d and brief_version = :v order by kind""", d=b["brief_date"], v=b["version"])
    writing = rows("""select (select coalesce(sum(quota_used), 0) / 1e6 from connector_runs
                              where source = 'writer' and started_at >= date_trunc('month', now()))::float as month_usd,
                             r.status, r.error, r.started_at
                      from (select 1) one left join lateral (select * from connector_runs where source = 'writer'
                                                             order by id desc limit 1) r on true""")[0]
    return b | {"drafts": drafts, "writing": writing | {"cap_usd": config.AI_WRITING_MONTHLY_CAP_USD},
                "studio_prompt": _studio_prompt(b)}


# --- waitlist ---

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SIGNUPS_PER_HOUR = 5
_recent: dict[str, deque] = defaultdict(deque)  # ponytail: per-process memory; fine for one api process, Redis if it scales out


class Signup(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def valid(cls, v: str) -> str:
        v = v.strip().lower()
        if len(v) > 254 or not EMAIL.match(v):
            raise ValueError("not a valid email address")
        return v


@app.post("/api/waitlist", status_code=201)
def join_waitlist(signup: Signup, request: Request):
    ip, now = request.client.host if request.client else "?", time.monotonic()
    hits = _recent[ip]
    while hits and now - hits[0] > 3600:
        hits.popleft()
    if len(hits) >= SIGNUPS_PER_HOUR:
        raise HTTPException(429, "too many signups from this address, try again later")
    hits.append(now)
    with engine.begin() as c:  # already on the list → same answer, so the form can't be used to test addresses
        c.execute(insert(Waitlist).values(email=signup.email).on_conflict_do_nothing())
    return {"ok": True}
