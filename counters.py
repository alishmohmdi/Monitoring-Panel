from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Counter

router = APIRouter(
    prefix="/counters",
    tags=["Counters"]
)


class CounterCreate(BaseModel):
    name: str
    phone: str | None = None
    telegram_user_id: str | None = None
    telegram_chat_id: str | None = None


class CounterResponse(BaseModel):
    id: int
    name: str
    phone: str | None
    telegram_user_id: str | None
    telegram_chat_id: str | None
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[CounterResponse])
def get_counters(db: Session = Depends(get_db)):
    return db.query(Counter).order_by(Counter.id.desc()).all()


@router.post("/", response_model=CounterResponse)
def create_counter(
    data: CounterCreate,
    db: Session = Depends(get_db)
):

    counter = Counter(
        name=data.name,
        phone=data.phone,
        telegram_user_id=data.telegram_user_id,
        telegram_chat_id=data.telegram_chat_id,
    )

    db.add(counter)
    db.commit()
    db.refresh(counter)

    return counter


@router.get("/{counter_id}", response_model=CounterResponse)
def get_counter(
    counter_id: int,
    db: Session = Depends(get_db)
):

    counter = (
        db.query(Counter)
        .filter(Counter.id == counter_id)
        .first()
    )

    if not counter:
        raise HTTPException(
            status_code=404,
            detail="Counter not found"
        )

    return counter