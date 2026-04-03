"""List accounts mode - connect to bank and display all SEPA accounts."""

from __future__ import annotations

from typing import Any

from fintts_postbank.client import create_client
from fintts_postbank.config import (
    IBAN,
    save_client_state,
)
from fintts_postbank.operations import fetch_accounts
from fintts_postbank.tan import handle_tan_challenge, interactive_cli_bootstrap


def run_list_accounts_mode(account_name: str | None = None) -> int:
    """Connect to the bank, display all SEPA accounts, and exit.

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("List Accounts Mode")
    print("=" * 40)

    # Discover and select account (lazy import to avoid circular)
    from fintts_postbank.main import _discover_and_select_account

    account = _discover_and_select_account(account_name)
    if account is not None:
        print(f"Using account: {account.name}")

    # Determine configured IBAN for marking
    configured_iban = account.iban if account is not None else IBAN
    acct_label = account.name if account is not None else None

    # Create FinTS client
    client = create_client(account=account)

    # Bootstrap TAN mechanisms
    print("\nInitializing TAN mechanisms...")
    interactive_cli_bootstrap(client, force_tan_selection=False, account=account)

    try:
        with client:
            if client.init_tan_response:
                tan = handle_tan_challenge(client.init_tan_response)
                client.send_tan(client.init_tan_response, tan)

            sepa_accounts = fetch_accounts(client)

        # Save session state
        save_client_state(client.deconstruct(), acct_label)

        if not sepa_accounts:
            print("\nNo SEPA accounts found.")
            return 1

        _print_account_list(sepa_accounts, configured_iban)
        return 0

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        return 1


def _print_account_list(sepa_accounts: list[Any], configured_iban: str) -> None:
    """Print SEPA accounts in a formatted table."""
    normalized_configured = configured_iban.replace(" ", "").upper()

    print(f"\nSEPA Accounts ({len(sepa_accounts)}):")
    print("-" * 60)
    print(f"  {'#':>3}  {'IBAN':<34}  {'BIC':<15}")
    print("-" * 60)

    for i, acc in enumerate(sepa_accounts, start=1):
        iban = acc.iban
        bic = getattr(acc, "bic", "N/A") or "N/A"
        is_configured = iban.replace(" ", "").upper() == normalized_configured
        marker = " *" if is_configured else ""
        print(f"  {i:>3}  {iban:<34}  {bic:<15}{marker}")

    print("-" * 60)
    print("  * = configured account (from .env)")
