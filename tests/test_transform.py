"""Runs the real dbt project against the test database (slow-ish: ~5 s per build)."""

from datetime import datetime, timezone

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
