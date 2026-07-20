from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import BrokerAccount, BrokerHolding, BrokerOrder
from app.repository import finish_ingestion, start_ingestion, upsert_many

BROKER_NAME = "toss_securities"


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _to_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def _to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


class TossInvestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        self.data = data or {}

    def to_detail(self) -> dict[str, Any]:
        return {
            "message": str(self),
            "code": self.code,
            "request_id": self.request_id,
            "data": self.data,
        }


class TossInvestClient:
    def __init__(
        self,
        settings: Optional[Settings] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session or requests.Session()
        self.base_url = self.settings.toss_base_url.rstrip("/")
        self._access_token: Optional[str] = None
        self._access_token_expires_at: Optional[datetime] = None

    def _ensure_credentials(self) -> None:
        if not self.settings.toss_client_id or not self.settings.toss_client_secret:
            raise TossInvestError(
                "Toss credentials are missing. Set TOSS_CLIENT_ID and TOSS_CLIENT_SECRET.",
                status_code=503,
                code="toss-credentials-missing",
            )

    def issue_access_token(self, force_refresh: bool = False) -> str:
        self._ensure_credentials()
        if (
            not force_refresh
            and self._access_token
            and self._access_token_expires_at
            and self._access_token_expires_at > datetime.utcnow() + timedelta(minutes=5)
        ):
            return self._access_token

        response = self.session.post(
            f"{self.base_url}/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.toss_client_id,
                "client_secret": self.settings.toss_client_secret,
            },
            headers={"User-Agent": "kr-stock-analyst-backend/0.1"},
            timeout=30,
        )
        payload = self._decode_response(response, expect_result=False)
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 0))
        self._access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        return self._access_token

    def _decode_response(self, response: requests.Response, *, expect_result: bool = True) -> Any:
        try:
            payload = response.json()
        except ValueError as exc:
            raise TossInvestError(
                f"Toss API returned a non-JSON response ({response.status_code}).",
                status_code=response.status_code,
                code="invalid-response",
            ) from exc

        if response.status_code >= 400:
            error = payload.get("error") or {}
            raise TossInvestError(
                error.get("message") or f"Toss API request failed with status {response.status_code}.",
                status_code=response.status_code,
                code=error.get("code"),
                request_id=error.get("requestId") or response.headers.get("X-Request-Id"),
                data=error.get("data"),
            )

        if expect_result:
            return payload.get("result")
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        account_seq: Optional[int] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> Any:
        headers = {
            "Authorization": f"Bearer {self.issue_access_token()}",
            "User-Agent": "kr-stock-analyst-backend/0.1",
        }
        if account_seq is not None:
            headers["X-Tossinvest-Account"] = str(account_seq)

        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=30,
        )
        return self._decode_response(response)

    def get_accounts(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/v1/accounts"))

    def get_holdings(self, account_seq: int, symbol: Optional[str] = None) -> dict[str, Any]:
        params = {"symbol": symbol} if symbol else None
        return self._request("GET", "/api/v1/holdings", account_seq=account_seq, params=params)

    def get_orders(
        self,
        account_seq: int,
        *,
        status: str = "OPEN",
        symbol: Optional[str] = None,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
        cursor: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"status": status}
        if symbol:
            params["symbol"] = symbol
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if cursor:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        return self._request("GET", "/api/v1/orders", account_seq=account_seq, params=params)

    def get_order(self, account_seq: int, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/orders/{order_id}", account_seq=account_seq)

    def create_order(self, account_seq: int, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/orders", account_seq=account_seq, json_body=payload)

    def modify_order(self, account_seq: int, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/orders/{order_id}/modify",
            account_seq=account_seq,
            json_body=payload,
        )

    def cancel_order(self, account_seq: int, order_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/orders/{order_id}/cancel", account_seq=account_seq, json_body={})

    def get_buying_power(self, account_seq: int, currency: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/buying-power",
            account_seq=account_seq,
            params={"currency": currency},
        )

    def get_sellable_quantity(self, account_seq: int, symbol: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/v1/sellable-quantity",
            account_seq=account_seq,
            params={"symbol": symbol},
        )

    def get_stocks(self, symbols: list[str]) -> list[dict[str, Any]]:
        filtered = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
        if not filtered:
            return []
        return list(self._request("GET", "/api/v1/stocks", params={"symbols": ",".join(filtered)}))


def get_toss_client(
    settings: Optional[Settings] = None,
    session: Optional[requests.Session] = None,
) -> TossInvestClient:
    return TossInvestClient(settings=settings, session=session)


def resolve_toss_account_seq(
    client: TossInvestClient,
    settings: Optional[Settings] = None,
    *,
    explicit_account_seq: Optional[int] = None,
) -> int:
    if explicit_account_seq is not None:
        return explicit_account_seq

    active_settings = settings or client.settings
    if active_settings.toss_account_seq is not None:
        return active_settings.toss_account_seq

    accounts = client.get_accounts()
    if active_settings.toss_account_no:
        for account in accounts:
            if account.get("accountNo") == active_settings.toss_account_no:
                return int(account["accountSeq"])
        raise TossInvestError(
            f"Toss accountNo {active_settings.toss_account_no} was not found in /api/v1/accounts.",
            status_code=404,
            code="toss-account-not-found",
        )

    if len(accounts) == 1:
        return int(accounts[0]["accountSeq"])

    raise TossInvestError(
        "Unable to resolve a Toss account. Set TOSS_ACCOUNT_SEQ or TOSS_ACCOUNT_NO, or pass account_seq explicitly.",
        status_code=400,
        code="toss-account-resolution-failed",
    )


def _broker_account_row(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "broker_name": BROKER_NAME,
        "account_seq": int(account["accountSeq"]),
        "account_no": account.get("accountNo"),
        "account_type": account.get("accountType"),
        "raw": str(account),
        "synced_at": datetime.utcnow(),
    }


def _holding_rows(account_seq: int, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in items:
        market_value = item.get("marketValue") or {}
        profit_loss = item.get("profitLoss") or {}
        daily_profit_loss = item.get("dailyProfitLoss") or {}
        cost = item.get("cost") or {}
        rows.append(
            {
                "broker_name": BROKER_NAME,
                "account_seq": account_seq,
                "symbol": item["symbol"],
                "name": item["name"],
                "market_country": item.get("marketCountry"),
                "currency": item.get("currency"),
                "quantity": _to_decimal(item.get("quantity")),
                "last_price": _to_decimal(item.get("lastPrice")),
                "average_purchase_price": _to_decimal(item.get("averagePurchasePrice")),
                "purchase_amount": _to_decimal(market_value.get("purchaseAmount")),
                "market_value": _to_decimal(market_value.get("amount")),
                "market_value_after_cost": _to_decimal(market_value.get("amountAfterCost")),
                "profit_loss": _to_decimal(profit_loss.get("amount")),
                "profit_loss_after_cost": _to_decimal(profit_loss.get("amountAfterCost")),
                "profit_loss_rate": _to_decimal(profit_loss.get("rate")),
                "profit_loss_rate_after_cost": _to_decimal(profit_loss.get("rateAfterCost")),
                "daily_profit_loss": _to_decimal(daily_profit_loss.get("amount")),
                "daily_profit_loss_rate": _to_decimal(daily_profit_loss.get("rate")),
                "commission": _to_decimal(cost.get("commission")),
                "tax": _to_decimal(cost.get("tax")),
                "raw": str(item),
                "synced_at": datetime.utcnow(),
            }
        )
    return rows


def _apply_holdings_summary(account: BrokerAccount, overview: dict[str, Any]) -> None:
    total_purchase_amount = overview.get("totalPurchaseAmount") or {}
    market_value = overview.get("marketValue") or {}
    profit_loss = overview.get("profitLoss") or {}
    daily_profit_loss = overview.get("dailyProfitLoss") or {}

    market_value_amount = market_value.get("amount") or {}
    market_value_after_cost = market_value.get("amountAfterCost") or {}
    profit_loss_amount = profit_loss.get("amount") or {}
    profit_loss_amount_after_cost = profit_loss.get("amountAfterCost") or {}
    daily_profit_loss_amount = daily_profit_loss.get("amount") or {}

    account.total_purchase_amount_krw = _to_decimal(total_purchase_amount.get("krw"))
    account.total_purchase_amount_usd = _to_decimal(total_purchase_amount.get("usd"))
    account.market_value_krw = _to_decimal(market_value_amount.get("krw"))
    account.market_value_usd = _to_decimal(market_value_amount.get("usd"))
    account.market_value_after_cost_krw = _to_decimal(market_value_after_cost.get("krw"))
    account.market_value_after_cost_usd = _to_decimal(market_value_after_cost.get("usd"))
    account.profit_loss_krw = _to_decimal(profit_loss_amount.get("krw"))
    account.profit_loss_usd = _to_decimal(profit_loss_amount.get("usd"))
    account.profit_loss_after_cost_krw = _to_decimal(profit_loss_amount_after_cost.get("krw"))
    account.profit_loss_after_cost_usd = _to_decimal(profit_loss_amount_after_cost.get("usd"))
    account.profit_loss_rate = _to_decimal(profit_loss.get("rate"))
    account.profit_loss_rate_after_cost = _to_decimal(profit_loss.get("rateAfterCost"))
    account.daily_profit_loss_krw = _to_decimal(daily_profit_loss_amount.get("krw"))
    account.daily_profit_loss_usd = _to_decimal(daily_profit_loss_amount.get("usd"))
    account.daily_profit_loss_rate = _to_decimal(daily_profit_loss.get("rate"))
    account.synced_at = datetime.utcnow()


def _order_row(account_seq: int, item: dict[str, Any]) -> dict[str, Any]:
    execution = item.get("execution") or {}
    return {
        "broker_name": BROKER_NAME,
        "account_seq": account_seq,
        "order_id": item["orderId"],
        "symbol": item["symbol"],
        "side": item.get("side"),
        "order_type": item.get("orderType"),
        "time_in_force": item.get("timeInForce"),
        "status": item.get("status"),
        "price": _to_decimal(item.get("price")),
        "quantity": _to_decimal(item.get("quantity")),
        "order_amount": _to_decimal(item.get("orderAmount")),
        "currency": item.get("currency"),
        "ordered_at": _to_datetime(item.get("orderedAt")),
        "canceled_at": _to_datetime(item.get("canceledAt")),
        "filled_quantity": _to_decimal(execution.get("filledQuantity")),
        "average_filled_price": _to_decimal(execution.get("averageFilledPrice")),
        "filled_amount": _to_decimal(execution.get("filledAmount")),
        "commission": _to_decimal(execution.get("commission")),
        "tax": _to_decimal(execution.get("tax")),
        "filled_at": _to_datetime(execution.get("filledAt")),
        "settlement_date": _to_date(execution.get("settlementDate")),
        "raw": str(item),
        "synced_at": datetime.utcnow(),
    }


def _sync_target_accounts(
    db: Session,
    client: TossInvestClient,
    *,
    account_seq: Optional[int] = None,
    settings: Optional[Settings] = None,
) -> list[dict[str, Any]]:
    accounts = client.get_accounts()
    upsert_many(db, BrokerAccount, [_broker_account_row(account) for account in accounts])
    db.commit()
    if account_seq is not None:
        return [account for account in accounts if int(account["accountSeq"]) == account_seq]
    active_settings = settings or client.settings
    if active_settings.toss_account_seq is not None:
        return [account for account in accounts if int(account["accountSeq"]) == active_settings.toss_account_seq]
    if active_settings.toss_account_no:
        return [account for account in accounts if account.get("accountNo") == active_settings.toss_account_no]
    return accounts


def sync_toss_accounts(
    db: Session,
    *,
    settings: Optional[Settings] = None,
    client: Optional[TossInvestClient] = None,
) -> int:
    active_settings = settings or get_settings()
    active_client = client or get_toss_client(settings=active_settings)
    run = start_ingestion(db, "toss", "accounts")
    try:
        accounts = active_client.get_accounts()
        count = upsert_many(db, BrokerAccount, [_broker_account_row(account) for account in accounts])
        db.commit()
        finish_ingestion(db, run, "success", rows_loaded=count, message=f"accounts={count}")
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded=0, message=str(exc))
        raise


def sync_toss_holdings(
    db: Session,
    *,
    account_seq: Optional[int] = None,
    symbol: Optional[str] = None,
    settings: Optional[Settings] = None,
    client: Optional[TossInvestClient] = None,
) -> int:
    active_settings = settings or get_settings()
    active_client = client or get_toss_client(settings=active_settings)
    run = start_ingestion(db, "toss", "holdings")
    try:
        targets = _sync_target_accounts(db, active_client, account_seq=account_seq, settings=active_settings)
        if not targets:
            raise TossInvestError(
                "No Toss accounts matched the requested account filter.",
                status_code=404,
                code="toss-account-not-found",
            )
        total_rows = 0
        for target in targets:
            current_account_seq = int(target["accountSeq"])
            overview = active_client.get_holdings(current_account_seq, symbol=symbol)
            db_account = db.scalar(
                select(BrokerAccount).where(
                    BrokerAccount.broker_name == BROKER_NAME,
                    BrokerAccount.account_seq == current_account_seq,
                )
            )
            if db_account is None:
                db_account = BrokerAccount(**_broker_account_row(target))
            _apply_holdings_summary(db_account, overview)
            db.add(db_account)

            if symbol:
                db.execute(
                    delete(BrokerHolding).where(
                        BrokerHolding.broker_name == BROKER_NAME,
                        BrokerHolding.account_seq == current_account_seq,
                        BrokerHolding.symbol == symbol,
                    )
                )
            else:
                db.execute(
                    delete(BrokerHolding).where(
                        BrokerHolding.broker_name == BROKER_NAME,
                        BrokerHolding.account_seq == current_account_seq,
                    )
                )
            rows = _holding_rows(current_account_seq, overview.get("items") or [])
            total_rows += upsert_many(db, BrokerHolding, rows)
        db.commit()
        finish_ingestion(db, run, "success", rows_loaded=total_rows, message=f"accounts={len(targets)}")
        return total_rows
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded=0, message=str(exc))
        raise


def sync_toss_orders(
    db: Session,
    *,
    account_seq: Optional[int] = None,
    status: str = "OPEN",
    settings: Optional[Settings] = None,
    client: Optional[TossInvestClient] = None,
) -> int:
    active_settings = settings or get_settings()
    active_client = client or get_toss_client(settings=active_settings)
    run = start_ingestion(db, "toss", "orders")
    try:
        targets = _sync_target_accounts(db, active_client, account_seq=account_seq, settings=active_settings)
        if not targets:
            raise TossInvestError(
                "No Toss accounts matched the requested account filter.",
                status_code=404,
                code="toss-account-not-found",
            )
        total_rows = 0
        for target in targets:
            current_account_seq = int(target["accountSeq"])
            cursor: Optional[str] = None
            while True:
                page = active_client.get_orders(
                    current_account_seq,
                    status=status,
                    cursor=cursor,
                    limit=100,
                )
                orders = page.get("orders") or []
                total_rows += upsert_many(
                    db,
                    BrokerOrder,
                    [_order_row(current_account_seq, item) for item in orders],
                )
                if not page.get("hasNext"):
                    break
                cursor = page.get("nextCursor")
                if not cursor:
                    break
        db.commit()
        finish_ingestion(db, run, "success", rows_loaded=total_rows, message=f"accounts={len(targets)}")
        return total_rows
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded=0, message=str(exc))
        raise


def refresh_toss_order_detail(
    db: Session,
    order_id: str,
    *,
    account_seq: Optional[int] = None,
    settings: Optional[Settings] = None,
    client: Optional[TossInvestClient] = None,
) -> BrokerOrder:
    active_settings = settings or get_settings()
    active_client = client or get_toss_client(settings=active_settings)
    resolved_account_seq = account_seq
    if resolved_account_seq is None:
        cached = db.scalar(
            select(BrokerOrder).where(
                BrokerOrder.broker_name == BROKER_NAME,
                BrokerOrder.order_id == order_id,
            )
        )
        if cached is not None:
            resolved_account_seq = cached.account_seq
    resolved_account_seq = resolve_toss_account_seq(
        active_client,
        active_settings,
        explicit_account_seq=resolved_account_seq,
    )
    order = active_client.get_order(resolved_account_seq, order_id)
    upsert_many(db, BrokerOrder, [_order_row(resolved_account_seq, order)])
    db.commit()
    stored = db.scalar(
        select(BrokerOrder).where(
            BrokerOrder.broker_name == BROKER_NAME,
            BrokerOrder.order_id == order_id,
        )
    )
    if stored is None:
        raise TossInvestError("Order was refreshed but not persisted.", status_code=500, code="order-persist-failed")
    return stored
