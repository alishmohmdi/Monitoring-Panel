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
    User,
    Counter,
    Route,
    AgencyRoute,
    Assignment,
    Task,
)

from services.auth_dependency import (
    get_current_user,
)

from services.auth_service import (
    hash_password,
)


router = APIRouter(
    prefix="/agency-admin",
    tags=["Agency Admin"],
)


# =========================================================
# ACCESS
# =========================================================

def require_agency_admin(
    current_user: User = Depends(
        get_current_user
    ),
):

    if current_user.role not in {
        "AGENCY_ADMIN",
        "SUPER_ADMIN",
    }:

        raise HTTPException(
            status_code=403,
            detail="Agency Admin access required",
        )

    if (
        current_user.role ==
        "AGENCY_ADMIN"
        and current_user.agency_id
        is None
    ):

        raise HTTPException(
            status_code=403,
            detail="User has no agency",
        )

    return current_user


def resolve_agency_id(
    current_user: User,
):

    if (
        current_user.role ==
        "AGENCY_ADMIN"
    ):

        return current_user.agency_id

    raise HTTPException(
        status_code=400,
        detail="Super Admin should use admin endpoints",
    )


# =========================================================
# SCHEMAS
# =========================================================

class AgencyCounterCreate(BaseModel):

    name: str

    phone: str | None = None


class AgencyUserCreate(BaseModel):

    counter_id: int | None = None

    username: str
    password: str

    full_name: str

    email: str | None = None

    role: str = "COUNTER"


class AgencyAssignmentCreate(BaseModel):

    route_id: int
    counter_id: int


# =========================================================
# DASHBOARD
# =========================================================

@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    agency = (
        db.query(Agency)
        .filter(
            Agency.id == agency_id
        )
        .first()
    )

    if not agency:

        raise HTTPException(
            status_code=404,
            detail="Agency not found",
        )

    users_count = (
        db.query(User)
        .filter(
            User.agency_id
            == agency_id
        )
        .count()
    )

    counters_count = (
        db.query(Counter)
        .filter(
            Counter.agency_id
            == agency_id
        )
        .count()
    )

    routes_count = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == agency_id,

            AgencyRoute.is_active
            == True,
        )
        .count()
    )

    tasks = (
        db.query(Task)
        .filter(
            Task.agency_id
            == agency_id
        )
        .all()
    )

    return {

        "agency": {
            "id":
                agency.id,

            "name":
                agency.name,

            "slug":
                agency.slug,

            "plan":
                agency.plan,

            "is_active":
                agency.is_active,
        },

        "users":
            users_count,

        "counters":
            counters_count,

        "routes":
            routes_count,

        "tasks": {
            "total":
                len(tasks),

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
    }


# =========================================================
# COUNTERS
# =========================================================

@router.get("/counters")
def counters(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    counters = (
        db.query(Counter)
        .filter(
            Counter.agency_id
            == agency_id
        )
        .order_by(
            Counter.id.desc()
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

        assignments_count = (
            db.query(Assignment)
            .filter(
                Assignment.agency_id
                == agency_id,

                Assignment.counter_id
                == counter.id,
            )
            .count()
        )

        result.append({

            "id":
                counter.id,

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

            "username":
                user.username
                if user
                else None,

            "assignments_count":
                assignments_count,
        })

    return result


@router.post("/counters")
def create_counter(
    data: AgencyCounterCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    counter = Counter(
        agency_id=agency_id,
        name=data.name,
        phone=data.phone,
        is_active=True,
    )

    db.add(counter)

    db.commit()

    db.refresh(counter)

    return {
        "id":
            counter.id,

        "name":
            counter.name,

        "phone":
            counter.phone,

        "is_active":
            counter.is_active,
    }


# =========================================================
# USERS
# =========================================================

@router.get("/users")
def users(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    users = (
        db.query(User)
        .filter(
            User.agency_id
            == agency_id
        )
        .order_by(
            User.id.desc()
        )
        .all()
    )

    return [
        {
            "id":
                user.id,

            "counter_id":
                user.counter_id,

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
        }

        for user in users
    ]


@router.post("/users")
def create_user(
    data: AgencyUserCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    if data.role not in {
        "COUNTER",
        "AGENCY_ADMIN",
    }:

        raise HTTPException(
            status_code=400,
            detail="Invalid role",
        )

    existing = (
        db.query(User)
        .filter(
            User.username
            == data.username
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=400,
            detail="Username already exists",
        )

    if data.counter_id:

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == data.counter_id,

                Counter.agency_id
                == agency_id,
            )
            .first()
        )

        if not counter:

            raise HTTPException(
                status_code=404,
                detail="Counter not found",
            )

    user = User(
        agency_id=agency_id,
        counter_id=data.counter_id,

        username=data.username,
        email=data.email,
        full_name=data.full_name,

        password_hash=
            hash_password(
                data.password
            ),

        role=data.role,
        is_active=True,
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return {
        "id":
            user.id,

        "username":
            user.username,

        "full_name":
            user.full_name,

        "role":
            user.role,

        "counter_id":
            user.counter_id,
    }


# =========================================================
# ROUTES
# =========================================================

@router.get("/routes")
def routes(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    agency_routes = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == agency_id,

            AgencyRoute.is_active
            == True,
        )
        .all()
    )

    result = []

    for item in agency_routes:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == item.route_id
            )
            .first()
        )

        if route:

            result.append({
                "id":
                    route.id,

                "name":
                    route.name,

                "url":
                    route.url,

                "is_active":
                    route.is_active,
            })

    return result


# =========================================================
# ASSIGNMENTS
# =========================================================

@router.get("/assignments")
def assignments(
    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    records = (
        db.query(Assignment)
        .filter(
            Assignment.agency_id
            == agency_id
        )
        .order_by(
            Assignment.id.desc()
        )
        .all()
    )

    result = []

    for item in records:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == item.route_id
            )
            .first()
        )

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == item.counter_id
            )
            .first()
        )

        result.append({
            "id":
                item.id,

            "route_id":
                item.route_id,

            "route_name":
                route.name
                if route
                else None,

            "counter_id":
                item.counter_id,

            "counter_name":
                counter.name
                if counter
                else None,
        })

    return result


@router.post("/assignments")
def create_assignment(
    data: AgencyAssignmentCreate,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    agency_route = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == agency_id,

            AgencyRoute.route_id
            == data.route_id,

            AgencyRoute.is_active
            == True,
        )
        .first()
    )

    if not agency_route:

        raise HTTPException(
            status_code=400,
            detail="Route is not enabled for this agency",
        )

    counter = (
        db.query(Counter)
        .filter(
            Counter.id
            == data.counter_id,

            Counter.agency_id
            == agency_id,
        )
        .first()
    )

    if not counter:

        raise HTTPException(
            status_code=404,
            detail="Counter not found",
        )

    existing = (
        db.query(Assignment)
        .filter(
            Assignment.agency_id
            == agency_id,

            Assignment.route_id
            == data.route_id,

            Assignment.counter_id
            == data.counter_id,
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=400,
            detail="Assignment already exists",
        )

    assignment = Assignment(
        agency_id=agency_id,
        route_id=data.route_id,
        counter_id=data.counter_id,
    )

    db.add(assignment)

    db.commit()

    db.refresh(assignment)

    return {
        "id":
            assignment.id,

        "route_id":
            assignment.route_id,

        "counter_id":
            assignment.counter_id,
    }


@router.delete(
    "/assignments/{assignment_id}"
)
def delete_assignment(
    assignment_id: int,

    db: Session = Depends(get_db),

    current_user: User = Depends(
        require_agency_admin
    ),
):

    agency_id = resolve_agency_id(
        current_user
    )

    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.id
            == assignment_id,

            Assignment.agency_id
            == agency_id,
        )
        .first()
    )

    if not assignment:

        raise HTTPException(
            status_code=404,
            detail="Assignment not found",
        )

    db.delete(assignment)

    db.commit()

    return {
        "success": True,
    }