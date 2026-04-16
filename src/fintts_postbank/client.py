"""FinTS client management and session handling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]

from fintts_postbank.config import (
    BLZ,
    HBCI_URL,
    IBAN,
    PRODUCT_ID,
    clear_client_state,
    get_settings,
    load_client_state,
    save_client_state,
)
from fintts_postbank.io.helpers import io_output
from fintts_postbank.logger import get_logger
from fintts_postbank.menu import run_menu_loop
from fintts_postbank.operations import fetch_accounts, find_account_by_iban
from fintts_postbank.tan import handle_tan_challenge

if TYPE_CHECKING:
    from fintts_postbank.config import AccountConfig
    from fintts_postbank.io import IOAdapter

logger = get_logger(__name__)


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
        logger.info("Creating client for account: %s", account.name)
        settings = get_settings(account.env_path)
        blz = account.blz
        hbci_url = account.hbci_url
        product_id = account.product_id
        saved_state = load_client_state(account.name)
    else:
        logger.info("Creating client with default settings")
        settings = get_settings()
        blz = BLZ
        hbci_url = HBCI_URL
        product_id = PRODUCT_ID
        saved_state = load_client_state()

    # Try to load saved session state
    if saved_state:
        logger.info("Loaded saved session state (%d bytes)", len(saved_state))
        print("Loading saved session state...")
    else:
        logger.info("No saved session state found")

    client = FinTS3PinTanClient(
        bank_identifier=blz,
        user_id=settings.username,
        pin=settings.password,
        server=hbci_url,
        product_id=product_id,
        from_data=saved_state,
    )

    return client


def create_and_bootstrap_client(
    io: IOAdapter | None = None,
    account: AccountConfig | None = None,
    force_tan_selection: bool = False,
) -> FinTS3PinTanClient:
    """Create a FinTS client and bootstrap TAN mechanisms, with stale-session retry.

    If TAN mechanism initialization fails and a saved session was used,
    clears the stale session and retries with a fresh connection.

    Args:
        io: Optional IOAdapter for I/O operations.
        account: Optional AccountConfig for multi-account support.
        force_tan_selection: If True, force manual TAN selection.

    Returns:
        Configured FinTS client with TAN mechanisms ready.
    """
    from fintts_postbank.tan import interactive_cli_bootstrap

    account_name = account.name if account is not None else None
    had_saved_state = load_client_state(account_name) is not None
    logger.info(
        "Bootstrap: account=%s, had_saved_state=%s, force_tan=%s",
        account_name, had_saved_state, force_tan_selection,
    )

    client = create_client(io, account)

    try:
        interactive_cli_bootstrap(
            client, force_tan_selection=force_tan_selection, io=io, account=account
        )
        logger.info("Bootstrap completed successfully")
        return client
    except ValueError as e:
        logger.warning("Bootstrap failed: %s", e)
        if "No TAN mechanisms available" not in str(e) or not had_saved_state:
            raise

    # Stale session — clear and retry once with fresh connection
    logger.info("Stale session detected, clearing and retrying")
    io_output(io, "Stale session detected, retrying with fresh connection...")
    clear_client_state(account_name)
    client = create_client(io, account)
    interactive_cli_bootstrap(
        client, force_tan_selection=force_tan_selection, io=io, account=account
    )
    logger.info("Bootstrap retry completed successfully")
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
            logger.info("Init TAN required (PSD2)")
            tan = handle_tan_challenge(client.init_tan_response, io)
            client.send_tan(client.init_tan_response, tan)
            logger.info("Init TAN completed")
        else:
            logger.info("No init TAN required")

        # Fetch accounts
        accounts = fetch_accounts(client, io)

        if not accounts:
            io_output(io, "No accounts found!")
            return False

        # Find the configured account
        sepa_account = find_account_by_iban(accounts, iban)
        if not sepa_account:
            io_output(io, f"Account with IBAN {iban} not found!")
            io_output(io, "Using first available account...")
            sepa_account = accounts[0]

        io_output(io, f"\nUsing account: {sepa_account.iban}")

        # Run interactive menu loop
        needs_reconnect = run_menu_loop(client, sepa_account, io)

    # Save session state for faster next startup
    session_data = client.deconstruct()
    save_client_state(session_data, account_name)
    logger.info("Session state saved (%d bytes) for account=%s", len(session_data), account_name)

    return needs_reconnect
