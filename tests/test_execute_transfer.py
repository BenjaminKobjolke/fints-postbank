"""Tests for input normalization in execute_transfer."""

from decimal import Decimal
from unittest.mock import MagicMock

from fintts_postbank.operations import execute_transfer


def test_execute_transfer_normalizes_sepa_fields() -> None:
    client = MagicMock()
    account = MagicMock(iban="DE00123")

    execute_transfer(
        client,
        account,
        recipient_iban="de89 3704 0044 0532 0130 00",
        recipient_bic=" cobadeffxxx ",
        recipient_name="Test",
        amount=Decimal("1.00"),
        reason="   ",
    )

    kwargs = client.simple_sepa_transfer.call_args.kwargs
    assert kwargs["iban"] == "DE89370400440532013000"
    assert kwargs["bic"] == "COBADEFFXXX"
    assert kwargs["reason"] == "NOTPROVIDED"


def test_execute_transfer_drops_invalid_bic() -> None:
    client = MagicMock()

    execute_transfer(
        client,
        MagicMock(iban="DE00123"),
        recipient_iban="DE89370400440532013000",
        recipient_bic="COBA.DE",
        recipient_name="Test",
        amount=Decimal("1.00"),
        reason="x",
    )

    assert client.simple_sepa_transfer.call_args.kwargs["bic"] == ""


def test_io_confirm_reasks_on_unknown_answer() -> None:
    from fintts_postbank.io.helpers import io_confirm

    io = MagicMock()
    io.input.side_effect = ["Yea", "y"]
    assert io_confirm(io, "? ") is True
    assert io.input.call_count == 2
