import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from trend_radar.scheduler import JOB_DEFAULTS


def late_job_runs(job_defaults: dict, late: timedelta) -> bool:
    """A job whose run time passed `late` ago while the process was frozen (a sleeping Mac): does it still run?"""
    ran = threading.Event()
    sched = BackgroundScheduler(timezone="UTC", job_defaults=job_defaults)
    sched.add_job(ran.set, "interval", hours=1, next_run_time=datetime.now(timezone.utc) - late)
    sched.start()
    try:
        return ran.wait(3)
    finally:
        sched.shutdown()


def test_job_woken_21_minutes_late_still_runs():
    assert not late_job_runs({**JOB_DEFAULTS, "misfire_grace_time": 600}, timedelta(minutes=21))  # the Nov 4 07:05 skip
    assert late_job_runs(JOB_DEFAULTS, timedelta(minutes=21))
    assert late_job_runs(JOB_DEFAULTS, timedelta(minutes=59))
