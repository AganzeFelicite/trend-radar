import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from trend_radar import config
from trend_radar.connectors import youtube


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not config.YOUTUBE_API_KEY:
        raise SystemExit("YOUTUBE_API_KEY is not set")

    # max_instances=1 is the job lock: a slow run is never overlapped by the next one.
    sched = BlockingScheduler(
        timezone="UTC", job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 600}
    )
    now = datetime.now(timezone.utc)
    sched.add_job(youtube.discover, "interval", hours=config.YOUTUBE_SEARCH_EVERY_HOURS, next_run_time=now)
    sched.add_job(youtube.snapshot, "cron", minute=5)
    sched.start()


if __name__ == "__main__":
    main()
