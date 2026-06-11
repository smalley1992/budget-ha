from sqlalchemy.orm import Session

from .. import models
from .common import get_month, get_or_create_month


def rollover_month(db: Session, source_period: str, target_period: str) -> dict:
    source = get_month(db, source_period)
    target = get_or_create_month(db, target_period)

    copied_income = 0
    copied_budget_lines = 0

    for line in db.query(models.IncomeLine).filter(
        models.IncomeLine.month_id == source.id,
        models.IncomeLine.is_static.is_(True),
    ):
        exists = db.query(models.IncomeLine).filter(
            models.IncomeLine.month_id == target.id,
            models.IncomeLine.user_id == line.user_id,
            models.IncomeLine.name == line.name,
            models.IncomeLine.amount_cents == line.amount_cents,
        ).one_or_none()
        if exists:
            continue
        db.add(
            models.IncomeLine(
                user_id=line.user_id,
                month_id=target.id,
                name=line.name,
                amount_cents=line.amount_cents,
                is_static=True,
                notes=line.notes,
            )
        )
        copied_income += 1

    for line in db.query(models.BudgetLine).filter(
        models.BudgetLine.month_id == source.id,
        models.BudgetLine.is_static.is_(True),
    ):
        exists = db.query(models.BudgetLine).filter(
            models.BudgetLine.month_id == target.id,
            models.BudgetLine.user_id == line.user_id,
            models.BudgetLine.type == line.type,
            models.BudgetLine.name == line.name,
            models.BudgetLine.amount_cents == line.amount_cents,
        ).one_or_none()
        if exists:
            continue
        db.add(
            models.BudgetLine(
                user_id=line.user_id,
                month_id=target.id,
                type=line.type,
                name=line.name,
                amount_cents=line.amount_cents,
                due_day=line.due_day,
                status="planned",
                paid_date=None,
                is_static=True,
                notes=line.notes,
                linked_debt_id=line.linked_debt_id,
                linked_savings_pot_id=line.linked_savings_pot_id,
            )
        )
        copied_budget_lines += 1

    db.commit()
    return {
        "source_period": source.period,
        "target_period": target.period,
        "copied_income_lines": copied_income,
        "copied_budget_lines": copied_budget_lines,
    }
