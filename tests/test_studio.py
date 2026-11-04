"""Content Package rules from the Nov 4 review. Pure tests build a Brief by hand; the last one goes through the API."""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session
from test_api import client, marts

from trend_radar import brief, config, studio
from trend_radar.brief import Brief, Evidence, Lead, TopicFact
from trend_radar.db import PublishedVideo, engine


def topic(slug, rank, rank_6h_ago=None, score=50.0, items=20, sources=3):
    return TopicFact(slug=slug, name=slug.title(), rank=rank, rank_6h_ago=rank_6h_ago, score=score, share=0.1,
                     growth=None, sources=sources, items=items, channels=10)


def make(top, items=None, riser=None, leads=None):
    items = items or {}
    return Brief(date=date(2026, 11, 4), generated_at=datetime(2026, 11, 4, 7, tzinfo=timezone.utc),
                 scores_at=datetime(2026, 11, 4, 6, tzinfo=timezone.utc), window_hours=24, top5=top,
                 biggest_riser=riser, make_this_now=None, breakout_videos=[], off_topic=[], freshness=[], notes=[],
                 evidence={t.slug: Evidence(items=items.get(t.slug, []), videos=(leads or {}).get(t.slug, []))
                           for t in top + ([riser] if riser else [])})


def test_topics_sharing_most_items_merge_into_one_segment_and_the_next_distinct_topic_fills_in():
    a, b, c, d, e, f = (topic(s, i) for i, s in enumerate("abcdef", 1))
    items = {"a": ["1", "2", "3", "4"], "b": ["1", "2", "3", "9"],  # 3 of 4 shared (75%): merged
             "c": ["5", "6"], "d": ["1", "2", "4"],  # d overlaps a, but a's segment is full: dropped
             "e": ["7", "8"], "f": ["10"]}  # e is the next distinct topic; f doesn't fit
    p = studio.package(make([a, b, c, d, e, f], items), None, 1, "draft")
    assert [s.label for s in p.segments] == ["A & B", "C", "E"]
    assert studio.overlap({"1", "2"}, {"2", "3"}) == 0.5  # exactly half is not "more than half"


def test_riser_takes_the_last_slot_and_movement_none_means_still_leading():
    top = [topic("a", 1, 1), topic("b", 2, 2), topic("c", 3, 3)]
    p = studio.package(make(top, riser=topic("r", 9, 15)), None, 1, "draft")
    assert [(s.label, s.kind) for s in p.segments] == [("A", "top"), ("B", "top"), ("R", "riser")]
    assert p.movement == "none" and p.segments[0].topics[0].movement == "unchanged in 6 hours (still #1)"
    assert p.segments[2].topics[0].movement == "up 6 places in 6 hours (#15 → #9)"
    moved = studio.package(make([topic("a", 1, 2), topic("b", 2, 1)]), None, 1, "draft")
    assert moved.movement == "some" and moved.segments[0].topics[0].movement == "up 1 place in 6 hours (#2 → #1)"


def test_riser_needs_15_items_score_10_and_3_places():
    ok = dict(slug="r", rank=5, rank_6h_ago=8, score=10.0, items=15, sources=2)
    assert brief.pick_riser([topic(**ok)]).slug == "r"
    for change in ({"items": 14}, {"score": 9.9}, {"rank_6h_ago": 7}, {"sources": 1}):
        assert brief.pick_riser([topic(**(ok | change))]) is None, change
    assert (config.RISER_MIN_ITEMS, config.RISER_MIN_SCORE, config.RISER_MIN_GAIN) == (15, 10, 3)


def test_research_list_drops_piracy_and_jailbreak_items_and_finds_official_links():
    leads = {"a": [Lead(title="PS5 Jailbreak for GTA 6", url="u1", by="x", metric="m"),
                   Lead(title="Pre-load guide", url="u2", by="y", metric="m",
                        links=["https://www.rockstargames.com/newswire/art…", "https://www.ign.com/articles/x"])]}
    p = studio.package(make([topic("a", 1)], leads=leads), None, 1, "draft")
    assert [x.title for x in p.segments[0].leads] == ["Pre-load guide"]
    assert [(o.url, o.truncated) for o in p.official_sources_in_our_data] == [("https://www.rockstargames.com/newswire/art", True)]


def test_metadata_host_length_and_scenes():
    p = studio.package(make([topic("a", 1), topic("b", 2)]), None, 3, "draft", ["Old title"])
    assert (p.package_id, p.format, p.language, p.host, p.target_length_seconds) == (
        "2026-11-04-daily_radar-en-v3", "daily_radar", "en", "Wi-Fido", 40)
    assert [c.file for c in p.cards] == ["cards/title.png", "cards/segment-1.png", "cards/segment-2.png", "cards/end.png"]
    assert p.scenes[0].start == 0 and p.scenes[-1].end == 40 and len(p.scenes) == 4  # hook, 2 segments, close
    assert all(x.type == "verified" for x in p.facts) and p.previous_titles == ["Old title"]
    md = studio.markdown(p)
    assert "RADAR" not in md and "| host | Wi-Fido" in md and "commentThreads.list" in md


def test_sensitive_topics_never_reach_a_package():
    assert not studio.allowed(topic("mark-tilbury-savings", 1).model_copy(update={"name": "Mark Tilbury Savings"}))
    assert not studio.allowed(topic("x", 1).model_copy(update={"name": "Crypto Investing"}))
    assert studio.allowed(topic("preload", 1))


def test_api_serves_the_package_with_the_last_published_titles():
    marts()
    brief.build()
    with Session(engine) as s:
        s.add_all([PublishedVideo(platform="youtube", title=f"Video {i}") for i in range(9)])
        s.commit()

    p = client.get("/api/admin/content-package").json()

    assert len(p["previous_titles"]) == 7 and p["host"] == "Wi-Fido"
    assert p["segments"][0]["label"] == "Pre-load" and p["facts"][0]["source"].startswith("Trend Radar topic_scores · preload")
    assert "| package_id | `2026-11-04-daily_radar-en-v1` |" in client.get("/api/admin/studio-prompt").text
