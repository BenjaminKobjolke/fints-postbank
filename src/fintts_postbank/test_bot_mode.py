"""Test bot mode - send a test message via configured bot to verify setup."""

from __future__ import annotations

import asyncio
from typing import Any

from fintts_postbank.config import (
    discover_accounts,
    get_bot_mode,
    get_bot_update_settings,
    get_telegram_settings,
    get_xmpp_settings,
    select_account,
)
from fintts_postbank.io import TelegramAdapter

TEST_MESSAGE = "Test message from fints-postbank - bot connection OK!"


def _run_telegram_test(telegram_settings: Any, target_user_id: int) -> int:
    """Send a test message via Telegram.

    Args:
        telegram_settings: Telegram bot settings.
        target_user_id: Telegram user ID to send to.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    from telegram_bot import TelegramBot  # type: ignore[import-untyped]
    from telegram_bot.config import Settings as TelegramBotSettings  # type: ignore[import-untyped]

    print("Initializing Telegram bot...")
    tg_bot_settings = TelegramBotSettings(
        bot_token=telegram_settings.bot_token,
        channel_id="@dummy_channel",
    )

    bot = TelegramBot.get_instance()
    bot.initialize(settings=tg_bot_settings)

    adapter = TelegramAdapter(bot, target_user_id)

    try:
        print(f"Sending test message to user {target_user_id}...")
        adapter.output(TEST_MESSAGE)
        bot.flush()
        print("Test message sent successfully!")
        return 0
    except Exception as e:
        print(f"Failed to send test message: {e}")
        return 1
    finally:
        bot.shutdown()


async def _run_xmpp_test_async(xmpp_settings: Any) -> int:
    """Send a test message via XMPP (async).

    Args:
        xmpp_settings: XMPP bot settings.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    from xmpp_bot import XmppBot  # type: ignore[import-untyped]
    from xmpp_bot.config import Settings as XmppBotSettings  # type: ignore[import-untyped]

    print("Initializing XMPP bot...")
    xmpp_bot_settings = XmppBotSettings(
        jid=xmpp_settings.jid,
        password=xmpp_settings.password,
        resource=xmpp_settings.resource,
        default_receiver=xmpp_settings.default_receiver,
    )

    bot = XmppBot.get_instance()
    await bot.initialize(settings=xmpp_bot_settings)

    target_jid = xmpp_settings.default_receiver

    try:
        print(f"Sending test message to {target_jid}...")
        await bot.reply_to_user(TEST_MESSAGE, target_jid)
        await bot.flush()
        print("Test message sent successfully!")
        return 0
    except Exception as e:
        print(f"Failed to send test message: {e}")
        return 1
    finally:
        bot.disconnect()


def _run_xmpp_test(xmpp_settings: Any) -> int:
    """Send a test message via XMPP.

    Args:
        xmpp_settings: XMPP bot settings.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    return asyncio.run(_run_xmpp_test_async(xmpp_settings))


def run_test_bot_mode(account_name: str | None = None) -> int:
    """Run the test-bot mode.

    Args:
        account_name: Optional account name from --account flag.

    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    print("Test Bot Mode")
    print("=" * 40)

    # Discover and select account
    account = None
    accounts = discover_accounts()
    if accounts:
        if len(accounts) > 1 and account_name is None:
            non_default = [a for a in accounts if a.name != "default"]
            if non_default:
                print("Multiple accounts found. Use --account <name> to specify which one.")
                print("Available accounts:")
                for a in accounts:
                    print(f"  - {a.name}")
                return 1

        if len(accounts) == 1 and accounts[0].name == "default" and account_name is None:
            account = None
        else:
            account = select_account(accounts, account_name)
            print(f"Using account: {account.name}")

    env_path = account.env_path if account is not None else None

    # Determine bot mode
    bot_mode = get_bot_mode(env_path)
    if bot_mode == "console":
        bot_mode = "telegram"
    print(f"Using {bot_mode.upper()} for test message")

    # Validate and send
    if bot_mode == "xmpp":
        xmpp_settings = get_xmpp_settings(env_path)
        errors = []
        if not xmpp_settings.jid:
            errors.append("XMPP_JID not set in .env")
        if not xmpp_settings.password:
            errors.append("XMPP_PASSWORD not set in .env")
        if not xmpp_settings.default_receiver:
            errors.append("XMPP_DEFAULT_RECEIVER not set in .env")
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return 1

        return _run_xmpp_test(xmpp_settings)
    else:
        telegram_settings = get_telegram_settings(env_path)
        bot_update_settings = get_bot_update_settings(env_path)
        errors = []
        if not telegram_settings.bot_token:
            errors.append("TELEGRAM_BOT_TOKEN not set in .env")
        if not bot_update_settings.telegram_target_user_id:
            errors.append("TELEGRAM_TARGET_USER_ID not set in .env")
        if errors:
            print("Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return 1

        return _run_telegram_test(
            telegram_settings, bot_update_settings.telegram_target_user_id
        )
