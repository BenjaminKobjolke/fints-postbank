"""Multi-account discovery and selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import BLZ as DEFAULT_BLZ
from .constants import HBCI_URL as DEFAULT_HBCI_URL
from .constants import IBAN as DEFAULT_IBAN
from .constants import PRODUCT_ID as DEFAULT_PRODUCT_ID
from .settings import _cached_dotenv_values

if TYPE_CHECKING:
    from fintts_postbank.io import IOAdapter


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent.parent


@dataclass(frozen=True)
class AccountConfig:
    """Configuration for a single bank account."""

    name: str  # e.g. "postbank" or "default"
    env_path: Path  # e.g. project_root / ".env.postbank"
    blz: str
    hbci_url: str
    iban: str
    product_id: str


def discover_accounts() -> list[AccountConfig]:
    """Discover available account configurations.

    Scans for .env.* files in the project root. If none found,
    falls back to the plain .env file with name="default".

    Returns:
        List of AccountConfig objects, one per discovered .env file.
    """
    project_root = _get_project_root()

    # Look for .env.* files (excluding .env.example)
    accounts: list[AccountConfig] = []
    for env_file in sorted(project_root.glob(".env.*")):
        # Skip .env.example
        if env_file.name == ".env.example":
            continue
        # Skip backup files
        if env_file.suffix in (".bak", ".backup", ".old"):
            continue

        account_name = env_file.name[len(".env."):]
        account = _load_account_from_env(account_name, env_file)
        if account is not None:
            accounts.append(account)

    # Fallback to plain .env if no .env.* files found
    if not accounts:
        plain_env = project_root / ".env"
        if plain_env.exists():
            account = _load_account_from_env("default", plain_env)
            if account is not None:
                accounts.append(account)

    return accounts


def _load_account_from_env(name: str, env_path: Path) -> AccountConfig | None:
    """Load an AccountConfig from an env file.

    Args:
        name: Account name (e.g. "postbank" or "default").
        env_path: Path to the .env file.

    Returns:
        AccountConfig or None if the file cannot be parsed.
    """
    values = _cached_dotenv_values(env_path)

    blz = values.get("BLZ", DEFAULT_BLZ)
    hbci_url = values.get("HBCI_URL", DEFAULT_HBCI_URL)
    iban = values.get("IBAN", DEFAULT_IBAN)
    product_id = values.get("PRODUCT_ID", DEFAULT_PRODUCT_ID)

    return AccountConfig(
        name=name,
        env_path=env_path,
        blz=blz,
        hbci_url=hbci_url,
        iban=iban,
        product_id=product_id,
    )


def select_account(
    accounts: list[AccountConfig],
    account_name: str | None = None,
    io: IOAdapter | None = None,
) -> AccountConfig:
    """Select an account from the discovered accounts.

    Args:
        accounts: List of discovered accounts.
        account_name: If given, select by name (skip interactive prompt).
        io: Optional IOAdapter for I/O operations.

    Returns:
        The selected AccountConfig.

    Raises:
        ValueError: If no accounts found or named account doesn't exist.
    """
    if not accounts:
        raise ValueError(
            "No account configurations found. "
            "Create a .env file or .env.<name> files in the project root."
        )

    # If account_name specified, find it
    if account_name is not None:
        for account in accounts:
            if account.name == account_name:
                return account
        available = ", ".join(a.name for a in accounts)
        raise ValueError(
            f"Account '{account_name}' not found. Available accounts: {available}"
        )

    # Single account: use it automatically
    if len(accounts) == 1:
        return accounts[0]

    # Multiple accounts: prompt interactively
    _io_output(io, "Multiple accounts found:")
    for i, account in enumerate(accounts):
        _io_output(io, f"  {i}) {account.name} (IBAN: {account.iban})")

    choice = _io_input(io, "Select account: ")
    try:
        idx = int(choice.strip())
        if 0 <= idx < len(accounts):
            return accounts[idx]
    except ValueError:
        pass

    # Try matching by name
    for account in accounts:
        if account.name == choice.strip():
            return account

    raise ValueError(f"Invalid selection: {choice}")


def _io_output(io: IOAdapter | None, message: str) -> None:
    """Output message using IOAdapter or print."""
    if io is not None:
        io.output(message)
    else:
        print(message)


def _io_input(io: IOAdapter | None, prompt: str) -> str:
    """Get input using IOAdapter or input()."""
    if io is not None:
        return io.input(prompt)
    return input(prompt)
