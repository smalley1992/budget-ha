from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..money import to_cents
from ..services.common import get_user
from ..services.serializers import savings_pot_out

router = APIRouter(prefix="/api/savings-pots", tags=["savings"])


@router.get("", response_model=list[schemas.SavingsPotOut])
def list_savings_pots(user_id: schemas.UserSlug = Query(min_length=1), db: Session = Depends(get_db)) -> list[dict]:
    user = get_user(db, user_id)
    pots = (
        db.query(models.SavingsPot)
        .filter(models.SavingsPot.user_id == user.id)
        .order_by(models.SavingsPot.id)
        .all()
    )
    return [savings_pot_out(db, pot) for pot in pots]


@router.post("", response_model=schemas.SavingsPotOut)
def create_savings_pot(payload: schemas.SavingsPotCreate, db: Session = Depends(get_db)) -> dict:
    user = get_user(db, payload.user_id)
    pot = models.SavingsPot(
        user_id=user.id,
        name=payload.name,
        starting_balance_cents=to_cents(payload.starting_balance),
        target_amount_cents=to_cents(payload.target_amount) if payload.target_amount is not None else None,
        notes=payload.notes,
    )
    db.add(pot)
    db.commit()
    db.refresh(pot)
    return savings_pot_out(db, pot)


@router.patch("/{pot_id}", response_model=schemas.SavingsPotOut)
def update_savings_pot(
    pot_id: int,
    payload: schemas.SavingsPotUpdate,
    db: Session = Depends(get_db),
) -> dict:
    pot = db.get(models.SavingsPot, pot_id)
    if not pot:
        raise HTTPException(status_code=404, detail="Savings pot not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        pot.name = updates["name"]
    if "starting_balance" in updates:
        pot.starting_balance_cents = to_cents(updates["starting_balance"])
    if "target_amount" in updates:
        pot.target_amount_cents = to_cents(updates["target_amount"]) if updates["target_amount"] is not None else None
    if "notes" in updates:
        pot.notes = updates["notes"]
    db.commit()
    db.refresh(pot)
    return savings_pot_out(db, pot)


@router.delete("/{pot_id}", status_code=204)
def delete_savings_pot(pot_id: int, db: Session = Depends(get_db)) -> None:
    pot = db.get(models.SavingsPot, pot_id)
    if not pot:
        raise HTTPException(status_code=404, detail="Savings pot not found")
    linked = db.query(models.BudgetLine).filter(models.BudgetLine.linked_savings_pot_id == pot_id).first()
    if linked:
        raise HTTPException(status_code=409, detail="Savings pot is linked to budget lines")
    db.delete(pot)
    db.commit()
