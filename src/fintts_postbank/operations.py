"""Account operations for fetching and displaying banking data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]

from fintts_postbank.io.helpers import io_output
from fintts_postbank.logger import get_logger
from fintts_postbank.tan import handle_tan_challenge

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter

logger = get_logger(__name__)


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
    logger.info("Fetching SEPA accounts")
    print("Fetching SEPA accounts...")

    response = client.get_sepa_accounts()
    logger.debug("get_sepa_accounts returned: %s", type(response).__name__)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        logger.info("TAN required for account fetch")
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)

    accounts: list[Any] = list(response)

    logger.info("Found %d account(s)", len(accounts))
    print(f"Found {len(accounts)} account(s)")
    for acc in accounts:
        logger.debug("Account: IBAN=%s, BIC=%s", acc.iban, acc.bic)
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
    logger.info("Fetching transactions from %s to %s", start_date, end_date)
    print(f"Fetching transactions from {start_date} to {end_date}...")

    logger.debug("Calling get_transactions...")
    print("[FINTS] Calling get_transactions...")
    response = client.get_transactions(account, start_date, end_date)
    logger.info("get_transactions returned: %s", type(response).__name__)
    print(f"[FINTS] get_transactions returned: {type(response).__name__}")

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        logger.info("TAN required for transactions")
        print("[FINTS] TAN required for transactions")
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)
        logger.info("After TAN, response type: %s", type(response).__name__)
        print(f"[FINTS] After TAN, response type: {type(response).__name__}")

    print("[FINTS] Converting response to list...")
    transactions: list[Any] = list(response) if response else []
    logger.info("Found %d transaction(s)", len(transactions))
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
    logger.info("Fetching account balance")
    print("Fetching account balance...")

    response = client.get_balance(account)
    logger.debug("get_balance returned: %s", type(response).__name__)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        logger.info("TAN required for balance")
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)

    logger.info("Balance fetched: %s", response)
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
    io_output(io, "\nTransactions:")

    for tx in transactions:
        if hasattr(tx, "data"):
            data = tx.data
            tx_date = data.get("date", "N/A")
            amount = data.get("amount", "N/A")
            purpose = data.get("purpose", "")
            applicant = data.get("applicant_name", "")
            io_output(io, f"\n{tx_date} | {amount}")
            if applicant:
                io_output(io, f"  From/To: {applicant}")
            if purpose:
                io_output(io, f"  Purpose: {purpose[:60]}...")
        else:
            io_output(io, f"\n{tx}")


def print_balance(
    balance: Any,
    io: IOAdapter | None = None,
) -> None:
    """Print balance information.

    Args:
        balance: Balance object from FinTS.
        io: Optional IOAdapter for I/O operations.
    """
    io_output(io, "\nBalance:")

    if balance:
        if hasattr(balance, "amount"):
            io_output(io, f"Current balance: {balance.amount}")
        else:
            io_output(io, f"Balance: {balance}")
    else:
        io_output(io, "Balance information not available")


def find_account_by_iban(accounts: list[Any], iban: str) -> Any | None:
    """Find account by IBAN.

    Args:
        accounts: List of SEPA accounts.
        iban: IBAN to search for.

    Returns:
        Matching account or None.
    """
    normalized_iban = iban.replace(" ", "").upper()
    for acc in accounts:
        if acc.iban.replace(" ", "").upper() == normalized_iban:
            return acc
    return None


def execute_transfer(
    client: FinTS3PinTanClient,
    account: Any,
    recipient_iban: str,
    recipient_bic: str | None,
    recipient_name: str,
    amount: Decimal,
    reason: str,
    io: IOAdapter | None = None,
) -> Any:
    """Execute a SEPA transfer.

    Args:
        client: Configured FinTS client.
        account: SEPA account object (source account).
        recipient_iban: Recipient's IBAN.
        recipient_bic: Recipient's BIC (None for domestic transfers).
        recipient_name: Recipient's name.
        amount: Transfer amount as Decimal.
        reason: Transfer reason/description.
        io: Optional IOAdapter for I/O operations.

    Returns:
        TransactionResponse with status and response details.
    """
    print(f"Initiating SEPA transfer of {amount} EUR to {recipient_iban}...")

    response = client.simple_sepa_transfer(
        account=account,
        iban=recipient_iban,
        bic=recipient_bic or "",
        recipient_name=recipient_name,
        amount=amount,
        account_name=account.iban,
        reason=reason,
    )

    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)

    return response


def print_transfer_result(
    response: Any,
    io: IOAdapter | None = None,
) -> None:
    """Print transfer result information.

    Args:
        response: TransactionResponse from the transfer.
        io: Optional IOAdapter for I/O operations.
    """
    from fints.client import ResponseStatus  # type: ignore[import-untyped]

    io_output(io, "\nTransfer Result:")

    if hasattr(response, "status"):
        if response.status == ResponseStatus.SUCCESS:
            io_output(io, "Transfer SUCCESSFUL")
        elif response.status == ResponseStatus.WARNING:
            io_output(io, "Transfer completed with WARNINGS")
        elif response.status == ResponseStatus.ERROR:
            io_output(io, "Transfer FAILED")
        else:
            io_output(io, f"Transfer status: {response.status}")

    if hasattr(response, "responses") and response.responses:
        for resp in response.responses:
            text = getattr(resp, "text", str(resp))
            io_output(io, f"  {text}")
