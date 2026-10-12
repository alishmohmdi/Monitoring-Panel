from datetime import (
    datetime,
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
    Counter,
    User,
)

from database.presence_models import (
    UserPresence,
)

from services.auth_dependency import (
    get_current_user,
)

from services.business_hours import (
    BUSINESS_TIMEZONE,
)


router = APIRouter(
    prefix="/presence",
    tags=["Presence"],
)


# =========================================================
# TIME HELPERS
# =========================================================

def utc_now_naive():
    return (
        datetime
        .now(timezone.utc)
        .replace(tzinfo=None)
    )


def tehran_today():
    return (
        datetime
        .now(BUSINESS_TIMEZONE)
        .date()
    )


# =========================================================
# PRESENCE STATUS
# =========================================================

def presence_status(
    last_seen_at,
):
    if not last_seen_at:
        return {
            "status": "OFFLINE",
            "seconds_since_activity": None,
        }

    now = utc_now_naive()

    seconds = int(
        (
            now - last_seen_at
        ).total_seconds()
    )

    seconds = max(
        0,
        seconds,
    )

    if seconds <= 120:
        status = "ONLINE"

    elif seconds <= 600:
        status = "IDLE"

    else:
        status = "OFFLINE"

    return {
        "status": status,
        "seconds_since_activity": seconds,
    }


# =========================================================
# HEARTBEAT
# =========================================================

@router.post("/heartbeat")
def heartbeat(
    db: Session = Depends(
        get_db
    ),

    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Called automatically by frontend.

    First call of the day:
        creates presence row.

    Next calls:
        update last_seen_at.
    """

    now = utc_now_naive()

    today = tehran_today()

    record = (
        db.query(UserPresence)
        .filter(
            UserPresence.user_id
            == current_user.id,

            UserPresence.work_date
            == today,
        )
        .first()
    )

    if not record:

        record = UserPresence(
            user_id=current_user.id,

            agency_id=current_user.agency_id,

            counter_id=current_user.counter_id,

            work_date=today,

            first_seen_at=now,

            last_seen_at=now,
        )

        db.add(record)

    else:

        record.last_seen_at = now

    db.commit()

    db.refresh(record)

    status = presence_status(
        record.last_seen_at
    )

    return {
        "success": True,

        "user_id":
            current_user.id,

        "counter_id":
            current_user.counter_id,

        "work_date":
            record.work_date,

        "first_seen_at":
            record.first_seen_at,

        "last_seen_at":
            record.last_seen_at,

        "presence_status":
            status["status"],

        "seconds_since_activity":
            status[
                "seconds_since_activity"
            ],
    }


# =========================================================
# MY PRESENCE
# =========================================================

@router.get("/me")
def my_presence(
    db: Session = Depends(
        get_db
    ),

    current_user: User = Depends(
        get_current_user
    ),
):
    today = tehran_today()

    record = (
        db.query(UserPresence)
        .filter(
            UserPresence.user_id
            == current_user.id,

            UserPresence.work_date
            == today,
        )
        .first()
    )

    if not record:

        return {
            "work_date":
                today,

            "first_seen_at":
                None,

            "last_seen_at":
                None,

            "presence_status":
                "OFFLINE",

            "seconds_since_activity":
                None,
        }

    status = presence_status(
        record.last_seen_at
    )

    return {
        "work_date":
            record.work_date,

        "first_seen_at":
            record.first_seen_at,

        "last_seen_at":
            record.last_seen_at,

        "presence_status":
            status["status"],

        "seconds_since_activity":
            status[
                "seconds_since_activity"
            ],
    }


# =========================================================
# MANAGEMENT TODAY
# =========================================================

@router.get("/today")
def today_presence(
    db: Session = Depends(
        get_db
    ),

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

    today = tehran_today()

    query = db.query(
        Counter
    )

    if (
        current_user.role
        == "AGENCY_ADMIN"
    ):
        query = query.filter(
            Counter.agency_id
            == current_user.agency_id
        )

    elif (
        current_user.role
        == "SUPER_ADMIN"
        and current_user.agency_id
        is not None
    ):
        query = query.filter(
            Counter.agency_id
            == current_user.agency_id
        )

    counters = (
        query
        .order_by(
            Counter.name.asc()
        )
        .all()
    )

    result = []

    for counter in counters:

        user = (
            db.query(User)
            .filter(
                User.counter_id
                == counter.id
            )
            .first()
        )

        record = None

        if user:

            record = (
                db.query(UserPresence)
                .filter(
                    UserPresence.user_id
                    == user.id,

                    UserPresence.work_date
                    == today,
                )
                .first()
            )

        if record:

            status = presence_status(
                record.last_seen_at
            )

        else:

            status = {
                "status":
                    "NOT_LOGGED_IN",

                "seconds_since_activity":
                    None,
            }

        result.append({
            "counter_id":
                counter.id,

            "counter_name":
                counter.name,

            "user_id":
                (
                    user.id
                    if user
                    else None
                ),

            "username":
                (
                    user.username
                    if user
                    else None
                ),

            "full_name":
                (
                    user.full_name
                    if user
                    else counter.name
                ),

            "work_date":
                today,

            "first_seen_at":
                (
                    record.first_seen_at
                    if record
                    else None
                ),

            "last_seen_at":
                (
                    record.last_seen_at
                    if record
                    else None
                ),

            "presence_status":
                status["status"],

            "seconds_since_activity":
                status[
                    "seconds_since_activity"
                ],
        })

    return {
        "date":
            today,

        "counters":
            result,
    }