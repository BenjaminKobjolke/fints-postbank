# fintts-postbank

FinTS client for Postbank banking operations using the python-fints library.

## Features

- Fetch SEPA account information
- Retrieve transactions (last 100 days by default)
- Get current account balance
- Support for BestSign (decoupled TAN) authentication

## Requirements

- Python >= 3.12
- [uv](https://docs.astral.sh/uv/) package manager

## Setup

1. Run the install script:
   ```
   install.bat
   ```

2. Copy `.env.example` to `.env` and fill in your Postbank credentials:
   ```
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
│       ├── settings.py      # Environment config
│       └── constants.py     # Bank constants
├── tests/
│   └── test_config.py
├── pyproject.toml
├── install.bat
├── update.bat
├── start.bat
└── tools/tests.bat
```

## Configuration

Bank-specific constants are in `src/fintts_postbank/config/constants.py`:
- BLZ: 36010043
- HBCI URL: https://hbci.postbank.de/banking/hbci.do
