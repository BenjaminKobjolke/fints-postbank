"""Process pending transfers mode - executes pending transfers from the ERP API."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import TYPE_CHECKING, Any

try:
    from erp_api_client import ApiSettings as SharedApiSettings
    from erp_api_client import ErpApiClient
except ImportError:
    SharedApiSettings = None  # type: ignore[assignment, misc]
    ErpApiClient = None  # type: ignore[assignment, misc]

from fintts_postbank.api_transfer import process_pending_transfers
from fintts_postbank.client import create_and_bootstrap_client
from fintts_postbank.config import (
    IBAN,
    discover_accounts,
    get_bot_mode,
    save_client_state,
    select_account,
)
from fintts_postbank.io import (
    IOAdapter,
    TelegramAdapterTimeoutError,
    XmppAdapterTimeoutError,
)
from fintts_postbank.operations import (
    fetch_accounts,
    find_account_by_iban,
)
from fintts_postbank.tan import handle_tan_challenge
from fintts_postbank.update_api_mode import (
    UpdateApiTelegramAdapter,
    UpdateApiXmppAdapter,
    _validate_configuration,
)

if TYPE_CHECKING:
    from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]
    from slixmpp import Message  # type: ignore[import-untyped]

    from fintts_postbank.config import AccountConfig


def _run_fints_transfer_session(
    adapter: IOAdapter,
    api_settings: Any,
    account: AccountConfig | None = None,
) -> int:
    """Open a FinTS session and process pending API transfers.

    Args:
        adapter: I/O adapter for chat-based confirmations and TAN.
        api_settings: API configuration settings.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero on failure).
    """
    print("[TRANSFER-MODE] Starting FinTS session...")

    iban = account.iban if account is not None else IBAN

    print(f"[TRANSFER-MODE] API URL: {api_settings.api_url}")
    shared_settings = SharedApiSettings(
        api_url=api_settings.api_url,
        api_email=api_settings.api_email,
        api_password=api_settings.api_password,
        api_company_id=api_settings.api_company_id,
        api_bank_account_id=api_settings.api_bank_account_id,
    )
    api_client = ErpApiClient(shared_settings)

    print("[TRANSFER-MODE] Creating FinTS client...")
    client: FinTS3PinTanClient = create_and_bootstrap_client(
        io=adapter, account=account
    )

    try:
        print("[TRANSFER-MODE] Opening FinTS session...")
        with client:
            if client.init_tan_response:
                print("[TRANSFER-MODE] TAN required for initialization")
                tan = handle_tan_challenge(client.init_tan_response, adapter)
                client.send_tan(client.init_tan_response, tan)
            else:
                print("[TRANSFER-MODE] No init TAN required")

            print("[TRANSFER-MODE] Fetching accounts...")
            accounts = fetch_accounts(client, adapter)
            if not accounts:
                print("[TRANSFER-MODE] ERROR: No accounts found!")
                return 1

            print(f"[TRANSFER-MODE] Looking for IBAN: {iban}")
            sepa_account = find_account_by_iban(accounts, iban)
            if not sepa_account:
                print(f"[TRANSFER-MODE] ERROR: Account with IBAN {iban} not found!")
                print(f"[TRANSFER-MODE] Available IBANs: {[a.iban for a in accounts]}")
                sepa_account = accounts[0]
                print(
                    f"[TRANSFER-MODE] Using first available account: {sepa_account.iban}"
                )

            print(f"[TRANSFER-MODE] Using account: {sepa_account.iban}")

            executed, declined, failed, total = process_pending_transfers(
                client, sepa_account, api_client, adapter
            )

            print(
                f"[TRANSFER-MODE] Completed. {executed} executed, {declined} declined,"
                f" {failed} failed (of {total})."
            )

        acct_label = account.name if account is not None else None
        save_client_state(client.deconstruct(), acct_label)

        return 0 if failed == 0 else 1

    except (TelegramAdapterTimeoutError, XmppAdapterTimeoutError):
        print("[TRANSFER-MODE] Session timed out waiting for TAN confirmation.")
        return 1
    except Exception as e:
        print(f"[TRANSFER-MODE] Error during FinTS session: {e}")
        import traceback

        traceback.print_exc()
        return 1


def _run_telegram_process_transfers(
    telegram_settings: Any,
    api_settings: Any,
    account: AccountConfig | None = None,
) -> int:
    """Run process-transfers mode using the Telegram backend.

    Args:
        telegram_settings: Telegram bot settings.
        api_settings: API configuration.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero on failure).
    """
    from telegram_bot import TelegramBot  # type: ignore[import-untyped]
    from telegram_bot.config import (  # type: ignore[import-untyped]
        Settings as TelegramBotSettings,
    )

    print("Initializing Telegram bot...")
    bot_settings = TelegramBotSettings(
        bot_token=telegram_settings.bot_token,
        channel_id="@dummy_channel",
    )

    bot = TelegramBot.get_instance()
    bot.initialize(settings=bot_settings)

    adapter = UpdateApiTelegramAdapter(
        bot,
        api_settings.telegram_target_user_id,
        timeout=300,
    )

    def on_update(update: Any) -> None:
        if update.message and update.message.text:
            user = update.message.from_user
            if user and user.id == api_settings.telegram_target_user_id:
                adapter.handle_incoming_message(update.message.text)

    bot.add_message_handler(on_update)

    result_container: list[int] = []
    session_complete = threading.Event()

    def session_thread() -> None:
        try:
            print("Session thread starting...")
            result = _run_fints_transfer_session(adapter, api_settings, account)
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


async def _run_xmpp_process_transfers_async(
    xmpp_settings: Any,
    api_settings: Any,
    account: AccountConfig | None = None,
) -> int:
    """Async runner for process-transfers mode over XMPP.

    Args:
        xmpp_settings: XMPP bot settings.
        api_settings: API configuration.
        account: Optional AccountConfig for multi-account support.

    Returns:
        Exit code (0 for success, non-zero on failure).
    """
    from xmpp_bot import XmppBot  # type: ignore[import-untyped]
    from xmpp_bot.config import (  # type: ignore[import-untyped]
        Settings as XmppBotSettings,
    )

    print("Initializing XMPP bot...")
    bot_settings = XmppBotSettings(
        jid=xmpp_settings.jid,
        password=xmpp_settings.password,
        resource=xmpp_settings.resource,
        default_receiver=xmpp_settings.default_receiver,
    )

    bot = XmppBot.get_instance()
    await bot.initialize(settings=bot_settings)

    event_loop = asyncio.get_running_loop()

    target_jid = xmpp_settings.default_receiver
    adapter = UpdateApiXmppAdapter(
        bot,
        target_jid,
        event_loop,
        timeout=300,
    )

    async def on_message(sender: str, body: str, msg: Message) -> None:
        bare_jid = sender.split("/")[0].lower()
        if bare_jid == target_jid.lower():
            adapter.handle_incoming_message(body)

    bot.add_message_handler("process_transfers_handler", on_message)

    result_container: list[int] = []
    session_complete = threading.Event()

    def session_thread() -> None:
        try:
            print("Session thread starting...")
            result = _run_fints_transfer_session(adapter, api_settings, account)
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


def _run_xmpp_process_transfers(
    xmpp_settings: Any,
    api_settings: Any,
    account: AccountConfig | None = None,
) -> int:
    """Sync wrapper for the async XMPP runner."""
    return asyncio.run(
        _run_xmpp_process_transfers_async(xmpp_settings, api_settings, account)
    )


def run_process_transfers_mode(account_name: str | None = None) -> int:
    """Run the process-transfers mode.

    Lists pending transfers from the ERP API, asks the user to confirm each
    one via Telegram or XMPP, executes confirmed transfers via FinTS, and
    PATCHes the resulting status back to the API.

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Exit code (0 for success, non-zero on failure).
    """
    if ErpApiClient is None:
        print("Error: erp-api-client is not installed.")
        print("Install it with: uv sync --extra api")
        return 1

    print("Process Transfers Mode")
    print("=" * 40)

    account: AccountConfig | None = None
    accounts = discover_accounts()
    if accounts:
        if len(accounts) > 1 and account_name is None:
            non_default = [a for a in accounts if a.name != "default"]
            if non_default:
                print(
                    "Multiple accounts found. Use --account <name> to specify which one."
                )
                print("Available accounts:")
                for a in accounts:
                    print(f"  - {a.name}")
                return 1

        if (
            len(accounts) == 1
            and accounts[0].name == "default"
            and account_name is None
        ):
            account = None
        else:
            account = select_account(accounts, account_name)
            print(f"Using account: {account.name}")

    env_path = account.env_path if account is not None else None

    bot_mode = get_bot_mode(env_path)
    if bot_mode == "console":
        bot_mode = "telegram"
    print(f"Using {bot_mode.upper()} for confirmations")

    _, bot_settings, api_settings, bot_mode = _validate_configuration(
        bot_mode, account
    )

    print(f"Checking API connectivity: {api_settings.api_url}")
    shared_settings = SharedApiSettings(
        api_url=api_settings.api_url,
        api_email=api_settings.api_email,
        api_password=api_settings.api_password,
        api_company_id=api_settings.api_company_id,
        api_bank_account_id=api_settings.api_bank_account_id,
    )
    api_client = ErpApiClient(shared_settings)
    ping_result = api_client.ping()
    if ping_result.success:
        print("[TRANSFER-MODE] API connection OK")
    else:
        print(f"[TRANSFER-MODE] ERROR: {ping_result.error_message}")
        print("Please check your API_URL, API_EMAIL, and API_PASSWORD settings.")
        return 1

    if bot_mode == "xmpp":
        return _run_xmpp_process_transfers(bot_settings, api_settings, account)
    return _run_telegram_process_transfers(bot_settings, api_settings, account)
