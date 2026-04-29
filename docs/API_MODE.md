# API Mode (`--update-api`)

Automated mode that fetches the current balance and recent transactions from
your bank via FinTS and posts them to the ERP API.

For executing pending bank transfers from the API, see
[`TRANSFER_API_MODE.md`](TRANSFER_API_MODE.md).

## Usage

```
api-mode.bat
```

Or directly:
```
fints-postbank --update-api [--account <name>] [--resync]
```

| Flag | Purpose |
|------|---------|
| `--account <name>` | Select a specific account in multi-account setups (`.env.<name>`) |
| `--resync` | Skip the local SQLite dedup cache and re-send every transaction in the configured date range |

## Required Configuration

API mode runs unattended and uses Telegram or XMPP to deliver TAN challenges.
A console-only setup is not supported.

### API settings (in `.env` or `.env.<name>`)

| Variable | Notes |
|----------|-------|
| `API_URL` | Base URL of the ERP API (e.g. `http://localhost/erp-api`) |
| `API_EMAIL` | Login email for the API |
| `API_PASSWORD` | Login password for the API |
| `API_COMPANY_ID` | Company ID for `X-Company-Id` header |
| `API_BANK_ACCOUNT_ID` | Integer ID of the bank account in the ERP |
| `TRANSACTION_START_DATE` | Earliest date to fetch. Absolute (`2026-01-01`) or relative (`30-days-ago`, `2-months-ago`, `4-weeks-ago`) |

### Bot settings

`BOT_MODE` defaults to `telegram` for API mode. Override with the `--xmpp`
flag or `BOT_MODE=xmpp` if you prefer XMPP.

**Telegram:**
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_TARGET_USER_ID` — receives status messages and TAN prompts

**XMPP:**
- `XMPP_JID`, `XMPP_PASSWORD`
- `XMPP_DEFAULT_RECEIVER` — receives status messages and TAN prompts
- `XMPP_RESOURCE` (optional)

### FinTS

Standard FinTS credentials (`FINTS_USERNAME`, `FINTS_PASSWORD`, `IBAN`) plus a
configured TAN mechanism. Run `fints-postbank --tan` once to select TAN method
before using API mode.

## Behaviour

1. Validates configuration and pings the API.
2. Opens a FinTS session and handles the PSD2 init TAN if required.
3. Fetches the configured account's current balance.
4. POSTs the balance to `/api/v1/bank-accounts/{id}/balances`. Server-side
   dedup (HTTP 409) prevents the same balance being recorded twice in a day.
5. Fetches transactions from `TRANSACTION_START_DATE` until today.
6. POSTs new transactions to `/api/v1/bank-accounts/{id}/transactions`. A
   local SQLite cache (`.transactions.db`) and the API's own dedup logic both
   skip already-sent rows.
7. Updates the locally stored "last balance".
8. Sends a chat summary **only if the balance changed** since the last run;
   otherwise stays silent to avoid notification spam.
9. Saves the FinTS session state for faster startup next time.

Pending bank transfers in the API are **not** touched by this mode — they are
ignored. Use `--process-transfers` to execute them.

## Resync

`--resync` clears the local dedup cache for the run, so every fetched
transaction is re-posted to the API. The API still rejects duplicates with
HTTP 409, so this is safe to use when local state has drifted from the
server. Only valid in combination with `--update-api`.

## Exit Codes

- `0` — sync completed (with or without new transactions)
- `1` — configuration, network, FinTS, or API error

## Troubleshooting

- **"TAN mechanism not configured"** — run `fints-postbank --tan` first.
- **"TELEGRAM_TARGET_USER_ID not set"** — Telegram mode requires this so the
  bot knows where to send TAN prompts.
- **"API authentication failed"** — verify `API_EMAIL` / `API_PASSWORD`.
- **"Account with IBAN ... not found"** — the IBAN in `.env` doesn't match
  any SEPA account returned by the bank. Use `--list-accounts` to see what's
  available.
