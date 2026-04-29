"""Account operations for fetching and displaying banking data."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fints.client import (  # type: ignore[import-untyped]
    FinTS3PinTanClient,
    NeedTANResponse,
    NeedVOPResponse,
)

from fintts_postbank.io.helpers import io_input, io_output
from fintts_postbank.logger import get_logger
from fintts_postbank.tan import handle_tan_challenge


class VOPDeclinedError(Exception):
    """Raised when the user declines a Verification of Payee challenge."""

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


def _format_vop_result(vop_result: Any) -> str:
    """Format a Verification-of-Payee result for display to the user."""
    descriptions = {
        "RCVC": "Full match. Bank requests explicit confirmation.",
        "RVMC": "Partial match — recipient name differs from bank records.",
        "RVNM": "No match — recipient name does not match the IBAN.",
        "RVNA": "Name check not available.",
        "PDNG": "Name check still pending.",
    }

    single = getattr(vop_result, "vop_single_result", None)
    lines: list[str] = ["Verification of Payee (Namensabgleich) result:"]

    if single is None:
        lines.append("  Bank returned no detailed result.")
        return "\n".join(lines)

    result_code = getattr(single, "result", None) or "?"
    description = descriptions.get(result_code, "Unknown result code.")
    lines.append(f"  Code: {result_code} — {description}")

    close_name = getattr(single, "close_match_name", None)
    if close_name:
        lines.append(f"  Bank's recorded name: {close_name}")

    other_id = getattr(single, "other_identification", None)
    if other_id:
        lines.append(f"  Other identification: {other_id}")

    na_reason = getattr(single, "na_reason", None)
    if na_reason:
        lines.append(f"  Reason: {na_reason}")

    notice = getattr(vop_result, "manual_authorization_notice", None)
    if notice:
        lines.append(notice.strip())

    return "\n".join(lines)


def handle_vop_challenge(
    response: Any,
    io: IOAdapter | None = None,
) -> bool:
    """Show VoP challenge details and ask the user whether to proceed.

    Args:
        response: The NeedVOPResponse from python-fints.
        io: Optional IOAdapter for I/O operations.

    Returns:
        True if the user confirms, False otherwise.
    """
    io_output(io, "")
    io_output(io, _format_vop_result(response.vop_result))
    answer = (
        io_input(io, "Confirm transfer despite name check result? (yes/no): ")
        .strip()
        .lower()
    )
    return answer in ("yes", "y")


def _log_vop_data(vop_result: Any, source: str) -> None:
    """Log VoP data for diagnostics (also printed to console)."""
    if vop_result is None:
        msg = f"[VoP/{source}] no vop_result attached"
        logger.info(msg)
        print(msg)
        return

    single = getattr(vop_result, "vop_single_result", None)
    if single is None:
        msg = f"[VoP/{source}] vop_result without vop_single_result"
        logger.info(msg)
        print(msg)
        return

    msg = (
        f"[VoP/{source}] result={getattr(single, 'result', None)!r}"
        f" close_match_name={getattr(single, 'close_match_name', None)!r}"
        f" other_identification={getattr(single, 'other_identification', None)!r}"
        f" recipient_IBAN={getattr(single, 'recipient_IBAN', None)!r}"
        f" info_IBAN={getattr(single, 'info_IBAN', None)!r}"
        f" na_reason={getattr(single, 'na_reason', None)!r}"
    )
    logger.info(msg)
    print(msg)

    notice = getattr(vop_result, "manual_authorization_notice", None)
    if notice:
        notice_msg = f"[VoP/{source}] authorization notice: {notice}"
        logger.info(notice_msg)
        print(notice_msg)


def _vop_needs_confirmation(vop_result: Any) -> bool:
    """Decide whether VoP data on a NeedTANResponse warrants a user prompt.

    The library returns NeedVOPResponse for RVMC/RVNM/RVNA. RCVC (full
    match) flows through NeedTANResponse with auto-approve. But some banks
    attach informative VoP data (e.g. close_match_name) even on the TAN
    path; in that case we still want the user to see and confirm it before
    a TAN is sent.
    """
    if vop_result is None:
        return False
    single = getattr(vop_result, "vop_single_result", None)
    if single is None:
        return False

    result_code = getattr(single, "result", None)
    if result_code in ("RVMC", "RVNM", "RVNA", "PDNG"):
        return True

    if any(
        getattr(single, field_name, None)
        for field_name in ("close_match_name", "other_identification", "na_reason")
    ):
        return True

    return False


def _log_response_codes(response: Any, source: str) -> None:
    """Log all response codes for diagnostics (also printed)."""
    responses = getattr(response, "responses", None)
    if not responses:
        return
    for resp in responses:
        code = getattr(resp, "code", None)
        text = getattr(resp, "text", None)
        msg = f"[Codes/{source}] {code} - {text}"
        logger.info(msg)
        print(msg)


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

    Raises:
        VOPDeclinedError: If the user declines a Verification of Payee
            challenge issued by the bank.
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

    msg = f"[Stage] simple_sepa_transfer returned: {type(response).__name__}"
    logger.info(msg)
    print(msg)
    if hasattr(response, "vop_result"):
        _log_vop_data(getattr(response, "vop_result", None), "initial")
    if not isinstance(response, (NeedTANResponse, NeedVOPResponse)):
        _log_response_codes(response, "no-tan-path")

    confirmed_vop_via_tan_path = False

    while isinstance(response, (NeedTANResponse, NeedVOPResponse)):
        if isinstance(response, NeedVOPResponse):
            if not handle_vop_challenge(response, io):
                raise VOPDeclinedError(
                    "User declined Verification of Payee challenge"
                )
            response = client.approve_vop_response(response)
            msg = (
                f"[Stage] approve_vop_response returned: "
                f"{type(response).__name__}"
            )
            logger.info(msg)
            print(msg)
            if hasattr(response, "vop_result"):
                _log_vop_data(getattr(response, "vop_result", None), "after-approve")
            continue

        # Some banks attach VoP info to a NeedTANResponse instead of returning
        # NeedVOPResponse. If the data is non-clean, prompt the user before
        # the TAN is sent so they get a chance to abort.
        if not confirmed_vop_via_tan_path:
            vop_result = getattr(response, "vop_result", None)
            if _vop_needs_confirmation(vop_result):
                if not handle_vop_challenge(response, io):
                    raise VOPDeclinedError(
                        "User declined Verification of Payee challenge"
                    )
                confirmed_vop_via_tan_path = True

        tan = handle_tan_challenge(response, io)
        response = client.send_tan(response, tan)
        msg = f"[Stage] send_tan returned: {type(response).__name__}"
        logger.info(msg)
        print(msg)

    _log_response_codes(response, "final")

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
