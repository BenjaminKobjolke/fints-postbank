"""Environment-based settings for FinTS authentication."""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

# Cache parsed env files to avoid repeated parsing (and repeated warnings)
_dotenv_cache: dict[Path, dict[str, str | None]] = {}


def _cached_dotenv_values(path: Path) -> dict[str, str | None]:
    """Parse a .env file, caching the result per path."""
    if path not in _dotenv_cache:
        _dotenv_cache[path] = dotenv_values(path)
    return _dotenv_cache[path]


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
class BotUpdateSettings:
    """Settings for --update-bot mode (bot notification without API)."""

    telegram_target_user_id: int | None = None
    transaction_days: int = 30


@dataclass(frozen=True)
class ApiSettings:
    """API settings for forecast-php integration."""

    api_url: str
    api_user: str
    api_password: str
    transaction_start_date: date
    telegram_target_user_id: int | None = None


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


def _get_value(
    key: str,
    env_values: dict[str, str | None] | None,
    default: str | None = None,
) -> str | None:
    """Get a config value from env_values dict or os.getenv fallback.

    Args:
        key: Environment variable name.
        env_values: Pre-loaded env values (from dotenv_values), or None.
        default: Default value if not found.

    Returns:
        The value, or default.
    """
    if env_values is not None:
        val = env_values.get(key)
        if val is not None:
            return val
    return os.getenv(key, default)


def _load_env(env_path: Path | None = None) -> dict[str, str | None] | None:
    """Load env values from a specific path, or load default .env.

    Args:
        env_path: Specific .env file to load. If None, loads default .env.

    Returns:
        Dict of env values if env_path given, None otherwise (uses os.getenv).
    """
    if env_path is not None:
        return _cached_dotenv_values(env_path)

    # Default: load into os.environ
    project_root = _get_project_root()
    load_dotenv(project_root / ".env")
    return None


def get_settings(env_path: Path | None = None) -> Settings:
    """Load settings from environment variables.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        Settings object with username and password.

    Raises:
        ValueError: If required environment variables are missing.
    """
    env_values = _load_env(env_path)

    username = _get_value("FINTS_USERNAME", env_values)
    password = _get_value("FINTS_PASSWORD", env_values)

    if not username:
        raise ValueError("FINTS_USERNAME environment variable is required")
    if not password:
        raise ValueError("FINTS_PASSWORD environment variable is required")

    # Load optional TAN preferences
    tan_mechanism = _get_value("FINTS_TAN_MECHANISM", env_values)
    tan_mechanism_name = _get_value("FINTS_TAN_MECHANISM_NAME", env_values)
    tan_medium = _get_value("FINTS_TAN_MEDIUM", env_values)

    return Settings(
        username=username,
        password=password,
        tan_mechanism=tan_mechanism,
        tan_mechanism_name=tan_mechanism_name,
        tan_medium=tan_medium,
    )


def get_telegram_settings(env_path: Path | None = None) -> TelegramSettings:
    """Load Telegram bot settings from environment variables.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        TelegramSettings object with bot token and allowed chat IDs.
    """
    env_values = _load_env(env_path)

    bot_token = _get_value("TELEGRAM_BOT_TOKEN", env_values)

    # Parse allowed chat IDs (comma-separated list)
    allowed_chat_ids_str = _get_value("TELEGRAM_ALLOWED_CHAT_IDS", env_values, "")
    allowed_chat_ids: set[int] | None = None

    if allowed_chat_ids_str and allowed_chat_ids_str.strip():
        try:
            allowed_chat_ids = {
                int(chat_id.strip())
                for chat_id in allowed_chat_ids_str.split(",")
                if chat_id.strip()
            }
        except ValueError:
            pass  # Invalid format, treat as no whitelist

    # Parse allowed user IDs (comma-separated list)
    allowed_user_ids_str = _get_value("TELEGRAM_ALLOWED_USER_IDS", env_values, "")
    allowed_user_ids: set[int] | None = None

    if allowed_user_ids_str and allowed_user_ids_str.strip():
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


def get_bot_mode(env_path: Path | None = None) -> str:
    """Get the bot mode from environment variable.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        Bot mode: "console", "telegram", or "xmpp"
    """
    env_values = _load_env(env_path)

    mode = (_get_value("BOT_MODE", env_values, "console") or "console").lower().strip()
    if mode not in ("console", "telegram", "xmpp"):
        return "console"
    return mode


def get_xmpp_settings(env_path: Path | None = None) -> XmppSettings:
    """Load XMPP bot settings from environment variables.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        XmppSettings object with XMPP configuration.
    """
    env_values = _load_env(env_path)

    jid = _get_value("XMPP_JID", env_values)
    password = _get_value("XMPP_PASSWORD", env_values)
    default_receiver = _get_value("XMPP_DEFAULT_RECEIVER", env_values)

    # Parse allowed JIDs (comma-separated list)
    allowed_jids_str = _get_value("XMPP_ALLOWED_JIDS", env_values, "")
    allowed_jids: frozenset[str] | None = None

    if allowed_jids_str and allowed_jids_str.strip():
        allowed_jids = frozenset(
            jid_item.strip().lower()
            for jid_item in allowed_jids_str.split(",")
            if jid_item.strip()
        )

    # Parse optional settings with defaults
    resource = _get_value("XMPP_RESOURCE", env_values, "fints-bot") or "fints-bot"

    connect_timeout_str = _get_value("XMPP_CONNECT_TIMEOUT", env_values, "30") or "30"
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


def get_bot_update_settings(env_path: Path | None = None) -> BotUpdateSettings:
    """Load bot-update settings from environment variables.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        BotUpdateSettings object with bot-update configuration.
    """
    env_values = _load_env(env_path)

    telegram_target_user_id: int | None = None
    target_str = _get_value("TELEGRAM_TARGET_USER_ID", env_values)
    if target_str:
        try:
            telegram_target_user_id = int(target_str)
        except ValueError:
            pass

    transaction_days = 30
    days_str = _get_value("TRANSACTION_DAYS", env_values)
    if days_str:
        try:
            transaction_days = int(days_str)
        except ValueError:
            pass

    return BotUpdateSettings(
        telegram_target_user_id=telegram_target_user_id,
        transaction_days=transaction_days,
    )


def get_api_settings(env_path: Path | None = None) -> ApiSettings:
    """Load API settings from environment variables.

    Args:
        env_path: Optional specific .env file to load from.

    Returns:
        ApiSettings object with API configuration.

    Raises:
        ValueError: If required environment variables are missing or invalid.
    """
    env_values = _load_env(env_path)

    api_url = _get_value("API_URL", env_values)
    api_user = _get_value("API_USER", env_values)
    api_password = _get_value("API_PASSWORD", env_values)
    telegram_target_user_id_str = _get_value("TELEGRAM_TARGET_USER_ID", env_values)
    transaction_start_date_str = _get_value("TRANSACTION_START_DATE", env_values)

    # Validate required fields
    missing = []
    if not api_url:
        missing.append("API_URL")
    if not api_user:
        missing.append("API_USER")
    if not api_password:
        missing.append("API_PASSWORD")
    if not transaction_start_date_str:
        missing.append("TRANSACTION_START_DATE")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Parse telegram target user ID (optional — only needed in telegram bot mode)
    telegram_target_user_id: int | None = None
    if telegram_target_user_id_str:
        try:
            telegram_target_user_id = int(telegram_target_user_id_str)
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
        transaction_start_date=transaction_start_date,
        telegram_target_user_id=telegram_target_user_id,
    )


def _get_env_path(env_path: Path | None = None) -> Path:
    """Get the path to the .env file.

    Args:
        env_path: Optional specific .env file path. If None, uses default .env.
    """
    if env_path is not None:
        return env_path
    project_root = _get_project_root()
    return project_root / ".env"


def save_tan_preferences(
    mechanism: str,
    mechanism_name: str,
    medium: str | None = None,
    env_path: Path | None = None,
) -> None:
    """Save TAN preferences to .env file.

    Updates or adds TAN preference variables in the .env file.

    Args:
        mechanism: TAN mechanism function number (e.g., "920").
        mechanism_name: TAN mechanism name (e.g., "BestSign").
        medium: TAN medium name (e.g., "BennyHauptHandy"), optional.
        env_path: Optional specific .env file to write to.
    """
    target_path = _get_env_path(env_path)

    # Read existing content
    if target_path.exists():
        content = target_path.read_text(encoding="utf-8")
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
    target_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _get_session_path(account_name: str | None = None) -> Path:
    """Get the path to the session file.

    Args:
        account_name: Optional account name for per-account session files.
    """
    project_root = _get_project_root()
    if account_name and account_name != "default":
        return project_root / f".fints_session.{account_name}"
    return project_root / ".fints_session"


def save_client_state(data: bytes, account_name: str | None = None) -> None:
    """Save client state to file for session reuse.

    Args:
        data: Serialized client state from client.deconstruct().
        account_name: Optional account name for per-account session files.
    """
    session_path = _get_session_path(account_name)
    session_path.write_bytes(data)


def load_client_state(account_name: str | None = None) -> bytes | None:
    """Load saved client state if available.

    Args:
        account_name: Optional account name for per-account session files.

    Returns:
        Serialized client state bytes, or None if not available.
    """
    session_path = _get_session_path(account_name)
    if session_path.exists():
        return session_path.read_bytes()
    return None


def clear_client_state(account_name: str | None = None) -> None:
    """Remove saved client state file.

    Args:
        account_name: Optional account name for per-account session files.
    """
    session_path = _get_session_path(account_name)
    if session_path.exists():
        session_path.unlink()
