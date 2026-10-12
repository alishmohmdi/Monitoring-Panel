from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import Route

router = APIRouter(
    prefix="/routes",
    tags=["Routes"]
)


class RouteCreate(BaseModel):
    name: str
    url: str


class RouteResponse(BaseModel):
    id: int
    name: str
    url: str
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[RouteResponse])
def get_routes(db: Session = Depends(get_db)):
    return db.query(Route).order_by(Route.id.desc()).all()


@router.post("/", response_model=RouteResponse)
def create_route(data: RouteCreate, db: Session = Depends(get_db)):

    existing_route = (
        db.query(Route)
        .filter(Route.url == data.url)
        .first()
    )

    if existing_route:
        raise HTTPException(
            status_code=400,
            detail="Route with this URL already exists"
        )

    route = Route(
        name=data.name,
        url=data.url
    )

    db.add(route)
    db.commit()
    db.refresh(route)

    return route


@router.get("/{route_id}", response_model=RouteResponse)
def get_route(route_id: int, db: Session = Depends(get_db)):

    route = (
        db.query(Route)
        .filter(Route.id == route_id)
        .first()
    )

    if not route:
        raise HTTPException(
            status_code=404,
            detail="Route not found"
        )

    return route