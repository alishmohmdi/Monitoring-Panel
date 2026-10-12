from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Task, Change, Counter


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"]
)


class TaskCreate(BaseModel):
    change_id: int
    counter_id: int | None = None


class TaskResponse(BaseModel):
    id: int
    change_id: int
    counter_id: int | None
    status: str
    created_at: datetime
    deadline: datetime | None
    completed_at: datetime | None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[TaskResponse])
def get_tasks(db: Session = Depends(get_db)):

    tasks = (
        db.query(Task)
        .order_by(Task.id.desc())
        .all()
    )

    now = datetime.utcnow()

    changed = False

    for task in tasks:
        if (
            task.status == "Pending"
            and task.deadline
            and now > task.deadline
        ):
            task.status = "Late"
            changed = True

    if changed:
        db.commit()

    return tasks


@router.post("/", response_model=TaskResponse)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db)
):

    change = (
        db.query(Change)
        .filter(Change.id == data.change_id)
        .first()
    )

    if not change:
        raise HTTPException(
            status_code=404,
            detail="Change not found"
        )

    if data.counter_id is not None:

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

    created_at = datetime.utcnow()
    deadline = created_at + timedelta(hours=2)

    task = Task(
        change_id=data.change_id,
        counter_id=data.counter_id,
        status="Pending",
        created_at=created_at,
        deadline=deadline
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.post("/{task_id}/done", response_model=TaskResponse)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db)
):

    task = (
        db.query(Task)
        .filter(Task.id == task_id)
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    task.status = "Done"
    task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    return task


@router.get("/pending", response_model=list[TaskResponse])
def get_pending_tasks(db: Session = Depends(get_db)):

    return (
        db.query(Task)
        .filter(Task.status == "Pending")
        .order_by(Task.id.desc())
        .all()
    )


@router.get("/late", response_model=list[TaskResponse])
def get_late_tasks(db: Session = Depends(get_db)):

    now = datetime.utcnow()

    tasks = (
        db.query(Task)
        .filter(
            Task.status == "Pending",
            Task.deadline < now
        )
        .all()
    )

    for task in tasks:
        task.status = "Late"

    if tasks:
        db.commit()

    return tasks