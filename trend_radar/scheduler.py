import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from trend_radar import ai, brief, config, maintenance, transform
from trend_radar.connectors import bluesky, rss, twitch, wikipedia, youtube

log = logging.getLogger("scheduler")

# max_instances=1 is the job lock: a slow run is never overlapped by the next one.
# misfire_grace_time=3600 + coalesce: a job that wakes late (laptop asleep, slow neighbour) still runs, once,
# instead of being skipped. Hourly jobs are never more than an hour behind their latest run time, so they always run.
JOB_DEFAULTS = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 3600}


def transform_cycle() -> None:
    """AI layer, then dbt. An AI failure (model, API, key) is logged in connector_runs and never blocks scoring."""
    for step in (ai.embed, ai.discover):
        try:
            step()
        except Exception:
            log.exception("%s failed; dbt build continues", step.__name__)
    transform.build()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    sched = BlockingScheduler(timezone="UTC", job_defaults=JOB_DEFAULTS)
    now = datetime.now(timezone.utc)
    if n := maintenance.abort_stale_runs(before=now):
        log.warning("marked %d run(s) left 'running' by the previous worker as aborted", n)

    # No keys needed: always on.
    sched.add_job(wikipedia.collect, "interval", hours=6, next_run_time=now)
    sched.add_job(rss.collect, "cron", minute=20, next_run_time=now)
    sched.add_job(maintenance.purge_raw, "cron", hour=3, minute=30)
    # Transform after every hourly ingestion job (:05 snapshot … :25 Bluesky). Also 3 min after start.
    sched.add_job(transform_cycle, "cron", minute=40, next_run_time=now + timedelta(minutes=3))
    sched.add_job(brief.build, "cron", hour=6, minute=50)  # Daily Brief from the 06:40 scores (P9.1)

    if config.YOUTUBE_API_KEY:
        sched.add_job(youtube.discover, "interval", hours=config.YOUTUBE_SEARCH_EVERY_HOURS, next_run_time=now)
        sched.add_job(youtube.snapshot, "cron", minute=5)
        # Also on start (after discovery): a sleeping Mac misses 06:15, and it costs ~6 units.
        sched.add_job(youtube.channels, "cron", hour=6, minute=15, next_run_time=now + timedelta(minutes=2))
    else:
        log.warning("YOUTUBE_API_KEY not set: YouTube jobs disabled")

    if config.TWITCH_CLIENT_ID and config.TWITCH_CLIENT_SECRET:
        sched.add_job(twitch.collect, "cron", minute=10, next_run_time=now)
    else:
        log.warning("TWITCH_CLIENT_ID/SECRET not set: Twitch jobs disabled")

    if config.BLUESKY_HANDLE and config.BLUESKY_APP_PASSWORD:
        sched.add_job(bluesky.collect, "cron", minute=25, next_run_time=now)
    else:
        log.warning("BLUESKY_HANDLE/APP_PASSWORD not set: Bluesky jobs disabled")

    sched.start()


if __name__ == "__main__":
    main()
