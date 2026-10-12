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
)

from services.auth_dependency import (
    get_current_user,
)

from services.auth_service import (
    hash_password,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


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
# SCHEMAS
# =========================================================

class AgencyCreate(BaseModel):

    name: str
    slug: str

    phone: str | None = None
    email: str | None = None

    plan: str = "basic"


class AgencyUpdate(BaseModel):

    name: str | None = None

    phone: str | None = None
    email: str | None = None

    plan: str | None = None

    is_active: bool | None = None


class CounterCreate(BaseModel):

    agency_id: int

    name: str

    phone: str | None = None


class UserCreate(BaseModel):

    agency_id: int | None = None

    counter_id: int | None = None

    username: str
    password: str

    full_name: str

    email: str | None = None

    role: str


class UserUpdate(BaseModel):

    full_name: str | None = None

    email: str | None = None

    role: str | None = None

    counter_id: int | None = None

    is_active: bool | None = None


class PasswordReset(BaseModel):

    new_password: str


class AgencyRouteCreate(BaseModel):

    agency_id: int
    route_id: int


class AssignmentCreateAdmin(BaseModel):

    agency_id: int

    route_id: int

    counter_id: int


# =========================================================
# DASHBOARD
# =========================================================

@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    return {

        "agencies": (
            db.query(Agency)
            .count()
        ),

        "active_agencies": (
            db.query(Agency)
            .filter(
                Agency.is_active == True
            )
            .count()
        ),

        "users": (
            db.query(User)
            .count()
        ),

        "counters": (
            db.query(Counter)
            .count()
        ),

        "routes": (
            db.query(Route)
            .filter(
                Route.is_active == True
            )
            .count()
        ),

        "agency_routes": (
            db.query(AgencyRoute)
            .filter(
                AgencyRoute.is_active == True
            )
            .count()
        ),
    }


# =========================================================
# AGENCIES
# =========================================================

@router.get("/agencies")
def list_agencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    agencies = (
        db.query(Agency)
        .order_by(
            Agency.id.desc()
        )
        .all()
    )

    result = []

    for agency in agencies:

        users_count = (
            db.query(User)
            .filter(
                User.agency_id
                == agency.id
            )
            .count()
        )

        counters_count = (
            db.query(Counter)
            .filter(
                Counter.agency_id
                == agency.id
            )
            .count()
        )

        routes_count = (
            db.query(AgencyRoute)
            .filter(
                AgencyRoute.agency_id
                == agency.id,
                AgencyRoute.is_active
                == True,
            )
            .count()
        )

        result.append({

            "id": agency.id,

            "name": agency.name,

            "slug": agency.slug,

            "phone": agency.phone,

            "email": agency.email,

            "plan": agency.plan,

            "is_active": agency.is_active,

            "created_at": agency.created_at,

            "users_count": users_count,

            "counters_count": counters_count,

            "routes_count": routes_count,
        })

    return result


@router.post("/agencies")
def create_agency(
    data: AgencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    existing = (
        db.query(Agency)
        .filter(
            Agency.slug == data.slug
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=400,
            detail="Agency slug already exists",
        )

    agency = Agency(
        name=data.name,
        slug=data.slug,
        phone=data.phone,
        email=data.email,
        plan=data.plan,
        is_active=True,
    )

    db.add(agency)

    db.commit()

    db.refresh(agency)

    return agency


@router.patch("/agencies/{agency_id}")
def update_agency(
    agency_id: int,
    data: AgencyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

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

    values = data.model_dump(
        exclude_unset=True
    )

    for key, value in values.items():

        setattr(
            agency,
            key,
            value
        )

    db.commit()

    db.refresh(agency)

    return agency


# =========================================================
# COUNTERS
# =========================================================

@router.get("/counters")
def list_counters(
    agency_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    query = db.query(Counter)

    if agency_id is not None:

        query = query.filter(
            Counter.agency_id
            == agency_id
        )

    counters = (
        query
        .order_by(
            Counter.id.desc()
        )
        .all()
    )

    result = []

    for counter in counters:

        agency = (
            db.query(Agency)
            .filter(
                Agency.id
                == counter.agency_id
            )
            .first()
        )

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
                Assignment.counter_id
                == counter.id
            )
            .count()
        )

        result.append({

            "id": counter.id,

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

            "telegram_connected":
                bool(
                    counter.telegram_chat_id
                ),

            "is_active":
                counter.is_active,

            "user_id":
                user.id
                if user
                else None,

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
    data: CounterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    agency = (
        db.query(Agency)
        .filter(
            Agency.id
            == data.agency_id
        )
        .first()
    )

    if not agency:

        raise HTTPException(
            status_code=404,
            detail="Agency not found",
        )

    counter = Counter(
        agency_id=data.agency_id,
        name=data.name,
        phone=data.phone,
        is_active=True,
    )

    db.add(counter)

    db.commit()

    db.refresh(counter)

    return {
        "id": counter.id,
        "agency_id": counter.agency_id,
        "name": counter.name,
        "phone": counter.phone,
        "is_active": counter.is_active,
    }


# =========================================================
# USERS
# =========================================================

@router.get("/users")
def list_users(
    agency_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    query = db.query(User)

    if agency_id is not None:

        query = query.filter(
            User.agency_id
            == agency_id
        )

    users = (
        query
        .order_by(
            User.id.desc()
        )
        .all()
    )

    result = []

    for user in users:

        agency = (
            db.query(Agency)
            .filter(
                Agency.id
                == user.agency_id
            )
            .first()
        )

        counter = None

        if user.counter_id:

            counter = (
                db.query(Counter)
                .filter(
                    Counter.id
                    == user.counter_id
                )
                .first()
            )

        result.append({

            "id": user.id,

            "agency_id":
                user.agency_id,

            "agency_name":
                agency.name
                if agency
                else None,

            "counter_id":
                user.counter_id,

            "counter_name":
                counter.name
                if counter
                else None,

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
        })

    return result


@router.post("/users")
def create_user(
    data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    allowed_roles = {
        "SUPER_ADMIN",
        "AGENCY_ADMIN",
        "COUNTER",
    }

    if data.role not in allowed_roles:

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

    if data.agency_id is not None:

        agency = (
            db.query(Agency)
            .filter(
                Agency.id
                == data.agency_id
            )
            .first()
        )

        if not agency:

            raise HTTPException(
                status_code=404,
                detail="Agency not found",
            )

    if data.counter_id is not None:

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == data.counter_id
            )
            .first()
        )

        if not counter:

            raise HTTPException(
                status_code=404,
                detail="Counter not found",
            )

        if (
            data.agency_id is not None
            and counter.agency_id
            != data.agency_id
        ):

            raise HTTPException(
                status_code=400,
                detail="Counter belongs to another agency",
            )

    user = User(
        agency_id=data.agency_id,
        counter_id=data.counter_id,
        username=data.username,
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(
            data.password
        ),
        role=data.role,
        is_active=True,
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    return {
        "id": user.id,
        "agency_id": user.agency_id,
        "counter_id": user.counter_id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    values = data.model_dump(
        exclude_unset=True
    )

    if (
        "role" in values
        and values["role"]
        not in {
            "SUPER_ADMIN",
            "AGENCY_ADMIN",
            "COUNTER",
        }
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid role",
        )

    for key, value in values.items():

        setattr(
            user,
            key,
            value
        )

    db.commit()

    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "agency_id": user.agency_id,
        "counter_id": user.counter_id,
        "is_active": user.is_active,
    }


@router.post(
    "/users/{user_id}/reset-password"
)
def reset_password(
    user_id: int,
    data: PasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if len(data.new_password) < 8:

        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
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
# ROUTES
# =========================================================

@router.get("/routes")
def list_routes(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    routes = (
        db.query(Route)
        .order_by(
            Route.name.asc()
        )
        .all()
    )

    return [
        {
            "id": route.id,
            "name": route.name,
            "url": route.url,
            "is_active": route.is_active,
        }
        for route in routes
    ]


# =========================================================
# AGENCY ROUTES
# =========================================================

@router.get("/agency-routes")
def list_agency_routes(
    agency_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    query = db.query(
        AgencyRoute
    )

    if agency_id is not None:

        query = query.filter(
            AgencyRoute.agency_id
            == agency_id
        )

    records = query.all()

    result = []

    for item in records:

        agency = (
            db.query(Agency)
            .filter(
                Agency.id
                == item.agency_id
            )
            .first()
        )

        route = (
            db.query(Route)
            .filter(
                Route.id
                == item.route_id
            )
            .first()
        )

        result.append({

            "id": item.id,

            "agency_id":
                item.agency_id,

            "agency_name":
                agency.name
                if agency
                else None,

            "route_id":
                item.route_id,

            "route_name":
                route.name
                if route
                else None,

            "is_active":
                item.is_active,
        })

    return result


@router.post("/agency-routes")
def add_agency_route(
    data: AgencyRouteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    agency = (
        db.query(Agency)
        .filter(
            Agency.id
            == data.agency_id
        )
        .first()
    )

    if not agency:

        raise HTTPException(
            status_code=404,
            detail="Agency not found",
        )

    route = (
        db.query(Route)
        .filter(
            Route.id
            == data.route_id
        )
        .first()
    )

    if not route:

        raise HTTPException(
            status_code=404,
            detail="Route not found",
        )

    existing = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == data.agency_id,

            AgencyRoute.route_id
            == data.route_id,
        )
        .first()
    )

    if existing:

        existing.is_active = True

        db.commit()

        return {
            "id": existing.id,
            "agency_id":
                existing.agency_id,
            "route_id":
                existing.route_id,
            "is_active": True,
        }

    item = AgencyRoute(
        agency_id=data.agency_id,
        route_id=data.route_id,
        is_active=True,
    )

    db.add(item)

    db.commit()

    db.refresh(item)

    return item


@router.delete(
    "/agency-routes/{agency_route_id}"
)
def remove_agency_route(
    agency_route_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    item = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.id
            == agency_route_id
        )
        .first()
    )

    if not item:

        raise HTTPException(
            status_code=404,
            detail="Agency Route not found",
        )

    item.is_active = False

    db.commit()

    return {
        "success": True,
    }


# =========================================================
# ASSIGNMENTS
# =========================================================

@router.get("/assignments")
def list_assignments(
    agency_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    query = db.query(
        Assignment
    )

    if agency_id is not None:

        query = query.filter(
            Assignment.agency_id
            == agency_id
        )

    assignments = (
        query
        .order_by(
            Assignment.id.desc()
        )
        .all()
    )

    result = []

    for assignment in assignments:

        agency = (
            db.query(Agency)
            .filter(
                Agency.id
                == assignment.agency_id
            )
            .first()
        )

        route = (
            db.query(Route)
            .filter(
                Route.id
                == assignment.route_id
            )
            .first()
        )

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == assignment.counter_id
            )
            .first()
        )

        result.append({

            "id":
                assignment.id,

            "agency_id":
                assignment.agency_id,

            "agency_name":
                agency.name
                if agency
                else None,

            "route_id":
                assignment.route_id,

            "route_name":
                route.name
                if route
                else None,

            "counter_id":
                assignment.counter_id,

            "counter_name":
                counter.name
                if counter
                else None,
        })

    return result


@router.post("/assignments")
def create_assignment(
    data: AssignmentCreateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    agency_route = (
        db.query(AgencyRoute)
        .filter(
            AgencyRoute.agency_id
            == data.agency_id,

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
            detail="This route is not enabled for this agency",
        )

    counter = (
        db.query(Counter)
        .filter(
            Counter.id
            == data.counter_id
        )
        .first()
    )

    if not counter:

        raise HTTPException(
            status_code=404,
            detail="Counter not found",
        )

    if (
        counter.agency_id
        != data.agency_id
    ):

        raise HTTPException(
            status_code=400,
            detail="Counter belongs to another agency",
        )

    existing = (
        db.query(Assignment)
        .filter(
            Assignment.agency_id
            == data.agency_id,

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
        agency_id=data.agency_id,
        route_id=data.route_id,
        counter_id=data.counter_id,
    )

    db.add(assignment)

    db.commit()

    db.refresh(
        assignment
    )

    return {
        "id":
            assignment.id,

        "agency_id":
            assignment.agency_id,

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
        require_super_admin
    ),
):

    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.id
            == assignment_id
        )
        .first()
    )

    if not assignment:

        raise HTTPException(
            status_code=404,
            detail="Assignment not found",
        )

    db.delete(
        assignment
    )

    db.commit()

    return {
        "success": True,
    }