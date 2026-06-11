# Budget Tracker Home Assistant Add-on Repository

This repository contains the Budget Tracker Home Assistant add-on.

## Add To Home Assistant

1. In Home Assistant, open **Settings > Add-ons > Add-on Store**.
2. Open the three-dot menu and choose **Repositories**.
3. Add this repository URL:

```text
https://github.com/smalley1992/budget-ha
```

4. Install **Budget Tracker** from the add-on store.
5. Open it from the add-on page, or enable the sidebar entry in Home Assistant.

Fresh installs start empty. Open the app and create the first family member, then add more profiles from Settings.

## Data

The add-on uses Home Assistant Ingress, so access is handled through Home Assistant's normal authentication and remote access path.

The add-on stores its SQLite database and uploads in Home Assistant's persistent add-on storage under `/data/budget-tracker`.

Settings includes manual database export/import for moving or restoring the Budget Tracker SQLite database.

Import is limited to `.db`, `.sqlite`, and `.sqlite3` files that pass SQLite integrity checks and match the Budget Tracker schema. It does not import archives, execute scripts, write Home Assistant configuration, access Home Assistant tokens, or restore attachment files.

Optional AI import can be enabled by adding a Google AI Studio API key in the app configuration page. The key is read from the user's local Home Assistant app options at runtime and is not included in this repository.

No local database, uploads, receipts, snapshots, or personal budget data are included in this repository.
