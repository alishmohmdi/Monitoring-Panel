from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from fastapi.security import (
    OAuth2PasswordRequestForm,
)

from sqlalchemy.orm import Session

from database.db import get_db

from database.models import (
    Counter,
    User,
)

from services.auth_service import (
    create_access_token,
    verify_password,
)

from services.auth_dependency import (
    get_current_user,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(
            User.username
            == form_data.username
        )
        .first()
    )

    if not user or not verify_password(
        form_data.password,
        user.password_hash,
    ):

        raise HTTPException(
            status_code=401,
            detail="Username or password is incorrect",
        )

    if not user.is_active:

        raise HTTPException(
            status_code=403,
            detail="User is inactive",
        )

    if user.role == "COUNTER":

        if user.counter_id is None:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Counter profile is not assigned "
                    "to this user"
                ),
            )

        counter = (
            db.query(Counter)
            .filter(
                Counter.id
                == user.counter_id
            )
            .first()
        )

        if not counter:

            raise HTTPException(
                status_code=403,
                detail="Counter profile not found",
            )

        if not counter.is_active:

            raise HTTPException(
                status_code=403,
                detail="Counter is inactive",
            )

        email = (
            user.email.strip()
            if user.email
            else ""
        )

        phone = (
            counter.phone.strip()
            if counter.phone
            else ""
        )

        if not email or not phone:

            raise HTTPException(
                status_code=403,
                detail=(
                    "Counter email and phone number "
                    "are required. Please contact admin."
                ),
            )

    user.last_login_at = (
        datetime.utcnow()
    )

    db.commit()

    token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        agency_id=user.agency_id,
    )

    return {
        "access_token":
            token,

        "token_type":
            "bearer",

        "user": {
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

            "agency_id":
                user.agency_id,

            "counter_id":
                user.counter_id,

            "profile_complete":
                True,
        },
    }


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):

    phone = None

    profile_complete = True

    if current_user.role == "COUNTER":

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

        phone = (
            counter.phone
            if counter
            else None
        )

        profile_complete = bool(
            current_user.email
            and current_user.email.strip()
            and phone
            and phone.strip()
        )

    return {
        "id":
            current_user.id,

        "username":
            current_user.username,

        "full_name":
            current_user.full_name,

        "email":
            current_user.email,

        "phone":
            phone,

        "role":
            current_user.role,

        "agency_id":
            current_user.agency_id,

        "counter_id":
            current_user.counter_id,

        "is_active":
            current_user.is_active,

        "profile_complete":
            profile_complete,
    }