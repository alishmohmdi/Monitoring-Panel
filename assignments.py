from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Assignment, Route, Counter


router = APIRouter(
    prefix="/assignments",
    tags=["Assignments"]
)


class AssignmentCreate(BaseModel):
    route_id: int
    counter_id: int


class AssignmentResponse(BaseModel):
    id: int
    route_id: int
    route_name: str

    counter_id: int
    counter_name: str


@router.get("/", response_model=list[AssignmentResponse])
def get_assignments(db: Session = Depends(get_db)):

    assignments = (
        db.query(Assignment)
        .order_by(Assignment.id.desc())
        .all()
    )

    result = []

    for assignment in assignments:

        route = (
            db.query(Route)
            .filter(Route.id == assignment.route_id)
            .first()
        )

        counter = (
            db.query(Counter)
            .filter(Counter.id == assignment.counter_id)
            .first()
        )

        result.append({
            "id": assignment.id,

            "route_id": assignment.route_id,
            "route_name": route.name if route else "Unknown",

            "counter_id": assignment.counter_id,
            "counter_name": counter.name if counter else "Unknown",
        })

    return result


@router.post("/", response_model=AssignmentResponse)
def create_assignment(
    data: AssignmentCreate,
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

    counter = (
        db.query(Counter)
        .filter(Counter.id == data.counter_id)
        .first()
    )

    if not counter:
        raise HTTPException(
            status_code=404,
            detail="Counter not found"
        )

    existing = (
        db.query(Assignment)
        .filter(
            Assignment.route_id == data.route_id,
            Assignment.counter_id == data.counter_id
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Assignment already exists"
        )

    assignment = Assignment(
        route_id=data.route_id,
        counter_id=data.counter_id
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "id": assignment.id,

        "route_id": route.id,
        "route_name": route.name,

        "counter_id": counter.id,
        "counter_name": counter.name,
    }


@router.delete("/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db)
):

    assignment = (
        db.query(Assignment)
        .filter(Assignment.id == assignment_id)
        .first()
    )

    if not assignment:
        raise HTTPException(
            status_code=404,
            detail="Assignment not found"
        )

    db.delete(assignment)
    db.commit()

    return {
        "success": True,
        "message": "Assignment deleted"
    }