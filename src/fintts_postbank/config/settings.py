"""Environment-based settings for FinTS authentication."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """FinTS authentication settings loaded from environment."""

    username: str
    password: str
    tan_mechanism: str | None = None
    tan_mechanism_name: str | None = None
    tan_medium: str | None = None


def get_settings() -> Settings:
    """Load settings from environment variables.

    Looks for .env file in project root directory.

    Returns:
        Settings object with username and password.

    Raises:
        ValueError: If required environment variables are missing.
    """
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    username = os.getenv("FINTS_USERNAME")
    password = os.getenv("FINTS_PASSWORD")

    if not username:
        raise ValueError("FINTS_USERNAME environment variable is required")
    if not password:
        raise ValueError("FINTS_PASSWORD environment variable is required")

    # Load optional TAN preferences
    tan_mechanism = os.getenv("FINTS_TAN_MECHANISM")
    tan_mechanism_name = os.getenv("FINTS_TAN_MECHANISM_NAME")
    tan_medium = os.getenv("FINTS_TAN_MEDIUM")

    return Settings(
        username=username,
        password=password,
        tan_mechanism=tan_mechanism,
        tan_mechanism_name=tan_mechanism_name,
        tan_medium=tan_medium,
    )


def _get_env_path() -> Path:
    """Get the path to the .env file."""
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / ".env"


def save_tan_preferences(
    mechanism: str,
    mechanism_name: str,
    medium: str | None = None,
) -> None:
    """Save TAN preferences to .env file.

    Updates or adds TAN preference variables in the .env file.

    Args:
        mechanism: TAN mechanism function number (e.g., "920").
        mechanism_name: TAN mechanism name (e.g., "BestSign").
        medium: TAN medium name (e.g., "BennyHauptHandy"), optional.
    """
    env_path = _get_env_path()

    # Read existing content
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
    else:
        lines = []

    # Variables to update/add
    updates = {
        "FINTS_TAN_MECHANISM": mechanism,
        "FINTS_TAN_MECHANISM_NAME": mechanism_name,
    }
    if medium:
        updates["FINTS_TAN_MEDIUM"] = medium

    # Track which variables were updated
    updated_vars: set[str] = set()

    # Update existing lines
    new_lines = []
    for line in lines:
        updated = False
        for var_name, var_value in updates.items():
            if line.startswith(f"{var_name}="):
                new_lines.append(f"{var_name}={var_value}")
                updated_vars.add(var_name)
                updated = True
                break
        if not updated:
            new_lines.append(line)

    # Add missing variables
    for var_name, var_value in updates.items():
        if var_name not in updated_vars:
            new_lines.append(f"{var_name}={var_value}")

    # Write back
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _get_session_path() -> Path:
    """Get the path to the session file."""
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / ".fints_session"


def save_client_state(data: bytes) -> None:
    """Save client state to file for session reuse.

    Args:
        data: Serialized client state from client.deconstruct().
    """
    session_path = _get_session_path()
    session_path.write_bytes(data)


def load_client_state() -> bytes | None:
    """Load saved client state if available.

    Returns:
        Serialized client state bytes, or None if not available.
    """
    session_path = _get_session_path()
    if session_path.exists():
        return session_path.read_bytes()
    return None


def clear_client_state() -> None:
    """Remove saved client state file."""
    session_path = _get_session_path()
    if session_path.exists():
        session_path.unlink()
