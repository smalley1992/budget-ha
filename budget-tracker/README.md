# Budget Tracker Home Assistant Add-on

This add-on runs Budget Tracker through Home Assistant Ingress.

After installation, open it from the add-on page or add it to the Home Assistant sidebar. Home Assistant handles access through its normal authentication and remote access path.

Fresh installs start empty. Create the first family member in the app, then add more profiles from Settings to build a combined family budget.

## Data

The add-on stores its SQLite database and uploads in persistent add-on storage:

```text
/data/budget-tracker/data/budget_tracker.db
/data/budget-tracker/uploads
```

## Manual Database Backup And Restore

Use Settings in the app to export or import the Budget Tracker SQLite database.

Import accepts only `.db`, `.sqlite`, and `.sqlite3` files that pass SQLite integrity checks and match the Budget Tracker schema. It does not import archives, execute scripts, write Home Assistant configuration, access Home Assistant tokens, or restore attachment files.

## Optional AI Import

The app can use a Google AI Studio API key from the app configuration page to preview entries from uploaded bills, receipts, and statements.

AI import sends the uploaded document to Google AI for extraction, then shows a review screen before anything is added. It does not execute scripts, write Home Assistant configuration, access Home Assistant tokens, or commit API keys to this repository.

## Updating The Packaged App Source

From the project root on your development machine, run:

```powershell
.\scripts\package-home-assistant-addon.ps1
```

Then copy `home-assistant-addon/budget-tracker` into your Home Assistant add-ons folder or repository.

Do not publish local runtime data, uploads, snapshots, logs, or dependency folders with the add-on source.
