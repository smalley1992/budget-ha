import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..money import from_cents, to_cents

router = APIRouter(prefix="/api/users", tags=["users"])


def _user_out(user: models.User) -> dict:
    return {
        "id": user.slug,
        "name": user.name,
        "icon": user.icon,
        "salary": from_cents(user.salary_cents),
    }


def _slug_base(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    if not slug:
        slug = "user"
    if slug == "combined":
        slug = "family-member"
    return slug[:32].strip("-") or "user"


def _unique_slug(db: Session, name: str) -> str:
    base = _slug_base(name)
    slug = base
    suffix = 2
    while db.query(models.User).filter(models.User.slug == slug).one_or_none():
        suffix_text = f"-{suffix}"
        slug = f"{base[: 32 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return slug


@router.get("", response_model=list[schemas.UserOut])
def list_users(db: Session = Depends(get_db)) -> list[dict]:
    users = db.query(models.User).order_by(models.User.id).all()
    return [_user_out(user) for user in users]


@router.post("", response_model=schemas.UserOut)
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    user = models.User(
        slug=_unique_slug(db, name),
        name=name,
        icon=(payload.icon or name[:1]).strip()[:8],
        salary_cents=to_cents(payload.salary),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.patch("/{slug}", response_model=schemas.UserOut)
def update_user(slug: schemas.UserSlug, payload: schemas.UserUpdate, db: Session = Depends(get_db)) -> dict:
    user = db.query(models.User).filter(models.User.slug == slug).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"]:
        user.name = updates["name"].strip()
    if "icon" in updates:
        user.icon = (updates["icon"] or "").strip()[:8]
    if "salary" in updates and updates["salary"] is not None:
        user.salary_cents = to_cents(updates["salary"])
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.delete("/{slug}", status_code=204)
def delete_user(slug: schemas.UserSlug, db: Session = Depends(get_db)) -> None:
    user = db.query(models.User).filter(models.User.slug == slug).one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    blockers = [
        db.query(models.IncomeLine).filter(models.IncomeLine.user_id == user.id).first(),
        db.query(models.BudgetLine).filter(models.BudgetLine.user_id == user.id).first(),
        db.query(models.Debt).filter(models.Debt.user_id == user.id).first(),
        db.query(models.SavingsPot).filter(models.SavingsPot.user_id == user.id).first(),
    ]
    if any(blockers):
        raise HTTPException(status_code=409, detail="User has budget data and cannot be deleted")

    db.delete(user)
    db.commit()
