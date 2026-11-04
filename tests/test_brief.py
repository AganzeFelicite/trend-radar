from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api import client, marts

from trend_radar import brief
from trend_radar.db import DailyBrief, engine


def test_brief_holds_only_verified_public_facts_and_versions_per_day():
    marts()  # hand-made marts: preload (top 5, 3 sources), map (1 source, below top 5), meme (off-topic)

    brief.build()
    brief.build()  # same day again: a new draft version, the first one is kept

    with Session(engine) as s:
        rows = s.scalars(select(DailyBrief).order_by(DailyBrief.version)).all()
    assert [(r.version, r.status) for r in rows] == [(1, "draft"), (2, "draft")]
    b = brief.Brief.model_validate(rows[-1].json)  # stored JSON round-trips through the schema
    assert [t.slug for t in b.top5] == ["preload"]  # map has one source, meme is off-topic
    assert (b.top5[0].score, b.top5[0].sources, b.top5[0].growth) == (80, 3, 1.6)
    assert b.biggest_riser is None  # map climbed 3 → 2 but on one source: same trust rule as the top 5
    assert [t.slug for t in b.off_topic] == ["meme"]
    assert [v.title for v in b.breakout_videos] == ["Pre-load guide", "Map tour"]
    assert b.make_this_now.slug == "preload"  # growing 1.6x on 3 sources; map: growth not measurable, one source
    assert b.scores_at == datetime(2026, 11, 4, 5, tzinfo=timezone.utc)
    assert any("youtube: no successful run yet" in n for n in b.notes)

    latest = client.get("/api/admin/brief").json()
    assert (latest["version"], latest["json"]["top5"][0]["name"]) == (2, "Pre-load")
