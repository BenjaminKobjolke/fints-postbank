"""Main entry point for Postbank FinTS operations."""

import sys

from fintts_postbank.client import create_client, run_session
from fintts_postbank.config import AccountConfig, discover_accounts, select_account
from fintts_postbank.tan import interactive_cli_bootstrap


def _parse_account_arg() -> str | None:
    """Parse --account <name> from sys.argv.

    Returns:
        Account name if specified, None otherwise.
    """
    for i, arg in enumerate(sys.argv):
        if arg == "--account" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


def _discover_and_select_account(
    account_name: str | None = None,
) -> AccountConfig | None:
    """Discover accounts and select one.

    Returns None if only the default .env exists (backward compat).

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Selected AccountConfig, or None for single default account.
    """
    accounts = discover_accounts()

    if not accounts:
        return None

    # If only one account and it's "default" and no --account flag, return None
    # to preserve backward-compatible behavior
    if len(accounts) == 1 and accounts[0].name == "default" and account_name is None:
        return None

    return select_account(accounts, account_name)


def run_console_mode(
    force_tan_selection: bool,
    account_name: str | None = None,
) -> None:
    """Run the FinTS client in console mode.

    Args:
        force_tan_selection: Whether to force TAN mechanism selection
        account_name: Optional account name from --account flag
    """
    print("Postbank FinTS Client")

    # Discover and select account
    account = _discover_and_select_account(account_name)
    if account is not None:
        print(f"Using account: {account.name}")

    try:
        first_run = True
        while True:
            # Create client
            client = create_client(account=account)

            # Bootstrap TAN mechanisms (required before with client:)
            # Only force TAN selection on first run if --tan was passed
            print("\nInitializing TAN mechanisms...")
            interactive_cli_bootstrap(
                client,
                force_tan_selection=force_tan_selection and first_run,
                account=account,
            )
            first_run = False

            # Run session (may request reconnection)
            needs_reconnect = run_session(client, account=account)

            if not needs_reconnect:
                break

            print("\nReconnecting...")

        print("\nSession saved. Goodbye.")

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Please ensure .env file exists with FINTS_USERNAME and FINTS_PASSWORD")
    except Exception as e:
        print(f"\nError: {e}")
        raise


def main() -> None:
    """Main entry point."""
    from fintts_postbank.config import get_bot_mode

    # Parse command line arguments
    force_tan_selection = "--tan" in sys.argv
    update_api_mode = "--update-api" in sys.argv
    update_bot_mode = "--update-bot" in sys.argv
    test_bot_mode = "--test-bot" in sys.argv
    account_name = _parse_account_arg()

    # Validate mutually exclusive mode flags
    mode_flags = [update_api_mode, update_bot_mode, test_bot_mode]
    if sum(mode_flags) > 1:
        print("Error: --update-api, --update-bot, and --test-bot are mutually exclusive")
        sys.exit(1)

    # Determine bot mode: CLI flags override env var
    telegram_flag = "--telegram" in sys.argv
    xmpp_flag = "--xmpp" in sys.argv

    # Validate mutually exclusive CLI flags
    if telegram_flag and xmpp_flag:
        print("Error: --telegram and --xmpp are mutually exclusive")
        sys.exit(1)

    # CLI flags override env var
    if telegram_flag:
        bot_mode = "telegram"
    elif xmpp_flag:
        bot_mode = "xmpp"
    else:
        bot_mode = get_bot_mode()  # From BOT_MODE env var, defaults to "console"

    if update_api_mode:
        # Import here to avoid loading dependencies in other modes
        from fintts_postbank.update_api_mode import run_update_api_mode

        sys.exit(run_update_api_mode(account_name=account_name))
    elif update_bot_mode:
        # Import here to avoid loading dependencies in other modes
        from fintts_postbank.update_bot_mode import run_update_bot_mode

        sys.exit(run_update_bot_mode(account_name=account_name))
    elif test_bot_mode:
        # Import here to avoid loading dependencies in other modes
        from fintts_postbank.test_bot_mode import run_test_bot_mode

        sys.exit(run_test_bot_mode(account_name=account_name))
    elif bot_mode == "telegram":
        # Import here to avoid loading telegram dependencies in console mode
        from fintts_postbank.telegram_mode import run_telegram_mode

        try:
            run_telegram_mode(force_tan_selection, account_name=account_name)
        except ValueError as e:
            print(f"\nConfiguration error: {e}")
        except Exception as e:
            print(f"\nError: {e}")
            raise
    elif bot_mode == "xmpp":
        # Import here to avoid loading xmpp dependencies in other modes
        from fintts_postbank.xmpp_mode import run_xmpp_mode

        try:
            run_xmpp_mode(force_tan_selection, account_name=account_name)
        except ValueError as e:
            print(f"\nConfiguration error: {e}")
        except Exception as e:
            print(f"\nError: {e}")
            raise
    else:
        run_console_mode(force_tan_selection, account_name=account_name)


if __name__ == "__main__":
    main()
