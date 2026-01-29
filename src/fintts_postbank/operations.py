"""Account operations for fetching and displaying banking data."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]

from fintts_postbank.tan import handle_tan_challenge

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter


def _output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


def fetch_accounts(
    client: FinTS3PinTanClient,
    io: IOAdapter | None = None,
) -> list[Any]:
    """Fetch SEPA accounts from the bank.

    Args:
        client: Configured FinTS client.
        io: Optional IOAdapter for I/O operations.

    Returns:
        List of SEPA account objects.
    """
    print("Fetching SEPA accounts...")

    response = client.get_sepa_accounts()

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)

    accounts: list[Any] = list(response)

    print(f"Found {len(accounts)} account(s)")
    for acc in accounts:
        print(f"  - IBAN: {acc.iban}, BIC: {acc.bic}")

    return accounts


def fetch_transactions(
    client: FinTS3PinTanClient,
    account: Any,
    start_date: date,
    end_date: date,
    io: IOAdapter | None = None,
) -> list[Any]:
    """Fetch transactions for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.
        start_date: Start date for transactions.
        end_date: End date for transactions.
        io: Optional IOAdapter for I/O operations.

    Returns:
        List of transaction objects.
    """
    print(f"Fetching transactions from {start_date} to {end_date}...")

    print("[FINTS] Calling get_transactions...")
    response = client.get_transactions(account, start_date, end_date)
    print(f"[FINTS] get_transactions returned: {type(response).__name__}")

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        print("[FINTS] TAN required for transactions")
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)
        print(f"[FINTS] After TAN, response type: {type(response).__name__}")

    print("[FINTS] Converting response to list...")
    transactions: list[Any] = list(response) if response else []
    print(f"[FINTS] Converted {len(transactions)} transactions")
    print(f"Found {len(transactions)} transaction(s)")

    return transactions


def fetch_balance(
    client: FinTS3PinTanClient,
    account: Any,
    io: IOAdapter | None = None,
) -> Any:
    """Fetch current balance for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.
        io: Optional IOAdapter for I/O operations.

    Returns:
        Balance information.
    """
    print("Fetching account balance...")

    response = client.get_balance(account)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)

    return response


def print_transactions(
    transactions: list[Any],
    io: IOAdapter | None = None,
) -> None:
    """Print transactions in a readable format.

    Args:
        transactions: List of transaction objects.
        io: Optional IOAdapter for I/O operations.
    """
    _output(io, "\nTransactions:")

    for tx in transactions:
        if hasattr(tx, "data"):
            data = tx.data
            tx_date = data.get("date", "N/A")
            amount = data.get("amount", "N/A")
            purpose = data.get("purpose", "")
            applicant = data.get("applicant_name", "")
            _output(io, f"\n{tx_date} | {amount}")
            if applicant:
                _output(io, f"  From/To: {applicant}")
            if purpose:
                _output(io, f"  Purpose: {purpose[:60]}...")
        else:
            _output(io, f"\n{tx}")


def print_balance(
    balance: Any,
    io: IOAdapter | None = None,
) -> None:
    """Print balance information.

    Args:
        balance: Balance object from FinTS.
        io: Optional IOAdapter for I/O operations.
    """
    _output(io, "\nBalance:")

    if balance:
        if hasattr(balance, "amount"):
            _output(io, f"Current balance: {balance.amount}")
        else:
            _output(io, f"Balance: {balance}")
    else:
        _output(io, "Balance information not available")


def find_account_by_iban(accounts: list[Any], iban: str) -> Any | None:
    """Find account by IBAN.

    Args:
        accounts: List of SEPA accounts.
        iban: IBAN to search for.

    Returns:
        Matching account or None.
    """
    for acc in accounts:
        if acc.iban == iban:
            return acc
    return None
