"""Main entry point for Postbank FinTS operations."""

from datetime import date, timedelta
from typing import Any

from fints.client import FinTS3PinTanClient, NeedTANResponse  # type: ignore[import-untyped]
from fints.hhd.flicker import terminal_flicker_unix  # type: ignore[import-untyped]

from fintts_postbank.config import BLZ, HBCI_URL, IBAN, PRODUCT_ID, get_settings


def get_valid_choice(prompt: str, max_index: int) -> int:
    """Get a valid integer choice from user within range.

    Args:
        prompt: The prompt to display.
        max_index: Maximum valid index (inclusive).

    Returns:
        Valid integer choice.
    """
    while True:
        try:
            choice = int(input(prompt))
            if 0 <= choice <= max_index:
                return choice
            print(f"Please enter a number between 0 and {max_index}")
        except ValueError:
            print("Please enter a valid number")


def interactive_cli_bootstrap(client: FinTS3PinTanClient) -> None:
    """Bootstrap TAN mechanisms with input validation.

    Replacement for fints.utils.minimal_interactive_cli_bootstrap
    that validates user input to prevent IndexError.

    Args:
        client: The FinTS client to configure.
    """
    # Fetch TAN mechanisms from bank if not already cached
    if not client.get_tan_mechanisms():
        client.fetch_tan_mechanisms()

    # Get available TAN mechanisms
    mechanisms = client.get_tan_mechanisms()

    if len(mechanisms) == 0:
        raise ValueError("No TAN mechanisms available")
    elif len(mechanisms) == 1:
        # Only one option, use it
        chosen_mechanism = list(mechanisms.values())[0]
        client.set_tan_mechanism(list(mechanisms.keys())[0])
        name = getattr(chosen_mechanism, "name", str(chosen_mechanism))
        print(f"Using TAN mechanism: {name}")
    else:
        # Multiple options, let user choose
        print("Multiple TAN mechanisms available. Which one do you prefer?")
        mech_list = list(mechanisms.items())
        for i, (key, value) in enumerate(mech_list):
            name = getattr(value, "name", str(value))
            print(f"{i} Function {key}: {name}")

        choice = get_valid_choice("Choice: ", len(mech_list) - 1)
        chosen_mechanism = mech_list[choice][1]
        client.set_tan_mechanism(mech_list[choice][0])

    # Check if we need to select a TAN medium
    # Check multiple possible indicators for needing TAN medium
    needs_medium = getattr(chosen_mechanism, "needs_tan_medium", None)
    supported_media = getattr(chosen_mechanism, "supported_media_number", 0)
    if needs_medium or supported_media > 0:
        print("We need the name of the TAN medium, let's fetch them from the bank")
        media = client.get_tan_media()

        if len(media[1]) == 0:
            raise ValueError("No TAN media available")
        elif len(media[1]) == 1:
            # Only one option, use it
            medium = media[1][0]
            client.set_tan_medium(medium)
            name = getattr(medium, "tan_medium_name", str(medium))
            print(f"Using TAN medium: {name}")
        else:
            # Multiple options, let user choose
            print("Multiple TAN media available. Which one do you prefer?")
            for i, medium in enumerate(media[1]):
                name = getattr(medium, "tan_medium_name", str(medium))
                print(f"{i} {name}")

            choice = get_valid_choice("Choice: ", len(media[1]) - 1)
            client.set_tan_medium(media[1][choice])


def handle_tan_challenge(response: NeedTANResponse) -> str:
    """Handle TAN challenge from bank.

    For decoupled TAN (BestSign app), prompts user to confirm on device.
    For other TAN methods, prompts for manual TAN entry.

    Args:
        response: The TAN challenge response from the bank.

    Returns:
        The TAN entered by user, or empty string for decoupled confirmation.
    """
    challenge = response.challenge
    print("\n" + "=" * 50)
    print("TAN CHALLENGE")
    print("=" * 50)

    if challenge:
        print(f"Challenge: {challenge}")

    # Check if this is a decoupled TAN (like BestSign)
    if response.challenge_hhduc:
        print("\nPlease confirm this transaction in your BestSign app.")
        print("Press Enter after confirming...")
        input()
        return ""

    # Check for flicker/photoTAN
    if response.challenge_hhduc:
        print("\nFlicker code displayed (if terminal supports it):")
        try:
            terminal_flicker_unix(response.challenge_hhduc)
        except Exception:
            print("(Flicker display not available on this terminal)")

    # Manual TAN entry
    tan = input("\nEnter TAN: ").strip()
    return tan


def create_client() -> FinTS3PinTanClient:
    """Create and configure FinTS client for Postbank.

    Returns:
        Configured FinTS client instance.
    """
    settings = get_settings()

    client = FinTS3PinTanClient(
        bank_identifier=BLZ,
        user_id=settings.username,
        pin=settings.password,
        server=HBCI_URL,
        product_id=PRODUCT_ID,
    )

    return client


def fetch_accounts(client: FinTS3PinTanClient) -> list[Any]:
    """Fetch SEPA accounts from the bank.

    Args:
        client: Configured FinTS client.

    Returns:
        List of SEPA account objects.
    """
    print("\nFetching SEPA accounts...")

    response = client.get_sepa_accounts()

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
        response = client.send_tan(response, tan)

    accounts: list[Any] = list(response)

    print(f"Found {len(accounts)} account(s)")
    for acc in accounts:
        print(f"  - IBAN: {acc.iban}, BIC: {acc.bic}")

    return accounts


def fetch_transactions(
    client: FinTS3PinTanClient,
    account: Any,
    days: int = 100,
) -> list[Any]:
    """Fetch transactions for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.
        days: Number of days to look back (default: 100).

    Returns:
        List of transaction objects.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    print(f"\nFetching transactions from {start_date} to {end_date}...")

    response = client.get_transactions(account, start_date, end_date)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
        response = client.send_tan(response, tan)

    transactions: list[Any] = list(response) if response else []
    print(f"Found {len(transactions)} transaction(s)")

    return transactions


def fetch_balance(client: FinTS3PinTanClient, account: Any) -> Any:
    """Fetch current balance for an account.

    Args:
        client: Configured FinTS client.
        account: SEPA account object.

    Returns:
        Balance information.
    """
    print("\nFetching account balance...")

    response = client.get_balance(account)

    # Handle TAN if required
    while isinstance(response, NeedTANResponse):
        tan = handle_tan_challenge(response)
        response = client.send_tan(response, tan)

    return response


def print_transactions(transactions: list[Any]) -> None:
    """Print transactions in a readable format.

    Args:
        transactions: List of transaction objects.
    """
    print("\n" + "=" * 70)
    print("TRANSACTIONS")
    print("=" * 70)

    for tx in transactions:
        if hasattr(tx, "data"):
            data = tx.data
            tx_date = data.get("date", "N/A")
            amount = data.get("amount", "N/A")
            purpose = data.get("purpose", "")
            applicant = data.get("applicant_name", "")
            print(f"\n{tx_date} | {amount}")
            if applicant:
                print(f"  From/To: {applicant}")
            if purpose:
                print(f"  Purpose: {purpose[:60]}...")
        else:
            print(f"\n{tx}")


def print_balance(balance: Any) -> None:
    """Print balance information.

    Args:
        balance: Balance object from FinTS.
    """
    print("\n" + "=" * 70)
    print("BALANCE")
    print("=" * 70)

    if balance:
        if hasattr(balance, "amount"):
            print(f"Current balance: {balance.amount}")
        else:
            print(f"Balance: {balance}")
    else:
        print("Balance information not available")


def find_account_by_iban(accounts: list[Any], iban: str) -> Any | None:
    """Find account by IBAN.

    Args:
        accounts: List of SEPA accounts.
        iban: IBAN to search for.

    Returns:
        Matching account or None.
    """
    for acc in accounts:
        if acc.iban == iban:
            return acc
    return None


def main() -> None:
    """Main entry point."""
    print("=" * 70)
    print("POSTBANK FINTS CLIENT")
    print("=" * 70)

    try:
        # Create client
        client = create_client()

        # Bootstrap TAN mechanisms (required before with client:)
        print("\nInitializing TAN mechanisms...")
        interactive_cli_bootstrap(client)

        # All operations must be inside a single with client: block
        with client:
            # Handle initialization TAN if needed (PSD2 requirement)
            if client.init_tan_response:
                tan = handle_tan_challenge(client.init_tan_response)
                client.send_tan(client.init_tan_response, tan)

            # Fetch accounts
            accounts = fetch_accounts(client)

            if not accounts:
                print("No accounts found!")
                return

            # Find the configured account
            account = find_account_by_iban(accounts, IBAN)
            if not account:
                print(f"Account with IBAN {IBAN} not found!")
                print("Using first available account...")
                account = accounts[0]

            print(f"\nUsing account: {account.iban}")

            # Fetch and display balance
            balance = fetch_balance(client, account)
            print_balance(balance)

            # Fetch and display transactions
            transactions = fetch_transactions(client, account)
            print_transactions(transactions)

        print("\n" + "=" * 70)
        print("DONE")
        print("=" * 70)

    except ValueError as e:
        print(f"\nConfiguration error: {e}")
        print("Please ensure .env file exists with FINTS_USERNAME and FINTS_PASSWORD")
    except Exception as e:
        print(f"\nError: {e}")
        raise


if __name__ == "__main__":
    main()
