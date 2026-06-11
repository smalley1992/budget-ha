# Budget Tracker

A self-hosted household and family budgeting app.

## What Is Included

- FastAPI backend with SQLite
- React + Vite + TypeScript frontend
- Local file uploads for receipts and bills
- First-run family member setup and local profile management
- Monthly income, bills, expenses, savings contributions, debt payments, and combined family totals
- Manual month rollover for static items
- No authentication and no AI scanning in the MVP

## Local Setup

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Configuration

Copy `.env.example` to `.env` if you want to override defaults.

- `DATABASE_URL`: defaults to `sqlite:///./data/budget_tracker.db`
- `UPLOAD_DIR`: defaults to `./uploads`
- `MAX_UPLOAD_MB`: defaults to `10`
- `FRONTEND_ORIGIN`: defaults to `http://localhost:5173`
- `FRONTEND_DIST_DIR`: optional path to a built frontend directory served by FastAPI

Runtime data is intentionally local and should not be committed:

- `data/budget_tracker.db`
- `uploads/`
- `snapshots/`

## Docker

```powershell
docker compose up --build
```

Frontend: `http://localhost:5173`

Backend API: `http://localhost:8000/api`

## Home Assistant Add-on

The project includes a local add-on package at:

```text
home-assistant-addon/budget-tracker
```

Refresh the packaged add-on source from the current app:

```powershell
.\scripts\package-home-assistant-addon.ps1
```

Then copy `home-assistant-addon/budget-tracker` into a Home Assistant local add-ons folder or add-on repository.

The add-on runs as its own web app on port `8099`:

```text
http://homeassistant.local:8099
```

The SQLite database and uploads are stored in the add-on's persistent `/data/budget-tracker` folder.
Fresh installs start with no family members. Open the app and create the first profile, then add more profiles from Settings.

## Public Repository Notes

The repository is designed to be shared without personal data. The add-on `app-src` folder should contain only copied backend/frontend source. Do not include local runtime data, uploads, snapshots, logs, or built dependency folders when publishing.

## Single-App Production Run

Build the frontend and let FastAPI serve it:

```powershell
cd frontend
npm run build
cd ..
$env:FRONTEND_DIST_DIR = Join-Path $PWD "frontend\dist"
$env:DATABASE_URL = "sqlite:///$($PWD.Path.Replace('\','/'))/data/budget_tracker.db"
$env:UPLOAD_DIR = Join-Path $PWD "uploads"
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8099
```

Open `http://localhost:8099`.

## Future AI Scanning

AI receipt and bill scanning is intentionally not implemented in Phase 1. The app keeps placeholders in `.env.example` for future configuration, and files are never sent to an AI provider by this MVP.
