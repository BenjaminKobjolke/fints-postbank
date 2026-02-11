"""FinTS client management and session handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]

from fintts_postbank.config import (
    BLZ,
    HBCI_URL,
    IBAN,
    PRODUCT_ID,
    get_settings,
    load_client_state,
    save_client_state,
)
from fintts_postbank.menu import run_menu_loop
from fintts_postbank.operations import fetch_accounts, find_account_by_iban
from fintts_postbank.tan import handle_tan_challenge

if TYPE_CHECKING:
    from fintts_postbank.config import AccountConfig
    from fintts_postbank.io import IOAdapter


def _output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


def create_client(
    io: IOAdapter | None = None,
    account: AccountConfig | None = None,
) -> FinTS3PinTanClient:
    """Create and configure FinTS client for Postbank.

    Attempts to load saved session state for faster initialization.

    Args:
        io: Optional IOAdapter for I/O operations.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Configured FinTS client instance.
    """
    # Use account-specific settings if provided
    if account is not None:
        settings = get_settings(account.env_path)
        blz = account.blz
        hbci_url = account.hbci_url
        product_id = account.product_id
        saved_state = load_client_state(account.name)
    else:
        settings = get_settings()
        blz = BLZ
        hbci_url = HBCI_URL
        product_id = PRODUCT_ID
        saved_state = load_client_state()

    # Try to load saved session state
    if saved_state:
        _output(io, "Loading saved session state...")

    client = FinTS3PinTanClient(
        bank_identifier=blz,
        user_id=settings.username,
        pin=settings.password,
        server=hbci_url,
        product_id=product_id,
        from_data=saved_state,
    )

    return client


def run_session(
    client: FinTS3PinTanClient,
    io: IOAdapter | None = None,
    account: AccountConfig | None = None,
) -> bool:
    """Run a single FinTS session.

    Args:
        client: Configured FinTS client.
        io: Optional IOAdapter for I/O operations.
        account: Optional AccountConfig for multi-account support.

    Returns:
        True if reconnection is needed, False for normal exit.
    """
    # Use account-specific IBAN if provided
    iban = account.iban if account is not None else IBAN
    account_name = account.name if account is not None else None

    with client:
        # Handle initialization TAN if needed (PSD2 requirement)
        if client.init_tan_response:
            tan = handle_tan_challenge(client.init_tan_response, io)
            client.send_tan(client.init_tan_response, tan)

        # Fetch accounts
        accounts = fetch_accounts(client, io)

        if not accounts:
            _output(io, "No accounts found!")
            return False

        # Find the configured account
        sepa_account = find_account_by_iban(accounts, iban)
        if not sepa_account:
            _output(io, f"Account with IBAN {iban} not found!")
            _output(io, "Using first available account...")
            sepa_account = accounts[0]

        _output(io, f"\nUsing account: {sepa_account.iban}")

        # Run interactive menu loop
        needs_reconnect = run_menu_loop(client, sepa_account, io)

    # Save session state for faster next startup
    session_data = client.deconstruct()
    save_client_state(session_data, account_name)

    return needs_reconnect
