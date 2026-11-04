"""Runs the real dbt project against the test database (slow-ish: ~5 s per build)."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from trend_radar import transform
from trend_radar.connectors.common import upsert_items, upsert_signals
from trend_radar.db import ConnectorRun, engine


def at(day, hour):
    return datetime(2026, 11, day, hour, tzinfo=timezone.utc)


def seed(signals):
    with Session(engine) as s:
        upsert_items(s, [dict(source="youtube", item_id="v1", item_type="video", title="GTA 6 map", url="https://y/v1")])
        upsert_signals(s, [dict(source="youtube", item_id="v1", metric_name=m, metric_value=v, captured_at=t)
                           for m, v, t in signals])
        s.commit()


@pytest.fixture(autouse=True)
def test_db(monkeypatch, tmp_path):
    monkeypatch.setenv("DBT_DBNAME", "trend_radar_test")
    monkeypatch.setenv("DBT_TARGET_PATH", str(tmp_path / "target"))
    monkeypatch.setenv("DBT_LOG_PATH", str(tmp_path / "logs"))


def test_build_computes_hourly_deltas_across_gaps_and_logs_the_run():
    seed([("views", 100, at(3, 15)), ("views", 160, at(3, 16)), ("views", 460, at(3, 21))])  # 5 h gap

    transform.build()

    with engine.connect() as c:
        rows = c.execute(text("select metric_value, delta, hours_since_prev, delta_per_hour, kind "
                              "from analytics.int_signal_deltas order by captured_at")).all()
    assert [(r[0], r[1], r[3]) for r in rows] == [(100, None, None), (160, 60, 60), (460, 300, 60)]
    assert rows[2].hours_since_prev == 5 and rows[0].kind == "cumulative"
    with Session(engine) as s:
        run = s.scalars(select(ConnectorRun)).one()
        # Fixture data is days old, so freshness flags the sources: partial, not error.
        assert (run.source, run.job, run.status) == ("dbt", "build", "partial") and "stale" in run.error


def test_metric_missing_from_catalog_fails_the_build():
    seed([("dislikes", 3, at(3, 15))])  # a connector wrote a metric nobody defined

    with pytest.raises(RuntimeError, match="not_null_stg_signals_kind"):
        transform.build()

    with Session(engine) as s:
        assert s.scalars(select(ConnectorRun.status)).one() == "error"


def test_topics_normalise_gta_names_match_aliases_and_surface_phrases_from_3_authors():
    now = datetime.now(timezone.utc)
    items = [
        ("y1", "c1", "GTA6 PRELOAD starts November 10!"),          # → preload ("gta6" normalised)
        ("y2", "c2", "Grand Theft Auto VI map size revealed"),     # → map (longest alias "map size")
        ("y3", "c3", "GTA V vs GTA 6: what changed?"),             # → gta-5, not gta 6
        ("y4", "c4", "成功撤离#GTA6"),                               # not English, no topic
        *[(f"b{i}", f"a{i}", f"The black friday deals before launch #{i}") for i in range(3)],  # 3 authors
        *[(f"s{i}", f"z{i}", f"What is the secret ending in it {i}") for i in range(2)],        # only 2 authors
    ]
    with Session(engine) as s:
        upsert_items(s, [dict(source="youtube", item_id=i, item_type="video", title=t, url=f"https://y/{i}",
                              channel_id=c, published_at=now) for i, c, t in items])
        s.commit()

    transform.build()

    with engine.connect() as c:
        topics = dict(c.execute(text("select item_id, string_agg(topic_slug, ',' order by topic_slug) "
                                     "from analytics.topic_items group by 1")).all())
        english = dict(c.execute(text("select item_id, is_english from analytics.int_item_text")).all())
        phrases = dict(c.execute(text("select phrase, channels from analytics.phrase_candidates")).all())
    assert topics == {"y1": "preload", "y2": "map", "y3": "gta-5"}
    assert english["y3"] is True and english["y4"] is False
    assert phrases.get("black friday") == 3 and "secret ending" not in phrases


def test_scores_rank_size_times_growth_flag_spikes_and_new_topics_and_drop_spam():
    H = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hrs = [H - timedelta(hours=h) for h in (47, 24, 12, 1)]  # prev window ends at H-24; burst = last 3h
    videos = {  # item: (channel, title, views at each reading)
        "p": ("c1", "GTA 6 preload time", [1000, 11000, 21000, 21000]),  # steady: 10k prev, 10k now
        "m1": ("c2", "GTA 6 map size", [0, 1000, 1000, 4000]),           # map: 1k prev → 9k now, all in last 3h
        "m2": ("c3", "GTA 6 map compared", [0, 0, 0, 3000]),
        "m3": ("c4", "The GTA 6 map again", [0, 0, 0, 3000]),
        "o": ("c5", "GTA 6 random stuff", [0, 9000, 10000, 10000]),      # no topic, still in the total
        "s": ("c6", "GTA 6 map shorts", [0, 0, 0, 100000]),              # 100k views, 1 comment: spam
        **{f"n{i}": (f"d{i}", f"GTA 6 trailer 3 hype {i}", [0, 0, 100, 100]) for i in range(3)},  # first seen now
    }
    with Session(engine) as s:
        upsert_items(s, [dict(source="youtube", item_id=i, item_type="video", title=t, url=f"https://y/{i}",
                              channel_id=c, published_at=H - timedelta(days=4)) for i, (c, t, _) in videos.items()])
        upsert_signals(s, [dict(source="youtube", item_id=i, metric_name="views", metric_value=v, captured_at=t)
                           for i, (_, _, vs) in videos.items() for v, t in zip(vs, hrs)]
                       + [dict(source="youtube", item_id="s", metric_name="comments", metric_value=1, captured_at=hrs[-1])])
        s.add(ConnectorRun(source="youtube", job="snapshot", status="ok", started_at=H - timedelta(hours=50)))
        s.commit()

    transform.build()

    with engine.connect() as c:
        latest = {r.topic_slug: r for r in c.execute(text(
            "select * from analytics.topic_scores where scored_at = (select max(scored_at) from analytics.topic_scores)"))}
        map_3h_ago = c.execute(text("select growth from analytics.topic_scores where topic_slug = 'map' "
                                    "and scored_at = :t"), {"t": H - timedelta(hours=3)}).scalar()
        spam = c.execute(text("select spam_reason from analytics.int_item_quality where item_id = 's'")).scalar()
    assert spam == "low_engagement"
    assert [t for t, r in sorted(latest.items(), key=lambda kv: kv[1].rank)][:2] == ["map", "preload"]
    m, p = latest["map"], latest["preload"]
    assert m.growth == 4 and m.is_spiking and not m.is_new        # 5% → 44% of views: capped growth
    assert abs(p.growth - 1) < 0.05 and not p.is_spiking            # same share both days
    assert latest["trailer-3"].is_new and not latest["preload"].is_new
    assert map_3h_ago == 1  # that hour's prev window opened before collection started: no growth claimed
