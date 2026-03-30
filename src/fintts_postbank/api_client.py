"""HTTP client for erp-api integration."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import httpx

from fintts_postbank.config import ApiSettings


@dataclass
class ApiResponse:
    """Response from API call."""

    success: bool
    is_duplicate: bool = False
    error_message: str | None = None


class ErpApiClient:
    """HTTP client for erp-api.

    Handles balance and transaction posting with JWT auth.
    """

    def __init__(self, settings: ApiSettings) -> None:
        """Initialize the API client.

        Args:
            settings: API configuration settings.
        """
        self.settings = settings
        self.base_url = settings.api_url.rstrip("/")
        self._token: str | None = None

        # Define endpoints in one place
        bank_account_base = (
            f"{self.base_url}/api/v1/bank-accounts/{settings.api_bank_account_id}"
        )
        self._auth_url = f"{self.base_url}/auth/token"
        self._balance_url = f"{bank_account_base}/balances"
        self._transaction_url = f"{bank_account_base}/transactions"
        self._ping_url = f"{self.base_url}/api/v1/bank-accounts"

    def _authenticate(self) -> bool:
        """Authenticate with the API and cache the JWT token.

        Returns:
            True if authentication succeeded, False otherwise.
        """
        payload = {
            "email": self.settings.api_email,
            "password": self.settings.api_password,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self._auth_url, json=payload)

                if response.status_code in (200, 201):
                    data = response.json()
                    self._token = data.get("access_token")
                    return self._token is not None
                return False
        except httpx.RequestError:
            return False

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authorization headers for API requests.

        Returns:
            Dict with Authorization and X-Company-Id headers.
        """
        return {
            "Authorization": f"Bearer {self._token}",
            "X-Company-Id": str(self.settings.api_company_id),
        }

    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid token, authenticating if needed.

        Returns:
            True if we have a valid token, False otherwise.
        """
        if self._token is None:
            return self._authenticate()
        return True

    def _request_with_retry(
        self,
        method: str,
        url: str,
        json_payload: dict | None = None,
        timeout: float = 30.0,
    ) -> httpx.Response | None:
        """Make an authenticated request with one retry on 401.

        Args:
            method: HTTP method ("GET" or "POST").
            url: The request URL.
            json_payload: Optional JSON payload for POST requests.
            timeout: Request timeout in seconds.

        Returns:
            The httpx.Response, or None if authentication failed.
        """
        if not self._ensure_authenticated():
            return None

        with httpx.Client(timeout=timeout) as client:
            kwargs: dict = {"headers": self._get_auth_headers()}
            if json_payload is not None:
                kwargs["json"] = json_payload

            response = client.request(method, url, **kwargs)

            # On 401, re-authenticate once and retry
            if response.status_code == 401:
                if not self._authenticate():
                    return response  # Return the 401 response
                kwargs["headers"] = self._get_auth_headers()
                response = client.request(method, url, **kwargs)

            return response

    def ping(self) -> ApiResponse:
        """Check if the API is reachable and credentials are valid.

        Returns:
            ApiResponse indicating success or failure.
        """
        try:
            response = self._request_with_retry("GET", self._ping_url, timeout=10.0)

            if response is None:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed",
                )

            if response.status_code == 401:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed (401 Unauthorized)",
                )
            elif response.status_code == 403:
                return ApiResponse(
                    success=False,
                    error_message="API access forbidden (403 Forbidden)",
                )
            # Any other response means the API is reachable
            return ApiResponse(success=True)
        except httpx.ConnectError as e:
            return ApiResponse(
                success=False,
                error_message=f"Cannot connect to API: {e}",
            )
        except httpx.RequestError as e:
            return ApiResponse(success=False, error_message=f"Request error: {e}")

    def post_balance(self, balance_date: date, value: Decimal) -> ApiResponse:
        """Post bank balance to the API.

        Args:
            balance_date: The date of the balance.
            value: The balance amount.

        Returns:
            ApiResponse indicating success or failure.
        """
        payload = {
            "date": balance_date.isoformat(),
            "value": str(value),
        }

        try:
            response = self._request_with_retry(
                "POST", self._balance_url, json_payload=payload
            )

            if response is None:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed",
                )

            if response.status_code in (200, 201):
                return ApiResponse(success=True)
            elif response.status_code == 409:
                # Duplicate - treat as success
                return ApiResponse(success=True, is_duplicate=True)
            elif response.status_code == 401:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed (401 Unauthorized)",
                )
            else:
                return ApiResponse(
                    success=False,
                    error_message=(
                        f"API error {response.status_code}: {response.text[:500]}"
                    ),
                )
        except httpx.RequestError as e:
            return ApiResponse(success=False, error_message=f"Request error: {e}")

    def post_transaction(
        self,
        name: str,
        value: Decimal,
        date_actual: date,
        *,
        purpose: str | None = None,
        applicant_iban: str | None = None,
        applicant_bic: str | None = None,
        posting_text: str | None = None,
        end_to_end_reference: str | None = None,
        customer_reference: str | None = None,
        creditor_id: str | None = None,
        mandate_reference: str | None = None,
        currency: str | None = None,
    ) -> ApiResponse:
        """Post a transaction to the API.

        Args:
            name: Transaction name/description.
            value: Transaction amount (positive or negative).
            date_actual: The actual date of the transaction.
            purpose: Full transaction purpose text.
            applicant_iban: IBAN of the sender/receiver.
            applicant_bic: BIC/SWIFT code of the sender/receiver bank.
            posting_text: Transaction type label (e.g. "SEPA-Ueberweisung").
            end_to_end_reference: SEPA end-to-end reference (EREF).
            customer_reference: Customer reference (KREF).
            creditor_id: SEPA creditor identifier (CRED).
            mandate_reference: SEPA mandate reference (MREF).
            currency: ISO 4217 currency code (e.g. "EUR").

        Returns:
            ApiResponse indicating success or failure.
        """
        payload: dict[str, str] = {
            "name": name,
            "value": str(value),
            "date_actual": date_actual.isoformat(),
            "status": "paid",
        }

        # Include optional fields only when present
        optional_fields = {
            "purpose": purpose,
            "applicant_iban": applicant_iban,
            "applicant_bic": applicant_bic,
            "posting_text": posting_text,
            "end_to_end_reference": end_to_end_reference,
            "customer_reference": customer_reference,
            "creditor_id": creditor_id,
            "mandate_reference": mandate_reference,
            "currency": currency,
        }
        for key, val in optional_fields.items():
            if val is not None:
                payload[key] = val

        try:
            response = self._request_with_retry(
                "POST", self._transaction_url, json_payload=payload
            )

            if response is None:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed",
                )

            if response.status_code in (200, 201):
                return ApiResponse(success=True)
            elif response.status_code == 409:
                # Duplicate - treat as success
                return ApiResponse(success=True, is_duplicate=True)
            elif response.status_code == 401:
                return ApiResponse(
                    success=False,
                    error_message="API authentication failed (401 Unauthorized)",
                )
            else:
                return ApiResponse(
                    success=False,
                    error_message=(
                        f"API error {response.status_code}: {response.text[:500]}"
                    ),
                )
        except httpx.RequestError as e:
            return ApiResponse(success=False, error_message=f"Request error: {e}")
