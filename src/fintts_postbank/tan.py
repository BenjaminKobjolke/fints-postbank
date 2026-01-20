"""TAN mechanism handling and authentication."""

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]
from fints.hhd.flicker import terminal_flicker_unix  # type: ignore[import-untyped]

from fintts_postbank.config import Settings, get_settings, save_tan_preferences
from fintts_postbank.ui import get_valid_choice


def _try_use_saved_preferences(
    client: FinTS3PinTanClient,
    settings: Settings,
    mechanisms: dict,
) -> bool:
    """Try to use saved TAN preferences if available and valid.

    Args:
        client: The FinTS client to configure.
        settings: Settings with saved TAN preferences.
        mechanisms: Available TAN mechanisms from bank.

    Returns:
        True if saved preferences were used, False otherwise.
    """
    if not settings.tan_mechanism or not settings.tan_mechanism_name:
        return False

    # Check if saved mechanism is still available
    if settings.tan_mechanism not in mechanisms:
        print(f"Saved TAN mechanism {settings.tan_mechanism} no longer available.")
        return False

    # Apply saved mechanism (no confirmation needed)
    client.set_tan_mechanism(settings.tan_mechanism)

    # Apply saved medium if available
    chosen_mechanism = mechanisms[settings.tan_mechanism]
    needs_medium = getattr(chosen_mechanism, "needs_tan_medium", None)
    supported_media = getattr(chosen_mechanism, "supported_media_number", 0)

    if (needs_medium or supported_media > 0) and settings.tan_medium:
        media = client.get_tan_media()
        # Find matching medium
        for medium in media[1]:
            medium_name = getattr(medium, "tan_medium_name", str(medium))
            if medium_name == settings.tan_medium:
                client.set_tan_medium(medium)
                # Show what's being used
                print(f"Using: {settings.tan_mechanism_name} - {settings.tan_medium}")
                print("(use --tan to change)")
                return True

        # Medium not found, need to re-select
        print(f"Saved TAN medium '{settings.tan_medium}' no longer available.")
        return False

    # Show what's being used (no medium)
    print(f"Using: {settings.tan_mechanism_name}")
    print("(use --tan to change)")
    return True


def _select_tan_mechanism(
    client: FinTS3PinTanClient,
    mechanisms: dict,
) -> tuple[str, str, object]:
    """Prompt user to select TAN mechanism.

    Args:
        client: The FinTS client to configure.
        mechanisms: Available TAN mechanisms from bank.

    Returns:
        Tuple of (mechanism_key, mechanism_name, mechanism_object).
    """
    if len(mechanisms) == 1:
        key = list(mechanisms.keys())[0]
        mechanism = list(mechanisms.values())[0]
        name = getattr(mechanism, "name", str(mechanism))
        client.set_tan_mechanism(key)
        print(f"Using TAN mechanism: {name}")
        return key, name, mechanism

    print("Multiple TAN mechanisms available. Which one do you prefer?")
    mech_list = list(mechanisms.items())
    for i, (key, value) in enumerate(mech_list):
        name = getattr(value, "name", str(value))
        print(f"{i} Function {key}: {name}")

    choice = get_valid_choice("Choice: ", len(mech_list) - 1)
    key, mechanism = mech_list[choice]
    name = getattr(mechanism, "name", str(mechanism))
    client.set_tan_mechanism(key)
    return key, name, mechanism


def _select_tan_medium(client: FinTS3PinTanClient) -> str | None:
    """Prompt user to select TAN medium if needed.

    Args:
        client: The FinTS client to configure.

    Returns:
        Selected medium name or None if not needed.
    """
    print("We need the name of the TAN medium, let's fetch them from the bank")
    media = client.get_tan_media()

    if len(media[1]) == 0:
        raise ValueError("No TAN media available")
    elif len(media[1]) == 1:
        medium = media[1][0]
        client.set_tan_medium(medium)
        name = getattr(medium, "tan_medium_name", str(medium))
        print(f"Using TAN medium: {name}")
        return name

    print("Multiple TAN media available. Which one do you prefer?")
    for i, medium in enumerate(media[1]):
        name = getattr(medium, "tan_medium_name", str(medium))
        print(f"{i} {name}")

    choice = get_valid_choice("Choice: ", len(media[1]) - 1)
    selected = media[1][choice]
    client.set_tan_medium(selected)
    name = getattr(selected, "tan_medium_name", str(selected))
    return name


def interactive_cli_bootstrap(
    client: FinTS3PinTanClient,
    force_tan_selection: bool = False,
) -> None:
    """Bootstrap TAN mechanisms with input validation and preference saving.

    Replacement for fints.utils.minimal_interactive_cli_bootstrap
    that validates user input, saves preferences, and reuses them.

    Args:
        client: The FinTS client to configure.
        force_tan_selection: If True, force manual TAN selection even if saved.
    """
    # Fetch TAN mechanisms from bank if not already cached
    if not client.get_tan_mechanisms():
        client.fetch_tan_mechanisms()

    mechanisms = client.get_tan_mechanisms()
    if len(mechanisms) == 0:
        raise ValueError("No TAN mechanisms available")

    # Load saved preferences
    settings = get_settings()

    # Try to use saved preferences (unless forced to re-select)
    if not force_tan_selection:
        if _try_use_saved_preferences(client, settings, mechanisms):
            return

    # Manual selection flow
    mech_key, mech_name, chosen_mechanism = _select_tan_mechanism(client, mechanisms)

    # Check if we need to select a TAN medium
    needs_medium = getattr(chosen_mechanism, "needs_tan_medium", None)
    supported_media = getattr(chosen_mechanism, "supported_media_number", 0)
    medium_name: str | None = None

    if needs_medium or supported_media > 0:
        medium_name = _select_tan_medium(client)

    # Save preferences for next time
    save_tan_preferences(mech_key, mech_name, medium_name)
    print("TAN preferences saved.")


def handle_tan_challenge(response: NeedTANResponse) -> str:
    """Handle TAN challenge from bank.

    For decoupled TAN (BestSign app), prompts user to confirm on device.
    For other TAN methods, prompts for manual TAN entry.

    Args:
        response: The TAN challenge response from the bank.

    Returns:
        The TAN entered by user, or empty string for decoupled confirmation.
    """
    challenge = response.challenge
    print("\n" + "=" * 50)
    print("TAN CHALLENGE")
    print("=" * 50)

    if challenge:
        print(f"Challenge: {challenge}")

    # Check if this is a decoupled TAN (like BestSign)
    if response.challenge_hhduc:
        print("\nPlease confirm this transaction in your BestSign app.")
        print("Press Enter after confirming...")
        input()
        return ""

    # Check for flicker/photoTAN
    if response.challenge_hhduc:
        print("\nFlicker code displayed (if terminal supports it):")
        try:
            terminal_flicker_unix(response.challenge_hhduc)
        except Exception:
            print("(Flicker display not available on this terminal)")

    # Manual TAN entry
    tan = input("\nEnter TAN: ").strip()
    return tan
