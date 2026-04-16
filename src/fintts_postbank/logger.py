"""Centralized logging with per-account rotating log files."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR: Path | None = None
_CONFIGURED = False

# 5 MB per file, keep 3 backups
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 3

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def setup_logging(account_name: str | None = None) -> None:
    """Configure logging with per-account rotating log files.

    Creates a log directory at <project_root>/logs/<account_name>/
    and sets up a rotating file handler. Should be called once at startup.

    Args:
        account_name: Account name for per-account log directory.
            Uses 'default' if None.
    """
    global _LOG_DIR, _CONFIGURED  # noqa: PLW0603

    if _CONFIGURED:
        return

    name = account_name or "default"
    _LOG_DIR = _get_project_root() / "logs" / name
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    log_file = _LOG_DIR / "fints.log"

    # Root logger for the package
    root_logger = logging.getLogger("fintts_postbank")
    root_logger.setLevel(logging.DEBUG)

    # Rotating file handler — captures everything
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    root_logger.addHandler(file_handler)

    _CONFIGURED = True
    root_logger.info("Logging initialized for account: %s", name)
    root_logger.info("Log directory: %s", _LOG_DIR)


def get_logger(name: str) -> logging.Logger:
    """Get a logger for the given module.

    Args:
        name: Module name, typically __name__.

    Returns:
        Logger instance under the fintts_postbank namespace.
    """
    # Strip prefix if already fully qualified
    if name.startswith("fintts_postbank."):
        return logging.getLogger(name)
    return logging.getLogger(f"fintts_postbank.{name}")
