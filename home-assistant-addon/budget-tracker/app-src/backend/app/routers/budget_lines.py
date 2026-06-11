from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..database import get_db
from ..money import to_cents
from ..services.common import get_or_create_month, get_user
from ..services.ledger import remove_budget_line_ledger, sync_budget_line_ledger
from ..services.serializers import budget_line_out

router = APIRouter(prefix="/api/budget-lines", tags=["budget-lines"])


def _validate_links(db: Session, user: models.User, line_type: str, debt_id: int | None, pot_id: int | None) -> tuple[int | None, int | None]:
    if line_type == "debt_payment":
        if debt_id is not None:
            debt = db.get(models.Debt, debt_id)
            if not debt or debt.user_id != user.id:
                raise HTTPException(status_code=400, detail="Linked debt is invalid for this user")
        return debt_id, None

    if line_type == "savings_contribution":
        if pot_id is None:
            pot = (
                db.query(models.SavingsPot)
                .filter(models.SavingsPot.user_id == user.id, models.SavingsPot.name == "General savings")
                .one_or_none()
            )
            if pot is None:
                pot = models.SavingsPot(
                    user_id=user.id,
                    name="General savings",
                    starting_balance_cents=0,
                    target_amount_cents=None,
                    notes="Default pot for uncategorised savings contributions.",
                )
                db.add(pot)
                db.flush()
            return None, pot.id
        if pot_id is not None:
            pot = db.get(models.SavingsPot, pot_id)
            if not pot or pot.user_id != user.id:
                raise HTTPException(status_code=400, detail="Linked savings pot is invalid for this user")
        return None, pot_id

    return None, None


@router.get("", response_model=list[schemas.BudgetLineOut])
def list_budget_lines(
    period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    user_id: schemas.UserSlug = Query(min_length=1),
    db: Session = Depends(get_db),
) -> list[dict]:
    user = get_user(db, user_id)
    month = get_or_create_month(db, period)
    db.commit()
    lines = (
        db.query(models.BudgetLine)
        .filter(models.BudgetLine.user_id == user.id, models.BudgetLine.month_id == month.id)
        .order_by(models.BudgetLine.due_day.is_(None), models.BudgetLine.due_day, models.BudgetLine.id)
        .all()
    )
    return [budget_line_out(db, line) for line in lines]


@router.post("", response_model=schemas.BudgetLineOut)
def create_budget_line(payload: schemas.BudgetLineCreate, db: Session = Depends(get_db)) -> dict:
    user = get_user(db, payload.user_id)
    month = get_or_create_month(db, payload.period)
    debt_id, pot_id = _validate_links(db, user, payload.type, payload.linked_debt_id, payload.linked_savings_pot_id)
    line = models.BudgetLine(
        user_id=user.id,
        month_id=month.id,
        type=payload.type,
        name=payload.name,
        amount_cents=to_cents(payload.amount),
        due_day=payload.due_day,
        status=payload.status,
        paid_date=payload.paid_date or (date.today() if payload.status == "paid" else None),
        is_static=payload.is_static,
        notes=payload.notes,
        linked_debt_id=debt_id,
        linked_savings_pot_id=pot_id,
    )
    db.add(line)
    db.flush()
    sync_budget_line_ledger(db, line)
    db.commit()
    db.refresh(line)
    return budget_line_out(db, line)


@router.patch("/{line_id}", response_model=schemas.BudgetLineOut)
def update_budget_line(
    line_id: int,
    payload: schemas.BudgetLineUpdate,
    db: Session = Depends(get_db),
) -> dict:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    updates = payload.model_dump(exclude_unset=True)
    new_type = updates.get("type", line.type)
    new_debt_id = updates.get("linked_debt_id", line.linked_debt_id)
    new_pot_id = updates.get("linked_savings_pot_id", line.linked_savings_pot_id)
    debt_id, pot_id = _validate_links(db, line.user, new_type, new_debt_id, new_pot_id)

    for field in ("type", "name", "due_day", "status", "paid_date", "is_static", "notes"):
        if field in updates:
            setattr(line, field, updates[field])
    if "amount" in updates:
        line.amount_cents = to_cents(updates["amount"])
    line.linked_debt_id = debt_id
    line.linked_savings_pot_id = pot_id
    if line.status == "paid" and line.paid_date is None:
        line.paid_date = date.today()
    if line.status == "planned":
        line.paid_date = None
    sync_budget_line_ledger(db, line)
    db.commit()
    db.refresh(line)
    return budget_line_out(db, line)


@router.post("/{line_id}/mark-paid", response_model=schemas.BudgetLineOut)
def mark_paid(line_id: int, db: Session = Depends(get_db)) -> dict:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    line.status = "paid"
    line.paid_date = date.today()
    sync_budget_line_ledger(db, line)
    db.commit()
    db.refresh(line)
    return budget_line_out(db, line)


@router.post("/{line_id}/mark-planned", response_model=schemas.BudgetLineOut)
def mark_planned(line_id: int, db: Session = Depends(get_db)) -> dict:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    line.status = "planned"
    line.paid_date = None
    sync_budget_line_ledger(db, line)
    db.commit()
    db.refresh(line)
    return budget_line_out(db, line)


@router.delete("/{line_id}", status_code=204)
def delete_budget_line(line_id: int, db: Session = Depends(get_db)) -> None:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    remove_budget_line_ledger(db, line.id)
    upload_dir = Path(get_settings().upload_dir)
    for attachment in list(line.attachments):
        path = upload_dir / attachment.stored_filename
        if path.exists():
            path.unlink()
    db.delete(line)
    db.commit()
