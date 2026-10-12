import asyncio
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler

from scraper.monitor_engine import scan_all_routes


scheduler = BlockingScheduler(
    timezone="Europe/Berlin"
)


def run_monitor():

    print()
    print("=" * 80)
    print("⏰ SCHEDULED SCAN")
    print("=" * 80)
    print(
        f"Started: {datetime.now()}"
    )

    try:

        asyncio.run(
            scan_all_routes()
        )

    except Exception as exc:

        print()
        print("❌ Scheduled scan failed")
        print(exc)


scheduler.add_job(
    run_monitor,

    trigger="interval",

    minutes=30,

    id="aryak_full_monitor",

    replace_existing=True,

    max_instances=1,

    coalesce=True,
)


if __name__ == "__main__":

    print()
    print("#" * 80)
    print("ARYAK TOUR MONITOR SCHEDULER")
    print("#" * 80)

    print()
    print("✅ Scheduler started")
    print("⏱ Scan interval: 30 minutes")
    print("🛑 Press CTRL+C to stop")

    
    run_monitor()

    try:

        scheduler.start()

    except KeyboardInterrupt:

        print()
        print("🛑 Scheduler stopped")