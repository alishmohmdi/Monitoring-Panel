from database.models import (
    AgencyRoute,
    Assignment,
    Change,
    Notification,
    Task,
)

from services.business_hours import (
    is_business_time,
    utc_now_naive,
)


def create_change_with_task(
    db,
    *,
    route_id: int,
    package_id: int | None,
    change_type: str,
    package_name: str | None = None,
    hotel_name: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
    old_price: float | None = None,
    new_price: float | None = None,
):
    """
    Create one global Change record and then create
    separate Tasks for every agency subscribed to the route.

    Business-hours behavior:

    - During working hours:
        Task -> NEW
        released_at -> now
        Notification -> created immediately

    - Outside working hours:
        Task -> QUEUED
        released_at -> None
        Notification -> not created

    The task timer does NOT start here.
    It starts only when the counter opens the task.
    """

    # =========================================================
    # CURRENT TIME / BUSINESS HOURS
    # =========================================================

    now = utc_now_naive()

    inside_business_hours = (
        is_business_time()
    )

    # =========================================================
    # CREATE GLOBAL CHANGE
    # =========================================================

    change = Change(
        route_id=route_id,
        package_id=package_id,

        hotel_name=hotel_name,
        package_name=package_name,

        change_type=change_type,

        old_value=old_value,
        new_value=new_value,

        old_price=old_price,
        new_price=new_price,

        detected_at=now,
    )

    db.add(change)

    # We need the Change ID
    # before creating Tasks.
    db.flush()

    # =========================================================
    # FIND AGENCIES SUBSCRIBED TO THIS ROUTE
    # =========================================================

    agency_routes = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.route_id == route_id,
            AgencyRoute.is_active == True,
        )
        .all()
    )

    if not agency_routes:
        print(
            f"⚠️ No agency subscribed to Route {route_id}"
        )

        return change

    # =========================================================
    # CREATE TASK FOR EVERY AGENCY
    # =========================================================

    created_tasks = 0

    for agency_route in agency_routes:

        agency_id = (
            agency_route.agency_id
        )

        # -----------------------------------------------------
        # FIND COUNTER RESPONSIBLE FOR THIS ROUTE
        # -----------------------------------------------------

        assignment = (
            db.query(Assignment)
            .filter(
                Assignment.agency_id == agency_id,
                Assignment.route_id == route_id,
            )
            .first()
        )

        if not assignment:
            print(
                "⚠️ No Counter assignment "
                f"for Agency {agency_id}, "
                f"Route {route_id}"
            )

            continue

        # -----------------------------------------------------
        # TASK STATUS
        # -----------------------------------------------------

        if inside_business_hours:
            task_status = "NEW"
            released_at = now

        else:
            task_status = "QUEUED"
            released_at = None

        # -----------------------------------------------------
        # CREATE TASK
        # -----------------------------------------------------

        task = Task(
            agency_id=agency_id,

            change_id=change.id,

            counter_id=(
                assignment.counter_id
            ),

            status=task_status,

            created_at=now,

            released_at=released_at,

            # Timer has NOT started yet.
            opened_at=None,
            started_at=None,
            deadline=None,

            completed_at=None,
        )

        db.add(task)

        # We need task.id for Notification.
        db.flush()

        created_tasks += 1

        # -----------------------------------------------------
        # NOTIFICATION
        # -----------------------------------------------------
        #
        # During business hours:
        # create notification immediately.
        #
        # Outside business hours:
        # do NOT create notification.
        # task_release_service will create it
        # when the task is released at working time.
        #

        if inside_business_hours:

            notification = Notification(
                agency_id=agency_id,

                task_id=task.id,

                counter_id=(
                    assignment.counter_id
                ),

                channel="telegram",

                status="pending",

                message=None,

                sent_at=None,

                created_at=now,
            )

            db.add(notification)

            print(
                f"🔔 Task {task.id} created "
                f"for Agency {agency_id} "
                f"→ Counter {assignment.counter_id} "
                f"→ status=NEW"
            )

        else:

            print(
                f"🌙 Task {task.id} queued "
                f"for Agency {agency_id} "
                f"→ Counter {assignment.counter_id} "
                f"→ status=QUEUED"
            )

    # =========================================================
    # DEBUG INFO
    # =========================================================

    print(
        f"✅ Change {change.id} created "
        f"for Route {route_id}"
    )

    print(
        f"✅ Tasks created: {created_tasks}"
    )

    print(
        "🕒 Business hours:",
        inside_business_hours,
    )

    return change