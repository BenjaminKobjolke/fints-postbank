"""I/O abstraction layer for console and Telegram interfaces."""

from .base import IOAdapter
from .console import ConsoleAdapter
from .telegram import TelegramAdapter, TelegramAdapterTimeoutError

__all__ = [
    "IOAdapter",
    "ConsoleAdapter",
    "TelegramAdapter",
    "TelegramAdapterTimeoutError",
]
