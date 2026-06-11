from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.common import get_or_create_month
from ..services.rollover import rollover_month

router = APIRouter(prefix="/api/months", tags=["months"])


@router.get("", response_model=list[schemas.MonthOut])
def list_months(db: Session = Depends(get_db)) -> list[models.Month]:
    return db.query(models.Month).order_by(models.Month.period).all()


@router.post("", response_model=schemas.MonthOut)
def create_month(payload: schemas.MonthCreate, db: Session = Depends(get_db)) -> models.Month:
    month = get_or_create_month(db, payload.period)
    db.commit()
    db.refresh(month)
    return month


@router.post("/rollover")
def rollover(payload: schemas.RolloverRequest, db: Session = Depends(get_db)) -> dict:
    return rollover_month(db, payload.source_period, payload.target_period)
