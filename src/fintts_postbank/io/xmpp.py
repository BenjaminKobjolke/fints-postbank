"""XMPP I/O adapter implementation."""

import asyncio
import queue
import threading
from typing import TYPE_CHECKING

from .base import IOAdapter

if TYPE_CHECKING:
    from xmpp_bot import XmppBot  # type: ignore[import-untyped]


class XmppAdapterTimeoutError(Exception):
    """Raised when waiting for user input times out."""


class XmppAdapter(IOAdapter):
    """XMPP-based I/O adapter using message queue for blocking input.

    This adapter allows synchronous FinTS code to work with asynchronous
    XMPP messaging by using a blocking queue for input and asyncio bridge
    for output.
    """

    # Default timeout for waiting on user input (5 minutes)
    DEFAULT_TIMEOUT = 300

    def __init__(
        self,
        bot: "XmppBot",
        jid: str,
        event_loop: asyncio.AbstractEventLoop,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the XMPP adapter.

        Args:
            bot: The XmppBot instance
            jid: The XMPP JID for this conversation (bare JID without resource)
            event_loop: The asyncio event loop for async/sync bridging
            timeout: Timeout in seconds for waiting on user input
        """
        self.bot = bot
        self.jid = jid
        self._event_loop = event_loop
        self.timeout = timeout
        self._input_queue: queue.Queue[str] = queue.Queue()
        self._waiting_for_input = False
        self._lock = threading.Lock()

    def output(self, message: str) -> None:
        """Send message to XMPP user.

        Uses asyncio bridge to call async bot method from sync context.
        """
        if message.strip():
            future = asyncio.run_coroutine_threadsafe(
                self.bot.reply_to_user(message, self.jid),
                self._event_loop,
            )
            try:
                future.result(timeout=30)  # Wait up to 30s for message to send
            except TimeoutError:
                pass  # Best effort - don't block on send failures

    def input(self, prompt: str) -> str:
        """Get input from XMPP user.

        Sends the prompt and blocks until user responds or timeout.

        Args:
            prompt: The prompt to send to the user

        Returns:
            The user's response

        Raises:
            XmppAdapterTimeoutError: If no response within timeout period
        """
        if prompt.strip():
            self.output(prompt)

        with self._lock:
            self._waiting_for_input = True

        try:
            response = self._input_queue.get(timeout=self.timeout)
            return response
        except queue.Empty as err:
            raise XmppAdapterTimeoutError(
                f"No response received within {self.timeout} seconds"
            ) from err
        finally:
            with self._lock:
                self._waiting_for_input = False

    def get_valid_choice(
        self, prompt: str, max_index: int, default: int | None = None
    ) -> int:
        """Get a valid integer choice from XMPP user.

        Args:
            prompt: The prompt to send
            max_index: Maximum valid choice (0 to max_index inclusive)
            default: Default value if user sends empty message

        Returns:
            The user's valid choice as an integer

        Raises:
            XmppAdapterTimeoutError: If no response within timeout period
        """
        while True:
            try:
                user_input = self.input(prompt).strip()

                if not user_input and default is not None:
                    return default

                choice = int(user_input)
                if 0 <= choice <= max_index:
                    return choice
                self.output(f"Please enter a number between 0 and {max_index}")
            except ValueError:
                self.output("Please enter a valid number")

    def handle_incoming_message(self, text: str) -> bool:
        """Handle an incoming message from the user.

        If we're waiting for input, queue the message and return True.
        Otherwise return False to indicate message wasn't handled.

        Args:
            text: The message text from the user

        Returns:
            True if message was handled (we were waiting for input)
        """
        with self._lock:
            if self._waiting_for_input:
                self._input_queue.put(text)
                return True
        return False

    def is_waiting_for_input(self) -> bool:
        """Check if this adapter is currently waiting for user input."""
        with self._lock:
            return self._waiting_for_input

    def cancel(self) -> None:
        """Cancel any pending input wait by sending empty response."""
        self._input_queue.put("")
