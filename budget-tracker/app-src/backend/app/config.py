from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self) -> None:
        default_db = f"sqlite:///{(PROJECT_ROOT / 'data' / 'budget_tracker.db').as_posix()}"
        self.database_url = os.getenv("DATABASE_URL", default_db)
        self.upload_dir = os.getenv("UPLOAD_DIR", str(PROJECT_ROOT / "uploads"))
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
        self.frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
        self.google_ai_api_key = os.getenv("GOOGLE_AI_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY") or ""
        self.google_ai_model = os.getenv("GOOGLE_AI_MODEL") or os.getenv("GOOGLE_GENAI_MODEL") or "gemma-4-31b-it"
        frontend_dist_dir = os.getenv("FRONTEND_DIST_DIR", "")
        self.frontend_dist_dir = Path(frontend_dist_dir) if frontend_dist_dir else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
