from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..money import to_cents
from ..services.common import get_user
from ..services.serializers import debt_out

router = APIRouter(prefix="/api/debts", tags=["debts"])


@router.get("", response_model=list[schemas.DebtOut])
def list_debts(user_id: schemas.UserSlug = Query(min_length=1), db: Session = Depends(get_db)) -> list[dict]:
    user = get_user(db, user_id)
    debts = db.query(models.Debt).filter(models.Debt.user_id == user.id).order_by(models.Debt.id).all()
    return [debt_out(db, debt) for debt in debts]


@router.post("", response_model=schemas.DebtOut)
def create_debt(payload: schemas.DebtCreate, db: Session = Depends(get_db)) -> dict:
    user = get_user(db, payload.user_id)
    debt = models.Debt(
        user_id=user.id,
        name=payload.name,
        starting_balance_cents=to_cents(payload.starting_balance),
        notes=payload.notes,
    )
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt_out(db, debt)


@router.patch("/{debt_id}", response_model=schemas.DebtOut)
def update_debt(debt_id: int, payload: schemas.DebtUpdate, db: Session = Depends(get_db)) -> dict:
    debt = db.get(models.Debt, debt_id)
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        debt.name = updates["name"]
    if "starting_balance" in updates:
        debt.starting_balance_cents = to_cents(updates["starting_balance"])
    if "notes" in updates:
        debt.notes = updates["notes"]
    db.commit()
    db.refresh(debt)
    return debt_out(db, debt)


@router.delete("/{debt_id}", status_code=204)
def delete_debt(debt_id: int, db: Session = Depends(get_db)) -> None:
    debt = db.get(models.Debt, debt_id)
    if not debt:
        raise HTTPException(status_code=404, detail="Debt not found")
    linked = db.query(models.BudgetLine).filter(models.BudgetLine.linked_debt_id == debt_id).first()
    if linked:
        raise HTTPException(status_code=409, detail="Debt is linked to budget lines")
    db.delete(debt)
    db.commit()
