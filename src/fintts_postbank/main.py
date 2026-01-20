"""Main entry point for Postbank FinTS operations."""

import sys

from fintts_postbank.client import create_client, run_session
from fintts_postbank.tan import interactive_cli_bootstrap


def main() -> None:
    """Main entry point."""
    # Parse command line arguments
    force_tan_selection = "--tan" in sys.argv

    print("=" * 70)
    print("POSTBANK FINTS CLIENT")
    print("=" * 70)

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

            print("\n" + "-" * 70)
            print("Reconnecting to bank...")
            print("-" * 70)

        print("\nSession saved.")

        print("\n" + "=" * 70)
        print("GOODBYE")
        print("=" * 70)

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Please ensure .env file exists with FINTS_USERNAME and FINTS_PASSWORD")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
