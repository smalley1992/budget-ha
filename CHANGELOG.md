# Changelog

## 0.5.8 - 2026-06-13

- Added a per-entry Paid now / Planned control to the add budget line form.
- Defaulted current and past month entries to paid, and future month entries to planned.
- Removed the global "new budget lines default to paid" setting to avoid future savings/debt entries changing balances early.
- Kept the top Savings card tied to actual savings pot balance instead of planned monthly savings lines.

## 0.5.7 - 2026-06-12

- Replaced the hidden native month input with an app-owned month picker.
- Made new month selection copy recurring/static lines from the current month before switching.
- Changed the Next Month action to create/copy recurring lines and navigate to the next month.

## 0.5.6 - 2026-06-12

- Suppressed Google AI thought summaries in AI import requests.
- Added minimal/no-thinking request controls for supported Gemini models.
- Added fallback handling when a model returns only thought blocks instead of final JSON.

## 0.5.5 - 2026-06-12

- Fixed dark mode metric/hero card text inheriting browser-default black button text.

## 0.5.4 - 2026-06-12

- Added Google AI model selection in Settings, including Gemma 4 26B, Gemma 4 31B, Gemini 2.5 Flash, and a custom model id option.
- Changed the default AI import model to `gemma-4-26b-a4b-it`.
- Added automatic fallback from `gemma-4-31b-it` to `gemma-4-26b-a4b-it` when Google returns retryable server failures.
- Added model-id validation before building Google API request URLs.
- Added free-tier limit guidance in Settings, pointing users to active Google AI Studio RPM/TPM/RPD limits.
- Moved the user switcher out of the mobile header and changed the mobile top bar to Month / Next Month / Settings.

## 0.5.3 - 2026-06-12

- Added retries for transient Google AI import failures.
- Stopped logging raw AI response snippets because uploaded documents can contain financial data.
- Ignored runtime upload files under the nested add-on app path.

## 0.5.2 - 2026-06-12

- Fixed mobile month picker overflow.

## 0.5.1 - 2026-06-12

- Improved mobile controls and dark mode styling.
