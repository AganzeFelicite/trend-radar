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
