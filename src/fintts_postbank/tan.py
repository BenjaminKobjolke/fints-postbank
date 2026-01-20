"""TAN mechanism handling and authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]
from fints.hhd.flicker import terminal_flicker_unix  # type: ignore[import-untyped]

from fintts_postbank.config import Settings, get_settings, save_tan_preferences
from fintts_postbank.ui import get_valid_choice

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter


def _output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


def _input(io: IOAdapter | None, prompt: str) -> str:
    """Get input using IOAdapter or input()."""
    if io is not None:
        return io.input(prompt)
    return input(prompt)


def _try_use_saved_preferences(
    client: FinTS3PinTanClient,
    settings: Settings,
    mechanisms: dict[str, Any],
    io: IOAdapter | None = None,
) -> bool:
    """Try to use saved TAN preferences if available and valid.

    Args:
        client: The FinTS client to configure.
        settings: Settings with saved TAN preferences.
        mechanisms: Available TAN mechanisms from bank.
        io: Optional IOAdapter for I/O operations.

    Returns:
        True if saved preferences were used, False otherwise.
    """
    if not settings.tan_mechanism or not settings.tan_mechanism_name:
        return False

    # Check if saved mechanism is still available
    if settings.tan_mechanism not in mechanisms:
        _output(io, f"Saved TAN mechanism {settings.tan_mechanism} no longer available.")
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
                _output(
                    io, f"Using: {settings.tan_mechanism_name} - {settings.tan_medium}"
                )
                _output(io, "(use --tan to change)")
                return True

        # Medium not found, need to re-select
        _output(io, f"Saved TAN medium '{settings.tan_medium}' no longer available.")
        return False

    # Show what's being used (no medium)
    _output(io, f"Using: {settings.tan_mechanism_name}")
    _output(io, "(use --tan to change)")
    return True


def _select_tan_mechanism(
    client: FinTS3PinTanClient,
    mechanisms: dict[str, Any],
    io: IOAdapter | None = None,
) -> tuple[str, str, Any]:
    """Prompt user to select TAN mechanism.

    Args:
        client: The FinTS client to configure.
        mechanisms: Available TAN mechanisms from bank.
        io: Optional IOAdapter for I/O operations.

    Returns:
        Tuple of (mechanism_key, mechanism_name, mechanism_object).
    """
    if len(mechanisms) == 1:
        key = list(mechanisms.keys())[0]
        mechanism = list(mechanisms.values())[0]
        name = getattr(mechanism, "name", str(mechanism))
        client.set_tan_mechanism(key)
        _output(io, f"Using TAN mechanism: {name}")
        return key, name, mechanism

    _output(io, "Multiple TAN mechanisms available. Which one do you prefer?")
    mech_list = list(mechanisms.items())
    for i, (key, value) in enumerate(mech_list):
        name = getattr(value, "name", str(value))
        _output(io, f"{i} Function {key}: {name}")

    choice = get_valid_choice("Choice: ", len(mech_list) - 1, io=io)
    key, mechanism = mech_list[choice]
    name = getattr(mechanism, "name", str(mechanism))
    client.set_tan_mechanism(key)
    return key, name, mechanism


def _select_tan_medium(
    client: FinTS3PinTanClient,
    io: IOAdapter | None = None,
) -> str | None:
    """Prompt user to select TAN medium if needed.

    Args:
        client: The FinTS client to configure.
        io: Optional IOAdapter for I/O operations.

    Returns:
        Selected medium name or None if not needed.
    """
    _output(io, "We need the name of the TAN medium, let's fetch them from the bank")
    media = client.get_tan_media()

    if len(media[1]) == 0:
        raise ValueError("No TAN media available")
    elif len(media[1]) == 1:
        medium = media[1][0]
        client.set_tan_medium(medium)
        name = getattr(medium, "tan_medium_name", str(medium))
        _output(io, f"Using TAN medium: {name}")
        return name

    _output(io, "Multiple TAN media available. Which one do you prefer?")
    for i, medium in enumerate(media[1]):
        name = getattr(medium, "tan_medium_name", str(medium))
        _output(io, f"{i} {name}")

    choice = get_valid_choice("Choice: ", len(media[1]) - 1, io=io)
    selected = media[1][choice]
    client.set_tan_medium(selected)
    name = getattr(selected, "tan_medium_name", str(selected))
    return name


def interactive_cli_bootstrap(
    client: FinTS3PinTanClient,
    force_tan_selection: bool = False,
    io: IOAdapter | None = None,
) -> None:
    """Bootstrap TAN mechanisms with input validation and preference saving.

    Replacement for fints.utils.minimal_interactive_cli_bootstrap
    that validates user input, saves preferences, and reuses them.

    Args:
        client: The FinTS client to configure.
        force_tan_selection: If True, force manual TAN selection even if saved.
        io: Optional IOAdapter for I/O operations.
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
        if _try_use_saved_preferences(client, settings, mechanisms, io):
            return

    # Manual selection flow
    mech_key, mech_name, chosen_mechanism = _select_tan_mechanism(
        client, mechanisms, io
    )

    # Check if we need to select a TAN medium
    needs_medium = getattr(chosen_mechanism, "needs_tan_medium", None)
    supported_media = getattr(chosen_mechanism, "supported_media_number", 0)
    medium_name: str | None = None

    if needs_medium or supported_media > 0:
        medium_name = _select_tan_medium(client, io)

    # Save preferences for next time
    save_tan_preferences(mech_key, mech_name, medium_name)
    _output(io, "TAN preferences saved.")


def handle_tan_challenge(
    response: NeedTANResponse,
    io: IOAdapter | None = None,
) -> str:
    """Handle TAN challenge from bank.

    For decoupled TAN (BestSign app), prompts user to confirm on device.
    For other TAN methods, prompts for manual TAN entry.

    Args:
        response: The TAN challenge response from the bank.
        io: Optional IOAdapter for I/O operations.

    Returns:
        The TAN entered by user, or empty string for decoupled confirmation.
    """
    challenge = response.challenge
    _output(io, "\nTAN Challenge:")

    if challenge:
        _output(io, f"Challenge: {challenge}")

    # Check if this is a decoupled TAN (like BestSign)
    if response.challenge_hhduc:
        _output(io, "\nPlease confirm this transaction in your BestSign app.")
        _input(io, "Press Enter after confirming...")
        return ""

    # Check for flicker/photoTAN
    if response.challenge_hhduc:
        _output(io, "\nFlicker code displayed (if terminal supports it):")
        try:
            terminal_flicker_unix(response.challenge_hhduc)
        except Exception:
            _output(io, "(Flicker display not available on this terminal)")

    # Manual TAN entry
    tan = _input(io, "\nEnter TAN: ").strip()
    return tan
