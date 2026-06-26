from apscheduler.schedulers.background import BackgroundScheduler
from fetch_github import store_all_data
import time


def start_scheduler(username, interval_hours=6):
    """
    Runs store_all_data every N hours in background.
    So your dashboard always shows fresh data.

    BackgroundScheduler = non-blocking, runs in separate thread.
    """
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        func=store_all_data,
        args=[username],
        trigger="interval",
        hours=interval_hours,
        id="github_refresh"
    )

    scheduler.start()
    print(f"Scheduler started — refreshing every {interval_hours}h")
    return scheduler
