from datetime import datetime
import re

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
)

from sqlalchemy.orm import Session

from database.db import get_db

from database.models import (
    Agency,
    AgencyRoute,
    Assignment,
    Counter,
    CredentialChangeRequest,
    Route,
    User,
)

from services.auth_dependency import (
    get_current_user,
)

from services.auth_service import (
    hash_password,
    verify_password,
)


router = APIRouter(
    prefix="/counter-accounts",
    tags=["Counter Accounts"],
)


# =========================================================
# SCHEMAS
# =========================================================

class CounterAccountCreate(BaseModel):

    agency_id: int

    full_name: str

    phone: str

    email: str

    username: str

    password: str

    route_ids: list[int] = Field(
        default_factory=list
    )


class CredentialChangeCreate(BaseModel):

    current_password: str

    new_username: str | None = None

    new_password: str | None = None


class CredentialRequestReview(BaseModel):

    note: str | None = None


# =========================================================
# HELPERS
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


def normalize_required_text(
    value: str,
    field_name: str,
):

    value = (
        value or ""
    ).strip()

    if not value:

        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required",
        )

    return value


def normalize_email(
    value: str,
):

    value = (
        value or ""
    ).strip().lower()

    if not value:

        raise HTTPException(
            status_code=400,
            detail="Email is required",
        )

    email_pattern = (
        r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    )

    if not re.match(
        email_pattern,
        value,
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid email address",
        )

    return value


def normalize_phone(
    value: str,
):

    value = (
        value or ""
    ).strip()

    if not value:

        raise HTTPException(
            status_code=400,
            detail="Phone number is required",
        )

    cleaned = (
        value
        .replace(" ", "")
        .replace("-", "")
    )

    if len(cleaned) < 7:

        raise HTTPException(
            status_code=400,
            detail="Invalid phone number",
        )

    return value


def validate_username(
    username: str,
):

    username = (
        username or ""
    ).strip()

    if len(username) < 3:

        raise HTTPException(
            status_code=400,
            detail="Username must be at least 3 characters",
        )

    if " " in username:

        raise HTTPException(
            status_code=400,
            detail="Username cannot contain spaces",
        )

    return username


def validate_password(
    password: str,
):

    if not password:

        raise HTTPException(
            status_code=400,
            detail="Password is required",
        )

    if len(password) < 8:

        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    return password


def get_counter_for_user(
    db: Session,
    user: User,
):

    if not user.counter_id:
        return None

    return (
        db.query(Counter)
        .filter(
            Counter.id
            == user.counter_id
        )
        .first()
    )


def validate_route_ids_for_agency(
    db: Session,
    agency_id: int,
    route_ids: list[int],
):

    unique_route_ids = list(
        dict.fromkeys(route_ids)
    )

    if not unique_route_ids:
        return []

    valid_routes = []

    for route_id in unique_route_ids:

        route = (
            db.query(Route)
            .filter(
                Route.id == route_id
            )
            .first()
        )

        if not route:

            raise HTTPException(
                status_code=404,
                detail=(
                    f"Route {route_id} not found"
                ),
            )

        if not route.is_active:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Route {route.name} is inactive"
                ),
            )

        agency_route = (
            db.query(AgencyRoute)
            .filter(
                AgencyRoute.agency_id
                == agency_id,

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
                    f"Route {route.name} is not enabled "
                    f"for this agency"
                ),
            )

        valid_routes.append(
            route
        )

    return valid_routes


def serialize_request(
    db: Session,
    request: CredentialChangeRequest,
):

    user = (
        db.query(User)
        .filter(
            User.id
            == request.user_id
        )
        .first()
    )

    counter = None

    if user and user.counter_id:

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == user.counter_id
            )
            .first()
        )

    return {
        "id":
            request.id,

        "user_id":
            request.user_id,

        "agency_id":
            request.agency_id,

        "counter_id":
            user.counter_id
            if user
            else None,

        "counter_name":
            counter.name
            if counter
            else None,

        "full_name":
            user.full_name
            if user
            else None,

        "current_username":
            user.username
            if user
            else None,

        "requested_username":
            request.requested_username,

        "change_username":
            bool(
                request.change_username
            ),

        "change_password":
            bool(
                request.change_password
            ),

        "status":
            request.status,

        "review_note":
            request.review_note,

        "created_at":
            request.created_at,

        "reviewed_at":
            request.reviewed_at,
    }


# =========================================================
# ADMIN - AVAILABLE ROUTES FOR AGENCY
# =========================================================

@router.get(
    "/admin/agencies/{agency_id}/available-routes"
)
def available_routes_for_agency(
    agency_id: int,
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

    for agency_route in agency_routes:

        route = (
            db.query(Route)
            .filter(
                Route.id
                == agency_route.route_id,

                Route.is_active
                == True,
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
        })

    result.sort(
        key=lambda item:
            item["name"].lower()
    )

    return result


# =========================================================
# ADMIN - CREATE COMPLETE COUNTER ACCOUNT
# =========================================================

@router.post("/admin/create")
def create_counter_account(
    data: CounterAccountCreate,
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

    if not agency.is_active:

        raise HTTPException(
            status_code=400,
            detail="Agency is inactive",
        )

    full_name = normalize_required_text(
        data.full_name,
        "Full name",
    )

    phone = normalize_phone(
        data.phone
    )

    email = normalize_email(
        data.email
    )

    username = validate_username(
        data.username
    )

    password = validate_password(
        data.password
    )

    valid_routes = (
        validate_route_ids_for_agency(
            db=db,
            agency_id=data.agency_id,
            route_ids=data.route_ids,
        )
    )

    existing_username = (
        db.query(User)
        .filter(
            User.username
            == username
        )
        .first()
    )

    if existing_username:

        raise HTTPException(
            status_code=400,
            detail="Username already exists",
        )

    existing_email = (
        db.query(User)
        .filter(
            User.email
            == email
        )
        .first()
    )

    if existing_email:

        raise HTTPException(
            status_code=400,
            detail="Email already exists",
        )

    counter = Counter(
        agency_id=data.agency_id,
        name=full_name,
        phone=phone,
        is_active=True,
    )

    try:

        db.add(counter)

        db.flush()

        user = User(
            agency_id=data.agency_id,
            counter_id=counter.id,
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hash_password(
                password
            ),
            role="COUNTER",
            is_active=True,
        )

        db.add(user)

        db.flush()

        created_assignments = []

        for route in valid_routes:

            assignment = Assignment(
                agency_id=data.agency_id,
                route_id=route.id,
                counter_id=counter.id,
            )

            db.add(assignment)

            created_assignments.append(
                assignment
            )

        db.commit()

        db.refresh(counter)
        db.refresh(user)

    except Exception:

        db.rollback()

        raise

    return {
        "success":
            True,

        "counter": {
            "id":
                counter.id,

            "agency_id":
                counter.agency_id,

            "name":
                counter.name,

            "phone":
                counter.phone,

            "is_active":
                counter.is_active,
        },

        "user": {
            "id":
                user.id,

            "agency_id":
                user.agency_id,

            "counter_id":
                user.counter_id,

            "username":
                user.username,

            "email":
                user.email,

            "full_name":
                user.full_name,

            "role":
                user.role,

            "is_active":
                user.is_active,
        },

        "routes": [
            {
                "id":
                    route.id,

                "name":
                    route.name,

                "url":
                    route.url,
            }
            for route in valid_routes
        ],

        "assignments_count":
            len(valid_routes),
    }


# =========================================================
# COUNTER - MY CONTACT STATUS
# =========================================================

@router.get("/me/status")
def my_account_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    counter = get_counter_for_user(
        db,
        current_user,
    )

    phone = (
        counter.phone.strip()
        if counter
        and counter.phone
        else ""
    )

    email = (
        current_user.email.strip()
        if current_user.email
        else ""
    )

    profile_complete = bool(
        email
        and phone
    )

    return {
        "user_id":
            current_user.id,

        "counter_id":
            current_user.counter_id,

        "email":
            email or None,

        "phone":
            phone or None,

        "profile_complete":
            profile_complete,
    }


# =========================================================
# COUNTER - CREATE CREDENTIAL CHANGE REQUEST
# =========================================================

@router.post("/me/change-request")
def create_change_request(
    data: CredentialChangeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    if current_user.role != "COUNTER":

        raise HTTPException(
            status_code=403,
            detail=(
                "Only counter users "
                "can submit this request"
            ),
        )

    if not verify_password(
        data.current_password,
        current_user.password_hash,
    ):

        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect",
        )

    pending_request = (
        db.query(
            CredentialChangeRequest
        )
        .filter(
            CredentialChangeRequest.user_id
            == current_user.id,

            CredentialChangeRequest.status
            == "PENDING",
        )
        .first()
    )

    if pending_request:

        raise HTTPException(
            status_code=400,
            detail=(
                "You already have "
                "a pending request"
            ),
        )

    requested_username = None
    requested_password_hash = None

    change_username = False
    change_password = False

    if (
        data.new_username
        and data.new_username.strip()
    ):

        requested_username = (
            validate_username(
                data.new_username
            )
        )

        if (
            requested_username
            == current_user.username
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "New username is the same "
                    "as current username"
                ),
            )

        existing = (
            db.query(User)
            .filter(
                User.username
                == requested_username,

                User.id
                != current_user.id,
            )
            .first()
        )

        if existing:

            raise HTTPException(
                status_code=400,
                detail="Username already exists",
            )

        change_username = True

    if data.new_password:

        validate_password(
            data.new_password
        )

        if verify_password(
            data.new_password,
            current_user.password_hash,
        ):

            raise HTTPException(
                status_code=400,
                detail=(
                    "New password must be "
                    "different from current password"
                ),
            )

        requested_password_hash = (
            hash_password(
                data.new_password
            )
        )

        change_password = True

    if (
        not change_username
        and not change_password
    ):

        raise HTTPException(
            status_code=400,
            detail="No changes requested",
        )

    request = CredentialChangeRequest(
        user_id=current_user.id,
        agency_id=current_user.agency_id,
        requested_username=requested_username,
        requested_password_hash=(
            requested_password_hash
        ),
        change_username=change_username,
        change_password=change_password,
        status="PENDING",
    )

    db.add(request)

    db.commit()

    db.refresh(request)

    return serialize_request(
        db,
        request,
    )


# =========================================================
# COUNTER - MY REQUESTS
# =========================================================

@router.get("/me/change-requests")
def my_change_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    requests = (
        db.query(
            CredentialChangeRequest
        )
        .filter(
            CredentialChangeRequest.user_id
            == current_user.id
        )
        .order_by(
            CredentialChangeRequest.id.desc()
        )
        .all()
    )

    return [
        serialize_request(
            db,
            request,
        )
        for request in requests
    ]


# =========================================================
# ADMIN - LIST REQUESTS
# =========================================================

@router.get("/admin/change-requests")
def admin_change_requests(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    query = db.query(
        CredentialChangeRequest
    )

    if status:

        query = query.filter(
            CredentialChangeRequest.status
            == status.upper()
        )

    requests = (
        query
        .order_by(
            CredentialChangeRequest.id.desc()
        )
        .all()
    )

    return [
        serialize_request(
            db,
            request,
        )
        for request in requests
    ]


# =========================================================
# ADMIN - APPROVE REQUEST
# =========================================================

@router.post(
    "/admin/change-requests/{request_id}/approve"
)
def approve_change_request(
    request_id: int,
    data: CredentialRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    request = (
        db.query(
            CredentialChangeRequest
        )
        .filter(
            CredentialChangeRequest.id
            == request_id
        )
        .first()
    )

    if not request:

        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    if request.status != "PENDING":

        raise HTTPException(
            status_code=400,
            detail=(
                "Request has already been reviewed"
            ),
        )

    user = (
        db.query(User)
        .filter(
            User.id
            == request.user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if (
        request.change_username
        and request.requested_username
    ):

        existing = (
            db.query(User)
            .filter(
                User.username
                == request.requested_username,

                User.id
                != user.id,
            )
            .first()
        )

        if existing:

            raise HTTPException(
                status_code=400,
                detail=(
                    "Requested username "
                    "is no longer available"
                ),
            )

        user.username = (
            request.requested_username
        )

    if (
        request.change_password
        and request.requested_password_hash
    ):

        user.password_hash = (
            request.requested_password_hash
        )

    request.status = "APPROVED"

    request.reviewed_by_user_id = (
        current_user.id
    )

    request.review_note = (
        data.note.strip()
        if data.note
        else None
    )

    request.reviewed_at = (
        datetime.utcnow()
    )

    db.commit()

    db.refresh(request)

    return serialize_request(
        db,
        request,
    )


# =========================================================
# ADMIN - REJECT REQUEST
# =========================================================

@router.post(
    "/admin/change-requests/{request_id}/reject"
)
def reject_change_request(
    request_id: int,
    data: CredentialRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_super_admin
    ),
):

    request = (
        db.query(
            CredentialChangeRequest
        )
        .filter(
            CredentialChangeRequest.id
            == request_id
        )
        .first()
    )

    if not request:

        raise HTTPException(
            status_code=404,
            detail="Request not found",
        )

    if request.status != "PENDING":

        raise HTTPException(
            status_code=400,
            detail=(
                "Request has already been reviewed"
            ),
        )

    request.status = "REJECTED"

    request.reviewed_by_user_id = (
        current_user.id
    )

    request.review_note = (
        data.note.strip()
        if data.note
        else None
    )

    request.reviewed_at = (
        datetime.utcnow()
    )

    db.commit()

    db.refresh(request)

    return serialize_request(
        db,
        request,
    )