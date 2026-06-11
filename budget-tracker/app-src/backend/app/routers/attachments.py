from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services.serializers import attachment_out
from ..services.uploads import stored_name_for, upload_path_for, validate_upload

router = APIRouter(tags=["attachments"])


@router.get("/api/budget-lines/{line_id}/attachments", response_model=list[schemas.AttachmentOut])
def list_attachments(line_id: int, db: Session = Depends(get_db)) -> list[dict]:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    attachments = (
        db.query(models.Attachment)
        .filter(models.Attachment.budget_line_id == line_id)
        .order_by(models.Attachment.created_at.desc())
        .all()
    )
    return [attachment_out(attachment) for attachment in attachments]


@router.post("/api/budget-lines/{line_id}/attachments", response_model=schemas.AttachmentOut)
async def upload_attachment(
    line_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    line = db.get(models.BudgetLine, line_id)
    if not line:
        raise HTTPException(status_code=404, detail="Budget line not found")
    content = await file.read()
    suffix = validate_upload(file, len(content))
    stored_filename = stored_name_for(suffix)
    path = upload_path_for(stored_filename)
    path.write_bytes(content)

    attachment = models.Attachment(
        budget_line_id=line.id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment_out(attachment)


@router.get("/api/attachments/{attachment_id}/download")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)) -> FileResponse:
    attachment = db.get(models.Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = upload_path_for(attachment.stored_filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Attachment file not found")
    return FileResponse(path, media_type=attachment.content_type, filename=attachment.original_filename)


@router.delete("/api/attachments/{attachment_id}", status_code=204)
def delete_attachment(attachment_id: int, db: Session = Depends(get_db)) -> None:
    attachment = db.get(models.Attachment, attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = upload_path_for(attachment.stored_filename)
    if path.exists():
        path.unlink()
    db.delete(attachment)
    db.commit()
