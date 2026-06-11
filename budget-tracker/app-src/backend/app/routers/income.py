from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..money import to_cents
from ..services.common import get_or_create_month, get_user
from ..services.serializers import income_line_out

router = APIRouter(prefix="/api/income-lines", tags=["income"])


@router.get("", response_model=list[schemas.IncomeLineOut])
def list_income_lines(
    period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    user_id: schemas.UserSlug = Query(min_length=1),
    db: Session = Depends(get_db),
) -> list[dict]:
    user = get_user(db, user_id)
    month = get_or_create_month(db, period)
    db.commit()
    lines = (
        db.query(models.IncomeLine)
        .filter(models.IncomeLine.user_id == user.id, models.IncomeLine.month_id == month.id)
        .order_by(models.IncomeLine.id)
        .all()
    )
    return [income_line_out(line) for line in lines]


@router.post("", response_model=schemas.IncomeLineOut)
def create_income_line(payload: schemas.IncomeLineCreate, db: Session = Depends(get_db)) -> dict:
    user = get_user(db, payload.user_id)
    month = get_or_create_month(db, payload.period)
    line = models.IncomeLine(
        user_id=user.id,
        month_id=month.id,
        name=payload.name,
        amount_cents=to_cents(payload.amount),
        is_static=payload.is_static,
        notes=payload.notes,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return income_line_out(line)


@router.patch("/{line_id}", response_model=schemas.IncomeLineOut)
def update_income_line(
    line_id: int,
    payload: schemas.IncomeLineUpdate,
    db: Session = Depends(get_db),
) -> dict:
    line = db.get(models.IncomeLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Income line not found")
    updates = payload.model_dump(exclude_unset=True)
    for field in ("name", "is_static", "notes"):
        if field in updates:
            setattr(line, field, updates[field])
    if "amount" in updates:
        line.amount_cents = to_cents(updates["amount"])
    db.commit()
    db.refresh(line)
    return income_line_out(line)


@router.delete("/{line_id}", status_code=204)
def delete_income_line(line_id: int, db: Session = Depends(get_db)) -> None:
    line = db.get(models.IncomeLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Income line not found")
    db.delete(line)
    db.commit()
