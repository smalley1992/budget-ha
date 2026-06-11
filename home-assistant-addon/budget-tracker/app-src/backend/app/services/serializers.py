from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..money import from_cents


def income_line_out(line: models.IncomeLine) -> dict:
    return {
        "id": line.id,
        "user_id": line.user.slug,
        "period": line.month.period,
        "name": line.name,
        "amount": from_cents(line.amount_cents),
        "is_static": line.is_static,
        "notes": line.notes,
    }


def budget_line_out(db: Session, line: models.BudgetLine) -> dict:
    attachment_count = (
        db.query(func.count(models.Attachment.id))
        .filter(models.Attachment.budget_line_id == line.id)
        .scalar()
    )
    return {
        "id": line.id,
        "user_id": line.user.slug,
        "period": line.month.period,
        "type": line.type,
        "name": line.name,
        "amount": from_cents(line.amount_cents),
        "due_day": line.due_day,
        "status": line.status,
        "paid_date": line.paid_date,
        "is_static": line.is_static,
        "notes": line.notes,
        "linked_debt_id": line.linked_debt_id,
        "linked_savings_pot_id": line.linked_savings_pot_id,
        "attachment_count": attachment_count or 0,
    }


def debt_out(db: Session, debt: models.Debt) -> dict:
    paid = (
        db.query(func.coalesce(func.sum(models.DebtTransaction.amount_cents), 0))
        .filter(models.DebtTransaction.debt_id == debt.id)
        .scalar()
    )
    return {
        "id": debt.id,
        "user_id": debt.user.slug,
        "name": debt.name,
        "starting_balance": from_cents(debt.starting_balance_cents),
        "paid_amount": from_cents(paid),
        "current_balance": from_cents(debt.starting_balance_cents - paid),
        "notes": debt.notes,
    }


def savings_pot_out(db: Session, pot: models.SavingsPot) -> dict:
    contributed = (
        db.query(func.coalesce(func.sum(models.SavingsTransaction.amount_cents), 0))
        .filter(models.SavingsTransaction.savings_pot_id == pot.id)
        .scalar()
    )
    return {
        "id": pot.id,
        "user_id": pot.user.slug,
        "name": pot.name,
        "starting_balance": from_cents(pot.starting_balance_cents),
        "contributed_amount": from_cents(contributed),
        "current_balance": from_cents(pot.starting_balance_cents + contributed),
        "target_amount": from_cents(pot.target_amount_cents) if pot.target_amount_cents is not None else None,
        "notes": pot.notes,
    }


def attachment_out(attachment: models.Attachment) -> dict:
    return {
        "id": attachment.id,
        "budget_line_id": attachment.budget_line_id,
        "original_filename": attachment.original_filename,
        "content_type": attachment.content_type,
        "size_bytes": attachment.size_bytes,
        "created_at": attachment.created_at,
    }
