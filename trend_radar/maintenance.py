"""Housekeeping jobs. Logged in connector_runs like every other job (source = "maintenance")."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, update

from trend_radar import config
from trend_radar.db import ConnectorRun, RawResponse, connector_run, engine


def purge_raw() -> None:
    """Bronze TTL: delete raw API responses older than RAW_RETENTION_DAYS. Silver is untouched."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=config.RAW_RETENTION_DAYS)
    with connector_run("maintenance", "purge_raw") as (s, run):
        run.items_count = s.execute(delete(RawResponse).where(RawResponse.fetched_at < cutoff)).rowcount
        s.commit()


def abort_stale_runs(before: datetime) -> int:
    """Worker start: a run still 'running' from before now was cut off by a restart (there is one worker)."""
    with engine.begin() as c:
        return c.execute(update(ConnectorRun)
                         .where(ConnectorRun.status == "running", ConnectorRun.started_at < before)
                         .values(status="aborted", finished_at=func.now(),
                                 error=func.coalesce(ConnectorRun.error, "worker restarted mid-run"))).rowcount
