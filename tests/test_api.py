"""API over hand-made marts (what dbt leaves in analytics.*), so these run in milliseconds."""

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from trend_radar import api
from trend_radar.db import Waitlist, engine

client = TestClient(api.app)


def marts():
    with engine.begin() as c:
        c.execute(text("""
            create schema analytics;
            create table analytics.topics as
              select * from (values ('preload', 'Pre-load', 'curated'), ('map', 'Map', 'curated'),
                                    ('quiet', 'Quiet', 'curated')) v(topic_slug, topic_name, origin);
            create table analytics.topic_scores as
              select * from (values
                ('2026-11-03 23:00+00'::timestamptz, 'map', 10.0, 3, 0.02, null::float, 1.0, 5, 5, 1, false, false, false),
                ('2026-11-04 04:00+00', 'preload', 100.0, 1, 0.20, null, 1.0, 50, 40, 3, false, false, false),
                ('2026-11-04 05:00+00', 'preload', 80.0, 1, 0.16, 0.10, 1.6, 45, 38, 3, false, true, false),
                ('2026-11-04 05:00+00', 'map', 30.0, 2, 0.06, null, 1.0, 12, 10, 2, true, false, false))
              v(scored_at, topic_slug, score, rank, attention, prev_attention, growth, items, channels, sources,
                is_new, is_spiking, is_confirmed);
            create table analytics.rising_items as
              select * from (values
                ('youtube', 'v1', 'Pre-load guide', 'https://y/v1', 'Small', 50000, 2000.0, 2000, 25000.0, '{preload}'::text[], now()),
                ('youtube', 'v2', 'Map tour', 'https://y/v2', 'Big', 90000, 4000.0, 5000000, 18.0, '{map}', now()),
                ('youtube', 'v3', 'Huge, subs unknown', 'https://y/v3', '?', 99000, 9000.0, null, 99000.0, '{}', now()),
                ('rss', 'n1', 'Pre-load starts Nov 10', 'https://n/1', 'IGN', 1, 1.0, null, null, '{preload}', now()),
                ('bluesky', 'p1', 'Pre-loading now', 'https://b/1', 'fan.bsky.social', 40, 2.0, null, null, '{preload}', now()))
              v(source, item_id, title, url, channel_title, activity_24h, per_hour, subscribers, per_1k_subs, topics, seen_at);
            create table analytics.topic_items as
              select * from (values ('preload', 'alias', 'pre load', now()), ('preload', 'alias', 'pre load', now()),
                                    ('preload', 'alias', 'november 10', now()), ('preload', 'semantic', null, now()))
              v(topic_slug, match_type, matched_alias, seen_at);
            insert into connector_runs (source, job, status, items_count, quota_used, finished_at)
              values ('dbt', 'build', 'ok', 38, 0, '2026-11-04 05:41+00');
        """))


def test_top_topics_topic_page_and_rising_videos():
    marts()

    top = client.get("/api/topics/top").json()
    assert top["updated_at"].startswith("2026-11-04T05:41")
    preload, map_ = top["topics"]
    assert (preload["name"], preload["score"], preload["growth"], preload["is_spiking"]) == ("Pre-load", 80, 1.6, True)
    assert preload["series"] == [0, 100, 80] and map_["series"] == [10, 0, 30]  # hours with no activity read 0
    assert (map_["rank_6h_ago"], preload["rank_6h_ago"]) == (3, None)  # map climbed 3 → 2; preload unranked then
    assert top["stats"] == {"items_24h": 5, "sources": 3, "topics": 3}
    assert map_["growth"] is None  # no previous window yet: growth not measurable, not "1×"
    assert client.get("/api/topics/top?limit=11").status_code == 422

    page = client.get("/api/topics/preload").json()
    assert [v["item_id"] for v in page["videos"]] == ["v1"]
    assert page["videos"][0]["topics"] == [{"slug": "preload", "name": "Pre-load"}]
    assert [n["outlet"] for n in page["news"]] == ["IGN"]
    assert [(p["author"], p["engagement_24h"]) for p in page["posts"]] == [("fan.bsky.social", 40)]
    assert page["keywords"] == [{"keyword": "pre load", "items": 2}, {"keyword": "november 10", "items": 1}]
    assert client.get("/api/topics/quiet").json()["topic"]["score"] == 0  # known topic, no activity this hour
    assert client.get("/api/topics/nope").status_code == 404

    rising = client.get("/api/videos/rising").json()["videos"]
    assert [v["item_id"] for v in rising] == ["v1", "v2"]  # small channel first; unknown subscriber count left out


def test_waitlist_validates_dedupes_and_rate_limits():
    api._recent.clear()

    assert client.post("/api/waitlist", json={"email": "not-an-email"}).status_code == 422
    assert client.post("/api/waitlist", json={"email": " Fan@Example.com "}).status_code == 201
    assert client.post("/api/waitlist", json={"email": "fan@example.com"}).status_code == 201  # same answer twice
    for i in range(3):  # 5 accepted in the hour
        client.post("/api/waitlist", json={"email": f"other{i}@example.com"})
    assert client.post("/api/waitlist", json={"email": "sixth@example.com"}).status_code == 429

    with Session(engine) as s:
        assert set(s.scalars(select(Waitlist.email))) == {"fan@example.com"} | {f"other{i}@example.com" for i in range(3)}
