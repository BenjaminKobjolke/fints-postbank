"""Environment-based settings for FinTS authentication."""

import os
from dataclasses import dataclass
from datetime import date
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


@dataclass(frozen=True)
class TelegramSettings:
    """Telegram bot settings loaded from environment."""

    bot_token: str | None = None
    allowed_chat_ids: set[int] | None = None
    allowed_user_ids: set[int] | None = None


@dataclass(frozen=True)
class XmppSettings:
    """XMPP bot settings loaded from environment."""

    jid: str | None = None
    password: str | None = None
    default_receiver: str | None = None
    allowed_jids: frozenset[str] | None = None
    resource: str = "fints-bot"
    connect_timeout: int = 30


@dataclass(frozen=True)
class ApiSettings:
    """API settings for forecast-php integration."""

    api_url: str
    api_user: str
    api_password: str
    telegram_target_user_id: int
    transaction_start_date: date


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


def get_telegram_settings() -> TelegramSettings:
    """Load Telegram bot settings from environment variables.

    Returns:
        TelegramSettings object with bot token and allowed chat IDs.
    """
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")

    # Parse allowed chat IDs (comma-separated list)
    allowed_chat_ids_str = os.getenv("TELEGRAM_ALLOWED_CHAT_IDS", "")
    allowed_chat_ids: set[int] | None = None

    if allowed_chat_ids_str.strip():
        try:
            allowed_chat_ids = {
                int(chat_id.strip())
                for chat_id in allowed_chat_ids_str.split(",")
                if chat_id.strip()
            }
        except ValueError:
            pass  # Invalid format, treat as no whitelist

    # Parse allowed user IDs (comma-separated list)
    allowed_user_ids_str = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
    allowed_user_ids: set[int] | None = None

    if allowed_user_ids_str.strip():
        try:
            allowed_user_ids = {
                int(user_id.strip())
                for user_id in allowed_user_ids_str.split(",")
                if user_id.strip()
            }
        except ValueError:
            pass  # Invalid format, treat as no whitelist

    return TelegramSettings(
        bot_token=bot_token,
        allowed_chat_ids=allowed_chat_ids,
        allowed_user_ids=allowed_user_ids,
    )


def get_bot_mode() -> str:
    """Get the bot mode from environment variable.

    Returns:
        Bot mode: "console", "telegram", or "xmpp"
    """
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"
    load_dotenv(env_path)

    mode = os.getenv("BOT_MODE", "console").lower().strip()
    if mode not in ("console", "telegram", "xmpp"):
        return "console"
    return mode


def get_xmpp_settings() -> XmppSettings:
    """Load XMPP bot settings from environment variables.

    Returns:
        XmppSettings object with XMPP configuration.
    """
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    jid = os.getenv("XMPP_JID")
    password = os.getenv("XMPP_PASSWORD")
    default_receiver = os.getenv("XMPP_DEFAULT_RECEIVER")

    # Parse allowed JIDs (comma-separated list)
    allowed_jids_str = os.getenv("XMPP_ALLOWED_JIDS", "")
    allowed_jids: frozenset[str] | None = None

    if allowed_jids_str.strip():
        allowed_jids = frozenset(
            jid_item.strip().lower()
            for jid_item in allowed_jids_str.split(",")
            if jid_item.strip()
        )

    # Parse optional settings with defaults
    resource = os.getenv("XMPP_RESOURCE", "fints-bot")

    connect_timeout_str = os.getenv("XMPP_CONNECT_TIMEOUT", "30")
    try:
        connect_timeout = int(connect_timeout_str)
    except ValueError:
        connect_timeout = 30

    return XmppSettings(
        jid=jid,
        password=password,
        default_receiver=default_receiver,
        allowed_jids=allowed_jids,
        resource=resource,
        connect_timeout=connect_timeout,
    )


def get_api_settings() -> ApiSettings:
    """Load API settings from environment variables.

    Returns:
        ApiSettings object with API configuration.

    Raises:
        ValueError: If required environment variables are missing or invalid.
    """
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    api_url = os.getenv("API_URL")
    api_user = os.getenv("API_USER")
    api_password = os.getenv("API_PASSWORD")
    telegram_target_user_id_str = os.getenv("TELEGRAM_TARGET_USER_ID")
    transaction_start_date_str = os.getenv("TRANSACTION_START_DATE")

    # Validate required fields
    missing = []
    if not api_url:
        missing.append("API_URL")
    if not api_user:
        missing.append("API_USER")
    if not api_password:
        missing.append("API_PASSWORD")
    if not telegram_target_user_id_str:
        missing.append("TELEGRAM_TARGET_USER_ID")
    if not transaction_start_date_str:
        missing.append("TRANSACTION_START_DATE")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Parse telegram target user ID
    try:
        telegram_target_user_id = int(telegram_target_user_id_str)  # type: ignore[arg-type]
    except ValueError as err:
        raise ValueError(
            f"TELEGRAM_TARGET_USER_ID must be an integer, got: {telegram_target_user_id_str}"
        ) from err

    # Parse transaction start date (YYYY-MM-DD format)
    try:
        transaction_start_date = date.fromisoformat(transaction_start_date_str)  # type: ignore[arg-type]
    except ValueError as err:
        raise ValueError(
            f"TRANSACTION_START_DATE must be in YYYY-MM-DD format, "
            f"got: {transaction_start_date_str}"
        ) from err

    return ApiSettings(
        api_url=api_url,  # type: ignore[arg-type]
        api_user=api_user,  # type: ignore[arg-type]
        api_password=api_password,  # type: ignore[arg-type]
        telegram_target_user_id=telegram_target_user_id,
        transaction_start_date=transaction_start_date,
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
