"""XMPP bot mode for FinTS client."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from xmpp_bot import XmppBot  # type: ignore[import-untyped]
from xmpp_bot.config import Settings as XmppBotSettings  # type: ignore[import-untyped]

from fintts_postbank.client import create_client, run_session
from fintts_postbank.config import discover_accounts, get_xmpp_settings, select_account
from fintts_postbank.io import XmppAdapter, XmppAdapterTimeoutError
from fintts_postbank.tan import interactive_cli_bootstrap

if TYPE_CHECKING:
    from slixmpp import Message  # type: ignore[import-untyped]

    from fintts_postbank.config import AccountConfig


class XmppSessionManager:
    """Manages XMPP chat sessions for FinTS operations."""

    def __init__(
        self,
        bot: XmppBot,
        event_loop: asyncio.AbstractEventLoop,
        force_tan_selection: bool = False,
        account: AccountConfig | None = None,
    ) -> None:
        """Initialize the session manager.

        Args:
            bot: The XmppBot instance
            event_loop: The asyncio event loop for async/sync bridging
            force_tan_selection: Whether to force TAN mechanism selection
            account: Optional AccountConfig for multi-account support
        """
        self.bot = bot
        self._event_loop = event_loop
        self.force_tan_selection = force_tan_selection
        self.account = account
        self._sessions: dict[str, XmppAdapter] = {}  # Keyed by bare JID
        self._session_threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

        # Get allowed JIDs from settings
        env_path = account.env_path if account is not None else None
        settings = get_xmpp_settings(env_path)
        self.allowed_jids = settings.allowed_jids

    def _get_bare_jid(self, jid: str) -> str:
        """Extract bare JID (without resource) from full JID.

        Args:
            jid: Full JID (may include resource)

        Returns:
            Bare JID (user@domain)
        """
        return jid.split("/")[0].lower()

    def is_authorized(self, jid: str) -> bool:
        """Check if a JID is authorized to use the bot.

        Args:
            jid: The XMPP JID

        Returns:
            True if authorized (no whitelist or in whitelist)
        """
        if not self.allowed_jids:
            return True  # No whitelist = allow all
        bare_jid = self._get_bare_jid(jid)
        return bare_jid in self.allowed_jids

    def get_or_create_adapter(self, jid: str) -> XmppAdapter | None:
        """Get existing adapter for JID or None if no active session.

        Args:
            jid: The XMPP JID

        Returns:
            XmppAdapter if session exists, None otherwise
        """
        bare_jid = self._get_bare_jid(jid)
        with self._lock:
            return self._sessions.get(bare_jid)

    def start_session(self, jid: str) -> bool:
        """Start a new FinTS session for a JID.

        Args:
            jid: The XMPP JID

        Returns:
            True if session started, False if already running
        """
        bare_jid = self._get_bare_jid(jid)
        with self._lock:
            if bare_jid in self._sessions:
                # Check if thread is still alive
                thread = self._session_threads.get(bare_jid)
                if thread and thread.is_alive():
                    return False  # Session already running

            # Create new adapter
            adapter = XmppAdapter(self.bot, bare_jid, self._event_loop)
            self._sessions[bare_jid] = adapter

            # Start session in background thread
            thread = threading.Thread(
                target=self._run_session_thread,
                args=(bare_jid, adapter),
                daemon=True,
            )
            self._session_threads[bare_jid] = thread
            thread.start()
            print(f"[SESSION] Started new session for jid={bare_jid}")
            return True

    def _run_session_thread(self, jid: str, adapter: XmppAdapter) -> None:
        """Run FinTS session in a background thread.

        Args:
            jid: The bare JID
            adapter: The XmppAdapter for this session
        """
        try:
            self._run_fints_session(adapter)
            print(f"[SESSION] Session ended normally for jid={jid}")
        except XmppAdapterTimeoutError:
            adapter.output("\nSession timed out due to inactivity.")
            adapter.output("Send /start to begin a new session.")
            print(f"[SESSION] Session timed out for jid={jid}")
        except ValueError as e:
            adapter.output(f"\nConfiguration error: {e}")
            print(f"[SESSION] Config error for jid={jid}: {e}")
        except Exception as e:
            adapter.output(f"\nError: {e}")
            adapter.output("Send /start to try again.")
            print(f"[SESSION] Error for jid={jid}: {e}")
        finally:
            # Clean up session
            with self._lock:
                self._sessions.pop(jid, None)
                self._session_threads.pop(jid, None)

    def _run_fints_session(self, adapter: XmppAdapter) -> None:
        """Run the main FinTS session logic.

        Args:
            adapter: The XmppAdapter for I/O
        """
        adapter.output("Postbank FinTS Client")
        adapter.output("Initializing TAN mechanisms...")

        # Main session loop (handles reconnection)
        needs_reconnect = True
        while needs_reconnect:
            # Create client
            client = create_client(adapter, account=self.account)

            # Bootstrap TAN mechanisms
            interactive_cli_bootstrap(
                client,
                force_tan_selection=self.force_tan_selection,
                io=adapter,
                account=self.account,
            )

            # Run session
            needs_reconnect = run_session(client, adapter, account=self.account)

            if needs_reconnect:
                adapter.output("\nReconnecting...")

        adapter.output("\nGoodbye! Send /start to begin a new session.")

    async def handle_message(self, sender: str, body: str, msg: Message) -> None:
        """Handle an incoming message from a user.

        Args:
            sender: The sender's JID
            body: The message body text
            msg: The full slixmpp Message object
        """
        bare_jid = self._get_bare_jid(sender)

        # Check authorization
        if not self.is_authorized(sender):
            await self.bot.reply_to_user("Unauthorized. Access denied.", bare_jid)
            print(f"[AUTH] Unauthorized access attempt from jid={sender}")
            return

        # Check for /start command
        if body.strip().lower() == "/start":
            if self.start_session(sender):
                pass  # Session will send its own welcome
            else:
                await self.bot.reply_to_user(
                    "Session already running. Please complete or wait for timeout.",
                    bare_jid,
                )
            return

        # Try to route to existing session
        adapter = self.get_or_create_adapter(sender)
        if adapter:
            if adapter.handle_incoming_message(body):
                return  # Message handled by session

        # No active session
        await self.bot.reply_to_user(
            "No active session. Send /start to begin.",
            bare_jid,
        )


async def run_xmpp_mode_async(
    force_tan_selection: bool = False,
    account_name: str | None = None,
) -> None:
    """Run the FinTS client in XMPP bot mode (async).

    Args:
        force_tan_selection: Whether to force TAN mechanism selection
        account_name: Optional account name from --account flag
    """
    # Discover and select account
    account: AccountConfig | None = None
    accounts = discover_accounts()
    if accounts:
        if len(accounts) == 1 and accounts[0].name == "default" and account_name is None:
            account = None  # Backward compat
        else:
            account = select_account(accounts, account_name)
            print(f"Using account: {account.name}")

    env_path = account.env_path if account is not None else None

    # Get XMPP settings
    settings = get_xmpp_settings(env_path)
    if not settings.jid:
        raise ValueError(
            "XMPP_JID not set. "
            "Please add it to your .env file."
        )
    if not settings.password:
        raise ValueError(
            "XMPP_PASSWORD not set. "
            "Please add it to your .env file."
        )

    # Create xmpp-bot Settings object
    bot_settings = XmppBotSettings(
        jid=settings.jid,
        password=settings.password,
        resource=settings.resource,
        default_receiver=settings.default_receiver or "",
    )

    # Initialize bot
    bot = XmppBot.get_instance()
    await bot.initialize(settings=bot_settings)

    # Get the event loop for async/sync bridging
    event_loop = asyncio.get_running_loop()

    # Create session manager
    manager = XmppSessionManager(bot, event_loop, force_tan_selection, account=account)

    # Set up message handler
    async def on_message(sender: str, body: str, msg: Message) -> None:
        """Handle incoming XMPP message."""
        print(f"[MSG] jid={sender} text={body!r}")
        await manager.handle_message(sender, body, msg)

    bot.add_message_handler("fints_handler", on_message)

    print("XMPP bot started. Press Ctrl+C to stop.")
    print(f"Bot JID: {settings.jid}")
    print(f"Allowed JIDs: {settings.allowed_jids or 'All'}")

    # Send startup message to allowed JIDs if configured
    if settings.allowed_jids:
        startup_message = "FinTS Bot is now online. Send /start to begin a session."
        print(f"Sending startup notification to {len(settings.allowed_jids)} user(s)...")
        for jid in settings.allowed_jids:
            try:
                await bot.reply_to_user(startup_message, jid)
                print(f"  - Notified {jid}")
            except Exception as e:
                print(f"  - Failed to notify {jid}: {e}")

    # Run bot until interrupted (bot is connected and processing via asyncio)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping bot...")
    finally:
        bot.disconnect()


def run_xmpp_mode(
    force_tan_selection: bool = False,
    account_name: str | None = None,
) -> None:
    """Run the FinTS client in XMPP bot mode.

    Args:
        force_tan_selection: Whether to force TAN mechanism selection
        account_name: Optional account name from --account flag
    """
    asyncio.run(run_xmpp_mode_async(force_tan_selection, account_name=account_name))
