# Session & TAN Storage

This document explains how the application persists data between runs so you don't need to enter a TAN or re-select your TAN mechanism every time.

## Overview

Three files in the project root store session-related data. All three are listed in `.gitignore` and never committed.

| File | Format | Purpose |
|------|--------|---------|
| `.env` | Key-value text | Credentials and saved TAN preferences |
| `.fints_session` | Binary (pickle) | Serialized FinTS client state |
| `.fints_transactions.db` | SQLite | Sent-transaction cache and last balance (`--update-api` mode) |

## 1. `.env` &mdash; TAN Preferences

On first run the application prompts you to choose a TAN mechanism (e.g. BestSign) and, if applicable, a TAN medium (e.g. your phone). After selection, three variables are appended to `.env`:

```
FINTS_TAN_MECHANISM=920
FINTS_TAN_MECHANISM_NAME=BestSign
FINTS_TAN_MEDIUM=BennyHauptHandy
```

On subsequent runs, `get_settings()` in `src/fintts_postbank/config/settings.py` loads these values. The TAN bootstrap in `src/fintts_postbank/tan.py` (`_try_use_saved_preferences`) checks whether the saved mechanism is still offered by the bank and applies it automatically, skipping the interactive selection.

If the saved mechanism or medium is no longer available, the application falls back to interactive selection and overwrites the saved values.

## 2. `.fints_session` &mdash; Client State

At the end of every successful session, `run_session()` in `src/fintts_postbank/client.py` calls `client.deconstruct()` to serialize the FinTS client state and writes the raw bytes to `.fints_session` via `save_client_state()`.

On the next startup, `create_client()` reads this file with `load_client_state()` and passes the bytes as the `from_data` parameter to `FinTS3PinTanClient`. This lets the library skip parts of the FinTS dialog initialization, which can reduce the number of TAN challenges required by the bank.

The session file is managed by three functions in `src/fintts_postbank/config/settings.py`:

- `save_client_state(data)` &mdash; writes bytes to `.fints_session`
- `load_client_state()` &mdash; returns the bytes, or `None` if the file doesn't exist
- `clear_client_state()` &mdash; deletes the file

## 3. `.fints_transactions.db` &mdash; Transaction Cache

Used exclusively in `--update-api` mode to prevent duplicate submissions to the external API. The SQLite database is managed by `TransactionDatabase` in `src/fintts_postbank/transaction_db.py` and contains two tables:

**`sent_transactions`** &mdash; records every transaction already forwarded to the API, keyed by `(fints_username, transaction_date, amount, purpose_hash)`.

**`last_balance`** &mdash; stores the most recent account balance per user so the API can be updated with the current balance.

## Resetting Stored Data

| What to reset | Action |
|---------------|--------|
| TAN preferences | Remove `FINTS_TAN_MECHANISM`, `FINTS_TAN_MECHANISM_NAME`, and `FINTS_TAN_MEDIUM` from `.env` |
| Session state | Delete `.fints_session` |
| Transaction cache | Delete `.fints_transactions.db` |
| Everything | Delete all three; keep the remaining `.env` variables (credentials, bot config, etc.) |

After deleting `.fints_session`, the next run will perform a full FinTS handshake and may require a new TAN.

## Multi-Account Mode

The application supports multiple bank accounts via per-account `.env` files.

### Setup

Instead of a single `.env`, create `.env.<name>` files in the project root:

- `.env.postbank` &mdash; Postbank account
- `.env.sparkasse` &mdash; Sparkasse account

Each file is a complete standalone configuration containing credentials (`FINTS_USERNAME`, `FINTS_PASSWORD`, `IBAN`), and optionally `BLZ`, `HBCI_URL`, `PRODUCT_ID` (defaults to Postbank values if omitted), TAN preferences, bot settings, and API settings.

If only the plain `.env` file exists, everything works as before (single-account mode).

### Account Selection

- **Console/bot modes:** If multiple accounts are found, the application prompts you to pick one interactively. If only one account exists, it is used automatically.
- **`--update-api` mode:** Use `--account <name>` to specify which account. This is required when multiple accounts exist.
- **All modes:** `--account <name>` can be used to skip the interactive prompt.

### Per-Account Session Files

Each account gets its own session file:

| Account name | Session file |
|-------------|--------------|
| `default` (plain `.env`) | `.fints_session` |
| `postbank` (`.env.postbank`) | `.fints_session.postbank` |
| `sparkasse` (`.env.sparkasse`) | `.fints_session.sparkasse` |

TAN preferences are saved back to the respective `.env.<name>` file.

### Per-Account Discovery

The application discovers accounts by scanning for `.env.*` files in the project root, excluding `.env.example` and backup files (`.bak`, `.backup`, `.old`). The account name is derived from the file suffix (e.g. `.env.postbank` &rarr; `postbank`).
