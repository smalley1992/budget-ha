import asyncio
import logging
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from ..database import get_db
from ..services.ai_import import build_import_prompt, call_google_ai, validate_ai_import_file
from ..services.serializers import budget_line_out, debt_out, savings_pot_out


router = APIRouter(prefix="/api/ai-import", tags=["ai-import"])
logger = logging.getLogger("app.ai_import")



@router.get("/config")
def ai_import_config() -> dict:
    settings = get_settings()
    return {
        "configured": bool(settings.google_ai_api_key.strip()),
        "model": settings.google_ai_model,
        "daily_request_design": "one request per uploaded document",
    }


def _context_for_import(db: Session, period: str, view: str) -> dict:
    users = db.query(models.User).order_by(models.User.id).all()
    visible_user_ids = {user.id for user in users}
    if view != "combined":
        visible_user_ids = {user.id for user in users if user.slug == view}

    month = db.query(models.Month).filter(models.Month.period == period).one_or_none()
    lines = []
    if month and visible_user_ids:
        budget_rows = (
            db.query(models.BudgetLine)
            .filter(models.BudgetLine.month_id == month.id, models.BudgetLine.user_id.in_(visible_user_ids))
            .all()
        )
        for row in budget_rows:
            data = budget_line_out(db, row)
            data.pop("paid_date", None)
            lines.append(data)

    debts = [debt_out(db, row) for row in db.query(models.Debt).filter(models.Debt.user_id.in_(visible_user_ids)).all()] if visible_user_ids else []
    savings = [savings_pot_out(db, row) for row in db.query(models.SavingsPot).filter(models.SavingsPot.user_id.in_(visible_user_ids)).all()] if visible_user_ids else []
    categories = [{"kind": row.kind, "name": row.name} for row in db.query(models.Category).order_by(models.Category.kind, models.Category.name).all()]
    return {
        "users": [{"id": user.slug, "name": user.name} for user in users],
        "existing_budget_lines": lines,
        "debts": debts,
        "savings_pots": savings,
        "categories": categories,
    }


@router.post("/preview")
async def preview_ai_import(
    period: str = Form(...),
    view: str = Form("combined"),
    api_key: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    logger.info(f"Received AI import preview request: period={period}, view={view}, filename={file.filename}")
    content = await file.read()
    mime_type = validate_ai_import_file(file, len(content))
    settings = get_settings()
    context = _context_for_import(db, period, view)
    prompt = build_import_prompt(period, view, context)
    
    result = await asyncio.to_thread(
        call_google_ai,
        api_key.strip() or settings.google_ai_api_key,
        settings.google_ai_model,
        prompt,
        mime_type,
        content
    )
    return {
        "document_type": result.get("document_type", "unknown"),
        "summary": result.get("summary", ""),
        "proposals": result.get("proposals", []),
    }
