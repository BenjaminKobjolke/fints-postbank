"""List TAN mode - connect to bank and display available TAN mechanisms and media."""

from __future__ import annotations

from typing import Any

from fintts_postbank.client import create_client
from fintts_postbank.config import (
    clear_client_state,
    get_settings,
    load_client_state,
    save_client_state,
)


def run_list_tan_mode(account_name: str | None = None) -> int:
    """Connect to the bank, display TAN mechanisms and media, and exit.

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("List TAN Mode")
    print("=" * 40)

    # Discover and select account (lazy import to avoid circular)
    from fintts_postbank.main import _discover_and_select_account

    account = _discover_and_select_account(account_name)
    if account is not None:
        print(f"Using account: {account.name}")

    # Load current settings to show what's configured
    env_path = account.env_path if account is not None else None
    settings = get_settings(env_path)
    acct_label = account.name if account is not None else None

    # Create client directly (skip bootstrap to avoid TAN selection prompt)
    had_saved_state = load_client_state(acct_label) is not None
    client = create_client(account=account)

    try:
        mechanisms = _fetch_mechanisms(client)

        # Stale session retry — same pattern as create_and_bootstrap_client
        if not mechanisms and had_saved_state:
            print("Stale session detected, retrying with fresh connection...")
            clear_client_state(acct_label)
            client = create_client(account=account)
            mechanisms = _fetch_mechanisms(client)

        if not mechanisms:
            print("\nNo TAN mechanisms available.")
            return 1

        _print_mechanisms(mechanisms, settings.tan_mechanism)

        # For each mechanism that needs media, set it and fetch media.
        # set_tan_mechanism() and get_tan_media() work outside a standing
        # dialog — same pattern as interactive_cli_bootstrap in tan.py.
        for key, mechanism in mechanisms.items():
            needs_medium = getattr(mechanism, "needs_tan_medium", None)
            supported_media = getattr(mechanism, "supported_media_number", 0)

            if not (needs_medium or supported_media > 0):
                continue

            mech_name = getattr(mechanism, "name", str(mechanism))
            client.set_tan_mechanism(key)

            try:
                media = client.get_tan_media()
            except Exception as e:
                print(f"\nCould not fetch media for {key} ({mech_name}): {e}")
                continue

            if not media[1]:
                print(f"\nNo TAN media found for {key} ({mech_name}).")
                continue

            _print_media(media[1], key, mech_name, settings.tan_medium)

        # Save session state
        save_client_state(client.deconstruct(), acct_label)

        print("\nSession saved.")
        return 0

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        return 1


def _fetch_mechanisms(client: Any) -> dict[str, Any]:
    """Fetch TAN mechanisms, returning empty dict on failure."""
    try:
        if not client.get_tan_mechanisms():
            client.fetch_tan_mechanisms()
        return client.get_tan_mechanisms()
    except Exception:
        return {}


def _print_mechanisms(
    mechanisms: dict[str, Any], configured_mechanism: str | None
) -> None:
    """Print TAN mechanisms in a formatted table."""
    print(f"\nTAN Mechanisms ({len(mechanisms)}):")
    print("-" * 55)
    print(f"  {'#':>3}  {'Function':<10}  {'Name'}")
    print("-" * 55)

    for i, (key, mechanism) in enumerate(mechanisms.items(), start=1):
        name = getattr(mechanism, "name", str(mechanism))
        marker = "  *" if key == configured_mechanism else ""
        print(f"  {i:>3}  {key:<10}  {name}{marker}")

    print("-" * 55)
    print("  * = configured in .env")


def _print_media(
    media_list: list[Any],
    mech_key: str,
    mech_name: str,
    configured_medium: str | None,
) -> None:
    """Print TAN media in a formatted table."""
    print(f"\nTAN Media for {mech_key} ({mech_name}):")
    print("-" * 55)
    print(f"  {'#':>3}  {'Name'}")
    print("-" * 55)

    for i, medium in enumerate(media_list, start=1):
        medium_name = getattr(medium, "tan_medium_name", str(medium))
        marker = "  *" if medium_name == configured_medium else ""
        print(f"  {i:>3}  {medium_name}{marker}")

    print("-" * 55)
    print("  * = configured in .env")
