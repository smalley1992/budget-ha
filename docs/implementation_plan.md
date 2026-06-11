# Enhance AI Logging and Timestamp Formatting

Improve logging across the AI import service and FastAPI application to ensure all output contains high-precision timestamps compatible with Home Assistant (HA) expectations. Address the application freeze/restart issue by ensuring that the asynchronous thread-offloaded execution is correctly packaged in the HA add-on.

## User Review Required

> [!NOTE]
> All custom log messages from the AI import flow will be prefix-labeled with `[AI Import]` and formatted with a high-precision timestamp: `[YYYY-MM-DD HH:MM:SS.mmm] INFO: [AI Import] ...`.
> We will also dynamically update Uvicorn's default formatters on startup so that standard request/access logs output identical timestamp prefixes, making all logs in the Home Assistant Supervisor consistent and easy to trace.

> [!WARNING]
> No sensitive values (such as the Google AI API key or document content raw secrets) will ever be logged. All API key variables are filtered and scrubbed before logging.

## Proposed Changes

### Backend Log Setup and Routing

#### [MODIFY] [main.py](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/main.py)
*   Implement `setup_logging()` to configure Python's root logger and dynamically override Uvicorn's error and access formatters to include timestamps (`[%(asctime)s.%(msecs)03d]`).
*   Call `setup_logging()` on module load to ensure it runs right after Uvicorn initializes its loggers.

#### [MODIFY] [ai_import.py (router)](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/routers/ai_import.py)
*   Add request logging at the start of `/api/ai-import/preview`.

#### [MODIFY] [ai_import.py (service)](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/services/ai_import.py)
*   Add logging for file validation, context details, prompt construction, request size, elapsed API request time, API errors, and response parsing results.

---

### Home Assistant Add-on & Packaging

#### [MODIFY] [config.yaml](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/home-assistant-addon/budget-tracker/config.yaml)
*   Bump version to `0.4.5` to trigger a new build when staging changes.

#### [RUN] Packaging Script
*   Run the script `.\scripts\package-home-assistant-addon.ps1` to ensure all frontend and backend source files (including `main.py`, `ai_import.py` router, and `ai_import.py` service) are properly copied to the HA add-on staging folder `home-assistant-addon/budget-tracker/app-src`.

---

## Verification Plan

### Automated Tests
*   Run pytest to confirm that database setup, seeding, and endpoints function correctly with the updated logging hooks:
    ```powershell
    cd backend
    python -m pytest
    ```

### Manual Verification
*   Start the backend locally via `uvicorn` and verify that the logs printed to the console have the formatted timestamps.
*   Run a mock AI import and inspect the console logs to verify that the request phases, payload sizes, model name, and elapsed times are printed correctly.
*   Confirm that no API keys or secrets are logged.
