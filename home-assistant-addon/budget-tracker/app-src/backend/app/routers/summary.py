from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..services.budget_totals import summary_for_view

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=schemas.SummaryOut)
def get_summary(
    period: str = Query(pattern=r"^\d{4}-\d{2}$"),
    view: schemas.ViewSlug = "combined",
    db: Session = Depends(get_db),
) -> dict:
    return summary_for_view(db, period, view)
