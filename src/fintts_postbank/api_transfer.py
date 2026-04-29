"""Process pending bank transfers fetched from the ERP API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fintts_postbank.io.helpers import io_output
from fintts_postbank.logger import get_logger
from fintts_postbank.menu import confirm_transfer
from fintts_postbank.operations import (
    VOPDeclinedError,
    execute_transfer,
    print_transfer_result,
)

if TYPE_CHECKING:
    from erp_api_client import ErpApiClient
    from fints.client import FinTS3PinTanClient  # type: ignore[import-untyped]

    from fintts_postbank.io import IOAdapter

logger = get_logger(__name__)


def process_pending_transfers(
    client: FinTS3PinTanClient,
    sepa_account: Any,
    api_client: ErpApiClient,
    adapter: IOAdapter,
) -> tuple[int, int, int, int]:
    """Process pending transfers from the ERP API.

    Lists pending transfers for the configured bank account, asks the user
    to confirm each one via the I/O adapter, executes confirmed transfers
    via FinTS, and PATCHes the result back to the API.

    Declined transfers are left in ``pending`` status (no API update).

    Args:
        client: Active FinTS client (already inside a session).
        sepa_account: The source SEPA account object.
        api_client: ERP API client for listing/updating transfers.
        adapter: I/O adapter for chat-based confirmation and TAN flow.

    Returns:
        Tuple of (executed, declined, failed, total).
    """
    from fints.client import ResponseStatus  # type: ignore[import-untyped]

    logger.info("Listing pending transfers from API")
    list_result = api_client.list_pending_transfers()

    if not list_result.success:
        message = (
            f"Could not list pending transfers: {list_result.error_message}"
        )
        logger.error(message)
        adapter.output(message)
        return (0, 0, 0, 0)

    transfers = list_result.transfers
    total = len(transfers)

    if not transfers:
        adapter.output("No pending transfers.")
        return (0, 0, 0, 0)

    adapter.output(f"Found {total} pending transfer(s).")

    executed = 0
    declined = 0
    failed = 0

    for index, transfer in enumerate(transfers, start=1):
        adapter.output(f"\n--- Transfer {index} of {total} (ID {transfer.id}) ---")
        details = {
            "recipient_iban": transfer.recipient_iban,
            "recipient_bic": transfer.recipient_bic,
            "recipient_name": transfer.recipient_name,
            "amount": transfer.amount,
            "reason": transfer.description or "",
        }

        if not confirm_transfer(details, sepa_account.iban, adapter):
            adapter.output(f"Transfer {transfer.id} skipped (left as pending).")
            declined += 1
            continue

        try:
            response = execute_transfer(
                client,
                sepa_account,
                recipient_iban=details["recipient_iban"],
                recipient_bic=details["recipient_bic"],
                recipient_name=details["recipient_name"],
                amount=details["amount"],
                reason=details["reason"],
                io=adapter,
            )
        except VOPDeclinedError:
            adapter.output(
                f"Transfer {transfer.id} skipped (Verification of Payee"
                " declined; left as pending)."
            )
            declined += 1
            continue
        except Exception as exc:  # noqa: BLE001
            error_message = f"FinTS error: {exc}"
            logger.exception("Transfer %d failed during execution", transfer.id)
            adapter.output(f"Transfer {transfer.id} FAILED: {error_message}")
            _patch_status(api_client, transfer.id, "failed", error_message, adapter)
            failed += 1
            continue

        print_transfer_result(response, adapter)

        status = getattr(response, "status", None)
        if status == ResponseStatus.SUCCESS:
            _patch_status(api_client, transfer.id, "sent", None, adapter)
            executed += 1
        else:
            # WARNING and ERROR both mean the bank did not cleanly accept the
            # transfer (e.g. "Freigabe kann nicht erteilt werden"). Mark as
            # failed so the user can retry via the API frontend.
            error_message = _build_error_message(response)
            _patch_status(
                api_client, transfer.id, "failed", error_message, adapter
            )
            failed += 1

    summary = (
        f"\nPending transfers complete: "
        f"{executed} executed, {declined} declined, {failed} failed "
        f"(of {total})."
    )
    adapter.output(summary)
    io_output(None, summary)

    return (executed, declined, failed, total)


def _patch_status(
    api_client: ErpApiClient,
    transfer_id: int,
    status: str,
    error_message: str | None,
    adapter: IOAdapter,
) -> None:
    """Update transfer status in the API and surface failures to the user."""
    result = api_client.update_transfer_status(
        transfer_id, status, error_message=error_message
    )
    if not result.success:
        warning = (
            f"WARNING: failed to update transfer {transfer_id} status to "
            f"{status} in API: {result.error_message}"
        )
        logger.warning(warning)
        adapter.output(warning)


def _build_error_message(response: Any) -> str:
    """Build a concise error message from a FinTS TransactionResponse."""
    parts: list[str] = []
    status = getattr(response, "status", None)
    if status is not None:
        parts.append(f"status={status}")

    responses = getattr(response, "responses", None)
    if responses:
        for resp in responses:
            text = getattr(resp, "text", None)
            if text:
                parts.append(str(text))

    if not parts:
        parts.append(str(response))

    return " | ".join(parts)[:500]
