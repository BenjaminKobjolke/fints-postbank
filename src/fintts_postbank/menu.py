"""Interactive menu handling for the CLI."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]
from schwifty import BIC, IBAN  # type: ignore[import-untyped]

from fintts_postbank.io.helpers import io_input, io_output
from fintts_postbank.operations import (
    VOPDeclinedError,
    execute_transfer,
    fetch_balance,
    fetch_transactions,
    print_balance,
    print_transactions,
    print_transfer_result,
)
from fintts_postbank.ui import get_valid_choice

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter

PERIOD_LABELS = {
    1: "today",
    2: "this week",
    3: "this month",
    4: "this year",
    5: "all",
}


def get_transaction_date_range(choice: int) -> tuple[date, date]:
    """Get date range for transactions based on user choice.

    Args:
        choice: Menu choice (1=today, 2=this week, 3=this month, 4=this year, 5=all).

    Returns:
        Tuple of (start_date, end_date).
    """
    today = date.today()

    if choice == 1:  # Today
        return today, today
    elif choice == 2:  # This week (Monday to today)
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        return monday, today
    elif choice == 3:  # This month
        first_of_month = today.replace(day=1)
        return first_of_month, today
    elif choice == 4:  # This year
        first_of_year = today.replace(month=1, day=1)
        return first_of_year, today
    else:  # All (default: last 365 days)
        return today - timedelta(days=365), today


def get_last_action_label(last_action: tuple[int, int | None]) -> str | None:
    """Get human-readable label for last action.

    Args:
        last_action: Tuple of (main_choice, period_choice).

    Returns:
        Label string or None if no last action.
    """
    main_choice, period_choice = last_action
    if main_choice == 1:
        return "Show balance"
    elif main_choice == 2 and period_choice is not None:
        period_label = PERIOD_LABELS.get(period_choice, "")
        return f"Show transactions ({period_label})"
    return None


def show_transactions_menu(io: IOAdapter | None = None) -> int:
    """Display transactions period menu and get user choice.

    Args:
        io: Optional IOAdapter for I/O operations.

    Returns:
        User's menu choice (0-5).
    """
    io_output(io, "\nSelect time period:")
    io_output(io, "1. Today")
    io_output(io, "2. This week")
    io_output(io, "3. This month")
    io_output(io, "4. This year")
    io_output(io, "5. All")
    io_output(io, "0. Back")
    return get_valid_choice("\nChoice: ", 5, io=io)


def show_menu(
    last_action_label: str | None = None,
    io: IOAdapter | None = None,
) -> int:
    """Display menu and get user choice.

    Args:
        last_action_label: Label for last action (shown as repeat hint).
        io: Optional IOAdapter for I/O operations.

    Returns:
        User's menu choice (0-2), or -1 to repeat last action.
    """
    io_output(io, "\n1. Show balance")
    io_output(io, "2. Show transactions")
    io_output(io, "3. Transfer")
    io_output(io, "0. Exit")
    if last_action_label:
        io_output(io, f"\n[Enter] {last_action_label}")
        return get_valid_choice("\nChoice: ", 3, default=-1, io=io)
    return get_valid_choice("\nChoice: ", 3, io=io)


def is_dialog_error(error: Exception) -> bool:
    """Check if an error indicates the dialog/session has closed.

    Args:
        error: The exception to check.

    Returns:
        True if this is a dialog closed error.
    """
    error_str = str(error).lower()
    return any(
        indicator in error_str
        for indicator in ["dialog", "geschlossen", "closed", "9999", "session"]
    )


def collect_transfer_details(
    io: IOAdapter | None = None,
) -> dict[str, Any] | None:
    """Collect SEPA transfer details from the user.

    Args:
        io: Optional IOAdapter for I/O operations.

    Returns:
        Dictionary with transfer details, or None if user cancels.
    """
    io_output(io, "\n--- SEPA Transfer ---")
    io_output(io, "Enter 'cancel' at any prompt to abort.\n")

    # Recipient IBAN
    while True:
        iban_input = io_input(io, "Recipient IBAN: ").strip()
        if iban_input.lower() == "cancel":
            return None
        try:
            recipient_iban = IBAN(iban_input)
            break
        except ValueError as e:
            io_output(io, f"Invalid IBAN: {e}")

    # Recipient BIC (optional)
    while True:
        bic_input = io_input(io, "Recipient BIC (press Enter to skip for domestic): ").strip()
        if bic_input.lower() == "cancel":
            return None
        if not bic_input:
            recipient_bic = None
            break
        try:
            recipient_bic = str(BIC(bic_input))
            break
        except ValueError as e:
            io_output(io, f"Invalid BIC: {e}")

    # Recipient name
    while True:
        recipient_name = io_input(io, "Recipient name: ").strip()
        if recipient_name.lower() == "cancel":
            return None
        if recipient_name:
            break
        io_output(io, "Recipient name cannot be empty.")

    # Amount
    while True:
        amount_input = io_input(io, "Amount (EUR): ").strip()
        if amount_input.lower() == "cancel":
            return None
        try:
            amount = Decimal(amount_input.replace(",", "."))
            if amount <= 0:
                io_output(io, "Amount must be greater than 0.")
            elif amount != amount.quantize(Decimal("0.01")):
                io_output(io, "Amount cannot have more than 2 decimal places.")
            else:
                break
        except InvalidOperation:
            io_output(io, "Invalid amount. Please enter a valid number (e.g., 100.50).")

    # Reason/description
    reason = io_input(io, "Transfer reason/description: ").strip()
    if reason.lower() == "cancel":
        return None

    return {
        "recipient_iban": str(recipient_iban),
        "recipient_bic": recipient_bic,
        "recipient_name": recipient_name,
        "amount": amount,
        "reason": reason,
    }


def confirm_transfer(
    details: dict[str, Any],
    source_iban: str,
    io: IOAdapter | None = None,
) -> bool:
    """Show transfer summary and ask for confirmation.

    Args:
        details: Transfer details dictionary.
        source_iban: Source account IBAN.
        io: Optional IOAdapter for I/O operations.

    Returns:
        True if user confirms, False otherwise.
    """
    io_output(io, "\n--- Transfer Summary ---")
    io_output(io, f"From:        {source_iban}")
    io_output(io, f"To IBAN:     {details['recipient_iban']}")
    if details["recipient_bic"]:
        io_output(io, f"To BIC:      {details['recipient_bic']}")
    io_output(io, f"Recipient:   {details['recipient_name']}")
    io_output(io, f"Amount:      {details['amount']:.2f} EUR")
    io_output(io, f"Reason:      {details['reason']}")
    io_output(io, "------------------------")

    confirmation = io_input(io, "\nConfirm transfer? (yes/no): ").strip().lower()
    return confirmation in ("yes", "y")


def run_menu_loop(
    client: FinTS3PinTanClient,
    account: Any,
    io: IOAdapter | None = None,
) -> bool:
    """Run interactive menu loop.

    Args:
        client: Configured FinTS client.
        account: SEPA account to operate on.
        io: Optional IOAdapter for I/O operations.

    Returns:
        True if reconnection is needed, False for normal exit.
    """
    last_action: tuple[int, int | None] = (0, None)

    while True:
        last_action_label = get_last_action_label(last_action)
        choice = show_menu(last_action_label, io)

        # Handle repeat last action
        if choice == -1 and last_action[0] != 0:
            choice = last_action[0]
            # For transactions, reuse the period choice
            if choice == 2 and last_action[1] is not None:
                period_choice = last_action[1]
                start_date, end_date = get_transaction_date_range(period_choice)
                try:
                    transactions = fetch_transactions(
                        client, account, start_date, end_date, io
                    )
                    print_transactions(transactions, io)
                except Exception as e:
                    if is_dialog_error(e):
                        io_output(io, f"\nSession expired: {e}")
                        io_output(io, "Reconnecting...")
                        return True
                    raise
                continue

        if choice == 0:
            return False
        elif choice == 1:
            try:
                balance = fetch_balance(client, account, io)
                print_balance(balance, io)
                last_action = (1, None)
            except Exception as e:
                if is_dialog_error(e):
                    io_output(io, f"\nSession expired: {e}")
                    io_output(io, "Reconnecting...")
                    return True
                raise
        elif choice == 2:
            period_choice = show_transactions_menu(io)
            if period_choice == 0:
                continue
            start_date, end_date = get_transaction_date_range(period_choice)
            try:
                transactions = fetch_transactions(
                    client, account, start_date, end_date, io
                )
                print_transactions(transactions, io)
                last_action = (2, period_choice)
            except Exception as e:
                if is_dialog_error(e):
                    io_output(io, f"\nSession expired: {e}")
                    io_output(io, "Reconnecting...")
                    return True
                raise
        elif choice == 3:
            details = collect_transfer_details(io)
            if details is None:
                io_output(io, "Transfer cancelled.")
                continue

            if not confirm_transfer(details, account.iban, io):
                io_output(io, "Transfer cancelled.")
                continue

            try:
                response = execute_transfer(
                    client,
                    account,
                    recipient_iban=details["recipient_iban"],
                    recipient_bic=details["recipient_bic"],
                    recipient_name=details["recipient_name"],
                    amount=details["amount"],
                    reason=details["reason"],
                    io=io,
                )
                print_transfer_result(response, io)
            except VOPDeclinedError:
                io_output(io, "Transfer cancelled (Verification of Payee declined).")
                continue
            except Exception as e:
                if is_dialog_error(e):
                    io_output(io, f"\nSession expired: {e}")
                    io_output(io, "Reconnecting...")
                    return True
                raise
