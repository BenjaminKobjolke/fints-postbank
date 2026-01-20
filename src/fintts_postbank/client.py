"""FinTS client management and session handling."""

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


def create_client() -> FinTS3PinTanClient:
    """Create and configure FinTS client for Postbank.

    Attempts to load saved session state for faster initialization.

    Returns:
        Configured FinTS client instance.
    """
    settings = get_settings()

    # Try to load saved session state
    saved_state = load_client_state()
    if saved_state:
        print("Loading saved session state...")

    client = FinTS3PinTanClient(
        bank_identifier=BLZ,
        user_id=settings.username,
        pin=settings.password,
        server=HBCI_URL,
        product_id=PRODUCT_ID,
        from_data=saved_state,
    )

    return client


def run_session(client: FinTS3PinTanClient) -> bool:
    """Run a single FinTS session.

    Args:
        client: Configured FinTS client.

    Returns:
        True if reconnection is needed, False for normal exit.
    """
    with client:
        # Handle initialization TAN if needed (PSD2 requirement)
        if client.init_tan_response:
            tan = handle_tan_challenge(client.init_tan_response)
            client.send_tan(client.init_tan_response, tan)

        # Fetch accounts
        accounts = fetch_accounts(client)

        if not accounts:
            print("No accounts found!")
            return False

        # Find the configured account
        account = find_account_by_iban(accounts, IBAN)
        if not account:
            print(f"Account with IBAN {IBAN} not found!")
            print("Using first available account...")
            account = accounts[0]

        print(f"\nUsing account: {account.iban}")

        # Run interactive menu loop
        needs_reconnect = run_menu_loop(client, account)

    # Save session state for faster next startup
    session_data = client.deconstruct()
    save_client_state(session_data)

    return needs_reconnect
