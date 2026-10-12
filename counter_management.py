from datetime import timedelta

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db

from database.models import (
    Agency,
    AgencyRoute,
    Assignment,
    Counter,
    Route,
    User,
)

from database.presence_models import (
    UserPresence,
)

from services.auth_dependency import (
    get_current_user,
)

from services.auth_service import (
    hash_password,
)

from services.business_hours import (
    utc_now_naive,
    utc_naive_to_tehran,
)


router = APIRouter(
    prefix="/counter-management",
    tags=["Counter Management"],
)


# =========================================================
# SCHEMAS
# =========================================================

class CounterUpdate(BaseModel):

    full_name: str
    phone: str
    email: str
    is_active: bool


class CounterPasswordReset(BaseModel):

    new_password: str


class CounterRoutesUpdate(BaseModel):

    route_ids: list[int]


# =========================================================
# ACCESS
# =========================================================

def require_super_admin(
    current_user: User = Depends(
        get_current_user
    ),
):

    if current_user.role != "SUPER_ADMIN":

        raise HTTPException(
            status_code=403,
            detail="Super Admin access required",
        )

    return current_user


# =========================================================
# HELPERS
# =========================================================

def get_counter_or_404(
    counter_id: int,
    db: Session,
):

    counter = (
        db.query(Counter)
        .filter(
            Counter.id == counter_id
        )
        .first()
    )

    if not counter:

        raise HTTPException(
            status_code=404,
            detail="Counter not found",
        )

    return counter


def get_counter_user(
    counter_id: int,
    db: Session,
):

    return (
        db.query(User)
        .filter(
            User.counter_id
            == counter_id
        )
        .first()
    )


def get_presence_status(
    user: User | None,
    db: Session,
):

    if not user:

        return {
            "status": "NO_USER",
            "last_seen_at": None,
        }

    now_utc = utc_now_naive()

    today_tehran = (
        utc_naive_to_tehran(
            now_utc
        ).date()
    )

    presence = (
        db.query(UserPresence)
        .filter(
            UserPresence.user_id
            == user.id,

            UserPresence.work_date
            == today_tehran,
        )
        .first()
    )

    if not presence:

        return {
            "status": "NOT_LOGGED_IN",
            "last_seen_at": None,
        }

    difference = (
        now_utc
        - presence.last_seen_at
    )

    seconds = max(
        0,
        int(
            difference.total_seconds()
        ),
    )

    if seconds <= 120:

        status = "ONLINE"

    elif seconds <= 600:

        status = "IDLE"

    else:

        status = "OFFLINE"

    return {
        "status":
            status,

        "first_seen_at":
            presence.first_seen_at,

        "last_seen_at":
            presence.last_seen_at,

        "seconds_since_last_seen":
            seconds,
    }


def serialize_counter(
    counter: Counter,
    db: Session,
):

    agency = (
        db.query(Agency)
        .filter(
            Agency.id
            == counter.agency_id
        )
        .first()
    )

    user = get_counter_user(
        counter.id,
        db,
    )

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.counter_id
            == counter.id
        )
        .all()
    )

    routes = []

    for assignment in assignments:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == assignment.route_id
            )
            .first()
        )

        if route:

            routes.append({
                "assignment_id":
                    assignment.id,

                "id":
                    route.id,

                "name":
                    route.name,

                "url":
                    route.url,

                "is_active":
                    route.is_active,
            })

    presence = get_presence_status(
        user,
        db,
    )

    return {
        "id":
            counter.id,

        "agency_id":
            counter.agency_id,

        "agency_name":
            agency.name
            if agency
            else None,

        "name":
            counter.name,

        "phone":
            counter.phone,

        "is_active":
            counter.is_active,

        "telegram_connected":
            bool(
                counter.telegram_chat_id
            ),

        "telegram_user_id":
            counter.telegram_user_id,

        "telegram_chat_id":
            counter.telegram_chat_id,

        "created_at":
            counter.created_at,

        "user": (
            {
                "id":
                    user.id,

                "username":
                    user.username,

                "full_name":
                    user.full_name,

                "email":
                    user.email,

                "role":
                    user.role,

                "is_active":
                    user.is_active,

                "last_login_at":
                    user.last_login_at,

                "created_at":
                    user.created_at,
            }
            if user
            else None
        ),

        "routes":
            routes,

        "assignments_count":
            len(routes),

        "presence":
            presence,
    }


# =========================================================
# LIST
# =========================================================

@router.get("")
def list_counter_management(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counters = (
        db.query(Counter)
        .order_by(
            Counter.id.desc()
        )
        .all()
    )

    return [
        serialize_counter(
            counter,
            db,
        )
        for counter in counters
    ]


# =========================================================
# DETAIL
# =========================================================

@router.get("/{counter_id}")
def counter_detail(
    counter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counter = get_counter_or_404(
        counter_id,
        db,
    )

    return serialize_counter(
        counter,
        db,
    )


# =========================================================
# UPDATE PROFILE
# =========================================================

@router.patch("/{counter_id}")
def update_counter(
    counter_id: int,
    data: CounterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counter = get_counter_or_404(
        counter_id,
        db,
    )

    user = get_counter_user(
        counter.id,
        db,
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Counter user account not found",
        )

    full_name = (
        data.full_name or ""
    ).strip()

    phone = (
        data.phone or ""
    ).strip()

    email = (
        data.email or ""
    ).strip().lower()

    if not full_name:

        raise HTTPException(
            status_code=400,
            detail="Full name is required",
        )

    if not phone:

        raise HTTPException(
            status_code=400,
            detail="Phone number is required",
        )

    if not email:

        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    if (
        "@" not in email
        or "." not in email
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid email address",
        )

    existing_email = (
        db.query(User)
        .filter(
            User.email == email,
            User.id != user.id,
        )
        .first()
    )

    if existing_email:

        raise HTTPException(
            status_code=400,
            detail="Email already exists",
        )

    counter.name = full_name
    counter.phone = phone
    counter.is_active = (
        data.is_active
    )

    user.full_name = full_name
    user.email = email
    user.is_active = (
        data.is_active
    )

    db.commit()

    db.refresh(counter)
    db.refresh(user)

    return serialize_counter(
        counter,
        db,
    )


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post(
    "/{counter_id}/reset-password"
)
def reset_counter_password(
    counter_id: int,
    data: CounterPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counter = get_counter_or_404(
        counter_id,
        db,
    )

    user = get_counter_user(
        counter.id,
        db,
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Counter user account not found",
        )

    if len(data.new_password) < 8:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be "
                "at least 8 characters"
            ),
        )

    user.password_hash = (
        hash_password(
            data.new_password
        )
    )

    db.commit()

    return {
        "success": True,
        "message": "Password updated",
    }


# =========================================================
# AVAILABLE ROUTES
# =========================================================

@router.get(
    "/{counter_id}/available-routes"
)
def counter_available_routes(
    counter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counter = get_counter_or_404(
        counter_id,
        db,
    )

    agency_routes = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == counter.agency_id,

            AgencyRoute.is_active
            == True,
        )
        .all()
    )

    current_assignments = (
        db.query(Assignment)
        .filter(
            Assignment.counter_id
            == counter.id
        )
        .all()
    )

    current_route_ids = {
        item.route_id
        for item
        in current_assignments
    }

    result = []

    for agency_route in agency_routes:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == agency_route.route_id
            )
            .first()
        )

        if not route:
            continue

        result.append({
            "id":
                route.id,

            "name":
                route.name,

            "url":
                route.url,

            "is_active":
                route.is_active,

            "assigned":
                route.id
                in current_route_ids,
        })

    result.sort(
        key=lambda item:
            item["name"].lower()
    )

    return result


# =========================================================
# REPLACE ROUTES
# =========================================================

@router.put(
    "/{counter_id}/routes"
)
def update_counter_routes(
    counter_id: int,
    data: CounterRoutesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    counter = get_counter_or_404(
        counter_id,
        db,
    )

    unique_route_ids = list(
        dict.fromkeys(
            data.route_ids
        )
    )

    for route_id in unique_route_ids:

        agency_route = (
            db.query(AgencyRoute)
            .filter(
                AgencyRoute.agency_id
                == counter.agency_id,

                AgencyRoute.route_id
                == route_id,

                AgencyRoute.is_active
                == True,
            )
            .first()
        )

        if not agency_route:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Route {route_id} "
                    "is not enabled "
                    "for this agency"
                ),
            )

        route = (
            db.query(Route)
            .filter(
                Route.id
                == route_id
            )
            .first()
        )

        if not route:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Route {route_id} "
                    "not found"
                ),
            )

        if not route.is_active:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Route {route.name} "
                    "is inactive"
                ),
            )

    existing_assignments = (
        db.query(Assignment)
        .filter(
            Assignment.counter_id
            == counter.id
        )
        .all()
    )

    for assignment in existing_assignments:

        db.delete(
            assignment
        )

    db.flush()

    for route_id in unique_route_ids:

        assignment = Assignment(
            agency_id=
                counter.agency_id,

            route_id=
                route_id,

            counter_id=
                counter.id,
        )

        db.add(
            assignment
        )

    db.commit()

    return serialize_counter(
        counter,
        db,
    )