from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import (
    Change,
    Route,
    Assignment,
    Task,
)


router = APIRouter(
    prefix="/changes",
    tags=["Changes"]
)


class ChangeCreate(BaseModel):
    route_id: int

    hotel_name: str | None = None
    package_name: str | None = None

    change_type: str

    old_value: str | None = None
    new_value: str | None = None

    old_price: float | None = None
    new_price: float | None = None


class ChangeResponse(BaseModel):
    id: int
    route_id: int

    hotel_name: str | None
    package_name: str | None

    change_type: str

    old_value: str | None
    new_value: str | None

    old_price: float | None
    new_price: float | None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[ChangeResponse])
def get_changes(db: Session = Depends(get_db)):

    return (
        db.query(Change)
        .order_by(Change.id.desc())
        .all()
    )


@router.post("/", response_model=ChangeResponse)
def create_change(
    data: ChangeCreate,
    db: Session = Depends(get_db)
):

    route = (
        db.query(Route)
        .filter(Route.id == data.route_id)
        .first()
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Route not found"
        )

    change = Change(
        route_id=data.route_id,
        hotel_name=data.hotel_name,
        package_name=data.package_name,
        change_type=data.change_type,
        old_value=data.old_value,
        new_value=data.new_value,
        old_price=data.old_price,
        new_price=data.new_price,
    )

    db.add(change)
    db.commit()
    db.refresh(change)

    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.route_id == data.route_id
        )
        .first()
    )

    if assignment:

        created_at = datetime.utcnow()
        deadline = created_at + timedelta(hours=2)

        task = Task(
            change_id=change.id,
            counter_id=assignment.counter_id,
            status="Pending",
            created_at=created_at,
            deadline=deadline,
        )

        db.add(task)
        db.commit()

    return change


@router.get("/{change_id}", response_model=ChangeResponse)
def get_change(
    change_id: int,
    db: Session = Depends(get_db)
):

    change = (
        db.query(Change)
        .filter(Change.id == change_id)
        .first()
    )

    if not change:
        raise HTTPException(
            status_code=404,
            detail="Change not found"
        )

    return change