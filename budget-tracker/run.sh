#!/usr/bin/env sh
set -eu

APP_DATA_DIR="${APP_DATA_DIR:-/data/budget-tracker}"
OPTIONS_FILE="${OPTIONS_FILE:-/data/options.json}"

mkdir -p "${APP_DATA_DIR}/data" "${APP_DATA_DIR}/uploads"

MAX_UPLOAD_MB="$(python - <<'PY'
import json
from pathlib import Path

path = Path("/data/options.json")
if path.exists():
    try:
        print(json.loads(path.read_text()).get("max_upload_mb", 10))
    except Exception:
        print(10)
else:
    print(10)
PY
)"

GOOGLE_AI_API_KEY="$(python - <<'PY'
import json
from pathlib import Path

path = Path("/data/options.json")
if path.exists():
    try:
        print(json.loads(path.read_text()).get("google_ai_api_key", ""))
    except Exception:
        print("")
else:
    print("")
PY
)"

export DATABASE_URL="${DATABASE_URL:-sqlite:///${APP_DATA_DIR}/data/budget_tracker.db}"
export UPLOAD_DIR="${UPLOAD_DIR:-${APP_DATA_DIR}/uploads}"
export MAX_UPLOAD_MB
export GOOGLE_AI_API_KEY
export FRONTEND_DIST_DIR="${FRONTEND_DIST_DIR:-/app/frontend}"
export FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-http://localhost:8099}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8099
