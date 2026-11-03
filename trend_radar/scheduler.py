import logging
from datetime import datetime, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from trend_radar import config
from trend_radar.connectors import twitch, wikipedia, youtube

log = logging.getLogger("scheduler")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    # max_instances=1 is the job lock: a slow run is never overlapped by the next one.
    sched = BlockingScheduler(
        timezone="UTC", job_defaults={"max_instances": 1, "coalesce": True, "misfire_grace_time": 600}
    )
    now = datetime.now(timezone.utc)

    sched.add_job(wikipedia.collect, "interval", hours=6, next_run_time=now)

    if config.YOUTUBE_API_KEY:
        sched.add_job(youtube.discover, "interval", hours=config.YOUTUBE_SEARCH_EVERY_HOURS, next_run_time=now)
        sched.add_job(youtube.snapshot, "cron", minute=5)
        sched.add_job(youtube.channels, "cron", hour=6, minute=15)
    else:
        log.warning("YOUTUBE_API_KEY not set: YouTube jobs disabled")

    if config.TWITCH_CLIENT_ID and config.TWITCH_CLIENT_SECRET:
        sched.add_job(twitch.collect, "cron", minute=10, next_run_time=now)
    else:
        log.warning("TWITCH_CLIENT_ID/SECRET not set: Twitch jobs disabled")

    sched.start()


if __name__ == "__main__":
    main()
