from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trend_radar import maintenance
from trend_radar.db import ConnectorRun, RawResponse, engine


def test_purge_raw_deletes_only_rows_past_retention():
    now = datetime.now(timezone.utc)
    with Session(engine) as s:
        s.add_all([RawResponse(source="youtube", endpoint="search", payload={}, fetched_at=now - timedelta(days=31)),
                   RawResponse(source="youtube", endpoint="search", payload={}, fetched_at=now - timedelta(days=29))])
        s.commit()

    maintenance.purge_raw()

    with Session(engine) as s:
        assert s.scalar(select(func.count()).select_from(RawResponse)) == 1
        run = s.scalars(select(ConnectorRun)).one()
        assert (run.source, run.job, run.status, run.items_count) == ("maintenance", "purge_raw", "ok", 1)


def test_abort_stale_runs_closes_only_runs_from_before_the_start():
    start = datetime.now(timezone.utc)
    with Session(engine) as s:
        s.add_all([ConnectorRun(source="dbt", job="build", status="running", started_at=start - timedelta(hours=5)),
                   ConnectorRun(source="rss", job="collect", status="ok", started_at=start - timedelta(hours=5)),
                   ConnectorRun(source="rss", job="collect", status="running", started_at=start + timedelta(seconds=1))])
        s.commit()

    assert maintenance.abort_stale_runs(before=start) == 1

    with Session(engine) as s:
        runs = {(r.source, r.status): r for r in s.scalars(select(ConnectorRun))}
    assert set(runs) == {("dbt", "aborted"), ("rss", "ok"), ("rss", "running")}
    assert runs["dbt", "aborted"].finished_at and runs["dbt", "aborted"].error == "worker restarted mid-run"
