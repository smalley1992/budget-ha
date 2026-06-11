# Logging and Packaging Tasks

- [x] Modify [main.py](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/main.py) to configure root and Uvicorn loggers with timestamps.
- [x] Add request start logging to [ai_import.py (router)](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/routers/ai_import.py).
- [x] Add detailed phase and performance logging to [ai_import.py (service)](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/backend/app/services/ai_import.py) and ensure API keys are scrubbed.
- [x] Enhance backend JSON extractor with regex markdown code block search, outer curly brace extraction, raw response snippets on failure, and exclude reasoning thought blocks.
- [x] Run backend tests locally to verify correctness.
- [x] Run the Home Assistant addon packaging script to copy updated source files.
- [x] Bump the add-on version to `0.4.6` in [config.yaml](file:///c:/Users/small/OneDrive/Documents/Budgets%20and%20Expenses/home-assistant-addon/budget-tracker/config.yaml).
