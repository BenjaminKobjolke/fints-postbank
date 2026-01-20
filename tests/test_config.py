"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from fintts_postbank.config import BLZ, HBCI_URL, IBAN, PRODUCT_ID
from fintts_postbank.config.settings import Settings, get_settings


class TestConstants:
    """Tests for bank constants."""

    def test_blz_format(self) -> None:
        """BLZ should be 8 digits."""
        assert len(BLZ) == 8
        assert BLZ.isdigit()

    def test_hbci_url_is_https(self) -> None:
        """HBCI URL should use HTTPS."""
        assert HBCI_URL.startswith("https://")

    def test_product_id_not_empty(self) -> None:
        """Product ID should not be empty."""
        assert len(PRODUCT_ID) > 0

    def test_iban_format(self) -> None:
        """IBAN should start with DE and be 22 characters."""
        assert IBAN.startswith("DE")
        assert len(IBAN) == 22


class TestSettings:
    """Tests for settings loading."""

    def test_settings_dataclass(self) -> None:
        """Settings should be immutable."""
        settings = Settings(username="test", password="secret")
        assert settings.username == "test"
        assert settings.password == "secret"

        with pytest.raises(AttributeError):
            settings.username = "changed"  # type: ignore[misc]

    def test_get_settings_missing_username(self) -> None:
        """Should raise ValueError if username is missing."""
        with patch.dict(os.environ, {"FINTS_PASSWORD": "test"}, clear=True):
            with pytest.raises(ValueError, match="FINTS_USERNAME"):
                get_settings()

    def test_get_settings_missing_password(self) -> None:
        """Should raise ValueError if password is missing."""
        with patch.dict(os.environ, {"FINTS_USERNAME": "test"}, clear=True):
            with pytest.raises(ValueError, match="FINTS_PASSWORD"):
                get_settings()

    def test_get_settings_success(self) -> None:
        """Should return Settings when both env vars are set."""
        with patch.dict(
            os.environ,
            {"FINTS_USERNAME": "testuser", "FINTS_PASSWORD": "testpass"},
            clear=True,
        ):
            settings = get_settings()
            assert settings.username == "testuser"
            assert settings.password == "testpass"
