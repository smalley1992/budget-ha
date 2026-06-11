from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models


def get_user(db: Session, slug: str) -> models.User:
    user = db.query(models.User).filter(models.User.slug == slug).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_or_create_month(db: Session, period: str) -> models.Month:
    month = db.query(models.Month).filter(models.Month.period == period).one_or_none()
    if month:
        return month
    month = models.Month(period=period)
    db.add(month)
    db.flush()
    return month


def get_month(db: Session, period: str) -> models.Month:
    month = db.query(models.Month).filter(models.Month.period == period).one_or_none()
    if not month:
        raise HTTPException(status_code=404, detail="Month not found")
    return month


def seed_default_categories(db: Session) -> None:
    categories = [
        ("income", "Salary"),
        ("income", "Other income"),
        ("bill", "Housing"),
        ("bill", "Utilities"),
        ("bill", "Broadband"),
        ("bill", "Insurance"),
        ("expense", "Groceries"),
        ("expense", "Transport"),
        ("expense", "Subscriptions"),
        ("expense", "Household"),
        ("savings_contribution", "Emergency fund"),
        ("savings_contribution", "Holiday"),
        ("debt_payment", "Credit card"),
        ("debt_payment", "Loan"),
    ]
    for kind, name in categories:
        exists = (
            db.query(models.Category)
            .filter(models.Category.kind == kind, models.Category.name == name)
            .one_or_none()
        )
        if not exists:
            db.add(models.Category(kind=kind, name=name))
    db.commit()
