import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import get_settings
from .. import database
from ..database import Base
from ..services.common import seed_default_categories
from ..services.migrations import ensure_user_profile_columns
from ..services.uploads import ALLOWED_TYPES, STORED_FILENAME_PATTERN


router = APIRouter(prefix="/api/backups", tags=["backups"])

ALLOWED_BACKUP_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def _database_path() -> Path:
    db_path = database.sqlite_database_path()
    if db_path is None:
        raise HTTPException(status_code=400, detail="Database import/export is only available for SQLite storage")
    return db_path


def _validate_sqlite_backup(path: Path) -> None:
    required_tables = {"users", "months", "categories", "income_lines", "budget_lines", "debts", "savings_pots", "attachments"}
    allowed_tables = required_tables | {"debt_transactions", "savings_transactions", "sqlite_sequence"}
    try:
        with closing(sqlite3.connect(path)) as connection:
            quick_check = connection.execute("PRAGMA quick_check").fetchone()
            if not quick_check or quick_check[0] != "ok":
                raise HTTPException(status_code=400, detail="Backup file failed SQLite integrity checks")
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            if foreign_keys:
                raise HTTPException(status_code=400, detail="Backup file has broken database links")
            objects = connection.execute("SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
            table_rows = [row for row in objects if row[0] == "table"]
            unsafe_objects = [row for row in objects if row[0] not in {"table", "index"}]
            if unsafe_objects:
                raise HTTPException(status_code=400, detail="Backup file contains unsupported database objects")
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=400, detail="Backup file is not a valid SQLite database") from exc

    table_names = {row[1] for row in table_rows}
    if not required_tables.issubset(table_names):
        raise HTTPException(status_code=400, detail="Backup file does not look like a Budget Tracker database")
    if not table_names.issubset(allowed_tables):
        raise HTTPException(status_code=400, detail="Backup file contains unexpected tables")

    with closing(sqlite3.connect(path)) as connection:
        attachment_rows = connection.execute("SELECT stored_filename, content_type FROM attachments").fetchall()
    allowed_content_types = set(ALLOWED_TYPES.values())
    for stored_filename, content_type in attachment_rows:
        if not isinstance(stored_filename, str) or not STORED_FILENAME_PATTERN.match(stored_filename):
            raise HTTPException(status_code=400, detail="Backup file contains unsafe attachment metadata")
        if content_type not in allowed_content_types:
            raise HTTPException(status_code=400, detail="Backup file contains unsupported attachment types")


def _copy_upload_to_temp(file: UploadFile) -> Path:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_BACKUP_SUFFIXES:
        raise HTTPException(status_code=400, detail="Backup file must be a .db, .sqlite, or .sqlite3 file")

    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    total = 0
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        while chunk := file.file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                temp_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="Backup file is too large")
            temp_file.write(chunk)
    return temp_path


@router.get("/database")
def export_database() -> FileResponse:
    db_path = _database_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Database file does not exist yet")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        db_path,
        media_type="application/vnd.sqlite3",
        filename=f"budget-tracker-{stamp}.sqlite3",
    )


@router.post("/database/import")
async def import_database(file: UploadFile = File(...)) -> dict:
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _copy_upload_to_temp(file)

    try:
        _validate_sqlite_backup(temp_path)
        backup_path = db_path.with_suffix(f"{db_path.suffix}.pre-restore")
        database.engine.dispose()
        if db_path.exists():
            shutil.copy2(db_path, backup_path)
        shutil.move(str(temp_path), db_path)
        Base.metadata.create_all(bind=database.engine)
        ensure_user_profile_columns(database.engine)
        with database.engine.begin() as connection:
            # Opens the replaced database once before the next user request.
            connection.exec_driver_sql("PRAGMA quick_check")

        with database.SessionLocal() as db:
            seed_default_categories(db)
        return {"ok": True, "message": "Database restored"}
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except PermissionError:
                pass
