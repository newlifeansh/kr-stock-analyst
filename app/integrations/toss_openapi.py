from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests


class TossOpenApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class LiveOrderDisabledError(TossOpenApiError):
    pass


@dataclass(frozen=True)
class TossCredentials:
    client_id: str
    client_secret: str
    account_seq: int | None = None


class TossOpenApiClient:
    """Small official Toss Open API client with live-order fail-closed behavior."""

    def __init__(
        self,
        credentials: TossCredentials,
        *,
        base_url: str = "https://openapi.tossinvest.com",
        live_orders_enabled: bool = False,
        timeout: float = 12.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        if not credentials.client_id or not credentials.client_secret:
            raise ValueError("Toss Open API client ID and secret are required")
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.live_orders_enabled = live_orders_enabled
        self.timeout = timeout
        self.session = session or requests.Session()
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = threading.Lock()

    def _token(self, *, force: bool = False) -> str:
        with self._token_lock:
            now = time.monotonic()
            if not force and self._access_token and now < self._token_expires_at - 60:
                return self._access_token
            response = self.session.post(
                f"{self.base_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.credentials.client_id,
                    "client_secret": self.credentials.client_secret,
                },
                timeout=self.timeout,
            )
            payload = self._decode(response)
            token = str(payload.get("access_token") or "")
            if not token:
                raise TossOpenApiError("Toss token response did not include access_token")
            self._access_token = token
            self._token_expires_at = now + max(0, int(payload.get("expires_in") or 0))
            return token

    @staticmethod
    def _decode(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TossOpenApiError(
                "Toss Open API returned a non-JSON response",
                status_code=response.status_code,
            ) from exc
        if not response.ok:
            error = payload.get("error") if isinstance(payload, dict) else None
            code = str(error.get("code")) if isinstance(error, dict) and error.get("code") else None
            message = (
                str(error.get("message"))
                if isinstance(error, dict) and error.get("message")
                else f"Toss Open API request failed with HTTP {response.status_code}"
            )
            raise TossOpenApiError(message, status_code=response.status_code, code=code)
        if not isinstance(payload, dict):
            raise TossOpenApiError("Toss Open API returned an invalid JSON object")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        account_required: bool = False,
        retry_auth: bool = True,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self._token()}"
        if account_required:
            if self.credentials.account_seq is None:
                raise TossOpenApiError("TOSS_OPENAPI_ACCOUNT_SEQ is required for this request")
            headers["X-Tossinvest-Account"] = str(self.credentials.account_seq)
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        if response.status_code == 401 and retry_auth:
            self._token(force=True)
            return self._request(
                method,
                path,
                account_required=account_required,
                retry_auth=False,
                **kwargs,
            )
        return self._decode(response)

    def accounts(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/v1/accounts").get("result") or [])

    def holdings(self) -> dict[str, Any]:
        return dict(
            self._request("GET", "/api/v1/holdings", account_required=True).get("result")
            or {}
        )

    def buying_power(self, currency: str) -> dict[str, Any]:
        return dict(
            self._request(
                "GET",
                "/api/v1/buying-power",
                account_required=True,
                params={"currency": currency.upper()},
            ).get("result")
            or {}
        )

    def exchange_rate(self) -> dict[str, Any]:
        return dict(
            self._request(
                "GET",
                "/api/v1/exchange-rate",
                params={"baseCurrency": "USD", "quoteCurrency": "KRW"},
            ).get("result")
            or {}
        )

    def orders(self, status: str) -> list[dict[str, Any]]:
        result = self._request(
            "GET",
            "/api/v1/orders",
            account_required=True,
            params={"status": status.upper(), "limit": 100},
        ).get("result") or {}
        return list(result.get("orders") or [])

    def order(self, order_id: str) -> dict[str, Any]:
        return dict(
            self._request(
                "GET", f"/api/v1/orders/{order_id}", account_required=True
            ).get("result")
            or {}
        )

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.live_orders_enabled:
            raise LiveOrderDisabledError(
                "Live order submission is disabled; set TOSS_AUTOTRADE_LIVE_ENABLED=true"
            )
        return dict(
            self._request(
                "POST",
                "/api/v1/orders",
                account_required=True,
                json=payload,
            ).get("result")
            or {}
        )
