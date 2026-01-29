"""I/O abstraction layer for console, Telegram, and XMPP interfaces."""

from .base import IOAdapter
from .console import ConsoleAdapter
from .telegram import TelegramAdapter, TelegramAdapterTimeoutError
from .xmpp import XmppAdapter, XmppAdapterTimeoutError

__all__ = [
    "IOAdapter",
    "ConsoleAdapter",
    "TelegramAdapter",
    "TelegramAdapterTimeoutError",
    "XmppAdapter",
    "XmppAdapterTimeoutError",
]
