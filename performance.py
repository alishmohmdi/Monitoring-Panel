from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from database.db import get_db

from database.models import (
    Assignment,
    Counter,
    Task,
    User,
)

from services.auth_dependency import (
    get_current_user,
)

from services.business_hours import (
    BUSINESS_TIMEZONE,
    remaining_business_seconds,
)


router = APIRouter(
    prefix="/performance",
    tags=["Performance"],
)


# =========================================================
# ACCESS
# =========================================================

def require_management(
    current_user: User = Depends(
        get_current_user
    ),
):
    if current_user.role not in {
        "SUPER_ADMIN",
        "AGENCY_ADMIN",
    }:
        raise HTTPException(
            status_code=403,
            detail="Management access required",
        )

    return current_user


# =========================================================
# TIME HELPERS
# =========================================================

def tehran_today_utc_range():
    """
    Returns start/end of current Tehran day
    converted to naive UTC datetimes.

    Database currently stores naive UTC.
    """

    now_tehran = datetime.now(
        BUSINESS_TIMEZONE
    )

    start_tehran = now_tehran.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    end_tehran = (
        start_tehran
        + timedelta(days=1)
    )

    start_utc = (
        start_tehran
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    end_utc = (
        end_tehran
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )

    return (
        start_utc,
        end_utc,
    )


def format_minutes(
    seconds: float | int | None,
):
    if seconds is None:
        return None

    return round(
        seconds / 60,
        1,
    )


# =========================================================
# DAILY PERFORMANCE
# =========================================================

@router.get("/today")
def today_performance(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_management
    ),
):
    start_utc, end_utc = (
        tehran_today_utc_range()
    )

    # -----------------------------------------------------
    # AGENCY SCOPE
    # -----------------------------------------------------

    counters_query = db.query(
        Counter
    )

    if (
        current_user.role
        == "AGENCY_ADMIN"
    ):
        counters_query = (
            counters_query
            .filter(
                Counter.agency_id
                == current_user.agency_id
            )
        )

    elif (
        current_user.role
        == "SUPER_ADMIN"
        and current_user.agency_id
        is not None
    ):
        # For Aryak's own Super Admin this keeps
        # the report focused on their agency
        # if agency_id is set.
        counters_query = (
            counters_query
            .filter(
                Counter.agency_id
                == current_user.agency_id
            )
        )

    counters = (
        counters_query
        .order_by(
            Counter.name.asc()
        )
        .all()
    )

    result = []

    # =====================================================
    # COUNTER LOOP
    # =====================================================

    for counter in counters:

        user = (
            db.query(User)
            .filter(
                User.counter_id
                == counter.id
            )
            .first()
        )

        # -------------------------------------------------
        # TASKS RELEASED / CREATED TODAY
        # -------------------------------------------------

        tasks = (
            db.query(Task)
            .filter(
                Task.counter_id
                == counter.id,

                Task.created_at
                >= start_utc,

                Task.created_at
                < end_utc,
            )
            .order_by(
                Task.created_at.desc()
            )
            .all()
        )

        # -------------------------------------------------
        # NORMALIZE EXPIRED PENDING TASKS
        # -------------------------------------------------

        changed = False

        for task in tasks:

            if (
                task.status == "PENDING"
                and task.deadline
            ):
                remaining = (
                    remaining_business_seconds(
                        task.deadline
                    )
                )

                if remaining == 0:
                    task.status = "LATE"
                    changed = True

        if changed:
            db.commit()

        # -------------------------------------------------
        # COUNTS
        # -------------------------------------------------

        total_tasks = len(
            tasks
        )

        new_count = len([
            task
            for task in tasks
            if task.status == "NEW"
        ])

        pending_count = len([
            task
            for task in tasks
            if task.status == "PENDING"
        ])

        done_tasks = [
            task
            for task in tasks
            if task.status == "DONE"
        ]

        done_count = len(
            done_tasks
        )

        late_count = len([
            task
            for task in tasks
            if task.status == "LATE"
        ])

        queued_count = len([
            task
            for task in tasks
            if task.status == "QUEUED"
        ])

        # -------------------------------------------------
        # AVERAGE COMPLETION TIME
        # -------------------------------------------------

        completion_seconds = []

        for task in done_tasks:

            if (
                task.started_at
                and task.completed_at
            ):
                seconds = (
                    task.completed_at
                    - task.started_at
                ).total_seconds()

                if seconds >= 0:
                    completion_seconds.append(
                        seconds
                    )

        average_seconds = None

        if completion_seconds:
            average_seconds = (
                sum(
                    completion_seconds
                )
                /
                len(
                    completion_seconds
                )
            )

        # -------------------------------------------------
        # ASSIGNMENTS
        # -------------------------------------------------

        assignments_count = (
            db.query(Assignment)
            .filter(
                Assignment.counter_id
                == counter.id
            )
            .count()
        )

        # -------------------------------------------------
        # LAST LOGIN
        # -------------------------------------------------

        last_login_at = (
            user.last_login_at
            if user
            else None
        )

        # -------------------------------------------------
        # PERFORMANCE SCORE
        # -------------------------------------------------

        score = 100

        if total_tasks > 0:

            late_penalty = (
                late_count * 15
            )

            open_penalty = (
                pending_count * 3
            )

            score -= (
                late_penalty
                + open_penalty
            )

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        # -------------------------------------------------
        # RESULT
        # -------------------------------------------------

        result.append({
            "counter_id":
                counter.id,

            "counter_name":
                counter.name,

            "phone":
                counter.phone,

            "is_active":
                counter.is_active,

            "telegram_connected":
                bool(
                    counter.telegram_chat_id
                ),

            "user": {
                "id":
                    user.id
                    if user
                    else None,

                "username":
                    user.username
                    if user
                    else None,

                "full_name":
                    user.full_name
                    if user
                    else counter.name,

                "last_login_at":
                    last_login_at,
            },

            "routes_count":
                assignments_count,

            "tasks": {
                "total":
                    total_tasks,

                "queued":
                    queued_count,

                "new":
                    new_count,

                "pending":
                    pending_count,

                "done":
                    done_count,

                "late":
                    late_count,
            },

            "average_completion_minutes":
                format_minutes(
                    average_seconds
                ),

            "performance_score":
                score,
        })

    # =====================================================
    # OVERALL
    # =====================================================

    total_tasks = sum(
        item["tasks"]["total"]
        for item in result
    )

    total_done = sum(
        item["tasks"]["done"]
        for item in result
    )

    total_late = sum(
        item["tasks"]["late"]
        for item in result
    )

    total_pending = sum(
        item["tasks"]["pending"]
        for item in result
    )

    total_new = sum(
        item["tasks"]["new"]
        for item in result
    )

    return {
        "date":
            datetime.now(
                BUSINESS_TIMEZONE
            ).date().isoformat(),

        "summary": {
            "counters":
                len(result),

            "tasks":
                total_tasks,

            "new":
                total_new,

            "pending":
                total_pending,

            "done":
                total_done,

            "late":
                total_late,
        },

        "counters":
            result,
    }