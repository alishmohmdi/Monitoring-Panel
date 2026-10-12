from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy.orm import Session

from database.db import get_db

from database.models import (
    User,
    Task,
    Change,
    Package,
    Route,
    Counter,
    Assignment,
)

from services.auth_dependency import (
    get_current_user,
)

from services.business_hours import (
    is_business_time,
    utc_now_naive,
    add_business_seconds,
    remaining_business_seconds,
    utc_naive_to_tehran,
)


router = APIRouter(
    prefix="/panel",
    tags=["Panel"],
)


# =========================================================
# HELPERS
# =========================================================

def get_task_or_404(
    task_id: int,
    db: Session,
):
    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task


def check_task_access(
    task: Task,
    current_user: User,
):
    if current_user.role == "SUPER_ADMIN":
        return

    if current_user.role == "AGENCY_ADMIN":

        if (
            task.agency_id
            != current_user.agency_id
        ):
            raise HTTPException(
                status_code=403,
                detail="Access denied",
            )

        return

    if current_user.role == "COUNTER":

        if (
            current_user.counter_id is None
            or task.counter_id
            != current_user.counter_id
        ):
            raise HTTPException(
                status_code=403,
                detail="This task is not assigned to you",
            )

        return

    raise HTTPException(
        status_code=403,
        detail="Access denied",
    )


def normalize_task_status(
    task: Task,
    db: Session,
):
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

            db.commit()
            db.refresh(task)


def serialize_task(
    task: Task,
    db: Session,
):
    normalize_task_status(
        task,
        db,
    )

    change = (
        db.query(Change)
        .filter(
            Change.id == task.change_id
        )
        .first()
    )

    route = None
    package = None
    counter = None

    if change:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == change.route_id
            )
            .first()
        )

        if change.package_id:

            package = (
                db.query(Package)
                .filter(
                    Package.id
                    == change.package_id
                )
                .first()
            )

    if task.counter_id:

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == task.counter_id
            )
            .first()
        )

    remaining_seconds = None

    if (
        task.status == "PENDING"
        and task.deadline
    ):
        remaining_seconds = (
            remaining_business_seconds(
                task.deadline
            )
        )

    return {
        "id":
            task.id,

        "agency_id":
            task.agency_id,

        "counter_id":
            task.counter_id,

        "counter_name":
            (
                counter.name
                if counter
                else None
            ),

        "status":
            task.status,

        "created_at":
            task.created_at,

        "released_at":
            task.released_at,

        "opened_at":
            task.opened_at,

        "started_at":
            task.started_at,

        "deadline":
            task.deadline,

        "completed_at":
            task.completed_at,

        "remaining_seconds":
            remaining_seconds,

        "change": {
            "id":
                (
                    change.id
                    if change
                    else None
                ),

            "type":
                (
                    change.change_type
                    if change
                    else None
                ),

            "hotel_name":
                (
                    change.hotel_name
                    if change
                    else None
                ),

            "package_name":
                (
                    change.package_name
                    if change
                    else None
                ),

            "old_value":
                (
                    change.old_value
                    if change
                    else None
                ),

            "new_value":
                (
                    change.new_value
                    if change
                    else None
                ),

            "old_price":
                (
                    change.old_price
                    if change
                    else None
                ),

            "new_price":
                (
                    change.new_price
                    if change
                    else None
                ),

            "detected_at":
                (
                    change.detected_at
                    if change
                    else None
                ),
        },

        "route": {
            "id":
                (
                    route.id
                    if route
                    else None
                ),

            "name":
                (
                    route.name
                    if route
                    else None
                ),
        },

        "package": {
            "id":
                (
                    package.id
                    if package
                    else None
                ),

            "title":
                (
                    package.title
                    if package
                    else None
                ),

            "departure_date":
                (
                    package.departure_date
                    if package
                    else None
                ),

            "return_date":
                (
                    package.return_date
                    if package
                    else None
                ),

            "duration":
                (
                    package.duration
                    if package
                    else None
                ),

            "url":
                (
                    package.url
                    if package
                    else None
                ),
        },
    }


def scoped_task_query(
    db: Session,
    current_user: User,
):
    query = db.query(Task)

    if current_user.role == "COUNTER":

        if current_user.counter_id is None:
            return query.filter(
                Task.id == -1
            )

        return query.filter(
            Task.counter_id
            == current_user.counter_id
        )

    if current_user.role == "AGENCY_ADMIN":

        return query.filter(
            Task.agency_id
            == current_user.agency_id
        )

    if current_user.role == "SUPER_ADMIN":
        return query

    raise HTTPException(
        status_code=403,
        detail="Access denied",
    )


def is_today_tehran(
    value: datetime | None,
) -> bool:
    if value is None:
        return False

    local_value = (
        utc_naive_to_tehran(
            value
        )
    )

    now_local = (
        utc_naive_to_tehran(
            utc_now_naive()
        )
    )

    return (
        local_value.date()
        ==
        now_local.date()
    )


# =========================================================
# MY TASKS
# =========================================================

@router.get("/my-tasks")
def my_tasks(
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    query = scoped_task_query(
        db,
        current_user,
    )

    tasks = (
        query
        .order_by(
            Task.created_at.desc()
        )
        .all()
    )

    return [
        serialize_task(
            task,
            db,
        )
        for task in tasks
    ]


# =========================================================
# DASHBOARD
# =========================================================

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    query = scoped_task_query(
        db,
        current_user,
    )

    tasks = query.all()

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

    return {
        "total":
            len(tasks),

        "queued":
            len([
                task
                for task in tasks
                if task.status
                == "QUEUED"
            ]),

        "new":
            len([
                task
                for task in tasks
                if task.status
                == "NEW"
            ]),

        "pending":
            len([
                task
                for task in tasks
                if task.status
                == "PENDING"
            ]),

        "done":
            len([
                task
                for task in tasks
                if task.status
                == "DONE"
            ]),

        "late":
            len([
                task
                for task in tasks
                if task.status
                == "LATE"
            ]),
    }


# =========================================================
# MORNING / TODAY DASHBOARD
# =========================================================

@router.get("/today")
def today_dashboard(
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    query = scoped_task_query(
        db,
        current_user,
    )

    tasks = (
        query
        .order_by(
            Task.created_at.desc()
        )
        .all()
    )

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

    today_tasks = [
        task
        for task in tasks
        if (
            is_today_tehran(
                task.released_at
            )
            or
            is_today_tehran(
                task.created_at
            )
            or
            is_today_tehran(
                task.completed_at
            )
        )
    ]

    recent_tasks = (
        tasks[:5]
    )

    return {
        "business_hours_active":
            is_business_time(),

        "today": {
            "total":
                len(today_tasks),

            "new":
                len([
                    task
                    for task in today_tasks
                    if task.status
                    == "NEW"
                ]),

            "pending":
                len([
                    task
                    for task in today_tasks
                    if task.status
                    == "PENDING"
                ]),

            "done":
                len([
                    task
                    for task in today_tasks
                    if task.status
                    == "DONE"
                ]),

            "late":
                len([
                    task
                    for task in today_tasks
                    if task.status
                    == "LATE"
                ]),

            "queued":
                len([
                    task
                    for task in today_tasks
                    if task.status
                    == "QUEUED"
                ]),
        },

        "recent_tasks": [
            serialize_task(
                task,
                db,
            )
            for task in recent_tasks
        ],
    }


# =========================================================
# TASK DETAIL
# =========================================================

@router.get("/tasks/{task_id}")
def task_detail(
    task_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    task = get_task_or_404(
        task_id,
        db,
    )

    check_task_access(
        task,
        current_user,
    )

    return serialize_task(
        task,
        db,
    )


# =========================================================
# OPEN TASK
# =========================================================

@router.post(
    "/tasks/{task_id}/open"
)
def open_task(
    task_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    task = get_task_or_404(
        task_id,
        db,
    )

    check_task_access(
        task,
        current_user,
    )

    if task.status == "QUEUED":

        raise HTTPException(
            status_code=409,
            detail=(
                "Task is waiting "
                "for business hours"
            ),
        )

    if task.status == "DONE":

        return serialize_task(
            task,
            db,
        )

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

            db.commit()
            db.refresh(task)

            return serialize_task(
                task,
                db,
            )

    if task.status == "NEW":

        if not is_business_time():

            raise HTTPException(
                status_code=409,
                detail=(
                    "Task timer can only "
                    "start during business hours"
                ),
            )

        now = utc_now_naive()

        task.status = "PENDING"

        task.opened_at = now

        task.started_at = now

        task.deadline = (
            add_business_seconds(
                now
            )
        )

        db.commit()
        db.refresh(task)

    return serialize_task(
        task,
        db,
    )


# =========================================================
# DONE TASK
# =========================================================

@router.post(
    "/tasks/{task_id}/done"
)
def done_task(
    task_id: int,
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    task = get_task_or_404(
        task_id,
        db,
    )

    check_task_access(
        task,
        current_user,
    )

    if task.status == "QUEUED":

        raise HTTPException(
            status_code=409,
            detail=(
                "Queued task cannot "
                "be completed yet"
            ),
        )

    if task.status == "DONE":

        return serialize_task(
            task,
            db,
        )

    now = utc_now_naive()

    if task.started_at is None:

        if not is_business_time():

            raise HTTPException(
                status_code=409,
                detail=(
                    "Task can only be completed "
                    "during business hours"
                ),
            )

        task.opened_at = now
        task.started_at = now

        task.deadline = (
            add_business_seconds(
                now
            )
        )

    task.status = "DONE"

    task.completed_at = now

    db.commit()
    db.refresh(task)

    return serialize_task(
        task,
        db,
    )


# =========================================================
# PROFILE
# =========================================================

@router.get("/profile")
def profile(
    db: Session = Depends(
        get_db
    ),
    current_user: User = Depends(
        get_current_user
    ),
):
    counter = None

    if current_user.counter_id:

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == current_user.counter_id
            )
            .first()
        )

    tasks_query = scoped_task_query(
        db,
        current_user,
    )

    tasks = tasks_query.all()

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

    assignments = []

    if current_user.counter_id:

        counter_assignments = (
            db.query(Assignment)
            .filter(
                Assignment.counter_id
                == current_user.counter_id
            )
            .all()
        )

        for assignment in counter_assignments:

            route = (
                db.query(Route)
                .filter(
                    Route.id
                    == assignment.route_id
                )
                .first()
            )

            if route:

                assignments.append({
                    "id":
                        route.id,

                    "name":
                        route.name,

                    "url":
                        route.url,
                })

    return {
        "user": {
            "id":
                current_user.id,

            "username":
                current_user.username,

            "full_name":
                current_user.full_name,

            "email":
                current_user.email,

            "role":
                current_user.role,

            "agency_id":
                current_user.agency_id,

            "counter_id":
                current_user.counter_id,

            "last_login_at":
                current_user.last_login_at,
        },

        "counter": {
            "id":
                (
                    counter.id
                    if counter
                    else None
                ),

            "name":
                (
                    counter.name
                    if counter
                    else None
                ),

            "phone":
                (
                    counter.phone
                    if counter
                    else None
                ),

            "telegram_connected":
                (
                    bool(
                        counter.telegram_chat_id
                    )
                    if counter
                    else False
                ),
        },

        "stats": {
            "total":
                len(tasks),

            "queued":
                len([
                    task
                    for task in tasks
                    if task.status
                    == "QUEUED"
                ]),

            "new":
                len([
                    task
                    for task in tasks
                    if task.status
                    == "NEW"
                ]),

            "pending":
                len([
                    task
                    for task in tasks
                    if task.status
                    == "PENDING"
                ]),

            "done":
                len([
                    task
                    for task in tasks
                    if task.status
                    == "DONE"
                ]),

            "late":
                len([
                    task
                    for task in tasks
                    if task.status
                    == "LATE"
                ]),
        },

        "routes":
            assignments,
    }