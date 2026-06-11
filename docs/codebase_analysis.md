# Budget Tracker Codebase Analysis & Overview

Welcome! This document provides a comprehensive overview of the **Budget Tracker** application, summarizing the codebase structure, tech stack, domain model rules, local execution steps, and deployment configuration to get you fully up to speed.

---

## 1. System Architecture & Tech Stack

The Budget Tracker is a self-hosted family and household budgeting app. Its stack is composed of:

*   **Backend**: Python, **FastAPI**, **SQLAlchemy 2** (ORM), and **SQLite** as the database.
    *   Designed without authentication or user session logic in the current version.
    *   Features local backup/restore (direct SQLite DB file export/import) and local receipt/bill file attachments.
*   **Frontend**: TypeScript, **React**, and **Vite**.
    *   A single-page application built on top of a streamlined and lightweight design.
    *   Saves the selected user profile and tab selections locally via `localStorage`.
*   **Home Assistant Integration**: A pre-configured Home Assistant add-on wrapper that allows the entire application to be packaged, built, and run within a Home Assistant OS container.

---

## 2. Directory Layout & Key Components

Here is the high-level layout of the codebase:

```text
/
├── backend/                             # FastAPI Backend Source
│   ├── app/
│   │   ├── main.py                      # Application entrypoint & CORS middleware
│   │   ├── config.py                    # Environment settings (load_dotenv)
│   │   ├── database.py                  # SQLAlchemy engine & session setup
│   │   ├── models.py                    # SQLite tables/DB models (SQLAlchemy)
│   │   ├── schemas.py                   # Pydantic schemas (not used heavily, dicts/typing instead)
│   │   ├── money.py                     # Cents conversions
│   │   ├── routers/                     # Route endpoints (budget lines, attachments, users, etc.)
│   │   ├── services/                    # Core business logic (ledger syncing, rollover, migrations)
│   │   └── tests/
│   │       └── test_api.py              # Pytest integration tests (12 tests)
│   ├── pyproject.toml                   # Python dependencies & metadata
│   └── Dockerfile                       # Backend containerization file
│
├── frontend/                            # React + Vite Frontend Source
│   ├── src/
│   │   ├── App.tsx                      # Main application UI, routing, and state
│   │   ├── main.tsx                     # React entrypoint
│   │   ├── styles.css                   # Main application styling (vanilla CSS)
│   │   ├── api/
│   │   │   └── client.ts                # Fetch API wrapper for all backend routes
│   │   └── types/
│   │       └── index.ts                 # TypeScript type declarations
│   ├── package.json                     # Frontend dependencies (React 19, Lucide, Vite 6)
│   └── vite.config.ts                   # Vite config (includes dev proxy for /api -> localhost:8000)
│
├── home-assistant-addon/                # Packaging for Home Assistant OS
│   └── budget-tracker/
│       ├── config.yaml                  # HA add-on configuration (ports, schema, metadata)
│       ├── Dockerfile                   # Multi-stage build (builds frontend, installs python backend)
│       ├── run.sh                       # Startup script (extracts configurations & runs uvicorn)
│       └── app-src/                     # Copy of the main code (transferred via packaging script)
│
├── scripts/
│   └── package-home-assistant-addon.ps1 # Robocopy script to stage frontend & backend to HA add-on source
│
├── data/                                # Runtime SQLite db folder (ignored in git)
└── uploads/                             # Runtime attachments folder (ignored in git)
```

---

## 3. Data Models & Business Rules

The data architecture handles budgeting on a monthly basis for multiple users. Key entity tables from models.py include:

### Core Tables
1.  **User**: Household profiles (e.g. `chris`, `jaye`), storing user-specific slug, name, icon, and estimated monthly salary.
2.  **Month**: Represented by a period string (e.g. `"2026-06"`).
3.  **IncomeLine**: Monthly recurring/one-off income streams linked to a `User` and `Month`.
4.  **BudgetLine**: Outgoing lines categorized by type (`"bill"`, `"expense"`, `"savings_contribution"`, `"debt_payment"`). Contains payment status (`"planned"` or `"paid"`).

### Ledgers & Financial Rules
Special ledger rules apply to **Debts** and **Savings Pots** to trace actual balances dynamically over time:
*   **Debt**: Tracks overall debt balance starting from a `starting_balance_cents`.
*   **SavingsPot**: Tracks savings progress starting from a `starting_balance_cents` with an optional target amount.
*   **Ledger Transaction Syncing**:
    *   **Planned** debt payments or savings contributions **do not** change the ledger balance.
    *   Marking a debt payment or savings contribution as **Paid** automatically generates a ledger entry (`DebtTransaction` / `SavingsTransaction`).
    *   Updating the payment's `amount_cents` updates the ledger transaction.
    *   Deleting the budget line or reverting it back to `Planned` automatically removes the ledger transaction.
    *   *Unlinked* savings contributions (no specific pot chosen) default to or create a `"General savings"` pot.

### Rollover Logic
A manual rollover service (`rollover.py`) allows copying static (recurring) lines from a source period to a target period:
*   Only copies `IncomeLine` or `BudgetLine` entries where `is_static` is `True`.
*   Resets the target status of budget lines to `"planned"`.
*   Excludes attachments from the rollover (copied items begin fresh without old receipts).

---

## 4. Run & Test Instructions

### Running Tests
The backend uses `pytest`. In this environment, you can run tests with:
```powershell
cd backend
python -m pytest
```

### Running Locally
To launch both servers simultaneously:

1.  **Backend** (Default port `8000`):
    ```powershell
    cd backend
    python -m uvicorn app.main:app --reload --port 8000
    ```
2.  **Frontend** (Default port `5173`, proxies `/api` requests to backend):
    ```powershell
    cd frontend
    npm install
    npm run dev
    ```

---

## 5. Home Assistant Add-on Packaging

The Home Assistant add-on executes a single-container run of both the backend and frontend:
*   It exposes the application web interface on port **`8099`**.
*   **Ingress** is enabled in the configuration (`ingress: true` in `config.yaml`), although the handoff suggests it was deployed by the user using standalone port mapping.
*   The script `.\scripts\package-home-assistant-addon.ps1` runs a `robocopy` sync to copy clean source code files from the project root into the `home-assistant-addon/budget-tracker/app-src` directory for packaging.

---

## 6. Current Observations & Observations for Next Steps
1.  **No authentication**: As detailed in the handoff, the site is designed to run in a private network or internal Home Assistant context. Adding a basic security layer (e.g. simple PIN gate) is a recommended next step if exposed outside the LAN.
2.  **AI Import**: The AI receipt scanning flow is disabled in Phase 1, though a `gemma-4-31b-it` model configuration placeholder exists.
3.  **Frontend structure**: The entire frontend UI code resides in `App.tsx` (~64KB). If we expand features, refactoring components out into separate files under `frontend/src/components` and `frontend/src/pages` would improve maintainability.
