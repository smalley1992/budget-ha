from pathlib import Path
import re
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from ..config import get_settings


ALLOWED_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}

STORED_FILENAME_PATTERN = re.compile(r"^[a-f0-9]{32}(\.jpg|\.jpeg|\.png|\.webp|\.pdf)$")


def upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def validate_upload(file: UploadFile, size_bytes: int) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    expected_type = ALLOWED_TYPES.get(suffix)
    if expected_type is None:
        raise HTTPException(status_code=400, detail="Unsupported file extension")
    if file.content_type != expected_type:
        raise HTTPException(status_code=400, detail="File MIME type does not match its extension")
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(status_code=413, detail="File is too large")
    return suffix


def stored_name_for(suffix: str) -> str:
    return f"{uuid4().hex}{suffix}"


def upload_path_for(stored_filename: str) -> Path:
    if not STORED_FILENAME_PATTERN.match(stored_filename):
        raise HTTPException(status_code=400, detail="Invalid attachment filename")
    root = upload_root().resolve()
    path = (root / stored_filename).resolve()
    if root != path.parent:
        raise HTTPException(status_code=400, detail="Invalid attachment path")
    return path
