# Budget Tracker Handoff

Date: 2026-06-11

## Current State

This is a private household budget tracker for Chris and Jaye.

The app is implemented as:

- Backend: FastAPI, SQLAlchemy 2, Pydantic-style schemas, SQLite
- Frontend: React, Vite, TypeScript
- Storage: local SQLite database plus local uploads folder
- No authentication yet
- AI scanning support added (disabled by default, uses Gemini API with gemini-2.5-flash as default model)
- Home Assistant add-on wrapper exists and has been built/deployed by the user on their HA server

Default users:

- `chris`
- `partner`, displayed as `Jaye`

All income and budget lines belong to one user. Combined view is computed only and does not create shared records.

## Important Paths

Project root:

```text
C:\Users\small\OneDrive\Documents\Budgets and Expenses
```

Main app:

```text
backend/
frontend/
data/
uploads/
local-ai-import-tester/  # Standalone client-only HTML budget AI import tester
```

Home Assistant add-on:

```text
home-assistant-addon/budget-tracker
```

Most recent local snapshot:

```text
snapshots/budget-tracker-snapshot-20260610-221812.zip
```

Packaging script:

```powershell
.\scripts\package-home-assistant-addon.ps1
```

## Backend Notes

Main entrypoint:

```text
backend/app/main.py
```

Key behavior:

- API routes live under `/api`.
- `GET /api/health` returns `{"ok": true}`.
- Startup creates tables, runs lightweight migrations, and seeds defaults.
- If `FRONTEND_DIST_DIR` is set, FastAPI serves the built React frontend from `/`.

Important env vars:

```text
DATABASE_URL
UPLOAD_DIR
MAX_UPLOAD_MB
FRONTEND_ORIGIN
FRONTEND_DIST_DIR
GOOGLE_AI_API_KEY (fallback: GOOGLE_GENAI_API_KEY)
GOOGLE_AI_MODEL (fallback: GOOGLE_GENAI_MODEL, defaults to gemini-2.5-flash)
```

Debt/savings ledger rules are implemented:

- Planned debt payments do not reduce balances.
- Paid linked debt payments reduce debt balances.
- Unmark/edit/delete adjusts or reverses the ledger transaction.
- Planned savings contributions do not increase pot balances.
- Paid linked savings contributions increase pot balances.
- Unmark/edit/delete adjusts or reverses the ledger transaction.
- Savings contributions without a selected pot go to/create General savings.

## Frontend Notes

Main files:

```text
frontend/src/App.tsx
frontend/src/styles.css
frontend/src/api/client.ts
```

Frontend API base:

```ts
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";
```

Local Vite dev proxy sends `/api` to the backend:

```text
frontend/vite.config.ts
```

UI state:

- Selected view persists in `localStorage`.
- Views are Chris, Jaye, Combined.
- Combined is read-only and drilldown-based.
- Budget, Savings, and Debts in solo views use tabbed card lists.
- Income opens from the Income hero as a card-based editor.
- Settings contains theme/default-paid/profile/refresh controls.

Recent UI refinements:

- Mobile hero cards stay in a 2x2 grid.
- Mobile line items use name/value first, then aligned chips.
- Desktop and mobile line item chips now share styling.
- Combined Outgoings rows are compact and no longer show bulky target/status chip rows.
- Combined Savings shows Chris/Jaye savings overview first, then pots.
- Pot cards can show `+£X this month`.
- Combined Leftover uses the same card language and shows income/outgoings/salary when available.
- Solo Debts only shows `Needs target` summary when there is non-zero unallocated paid debt.

## Home Assistant Add-on

Add-on folder:

```text
home-assistant-addon/budget-tracker
```

Files:

```text
config.yaml
Dockerfile
run.sh
icon.png
logo.png
README.md
app-src/
```

Add-on behavior:

- Runs as a standalone web app.
- Does not rely on Home Assistant Ingress.
- Exposes web UI on port `8099`.
- `webui` is configured as `http://[HOST]:[PORT:8099]`.
- Persistent data is stored under:

```text
/data/budget-tracker/data/budget_tracker.db
/data/budget-tracker/uploads
```

The add-on Dockerfile:

- Builds the React frontend with `VITE_API_BASE_URL=/api`.
- Installs the FastAPI backend.
- Copies frontend `dist` into `/app/frontend`.
- Runs `uvicorn app.main:app --host 0.0.0.0 --port 8099`.

The user has already built the image and deployed it on their HA server.

## Validation Last Run

Last local validation before handoff:

```powershell
cd frontend
npm run build
```

Passed.

```powershell
cd backend
python -m pytest
```

Passed: `8 passed`.

Production-style single-port smoke test passed locally:

- `/` returned `200`
- `/api/health` returned `{"ok": true}`

Docker was not available locally at the time, so the HA add-on image could not be built in this environment. The user later built/deployed it on the HA server.

## Known Constraints / Risks

- No authentication yet. Privacy depends on local network and HA exposure settings.
- App is intended for private household use only at this stage.
- Upload validation exists, but uploads are still user-supplied files and should remain local/private.
- SQLite is currently sufficient for MVP.
- Home Assistant add-on currently uses standalone web access, not Ingress.
- Git was not available on PATH in this environment, so no commits were created here.

## Useful Commands

Local backend:

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Local frontend:

```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Build frontend:

```powershell
cd frontend
npm run build
```

Run backend tests:

```powershell
cd backend
python -m pytest
```

Refresh HA add-on source:

```powershell
.\scripts\package-home-assistant-addon.ps1
```

## Suggested Next Steps

1. Verify the deployed HA add-on opens at its standalone web URL.
2. Check HA add-on logs for startup, database path, and upload path.
3. Confirm existing data is present or migrate/import the local SQLite database if needed.
4. Add a simple PIN/password gate before exposing beyond the trusted LAN.
5. Add backup/export controls for the SQLite database and uploads.
6. Consider Home Assistant Ingress later, but keep standalone web access working.
7. Add receipt/bill AI scanning only after the core budgeting flow is stable.

## AI Import & Local Tester

- **Backend Integration**: Supports Google AI Studio (Gemini API) to scan bills/receipts. Uses `GOOGLE_AI_API_KEY` (or `GOOGLE_GENAI_API_KEY` as fallback) and `GOOGLE_AI_MODEL` (or `GOOGLE_GENAI_MODEL` as fallback, defaulting to `gemini-2.5-flash`).
- **Local Tester**: The `local-ai-import-tester/index.html` is a standalone, client-only HTML page that makes direct CORS requests to Google AI Studio Gemini API using a user-specified API key and selected model. It uses the same structured JSON output shape and prompt rules as the backend service, making it easy to test prompts and model behavior without backend infrastructure.
