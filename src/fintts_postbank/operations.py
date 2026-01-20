"""Account operations for fetching and displaying banking data."""

from datetime import date
from typing import Any

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]

from fintts_postbank.tan import handle_tan_challenge


def fetch_accounts(client: FinTS3PinTanClient) -> list[Any]:
    """Fetch SEPA accounts from the bank.

    Args:
        client: Configured FinTS client.

    Returns:
        List of SEPA account objects.
    """
    print("\nFetching SEPA accounts...")

    response = client.get_sepa_accounts()

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
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
) -> list[Any]:
    """Fetch transactions for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.
        start_date: Start date for transactions.
        end_date: End date for transactions.

    Returns:
        List of transaction objects.
    """
    print(f"\nFetching transactions from {start_date} to {end_date}...")

    response = client.get_transactions(account, start_date, end_date)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
        response = client.send_tan(response, tan)

    transactions: list[Any] = list(response) if response else []
    print(f"Found {len(transactions)} transaction(s)")

    return transactions


def fetch_balance(client: FinTS3PinTanClient, account: Any) -> Any:
    """Fetch current balance for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.

    Returns:
        Balance information.
    """
    print("\nFetching account balance...")

    response = client.get_balance(account)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
        response = client.send_tan(response, tan)

    return response


def print_transactions(transactions: list[Any]) -> None:
    """Print transactions in a readable format.

    Args:
        transactions: List of transaction objects.
    """
    print("\n" + "=" * 70)
    print("TRANSACTIONS")
    print("=" * 70)

    for tx in transactions:
        if hasattr(tx, "data"):
            data = tx.data
            tx_date = data.get("date", "N/A")
            amount = data.get("amount", "N/A")
            purpose = data.get("purpose", "")
            applicant = data.get("applicant_name", "")
            print(f"\n{tx_date} | {amount}")
            if applicant:
                print(f"  From/To: {applicant}")
            if purpose:
                print(f"  Purpose: {purpose[:60]}...")
        else:
            print(f"\n{tx}")


def print_balance(balance: Any) -> None:
    """Print balance information.

    Args:
        balance: Balance object from FinTS.
    """
    print("\n" + "=" * 70)
    print("BALANCE")
    print("=" * 70)

    if balance:
        if hasattr(balance, "amount"):
            print(f"Current balance: {balance.amount}")
        else:
            print(f"Balance: {balance}")
    else:
        print("Balance information not available")


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
