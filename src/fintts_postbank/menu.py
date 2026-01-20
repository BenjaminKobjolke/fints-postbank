"""Interactive menu handling for the CLI."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]

from fintts_postbank.operations import (
    fetch_balance,
    fetch_transactions,
    print_balance,
    print_transactions,
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


def _output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


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
    _output(io, "\nSelect time period:")
    _output(io, "1. Today")
    _output(io, "2. This week")
    _output(io, "3. This month")
    _output(io, "4. This year")
    _output(io, "5. All")
    _output(io, "0. Back")
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
    _output(io, "\n1. Show balance")
    _output(io, "2. Show transactions")
    _output(io, "0. Exit")
    if last_action_label:
        _output(io, f"\n[Enter] {last_action_label}")
        return get_valid_choice("\nChoice: ", 2, default=-1, io=io)
    return get_valid_choice("\nChoice: ", 2, io=io)


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
                        _output(io, f"\nSession expired: {e}")
                        _output(io, "Reconnecting...")
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
                    _output(io, f"\nSession expired: {e}")
                    _output(io, "Reconnecting...")
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
                    _output(io, f"\nSession expired: {e}")
                    _output(io, "Reconnecting...")
                    return True
                raise
