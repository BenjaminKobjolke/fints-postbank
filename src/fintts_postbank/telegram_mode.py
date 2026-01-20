"""Telegram bot mode for FinTS client."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any

from telegram_bot import TelegramBot  # type: ignore[import-untyped]
from telegram_bot.config import Settings as TelegramBotSettings  # type: ignore[import-untyped]

from fintts_postbank.client import create_client, run_session
from fintts_postbank.config import get_telegram_settings
from fintts_postbank.io import TelegramAdapter, TelegramAdapterTimeoutError
from fintts_postbank.tan import interactive_cli_bootstrap

if TYPE_CHECKING:
    pass


class TelegramSessionManager:
    """Manages Telegram chat sessions for FinTS operations."""

    def __init__(self, bot: TelegramBot, force_tan_selection: bool = False) -> None:
        """Initialize the session manager.

        Args:
            bot: The TelegramBot instance
            force_tan_selection: Whether to force TAN mechanism selection
        """
        self.bot = bot
        self.force_tan_selection = force_tan_selection
        self._sessions: dict[int, TelegramAdapter] = {}
        self._session_threads: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

        # Get allowed chat IDs from settings
        settings = get_telegram_settings()
        self.allowed_chat_ids = settings.allowed_chat_ids

    def is_authorized(self, chat_id: int) -> bool:
        """Check if a chat ID is authorized to use the bot.

        Args:
            chat_id: The Telegram chat ID

        Returns:
            True if authorized (no whitelist or in whitelist)
        """
        if not self.allowed_chat_ids:
            return True  # No whitelist = allow all
        return chat_id in self.allowed_chat_ids

    def get_or_create_adapter(self, chat_id: int) -> TelegramAdapter | None:
        """Get existing adapter for chat or None if no active session.

        Args:
            chat_id: The Telegram chat ID

        Returns:
            TelegramAdapter if session exists, None otherwise
        """
        with self._lock:
            return self._sessions.get(chat_id)

    def start_session(self, chat_id: int) -> bool:
        """Start a new FinTS session for a chat.

        Args:
            chat_id: The Telegram chat ID

        Returns:
            True if session started, False if already running
        """
        with self._lock:
            if chat_id in self._sessions:
                # Check if thread is still alive
                thread = self._session_threads.get(chat_id)
                if thread and thread.is_alive():
                    return False  # Session already running

            # Create new adapter
            adapter = TelegramAdapter(self.bot, chat_id)
            self._sessions[chat_id] = adapter

            # Start session in background thread
            thread = threading.Thread(
                target=self._run_session_thread,
                args=(chat_id, adapter),
                daemon=True,
            )
            self._session_threads[chat_id] = thread
            thread.start()
            print(f"[SESSION] Started new session for chat_id={chat_id}")
            return True

    def _run_session_thread(self, chat_id: int, adapter: TelegramAdapter) -> None:
        """Run FinTS session in a background thread.

        Args:
            chat_id: The Telegram chat ID
            adapter: The TelegramAdapter for this session
        """
        try:
            self._run_fints_session(adapter)
            print(f"[SESSION] Session ended normally for chat_id={chat_id}")
        except TelegramAdapterTimeoutError:
            adapter.output("\nSession timed out due to inactivity.")
            adapter.output("Send /start to begin a new session.")
            print(f"[SESSION] Session timed out for chat_id={chat_id}")
        except ValueError as e:
            adapter.output(f"\nConfiguration error: {e}")
            print(f"[SESSION] Config error for chat_id={chat_id}: {e}")
        except Exception as e:
            adapter.output(f"\nError: {e}")
            adapter.output("Send /start to try again.")
            print(f"[SESSION] Error for chat_id={chat_id}: {e}")
        finally:
            # Clean up session
            with self._lock:
                self._sessions.pop(chat_id, None)
                self._session_threads.pop(chat_id, None)

    def _run_fints_session(self, adapter: TelegramAdapter) -> None:
        """Run the main FinTS session logic.

        Args:
            adapter: The TelegramAdapter for I/O
        """
        adapter.output("Postbank FinTS Client")
        adapter.output("Initializing TAN mechanisms...")

        # Main session loop (handles reconnection)
        needs_reconnect = True
        while needs_reconnect:
            # Create client
            client = create_client(adapter)

            # Bootstrap TAN mechanisms
            interactive_cli_bootstrap(
                client, force_tan_selection=self.force_tan_selection, io=adapter
            )

            # Run session
            needs_reconnect = run_session(client, adapter)

            if needs_reconnect:
                adapter.output("\nReconnecting...")

        adapter.output("\nGoodbye! Send /start to begin a new session.")

    def handle_message(self, chat_id: int, text: str) -> None:
        """Handle an incoming message from a chat.

        Args:
            chat_id: The Telegram chat ID
            text: The message text
        """
        # Check authorization
        if not self.is_authorized(chat_id):
            self.bot.reply_to_user("Unauthorized. Access denied.", chat_id)
            print(f"[AUTH] Unauthorized access attempt from chat_id={chat_id}")
            return

        # Check for /start command
        if text.strip().lower() == "/start":
            if self.start_session(chat_id):
                pass  # Session will send its own welcome
            else:
                self.bot.reply_to_user(
                    "Session already running. Please complete or wait for timeout.",
                    chat_id,
                )
            return

        # Try to route to existing session
        adapter = self.get_or_create_adapter(chat_id)
        if adapter:
            if adapter.handle_incoming_message(text):
                return  # Message handled by session

        # No active session
        self.bot.reply_to_user(
            "No active session. Send /start to begin.",
            chat_id,
        )


def run_telegram_mode(force_tan_selection: bool = False) -> None:
    """Run the FinTS client in Telegram bot mode.

    Args:
        force_tan_selection: Whether to force TAN mechanism selection
    """
    # Get bot token from our settings
    our_settings = get_telegram_settings()
    if not our_settings.bot_token:
        raise ValueError(
            "TELEGRAM_BOT_TOKEN not set. "
            "Please add it to your .env file."
        )

    # Create telegram-bot Settings object
    # We use a dummy channel_id since we only use direct messages
    bot_settings = TelegramBotSettings(
        bot_token=our_settings.bot_token,
        channel_id="@dummy_channel",  # Not used, but required by library
    )

    # Initialize bot
    bot = TelegramBot.get_instance()
    bot.initialize(settings=bot_settings)

    # Create session manager
    manager = TelegramSessionManager(bot, force_tan_selection)

    # Set up message handler
    def on_update(update: Any) -> None:
        """Handle incoming Telegram update."""
        if update.message and update.message.text:
            chat_id = update.message.chat_id
            user = update.message.from_user
            text = update.message.text

            # Log connection info
            user_id = user.id if user else "unknown"
            username = user.username if user and user.username else "no_username"
            first_name = user.first_name if user and user.first_name else ""
            print(
                f"[MSG] chat_id={chat_id} user_id={user_id} "
                f"username=@{username} name={first_name!r} text={text!r}"
            )

            manager.handle_message(chat_id, text)

    bot.add_message_handler(on_update)

    print("Telegram bot started. Press Ctrl+C to stop.")
    print(f"Allowed chat IDs: {our_settings.allowed_chat_ids or 'All'}")

    # Keep main thread alive until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot...")
        bot.shutdown()
