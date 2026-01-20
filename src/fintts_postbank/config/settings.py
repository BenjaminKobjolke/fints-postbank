"""Environment-based settings for FinTS authentication."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """FinTS authentication settings loaded from environment."""

    username: str
    password: str


def get_settings() -> Settings:
    """Load settings from environment variables.

    Looks for .env file in project root directory.

    Returns:
        Settings object with username and password.

    Raises:
        ValueError: If required environment variables are missing.
    """
    # Find project root (where .env should be)
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"

    load_dotenv(env_path)

    username = os.getenv("FINTS_USERNAME")
    password = os.getenv("FINTS_PASSWORD")

    if not username:
        raise ValueError("FINTS_USERNAME environment variable is required")
    if not password:
        raise ValueError("FINTS_PASSWORD environment variable is required")

    return Settings(username=username, password=password)
