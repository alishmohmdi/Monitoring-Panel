from database.models import (
    Notification,
    Task,
)

from services.business_hours import (
    is_business_time,
    utc_now_naive,
)


def release_queued_tasks(db) -> int:
    """
    Release all QUEUED tasks when company business hours begin.

    Rules:

    Outside business hours:
        QUEUED stays QUEUED.
        No notification is created.

    During business hours:
        QUEUED -> NEW
        released_at = now

        A notification record is created
        for the assigned counter.

    Important:
        The 2-hour SLA timer DOES NOT start here.

        Timer starts only when the counter
        opens the task through:

        POST /panel/tasks/{task_id}/open
    """

    # =========================================================
    # BUSINESS HOURS CHECK
    # =========================================================

    if not is_business_time():

        return 0


    # =========================================================
    # FIND QUEUED TASKS
    # =========================================================

    queued_tasks = (
        db.query(Task)
        .filter(
            Task.status == "QUEUED"
        )
        .order_by(
            Task.created_at.asc()
        )
        .all()
    )


    if not queued_tasks:

        return 0


    now = utc_now_naive()

    released_count = 0


    # =========================================================
    # RELEASE TASKS
    # =========================================================

    for task in queued_tasks:

        # -----------------------------------------------------
        # CHANGE STATUS
        # -----------------------------------------------------

        task.status = "NEW"

        task.released_at = now


        # -----------------------------------------------------
        # PREVENT DUPLICATE NOTIFICATION
        # -----------------------------------------------------

        existing_notification = (
            db.query(Notification)
            .filter(
                Notification.task_id
                == task.id,

                Notification.counter_id
                == task.counter_id,

                Notification.channel
                == "telegram",
            )
            .first()
        )


        # -----------------------------------------------------
        # CREATE NOTIFICATION
        # -----------------------------------------------------

        if not existing_notification:

            notification = Notification(
                agency_id=task.agency_id,

                task_id=task.id,

                counter_id=task.counter_id,

                channel="telegram",

                status="pending",

                message=None,

                sent_at=None,

                created_at=now,
            )

            db.add(
                notification
            )


        released_count += 1


        print(
            f"🔔 Task {task.id} released "
            f"→ Counter {task.counter_id} "
            f"→ status=NEW"
        )


    # =========================================================
    # SAVE
    # =========================================================

    db.commit()


    print(
        f"✅ Released queued tasks: "
        f"{released_count}"
    )


    return released_count