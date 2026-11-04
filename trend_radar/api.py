"""Read-only API over the gold marts (analytics.*), plus the waitlist. Same image as the worker:
uvicorn trend_radar.api:app. Caddy routes /api here; the Next.js site calls it server-side.
"""

import re
import time
from collections import defaultdict, deque

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from trend_radar.db import Waitlist, engine

app = FastAPI(title="Trend Radar API", docs_url="/api/docs", openapi_url="/api/openapi.json")

UPDATED_AT = """select max(finished_at) from connector_runs
                where source = 'dbt' and job = 'build' and status in ('ok', 'partial')"""

# One row per topic in the latest scored hour. series = score for every scored hour of the last 7 days (0 = no activity).
TOPICS = """
with hours as (select distinct scored_at from analytics.topic_scores),
latest as (select max(scored_at) as t from hours)
select s.topic_slug as slug, t.topic_name as name, t.origin, s.rank::int, coalesce(s.score, 0)::float as score,
       s.attention, s.prev_attention, s.growth, s.items, s.channels, s.sources,
       s.is_new, s.is_spiking, s.is_confirmed,
       array(select coalesce(h2.score, 0)::float
             from hours h left join analytics.topic_scores h2 on h2.scored_at = h.scored_at and h2.topic_slug = s.topic_slug
             order by h.scored_at) as series,
       (select min(scored_at) from hours) as series_start
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
    topics = rows(TOPICS + " order by s.rank, s.score desc, s.topic_slug limit :limit", limit=limit)
    return {"updated_at": updated_at(), "topics": [topic_view(r) for r in topics]}


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
