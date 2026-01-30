"""Configuration module for fintts-postbank."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .constants import BLZ, HBCI_URL, PRODUCT_ID
from .constants import IBAN as DEFAULT_IBAN
from .settings import (
    ApiSettings,
    Settings,
    TelegramSettings,
    XmppSettings,
    clear_client_state,
    get_api_settings,
    get_bot_mode,
    get_settings,
    get_telegram_settings,
    get_xmpp_settings,
    load_client_state,
    save_client_state,
    save_tan_preferences,
)

# Load .env and get IBAN (with fallback to default from constants)
_project_root = Path(__file__).parent.parent.parent.parent
load_dotenv(_project_root / ".env")
IBAN = os.getenv("IBAN", DEFAULT_IBAN)

__all__ = [
    "ApiSettings",
    "BLZ",
    "HBCI_URL",
    "IBAN",
    "PRODUCT_ID",
    "Settings",
    "TelegramSettings",
    "XmppSettings",
    "clear_client_state",
    "get_api_settings",
    "get_bot_mode",
    "get_settings",
    "get_telegram_settings",
    "get_xmpp_settings",
    "load_client_state",
    "save_client_state",
    "save_tan_preferences",
]
