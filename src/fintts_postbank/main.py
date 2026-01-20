"""Main entry point for Postbank FinTS operations."""

import sys

from fintts_postbank.client import create_client, run_session
from fintts_postbank.tan import interactive_cli_bootstrap


def run_console_mode(force_tan_selection: bool) -> None:
    """Run the FinTS client in console mode.

    Args:
        force_tan_selection: Whether to force TAN mechanism selection
    """
    print("Postbank FinTS Client")

    try:
        first_run = True
        while True:
            # Create client
            client = create_client()

            # Bootstrap TAN mechanisms (required before with client:)
            # Only force TAN selection on first run if --tan was passed
            print("\nInitializing TAN mechanisms...")
            interactive_cli_bootstrap(
                client,
                force_tan_selection=force_tan_selection and first_run,
            )
            first_run = False

            # Run session (may request reconnection)
            needs_reconnect = run_session(client)

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
    # Parse command line arguments
    force_tan_selection = "--tan" in sys.argv
    telegram_mode = "--telegram" in sys.argv
    update_api_mode = "--update-api" in sys.argv

    if update_api_mode:
        # Import here to avoid loading dependencies in other modes
        from fintts_postbank.update_api_mode import run_update_api_mode

        sys.exit(run_update_api_mode())
    elif telegram_mode:
        # Import here to avoid loading telegram dependencies in console mode
        from fintts_postbank.telegram_mode import run_telegram_mode

        try:
            run_telegram_mode(force_tan_selection)
        except ValueError as e:
            print(f"\nConfiguration error: {e}")
        except Exception as e:
            print(f"\nError: {e}")
            raise
    else:
        run_console_mode(force_tan_selection)


if __name__ == "__main__":
    main()
