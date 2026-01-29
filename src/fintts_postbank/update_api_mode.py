"""Update API mode - automated FinTS data fetch and API posting."""

from __future__ import annotations

import sys
import threading
import time
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from telegram_bot import TelegramBot  # type: ignore[import-untyped]
from telegram_bot.config import Settings as TelegramBotSettings  # type: ignore[import-untyped]

from fintts_postbank.api_client import ForecastApiClient
from fintts_postbank.client import create_client
from fintts_postbank.config import (
    IBAN,
    get_api_settings,
    get_settings,
    get_telegram_settings,
)
from fintts_postbank.io import TelegramAdapter, TelegramAdapterTimeoutError
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


class UpdateApiAdapter(TelegramAdapter):
    """Telegram adapter for update-api mode.

    Sends messages to a specific target user and waits for their response.
    """

    def __init__(
        self,
        bot: TelegramBot,
        target_user_id: int,
        timeout: int = 300,
    ) -> None:
        """Initialize the update-api adapter.

        Args:
            bot: The TelegramBot instance.
            target_user_id: The Telegram user ID to communicate with.
            timeout: Timeout in seconds for waiting on user input.
        """
        super().__init__(bot, target_user_id, timeout)
        self.target_user_id = target_user_id


def _validate_configuration() -> tuple[Any, Any, Any]:
    """Validate all required configuration for update-api mode.

    Returns:
        Tuple of (fints_settings, telegram_settings, api_settings).

    Raises:
        SystemExit: If configuration is invalid or missing.
    """
    errors: list[str] = []

    # Check FinTS settings
    try:
        fints_settings = get_settings()
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

    # Check Telegram settings
    telegram_settings = get_telegram_settings()
    if not telegram_settings.bot_token:
        errors.append("TELEGRAM_BOT_TOKEN not set in .env")

    # Check API settings
    try:
        api_settings = get_api_settings()
    except ValueError as e:
        errors.append(f"API settings: {e}")
        api_settings = None

    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    return fints_settings, telegram_settings, api_settings


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
    adapter: UpdateApiAdapter,
    api_settings: Any,
    fints_settings: Any,
) -> int:
    """Run the FinTS session and post data to API.

    Args:
        adapter: The Telegram adapter for I/O.
        api_settings: API configuration settings.
        fints_settings: FinTS configuration settings.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("[API-MODE] Starting FinTS session...")

    # Create API client and transaction DB
    print(f"[API-MODE] API URL: {api_settings.api_url}")
    api_client = ForecastApiClient(api_settings)
    tx_db = TransactionDatabase()

    # Create FinTS client
    print("[API-MODE] Creating FinTS client...")
    client: FinTS3PinTanClient = create_client(adapter)

    # Bootstrap TAN mechanisms (uses saved preferences)
    print("[API-MODE] Initializing TAN mechanisms...")
    interactive_cli_bootstrap(client, force_tan_selection=False, io=adapter)

    try:
        print("[API-MODE] Opening FinTS session...")
        with client:
            # Handle initialization TAN if needed (PSD2 requirement)
            if client.init_tan_response:
                print("[API-MODE] TAN required for initialization")
                tan = handle_tan_challenge(client.init_tan_response, adapter)
                client.send_tan(client.init_tan_response, tan)
            else:
                print("[API-MODE] No init TAN required")

            # Fetch accounts
            print("[API-MODE] Fetching accounts...")
            try:
                accounts = fetch_accounts(client, adapter)
                print(f"[API-MODE] Found {len(accounts) if accounts else 0} accounts")
            except Exception as e:
                print(f"[API-MODE] ERROR fetching accounts: {e}")
                import traceback
                traceback.print_exc()
                raise
            if not accounts:
                print("[API-MODE] ERROR: No accounts found!")
                adapter.output("No accounts found!")
                return 1

            # Find the configured account
            print(f"[API-MODE] Looking for IBAN: {IBAN}")
            account = find_account_by_iban(accounts, IBAN)
            if not account:
                print(f"[API-MODE] ERROR: Account with IBAN {IBAN} not found!")
                print(f"[API-MODE] Available IBANs: {[a.iban for a in accounts]}")
                adapter.output(f"Account with IBAN {IBAN} not found!")
                # Use first account as fallback
                account = accounts[0]
                print(f"[API-MODE] Using first available account: {account.iban}")

            print(f"[API-MODE] Using account: {account.iban}")

            # Fetch and post balance
            print("[API-MODE] Fetching balance...")
            balance = fetch_balance(client, account, adapter)
            balance_value: Decimal | None = None

            if balance and hasattr(balance, "amount"):
                balance_amount = balance.amount
                if hasattr(balance_amount, "amount"):
                    # mt940 Amount object
                    balance_value = Decimal(str(balance_amount.amount))
                else:
                    balance_value = Decimal(str(balance_amount))

                print(f"[API-MODE] Balance: {balance_value}")

                # Post balance to API
                print("[API-MODE] Posting balance to API...")
                balance_result = api_client.post_balance(date.today(), balance_value)

                if balance_result.success:
                    if balance_result.is_duplicate:
                        print("[API-MODE] Balance already recorded (duplicate)")
                    else:
                        print("[API-MODE] Balance posted successfully!")
                else:
                    print(f"[API-MODE] Failed to post balance: {balance_result.error_message}")
                    adapter.output(f"Failed to post balance: {balance_result.error_message}")
                    return 1
            else:
                print("[API-MODE] Could not fetch balance")
                adapter.output("Could not fetch balance.")

            # Fetch transactions
            start_date = api_settings.transaction_start_date
            end_date = date.today()
            print(f"[API-MODE] Fetching transactions from {start_date} to {end_date}...")
            print("[API-MODE] (This may require TAN - check Telegram)")

            try:
                transactions = fetch_transactions(
                    client, account, start_date, end_date, adapter
                )
                tx_count = len(transactions) if transactions else 0
                print(f"[API-MODE] Received {tx_count} transactions")
            except Exception as e:
                print(f"[API-MODE] ERROR fetching transactions: {e}")
                import traceback
                traceback.print_exc()
                raise

            # Process transactions
            sent_count = 0
            skipped_count = 0
            error_count = 0

            if not transactions:
                print("[API-MODE] No transactions found")
            else:
                for tx in transactions:
                    tx_data = _extract_transaction_data(tx)
                    if not tx_data:
                        continue

                    tx_date, amount, name, purpose = tx_data

                    # Check if already sent
                    if tx_db.is_transaction_sent(
                        fints_settings.username, tx_date, amount, name, purpose
                    ):
                        skipped_count += 1
                        continue

                    # Build transaction name for API
                    tx_name = name if name else purpose[:50] if purpose else "Unknown"

                    # Post to API
                    result = api_client.post_transaction(tx_name, amount, tx_date)

                    if result.success:
                        # Mark as sent in local DB
                        tx_db.mark_transaction_sent(
                            fints_settings.username, tx_date, amount, name, purpose
                        )
                        if result.is_duplicate:
                            skipped_count += 1
                        else:
                            sent_count += 1
                    else:
                        error_count += 1
                        adapter.output(f"Failed to post transaction: {result.error_message}")

            if transactions:
                print(
                    f"[API-MODE] Transactions: {sent_count} sent, "
                    f"{skipped_count} skipped, {error_count} errors"
                )

        # Build consolidated summary message
        print("[API-MODE] Completed successfully!")
        summary_parts = ["✓ Sync complete"]
        if balance_value is not None:
            summary_parts.append(f"Balance: {balance_value:.2f}€")
        summary_parts.append(f"Transactions: {sent_count} new, {skipped_count} skipped")
        adapter.output(" | ".join(summary_parts))
        return 0

    except TelegramAdapterTimeoutError:
        adapter.output("Session timed out waiting for TAN confirmation.")
        return 1
    except Exception as e:
        adapter.output(f"Error during FinTS session: {e}")
        return 1


def run_update_api_mode() -> int:
    """Run the update-api mode.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("Update API Mode")
    print("=" * 40)

    # Validate configuration
    fints_settings, telegram_settings, api_settings = _validate_configuration()

    # Check API connectivity
    print(f"Checking API connectivity: {api_settings.api_url}")
    api_client = ForecastApiClient(api_settings)
    ping_result = api_client.ping()
    if ping_result.success:
        print("[API-MODE] API connection OK")
    else:
        print(f"[API-MODE] ERROR: {ping_result.error_message}")
        print("Please check your API_URL, API_USER, and API_PASSWORD settings.")
        return 1

    # Initialize Telegram bot
    print("Initializing Telegram bot...")
    bot_settings = TelegramBotSettings(
        bot_token=telegram_settings.bot_token,
        channel_id="@dummy_channel",  # Not used, but required by library
    )

    bot = TelegramBot.get_instance()
    bot.initialize(settings=bot_settings)

    # Create adapter for target user
    adapter = UpdateApiAdapter(
        bot,
        api_settings.telegram_target_user_id,
        timeout=300,  # 5 minutes for TAN confirmation
    )

    # Send startup notification to target user
    print(f"Notifying user {api_settings.telegram_target_user_id}...")
    try:
        bot.reply_to_user(
            "FinTS API sync starting. You may receive TAN challenges.",
            api_settings.telegram_target_user_id,
        )
    except Exception as e:
        print(f"Warning: Could not send startup notification: {e}")

    # Set up message handler for receiving TAN responses
    def on_update(update: Any) -> None:
        """Handle incoming Telegram update."""
        if update.message and update.message.text:
            user = update.message.from_user
            if user and user.id == api_settings.telegram_target_user_id:
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
            result = _run_fints_session(adapter, api_settings, fints_settings)
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
        return 1

    # Send completion message to all allowed users
    result = result_container[0] if result_container else 1
    telegram_settings = get_telegram_settings()
    if telegram_settings.allowed_user_ids:
        if result == 0:
            completion_msg = "FinTS API sync completed successfully."
        else:
            completion_msg = "FinTS API sync finished with errors."
        print(f"Notifying {len(telegram_settings.allowed_user_ids)} user(s) of completion...")
        for user_id in telegram_settings.allowed_user_ids:
            try:
                bot.reply_to_user(completion_msg, user_id)
                print(f"  - Notified user {user_id}")
            except Exception as e:
                print(f"  - Failed to notify user {user_id}: {e}")

    bot.shutdown()
    return result
