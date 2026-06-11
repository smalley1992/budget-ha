from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..money import from_cents


EMPTY_TOTALS = {
    "income": 0,
    "bills": 0,
    "expenses": 0,
    "savings_contributions": 0,
    "debt_payments": 0,
    "outgoings": 0,
    "leftover": 0,
}


def totals_for_user(db: Session, period: str, user_slug: str) -> dict:
    user = db.query(models.User).filter(models.User.slug == user_slug).one_or_none()
    month = db.query(models.Month).filter(models.Month.period == period).one_or_none()
    if not user or not month:
        return EMPTY_TOTALS.copy()

    income = (
        db.query(func.coalesce(func.sum(models.IncomeLine.amount_cents), 0))
        .filter(models.IncomeLine.user_id == user.id, models.IncomeLine.month_id == month.id)
        .scalar()
    )
    rows = (
        db.query(models.BudgetLine.type, func.coalesce(func.sum(models.BudgetLine.amount_cents), 0))
        .filter(models.BudgetLine.user_id == user.id, models.BudgetLine.month_id == month.id)
        .group_by(models.BudgetLine.type)
        .all()
    )
    by_type = {kind: cents for kind, cents in rows}
    bills = by_type.get("bill", 0)
    expenses = by_type.get("expense", 0)
    savings = by_type.get("savings_contribution", 0)
    debt = by_type.get("debt_payment", 0)
    outgoings = bills + expenses + savings + debt

    return {
        "income": from_cents(income),
        "bills": from_cents(bills),
        "expenses": from_cents(expenses),
        "savings_contributions": from_cents(savings),
        "debt_payments": from_cents(debt),
        "outgoings": from_cents(outgoings),
        "leftover": from_cents(income - outgoings),
    }


def summary_for_view(db: Session, period: str, view: str) -> dict:
    if view != "combined":
        return {"period": period, "view": view, "totals": totals_for_user(db, period, view), "by_user": None}

    users = db.query(models.User).order_by(models.User.id).all()
    by_user = {user.slug: totals_for_user(db, period, user.slug) for user in users}
    totals = {}
    for key in EMPTY_TOTALS:
        totals[key] = round(sum(row[key] for row in by_user.values()), 2)
    return {"period": period, "view": "combined", "totals": totals, "by_user": by_user}
