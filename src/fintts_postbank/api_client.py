"""HTTP client for forecast-php API integration."""

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


class ForecastApiClient:
    """HTTP client for forecast-php API.

    Handles balance and transaction posting with HTTP Basic Auth.
    """

    def __init__(self, settings: ApiSettings) -> None:
        """Initialize the API client.

        Args:
            settings: API configuration settings.
        """
        self.settings = settings
        self.base_url = settings.api_url.rstrip("/")
        self._auth = httpx.BasicAuth(settings.api_user, settings.api_password)

        # Define endpoints in one place
        self._balance_url = f"{self.base_url}/index.php/records/bankbalance"
        self._transaction_url = f"{self.base_url}/transaction.php"

    def ping(self) -> ApiResponse:
        """Check if the API is reachable and credentials are valid.

        Returns:
            ApiResponse indicating success or failure.
        """
        try:
            with httpx.Client(auth=self._auth, timeout=10.0) as client:
                # Use GET to check if API is reachable (might return 404 or empty, that's ok)
                response = client.get(self._balance_url)

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
            with httpx.Client(auth=self._auth, timeout=30.0) as client:
                response = client.post(self._balance_url, json=payload)

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
    ) -> ApiResponse:
        """Post a transaction to the API.

        Args:
            name: Transaction name/description.
            value: Transaction amount (positive or negative).
            date_actual: The actual date of the transaction.

        Returns:
            ApiResponse indicating success or failure.
        """
        payload = {
            "name": name,
            "value": str(value),
            "dateactual": date_actual.isoformat(),
            "status": "paid",
        }

        try:
            with httpx.Client(auth=self._auth, timeout=30.0) as client:
                response = client.post(self._transaction_url, json=payload)

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
