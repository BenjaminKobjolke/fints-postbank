# fints-postbank

FinTS client for Postbank banking operations using the python-fints library.

## Features

- Fetch SEPA account information
- Retrieve transactions (last 100 days by default)
- Get current account balance
- Support for BestSign (decoupled TAN) authentication
- Multi-account support via per-account `.env` files
- Telegram and XMPP bot notifications for balance changes
- Automated update modes (`--update-bot`, `--update-api`)
- Bot connection test mode (`--test-bot`)

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Dependencies

This project uses:
- [telegram-bot](https://github.com/BenjaminKobjolke/telegram-bot) for Telegram integration
- [xmpp-bot](https://github.com/BenjaminKobjolke/xmpp-bot.git) for XMPP integration

Both are installed as local editable dependencies via uv from sibling directories (`D:\GIT\BenjaminKobjolke\telegram-bot` and `D:\GIT\BenjaminKobjolke\xmpp-bot`).

## Setup

1. Run the install script:
   ```
   install.bat
   ```

2. Copy `.env.example` to `.env` and fill in your Postbank credentials:
   ```
   IBAN=DE30760100850087278859
   FINTS_USERNAME=your_postbank_id
   FINTS_PASSWORD=your_password
   ```

## Usage

Run the client:
```
start.bat
```

The client will:
1. Connect to Postbank via FinTS/HBCI
2. Fetch your SEPA accounts
3. Display account balance
4. Show recent transactions

When prompted for TAN (BestSign), confirm the transaction in your Postbank app and press Enter.

## Multi-Account Mode

The application supports multiple bank accounts. Each account has its own `.env.<name>` file with independent credentials, IBAN, and settings.

### Setup

Create a `.env.<name>` file for each account:

```
.env.postbank     # Postbank account
.env.sparkasse    # Sparkasse account
```

Each file is a complete standalone config:
```env
BLZ=36010043                                      # Optional, defaults to Postbank
HBCI_URL=https://hbci.postbank.de/banking/hbci.do # Optional, defaults to Postbank
IBAN=DE30760100850087278859
FINTS_USERNAME=your_user_id
FINTS_PASSWORD=your_password
```

If only the plain `.env` file exists, everything works as before (single-account mode).

### Account Selection

- **Console/bot modes:** If multiple accounts are found, you are prompted to pick one. Use `--account <name>` to skip the prompt.
- **`--update-api` mode:** `--account <name>` is required when multiple accounts exist.

The `<name>` matches the part after `.env.` in the filename — e.g. `.env.postbank` → `--account postbank`.

```
fints-postbank --account postbank
fints-postbank --update-api --account sparkasse
```

Each account gets its own session file (`.fints_session.<name>`) and TAN preferences are saved back to the respective `.env.<name>` file.

## Bot Modes

The client supports different messaging backends for notifications and TAN input:

### Configuration

Set `BOT_MODE` in your `.env` file:
```env
BOT_MODE=console    # Default: interactive console mode
BOT_MODE=telegram   # Use Telegram bot for notifications
BOT_MODE=xmpp       # Use XMPP bot for notifications
```

CLI flags `--telegram` or `--xmpp` override the environment variable.

### Telegram Mode

Requires in `.env`:
```env
BOT_MODE=telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_CHAT_IDS=123456789           # Optional whitelist
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321 # Optional whitelist
```

Run: `fints-postbank --telegram` or just `fints-postbank` with `BOT_MODE=telegram`

### XMPP Mode

Requires in `.env`:
```env
BOT_MODE=xmpp
XMPP_JID=bot@xmpp.example.com
XMPP_PASSWORD=your_xmpp_password
XMPP_DEFAULT_RECEIVER=user@xmpp.example.com   # Required for --update-api
XMPP_ALLOWED_JIDS=user1@example.com,user2@example.com  # Optional whitelist
XMPP_RESOURCE=fints-bot                       # Optional, default: fints-bot
XMPP_CONNECT_TIMEOUT=30                       # Optional, default: 30
```

Run: `fints-postbank --xmpp` or just `fints-postbank` with `BOT_MODE=xmpp`

## Bot Update Mode (--update-bot)

Automated mode that fetches bank data and sends a notification via bot (Telegram or XMPP) when the balance changes. Unlike `--update-api`, this mode does not post data to an external API.

### Configuration

Requires in `.env`:
```env
BOT_MODE=telegram              # or xmpp - for TAN notifications
TELEGRAM_TARGET_USER_ID=123456789  # User to receive notifications and TAN prompts
# TRANSACTION_DAYS=30          # Optional, defaults to 30
```

Run: `fints-postbank --update-bot` or use `bot-mode.bat`

### What it does

1. Connects to the bank via FinTS
2. Fetches balance and recent transactions (last N days)
3. If the balance changed since the last run, sends a summary via bot
4. If the balance is unchanged, logs silently without notifying

## Test Bot Mode (--test-bot)

Sends a test message via the configured bot (Telegram or XMPP) to verify your setup is working correctly. No bank connection is made.

Run: `fints-postbank --test-bot` or with a specific account: `fints-postbank --test-bot --account postbank`

Uses the same `BOT_MODE`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_TARGET_USER_ID` (or XMPP equivalents) from your `.env` file.

## API Mode (--update-api)

Automated mode that fetches bank data and posts it to an external API. Useful for syncing transactions to your own finance tracking system.

### Configuration

Requires in `.env`:
```env
BOT_MODE=telegram              # or xmpp - for TAN notifications
API_URL=http://localhost/api   # Your API base URL
API_USER=your_api_user
API_PASSWORD=your_api_password
TELEGRAM_TARGET_USER_ID=123456789  # User to receive TAN prompts
TRANSACTION_START_DATE=2024-01-01  # Sync transactions from this date
```

Run: `fints-postbank --update-api`

### API Endpoints

Your API must implement these endpoints with HTTP Basic Auth:

#### Balance Endpoint
`POST {API_URL}/index.php/records/bankbalance`

Request body (JSON):
```json
{
  "date": "2024-01-15",
  "value": "1234.56"
}
```

#### Transaction Endpoint
`POST {API_URL}/transaction.php`

Request body (JSON):
```json
{
  "name": "AMAZON EU SARL",
  "value": "-49.99",
  "dateactual": "2024-01-15",
  "status": "paid"
}
```

### Response Codes

| Code | Meaning |
|------|---------|
| 200, 201 | Success |
| 409 | Duplicate (treated as success) |
| 401 | Authentication failed |

### Example PHP Implementation

```php
<?php
// transaction.php
header('Content-Type: application/json');

// Basic Auth check
if (!isset($_SERVER['PHP_AUTH_USER']) ||
    $_SERVER['PHP_AUTH_USER'] !== 'your_user' ||
    $_SERVER['PHP_AUTH_PW'] !== 'your_password') {
    http_response_code(401);
    exit(json_encode(['error' => 'Unauthorized']));
}

$data = json_decode(file_get_contents('php://input'), true);

// Check for duplicate
if (transaction_exists($data['name'], $data['dateactual'], $data['value'])) {
    http_response_code(409);
    exit(json_encode(['error' => 'Duplicate']));
}

// Save transaction
save_transaction($data);
http_response_code(201);
echo json_encode(['success' => true]);
```

## Development

Run tests:
```
tools\tests.bat
```

Update dependencies:
```
update.bat
```

## Project Structure

```
fintts-postbank/
├── src/fintts_postbank/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   └── config/
│       ├── __init__.py
│       ├── accounts.py      # Multi-account discovery & selection
│       ├── settings.py      # Environment config
│       └── constants.py     # Bank constants
├── tests/
│   └── test_config.py
├── pyproject.toml
├── install.bat
├── update.bat
├── start.bat
├── bot-mode.bat
└── tools/tests.bat
```

## Configuration

### Environment Variables

Required in `.env` (or `.env.<name>` for multi-account):
- `IBAN` - Your account IBAN
- `FINTS_USERNAME` - Your bank user ID
- `FINTS_PASSWORD` - Your bank password

Optional (defaults to Postbank if omitted):
- `BLZ` - Bank code (Bankleitzahl)
- `HBCI_URL` - Bank FinTS/HBCI endpoint URL
- `PRODUCT_ID` - FinTS product registration ID

### Bank Constants

Default bank constants (used when not set in `.env`) are in `src/fintts_postbank/config/constants.py`:
- BLZ: 36010043
- HBCI URL: https://hbci.postbank.de/banking/hbci.do
