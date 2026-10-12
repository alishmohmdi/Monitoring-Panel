import time
import traceback

from database.db import (
    SessionLocal,
)

from services.business_hours import (
    is_business_time,
    tehran_now,
)

from services.task_release_service import (
    release_queued_tasks,
)


# =========================================================
# CONFIG
# =========================================================

CHECK_INTERVAL_SECONDS = 30


# =========================================================
# RELEASE CHECK
# =========================================================

def run_release_check():
    """
    Run one QUEUED-task release check.

    This function:

    1. Opens a database session.
    2. Checks company working hours.
    3. Releases QUEUED tasks if appropriate.
    4. Safely closes the database session.
    """

    db = SessionLocal()

    try:

        now = tehran_now()

        print(
            "\n"
            "--------------------------------------------------"
        )

        print(
            "🕒 Tehran time:",
            now.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        )


        # -----------------------------------------------------
        # OUTSIDE BUSINESS HOURS
        # -----------------------------------------------------

        if not is_business_time(
            now
        ):

            print(
                "🌙 Outside business hours "
                "(10:00 - 17:00)"
            )

            print(
                "Queued tasks remain queued."
            )

            return


        # -----------------------------------------------------
        # BUSINESS HOURS
        # -----------------------------------------------------

        print(
            "☀️ Business hours active"
        )


        released = (
            release_queued_tasks(
                db
            )
        )


        if released == 0:

            print(
                "✅ No queued tasks "
                "waiting for release."
            )

        else:

            print(
                f"🚀 {released} task(s) "
                "released."
            )


    except Exception as exc:

        db.rollback()

        print(
            "❌ Business-hours "
            "scheduler error:"
        )

        print(
            str(exc)
        )

        traceback.print_exc()


    finally:

        db.close()


# =========================================================
# MAIN WORKER
# =========================================================

def main():

    print(
        "=" * 60
    )

    print(
        "ARYAK BUSINESS HOURS SCHEDULER"
    )

    print(
        "=" * 60
    )

    print(
        "✅ Scheduler started"
    )

    print(
        "🕙 Working hours: "
        "10:00 - 17:00 Tehran"
    )

    print(
        "🔄 Check interval:",
        CHECK_INTERVAL_SECONDS,
        "seconds",
    )

    print(
        "🌙 Changes outside working hours "
        "stay QUEUED"
    )

    print(
        "☀️ QUEUED tasks are released "
        "during working hours"
    )

    print(
        "⏱ SLA timer starts only "
        "when Counter opens Task"
    )


    try:

        while True:

            run_release_check()

            time.sleep(
                CHECK_INTERVAL_SECONDS
            )


    except KeyboardInterrupt:

        print(
            "\n"
            "🛑 Business Hours Scheduler stopped."
        )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    main()