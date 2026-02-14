"""Update bot mode - automated FinTS data fetch with bot notification (no API)."""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from fintts_postbank.client import create_client
from fintts_postbank.config import (
    IBAN,
    discover_accounts,
    get_bot_mode,
    get_bot_update_settings,
    get_settings,
    get_telegram_settings,
    get_xmpp_settings,
    select_account,
)
from fintts_postbank.io import (
    IOAdapter,
    TelegramAdapter,
    TelegramAdapterTimeoutError,
    XmppAdapter,
    XmppAdapterTimeoutError,
)
from fintts_postbank.operations import (
    fetch_accounts,
    fetch_balance,
    fetch_transactions,
    find_account_by_iban,
)
from fintts_postbank.tan import handle_tan_challenge, interactive_cli_bootstrap
from fintts_postbank.transaction_db import TransactionDatabase

if TYPE_CHECKING:
    from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]
    from slixmpp import Message  # type: ignore[import-untyped]
    from telegram_bot import TelegramBot  # type: ignore[import-untyped]
    from xmpp_bot import XmppBot  # type: ignore[import-untyped]

    from fintts_postbank.config import AccountConfig, BotUpdateSettings


class UpdateBotTelegramAdapter(TelegramAdapter):
    """Telegram adapter for update-bot mode.

    Sends messages to a specific target user and waits for their response.
    """

    def __init__(
        self,
        bot: TelegramBot,
        target_user_id: int,
        timeout: int = 300,
    ) -> None:
        """Initialize the update-bot adapter.

        Args:
            bot: The TelegramBot instance.
            target_user_id: The Telegram user ID to communicate with.
            timeout: Timeout in seconds for waiting on user input.
        """
        super().__init__(bot, target_user_id, timeout)
        self.target_user_id = target_user_id


class UpdateBotXmppAdapter(XmppAdapter):
    """XMPP adapter for update-bot mode.

    Sends messages to a specific target JID and waits for their response.
    """

    def __init__(
        self,
        bot: XmppBot,
        target_jid: str,
        event_loop: asyncio.AbstractEventLoop,
        timeout: int = 300,
    ) -> None:
        """Initialize the update-bot XMPP adapter.

        Args:
            bot: The XmppBot instance.
            target_jid: The XMPP JID to communicate with.
            event_loop: The asyncio event loop for async/sync bridging.
            timeout: Timeout in seconds for waiting on user input.
        """
        super().__init__(bot, target_jid, event_loop, timeout)
        self.target_jid = target_jid


def _validate_configuration(
    bot_mode: str,
    account: AccountConfig | None = None,
) -> tuple[Any, Any, Any]:
    """Validate all required configuration for update-bot mode.

    Args:
        bot_mode: The messaging backend mode ("telegram" or "xmpp").
        account: Optional AccountConfig for multi-account support.

    Returns:
        Tuple of (fints_settings, bot_settings, bot_mode).
        bot_settings is TelegramSettings or XmppSettings depending on mode.

    Raises:
        SystemExit: If configuration is invalid or missing.
    """
    env_path = account.env_path if account is not None else None
    errors: list[str] = []

    # Check FinTS settings
    try:
        fints_settings = get_settings(env_path)
    except ValueError as e:
        errors.append(f"FinTS settings: {e}")
        fints_settings = None

    # Check TAN defaults
    if fints_settings:
        if not fints_settings.tan_mechanism or not fints_settings.tan_mechanism_name:
            errors.append(
                "TAN mechanism not configured. "
                "Run 'fints-postbank --tan' first to select TAN method."
            )

    # Check bot settings based on mode
    bot_settings: Any = None
    if bot_mode == "xmpp":
        xmpp_settings = get_xmpp_settings(env_path)
        if not xmpp_settings.jid:
            errors.append("XMPP_JID not set in .env")
        if not xmpp_settings.password:
            errors.append("XMPP_PASSWORD not set in .env")
        if not xmpp_settings.default_receiver:
            errors.append("XMPP_DEFAULT_RECEIVER not set in .env (required for --update-bot)")
        bot_settings = xmpp_settings
    else:
        telegram_settings = get_telegram_settings(env_path)
        if not telegram_settings.bot_token:
            errors.append("TELEGRAM_BOT_TOKEN not set in .env")
        bot_settings = telegram_settings

    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    return fints_settings, bot_settings, bot_mode


def _extract_transaction_data(tx: Any) -> tuple[date, Decimal, str, str] | None:
    """Extract relevant data from a transaction object.

    Args:
        tx: Transaction object from FinTS.

    Returns:
        Tuple of (date, amount, name, purpose) or None if extraction fails.
    """
    if not hasattr(tx, "data"):
        return None

    data = tx.data
    tx_date = data.get("date")
    amount = data.get("amount")
    applicant = data.get("applicant_name", "")
    purpose = data.get("purpose", "")

    if not tx_date or amount is None:
        return None

    # Convert amount to Decimal
    if hasattr(amount, "amount"):
        # mt940 Amount object
        amount_decimal = Decimal(str(amount.amount))
    elif isinstance(amount, Decimal):
        amount_decimal = amount
    else:
        try:
            amount_decimal = Decimal(str(amount))
        except (ValueError, TypeError):
            return None

    return tx_date, amount_decimal, applicant, purpose


def _run_fints_session(
    adapter: IOAdapter,
    bot_update_settings: BotUpdateSettings,
    fints_settings: Any,
    account: AccountConfig | None = None,
) -> int:
    """Run the FinTS session and notify via bot.

    Args:
        adapter: The I/O adapter for messaging.
        bot_update_settings: Bot-update configuration settings.
        fints_settings: FinTS configuration settings.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("[BOT-MODE] Starting FinTS session...")

    # Use account-specific IBAN if provided
    iban = account.iban if account is not None else IBAN

    # Create transaction DB (for balance tracking only)
    tx_db = TransactionDatabase()

    # Create FinTS client
    print("[BOT-MODE] Creating FinTS client...")
    client: FinTS3PinTanClient = create_client(adapter, account=account)

    # Bootstrap TAN mechanisms (uses saved preferences)
    print("[BOT-MODE] Initializing TAN mechanisms...")
    interactive_cli_bootstrap(client, force_tan_selection=False, io=adapter, account=account)

    try:
        print("[BOT-MODE] Opening FinTS session...")
        with client:
            # Handle initialization TAN if needed (PSD2 requirement)
            if client.init_tan_response:
                print("[BOT-MODE] TAN required for initialization")
                tan = handle_tan_challenge(client.init_tan_response, adapter)
                client.send_tan(client.init_tan_response, tan)
            else:
                print("[BOT-MODE] No init TAN required")

            # Fetch accounts
            print("[BOT-MODE] Fetching accounts...")
            try:
                accounts = fetch_accounts(client, adapter)
                print(f"[BOT-MODE] Found {len(accounts) if accounts else 0} accounts")
            except Exception as e:
                print(f"[BOT-MODE] ERROR fetching accounts: {e}")
                import traceback

                traceback.print_exc()
                raise
            if not accounts:
                print("[BOT-MODE] ERROR: No accounts found!")
                return 1

            # Find the configured account
            print(f"[BOT-MODE] Looking for IBAN: {iban}")
            sepa_account = find_account_by_iban(accounts, iban)
            if not sepa_account:
                print(f"[BOT-MODE] ERROR: Account with IBAN {iban} not found!")
                print(f"[BOT-MODE] Available IBANs: {[a.iban for a in accounts]}")
                # Use first account as fallback
                sepa_account = accounts[0]
                print(f"[BOT-MODE] Using first available account: {sepa_account.iban}")

            print(f"[BOT-MODE] Using account: {sepa_account.iban}")

            # Fetch balance
            print("[BOT-MODE] Fetching balance...")
            balance = fetch_balance(client, sepa_account, adapter)
            balance_value: Decimal | None = None

            if balance and hasattr(balance, "amount"):
                balance_amount = balance.amount
                if hasattr(balance_amount, "amount"):
                    # mt940 Amount object
                    balance_value = Decimal(str(balance_amount.amount))
                else:
                    balance_value = Decimal(str(balance_amount))

                print(f"[BOT-MODE] Balance: {balance_value}")
            else:
                print("[BOT-MODE] Could not fetch balance")

            # Fetch transactions (last N days)
            transaction_days = bot_update_settings.transaction_days
            start_date = date.today() - timedelta(days=transaction_days)
            end_date = date.today()
            print(f"[BOT-MODE] Fetching transactions from {start_date} to {end_date}...")
            print("[BOT-MODE] (This may require TAN - check your messaging app)")

            try:
                transactions = fetch_transactions(
                    client, sepa_account, start_date, end_date, adapter
                )
                tx_count = len(transactions) if transactions else 0
                print(f"[BOT-MODE] Received {tx_count} transactions")
            except Exception as e:
                print(f"[BOT-MODE] ERROR fetching transactions: {e}")
                import traceback

                traceback.print_exc()
                raise

            # Collect transaction details
            all_transactions: list[tuple[date, Decimal, str]] = []
            if transactions:
                for tx in transactions:
                    tx_data = _extract_transaction_data(tx)
                    if not tx_data:
                        continue
                    tx_date, amount, name, _purpose = tx_data
                    tx_name = name if name else _purpose[:50] if _purpose else "Unknown"
                    all_transactions.append((tx_date, amount, tx_name))

        # Check if balance changed compared to last sync
        previous_balance = tx_db.get_last_balance(fints_settings.username)
        balance_changed = balance_value is not None and (
            previous_balance is None or previous_balance != balance_value
        )

        # Update stored balance after successful sync
        if balance_value is not None:
            tx_db.update_last_balance(fints_settings.username, balance_value)

        # Build consolidated summary message
        print("[BOT-MODE] Completed successfully!")
        summary_parts = []
        if balance_value is not None:
            summary_parts.append(f"Balance: {balance_value:.2f}€")
        summary_parts.append(f"Transactions ({transaction_days}d): {len(all_transactions)}")
        summary_msg = " | ".join(summary_parts)

        # Only send chat message if balance changed
        if balance_changed:
            print(
                f"[BOT-MODE] Balance changed ({previous_balance} -> {balance_value}),"
                " notifying user"
            )
            adapter.output(summary_msg)

            # Show details of recent transactions
            if all_transactions:
                for tx_date, amount, tx_name in all_transactions:
                    sign = "+" if amount >= 0 else ""
                    adapter.output(f"  {tx_date}: {sign}{amount:.2f}€ - {tx_name}")
        else:
            print(f"[BOT-MODE] Balance unchanged ({balance_value}), skipping notification")
            print(f"[BOT-MODE] {summary_msg}")

        return 0

    except (TelegramAdapterTimeoutError, XmppAdapterTimeoutError):
        print("[BOT-MODE] Session timed out waiting for TAN confirmation.")
        return 1
    except Exception as e:
        print(f"[BOT-MODE] Error during FinTS session: {e}")
        return 1


def _run_telegram_update_bot(
    fints_settings: Any,
    telegram_settings: Any,
    bot_update_settings: BotUpdateSettings,
    account: AccountConfig | None = None,
) -> int:
    """Run update-bot mode using Telegram backend.

    Args:
        fints_settings: FinTS configuration.
        telegram_settings: Telegram bot settings.
        bot_update_settings: Bot-update configuration.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    from telegram_bot import TelegramBot  # type: ignore[import-untyped]
    from telegram_bot.config import Settings as TelegramBotSettings  # type: ignore[import-untyped]

    # Initialize Telegram bot
    print("Initializing Telegram bot...")
    tg_bot_settings = TelegramBotSettings(
        bot_token=telegram_settings.bot_token,
        channel_id="@dummy_channel",  # Not used, but required by library
    )

    bot = TelegramBot.get_instance()
    bot.initialize(settings=tg_bot_settings)

    # Determine target user ID
    target_user_id = bot_update_settings.telegram_target_user_id

    # Create adapter for target user
    adapter = UpdateBotTelegramAdapter(
        bot,
        target_user_id,
        timeout=300,  # 5 minutes for TAN confirmation
    )

    # Set up message handler for receiving TAN responses
    def on_update(update: Any) -> None:
        """Handle incoming Telegram update."""
        if update.message and update.message.text:
            user = update.message.from_user
            if user and user.id == target_user_id:
                # Route message to adapter
                adapter.handle_incoming_message(update.message.text)

    bot.add_message_handler(on_update)

    # Run the session in a separate thread so we can handle Telegram messages
    result_container: list[int] = []
    session_complete = threading.Event()

    def session_thread() -> None:
        """Run the FinTS session."""
        try:
            print("Session thread starting...")
            result = _run_fints_session(
                adapter, bot_update_settings, fints_settings, account
            )
            print(f"Session completed with result: {result}")
            result_container.append(result)
        except Exception as e:
            import traceback

            print(f"Session thread error: {e}")
            traceback.print_exc()
            result_container.append(1)
        finally:
            session_complete.set()

    thread = threading.Thread(target=session_thread, daemon=True)
    thread.start()

    # Wait for session to complete
    try:
        while not session_complete.is_set():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        bot.flush()
        bot.shutdown()
        return 1

    result = result_container[0] if result_container else 1
    bot.flush()
    bot.shutdown()
    return result


async def _run_xmpp_update_bot_async(
    fints_settings: Any,
    xmpp_settings: Any,
    bot_update_settings: BotUpdateSettings,
    account: AccountConfig | None = None,
) -> int:
    """Run update-bot mode using XMPP backend (async).

    Args:
        fints_settings: FinTS configuration.
        xmpp_settings: XMPP bot settings.
        bot_update_settings: Bot-update configuration.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    from xmpp_bot import XmppBot  # type: ignore[import-untyped]
    from xmpp_bot.config import Settings as XmppBotSettings  # type: ignore[import-untyped]

    # Initialize XMPP bot
    print("Initializing XMPP bot...")
    xmpp_bot_settings = XmppBotSettings(
        jid=xmpp_settings.jid,
        password=xmpp_settings.password,
        resource=xmpp_settings.resource,
        default_receiver=xmpp_settings.default_receiver,
    )

    bot = XmppBot.get_instance()
    await bot.initialize(settings=xmpp_bot_settings)

    # Get the event loop for async/sync bridging
    event_loop = asyncio.get_running_loop()

    # Create adapter for target JID
    target_jid = xmpp_settings.default_receiver
    adapter = UpdateBotXmppAdapter(
        bot,
        target_jid,
        event_loop,
        timeout=300,  # 5 minutes for TAN confirmation
    )

    # Set up message handler for receiving TAN responses
    async def on_message(sender: str, body: str, msg: Message) -> None:
        """Handle incoming XMPP message."""
        bare_jid = sender.split("/")[0].lower()
        if bare_jid == target_jid.lower():
            # Route message to adapter
            adapter.handle_incoming_message(body)

    bot.add_message_handler("update_bot_handler", on_message)

    # Run the session in a separate thread so we can handle XMPP messages
    result_container: list[int] = []
    session_complete = threading.Event()

    def session_thread() -> None:
        """Run the FinTS session."""
        try:
            print("Session thread starting...")
            result = _run_fints_session(
                adapter, bot_update_settings, fints_settings, account
            )
            print(f"Session completed with result: {result}")
            result_container.append(result)
        except Exception as e:
            import traceback

            print(f"Session thread error: {e}")
            traceback.print_exc()
            result_container.append(1)
        finally:
            session_complete.set()

    thread = threading.Thread(target=session_thread, daemon=True)
    thread.start()

    # Wait for session to complete (bot is already connected and processing)
    try:
        while not session_complete.is_set():
            await asyncio.sleep(0.5)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        bot.disconnect()
        return 1

    result = result_container[0] if result_container else 1
    bot.disconnect()
    return result


def _run_xmpp_update_bot(
    fints_settings: Any,
    xmpp_settings: Any,
    bot_update_settings: BotUpdateSettings,
    account: AccountConfig | None = None,
) -> int:
    """Run update-bot mode using XMPP backend.

    Args:
        fints_settings: FinTS configuration.
        xmpp_settings: XMPP bot settings.
        bot_update_settings: Bot-update configuration.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    return asyncio.run(
        _run_xmpp_update_bot_async(fints_settings, xmpp_settings, bot_update_settings, account)
    )


def run_update_bot_mode(account_name: str | None = None) -> int:
    """Run the update-bot mode.

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("Update Bot Mode")
    print("=" * 40)

    # Discover and select account
    account: AccountConfig | None = None
    accounts = discover_accounts()
    if accounts:
        # For multi-account: require --account if multiple exist
        if len(accounts) > 1 and account_name is None:
            # Check if they're all non-default
            non_default = [a for a in accounts if a.name != "default"]
            if non_default:
                print("Multiple accounts found. Use --account <name> to specify which one.")
                print("Available accounts:")
                for a in accounts:
                    print(f"  - {a.name}")
                return 1

        if len(accounts) == 1 and accounts[0].name == "default" and account_name is None:
            account = None  # Backward compat
        else:
            account = select_account(accounts, account_name)
            print(f"Using account: {account.name}")

    env_path = account.env_path if account is not None else None

    # Determine bot mode (defaults to telegram for update-bot if not set)
    bot_mode = get_bot_mode(env_path)
    if bot_mode == "console":
        bot_mode = "telegram"  # Default to telegram for update-bot mode
    print(f"Using {bot_mode.upper()} for notifications")

    # Load bot-update settings
    bot_update_settings = get_bot_update_settings(env_path)

    # Validate configuration (FinTS + bot only, no API)
    fints_settings, bot_settings, bot_mode = _validate_configuration(bot_mode, account)

    # Validate target user ID for Telegram mode
    if bot_mode == "telegram" and not bot_update_settings.telegram_target_user_id:
        print("Configuration error:")
        print("  - TELEGRAM_TARGET_USER_ID not set in .env (required for --update-bot)")
        return 1

    # Run with appropriate backend
    if bot_mode == "xmpp":
        return _run_xmpp_update_bot(
            fints_settings, bot_settings, bot_update_settings, account
        )
    else:
        return _run_telegram_update_bot(
            fints_settings, bot_settings, bot_update_settings, account
        )
