from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.cli import _autotrade_log_signature
from app.db import Base
from app.integrations.toss_openapi import (
    LiveOrderDisabledError,
    TossCredentials,
    TossOpenApiClient,
)
from app.models import AutoTradeOrder
from app.services.auto_trading import (
    AutoTradePolicy,
    execute_cycle,
    extract_actionable_events,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _payload(now: datetime, scope: str) -> dict:
    if scope == "KR":
        return {
            "status": "ready",
            "data_state": "ready",
            "strategy_version": "position-lifecycle-v8.1",
            "as_of": now.isoformat(),
            "new_entries_allowed": True,
            "items": [
                {
                    "code": "005930",
                    "event_side": "buy",
                    "status": "confirmed",
                    "execution_date": "2026-10-22",
                    "price": "100000",
                    "intraday_execution_verified": True,
                    "state_after": "entered",
                }
            ],
        }
    return {
        "status": "ready",
        "data_state": "ready",
        "strategy_version": "position-lifecycle-us-v3-hybrid1",
        "as_of": now.isoformat(),
        "new_entries_allowed": True,
        "items": [
            {
                "code": "AAPL",
                "events": [
                    {
                        "event_id": "us-hybrid-v1:AAPL:buy:1:2026-10-22",
                        "code": "AAPL",
                        "side": "buy",
                        "execution_date": "2026-10-22",
                        "price": "200",
                        "intraday_execution_verified": True,
                    }
                ],
            }
        ],
    }


class FakeTossClient:
    def __init__(self) -> None:
        self.created: list[dict] = []
        self.details: dict[str, dict] = {}
        self.holding_items: list[dict] = []
        self.krw_power = "1000000"
        self.usd_power = "1000"

    def exchange_rate(self):
        return {"rate": "1400"}

    def holdings(self):
        return {"items": self.holding_items}

    def orders(self, _status):
        return []

    def buying_power(self, currency):
        return {
            "cashBuyingPower": self.krw_power if currency == "KRW" else self.usd_power
        }

    def create_order(self, payload):
        self.created.append(payload)
        return {"orderId": f"order-{len(self.created)}", "clientOrderId": payload["clientOrderId"]}

    def order(self, order_id):
        if order_id in self.details:
            return self.details[order_id]
        payload = next(item for item in self.created if f"order-{self.created.index(item) + 1}" == order_id)
        return {
            "orderId": order_id,
            "symbol": payload["symbol"],
            "side": payload["side"],
            "status": "PENDING",
            "execution": {"filledQuantity": "0"},
        }


def test_policy_enforces_approved_thirty_seventy_split() -> None:
    policy = AutoTradePolicy()
    assert policy.kr_budget_krw == Decimal("300000")
    assert policy.us_budget_krw == Decimal("700000")
    with pytest.raises(ValueError, match="30% / US 70%"):
        AutoTradePolicy(kr_budget_krw=Decimal("500000"), us_budget_krw=Decimal("500000"))


def test_signal_extraction_requires_fresh_verified_current_market_day() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    events = extract_actionable_events(
        _payload(now, "US"), market_scope="US", now=now, max_age_seconds=180
    )
    assert [event.symbol for event in events] == ["AAPL"]
    stale = _payload(now - timedelta(minutes=4), "US")
    assert extract_actionable_events(
        stale, market_scope="US", now=now, max_age_seconds=180
    ) == []
    unverified = _payload(now, "KR")
    unverified["items"][0]["intraday_execution_verified"] = False
    assert extract_actionable_events(
        unverified, market_scope="KR", now=now, max_age_seconds=180
    ) == []
    assert extract_actionable_events(
        _payload(now, "KR"),
        market_scope="KR",
        now=now.replace(tzinfo=None),
        max_age_seconds=180,
    )


def test_domestic_feed_uses_entry_safety_guard_when_new_entry_flag_is_absent() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    payload = _payload(now, "KR")
    payload.pop("new_entries_allowed")
    payload["entry_safety_guard"] = {"active": False, "state": "collecting"}

    assert len(
        extract_actionable_events(
            payload, market_scope="KR", now=now, max_age_seconds=180
        )
    ) == 1

    payload["entry_safety_guard"] = {"active": True, "state": "blocked"}
    assert (
        extract_actionable_events(
            payload, market_scope="KR", now=now, max_age_seconds=180
        )
        == []
    )


def test_us_feed_still_requires_explicit_new_entry_permission() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    payload = _payload(now, "US")
    payload.pop("new_entries_allowed")

    assert (
        extract_actionable_events(
            payload, market_scope="US", now=now, max_age_seconds=180
        )
        == []
    )


def test_daemon_log_signature_ignores_small_fx_noise_but_records_state_changes() -> None:
    base = {
        "capital_ready": False,
        "capital_state": {
            "KR": {"funded": False, "total_capital_krw": "98122"},
            "US": {"funded": False, "total_capital_krw": "159.2"},
        },
        "submitted": [],
        "skipped": ["event:capital-not-funded"],
        "reconciliation": [],
    }
    fx_noise = {
        **base,
        "capital_state": {
            **base["capital_state"],
            "US": {"funded": False, "total_capital_krw": "159.9"},
        },
    }
    funded = {
        **base,
        "capital_ready": True,
        "capital_state": {
            "KR": {"funded": True, "total_capital_krw": "300000"},
            "US": {"funded": True, "total_capital_krw": "700000"},
        },
    }

    assert _autotrade_log_signature(base) == _autotrade_log_signature(fx_noise)
    assert _autotrade_log_signature(base) != _autotrade_log_signature(funded)


def test_live_cycle_caps_kr_and_us_orders_and_never_duplicates() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    client = FakeTossClient()
    with _session() as db:
        first = execute_cycle(
            db,
            client,
            kr_payload=_payload(now, "KR"),
            us_payload=_payload(now, "US"),
            policy=AutoTradePolicy(),
            now=now,
        )
        assert len(first["submitted"]) == 2
        assert client.created[0]["symbol"] == "005930"
        assert client.created[0]["quantity"] == "1"
        assert client.created[1]["symbol"] == "AAPL"
        assert client.created[1]["orderAmount"] == "247.50"
        assert sum(
            Decimal(str(row.requested_notional_krw))
            for row in db.scalars(select(AutoTradeOrder).where(AutoTradeOrder.market_scope == "KR"))
        ) <= Decimal("300000")
        assert sum(
            Decimal(str(row.requested_notional_krw))
            for row in db.scalars(select(AutoTradeOrder).where(AutoTradeOrder.market_scope == "US"))
        ) <= Decimal("700000")
        second = execute_cycle(
            db,
            client,
            kr_payload=_payload(now, "KR"),
            us_payload=_payload(now, "US"),
            policy=AutoTradePolicy(),
            now=now,
        )
        assert second["submitted"] == []
        assert len(client.created) == 2
        assert all(reason.endswith(":duplicate") for reason in second["skipped"])


def test_partial_fill_sync_drives_original_quantity_partial_sell() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    kr = _payload(now, "KR")
    kr["items"][0]["price"] = "50000"
    empty = {
        "status": "ready",
        "data_state": "ready",
        "strategy_version": "position-lifecycle-us-v3-hybrid1",
        "as_of": now.isoformat(),
        "new_entries_allowed": True,
        "items": [],
    }
    client = FakeTossClient()
    with _session() as db:
        execute_cycle(
            db, client, kr_payload=kr, us_payload=empty, policy=AutoTradePolicy(), now=now
        )
        client.details["order-1"] = {
            "orderId": "order-1",
            "symbol": "005930",
            "side": "BUY",
            "status": "FILLED",
            "execution": {
                "filledQuantity": "2",
                "averageFilledPrice": "50000",
                "filledAmount": "100000",
                "commission": "15",
                "tax": "0",
            },
        }
        execute_cycle(
            db, client, kr_payload=kr, us_payload=empty, policy=AutoTradePolicy(), now=now
        )
        partial = _payload(now, "KR")
        partial["items"][0].update(
            {
                "event_side": "partial_sell",
                "side": "sell",
                "price": "51500",
                "state_after": "partially_exited",
            }
        )
        execute_cycle(
            db,
            client,
            kr_payload=partial,
            us_payload=empty,
            policy=AutoTradePolicy(),
            now=now,
        )
        assert client.created[-1] == {
            "clientOrderId": client.created[-1]["clientOrderId"],
            "symbol": "005930",
            "side": "SELL",
            "orderType": "MARKET",
            "quantity": "1",
        }


def test_unknown_old_submission_is_blocked_without_resend() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    empty_kr = _payload(now, "KR")
    empty_kr["items"] = []
    empty_us = _payload(now, "US")
    empty_us["items"] = []
    client = FakeTossClient()
    with _session() as db:
        row = AutoTradeOrder(
            signal_event_id="old-event",
            client_order_id="sn-old",
            strategy_version="v1",
            market_scope="KR",
            symbol="005930",
            side="BUY",
            status="SUBMITTING",
            request_payload=json.dumps(
                {
                    "clientOrderId": "sn-old",
                    "symbol": "005930",
                    "side": "BUY",
                    "orderType": "MARKET",
                    "quantity": "1",
                }
            ),
            requested_notional_krw=Decimal("50000"),
            created_at=now.replace(tzinfo=None) - timedelta(minutes=9),
        )
        db.add(row)
        db.commit()
        result = execute_cycle(
            db,
            client,
            kr_payload=empty_kr,
            us_payload=empty_us,
            policy=AutoTradePolicy(),
            now=now,
        )
        assert row.status == "AMBIGUOUS_BLOCKED"
        assert client.created == []
        assert "blocked:sn-old:ambiguous" in result["reconciliation"]


def test_existing_account_holdings_consume_the_market_budget() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    client = FakeTossClient()
    client.holding_items = [
        {
            "marketCountry": "KR",
            "marketValue": {"purchaseAmount": "290000", "amount": "290000"},
        }
    ]
    kr = _payload(now, "KR")
    kr["items"][0]["price"] = "50000"
    empty_us = _payload(now, "US")
    empty_us["items"] = []
    with _session() as db:
        result = execute_cycle(
            db,
            client,
            kr_payload=kr,
            us_payload=empty_us,
            policy=AutoTradePolicy(),
            now=now,
        )
        assert client.created == []
        assert any(reason.endswith(":insufficient-kr-budget") for reason in result["skipped"])


def test_market_daily_loss_limit_blocks_only_new_buys() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    client = FakeTossClient()
    empty_us = _payload(now, "US")
    empty_us["items"] = []
    with _session() as db:
        db.add(
            AutoTradeOrder(
                signal_event_id="prior-loss",
                client_order_id="sn-prior-loss",
                strategy_version="v1",
                market_scope="KR",
                symbol="000660",
                side="SELL",
                status="FILLED",
                request_payload="{}",
                requested_notional_krw=Decimal("100000"),
                realized_pnl_krw=Decimal("-3000"),
                updated_at=now.replace(tzinfo=None),
            )
        )
        db.commit()
        result = execute_cycle(
            db,
            client,
            kr_payload=_payload(now, "KR"),
            us_payload=empty_us,
            policy=AutoTradePolicy(),
            now=now,
        )
        assert client.created == []
        assert any(reason.endswith(":daily-loss-limit") for reason in result["skipped"])


def test_new_buys_wait_until_both_thirty_seventy_sleeves_are_funded() -> None:
    now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    client = FakeTossClient()
    client.krw_power = "98122"
    client.usd_power = "0.12"
    empty_us = _payload(now, "US")
    empty_us["items"] = []
    with _session() as db:
        result = execute_cycle(
            db,
            client,
            kr_payload=_payload(now, "KR"),
            us_payload=empty_us,
            policy=AutoTradePolicy(),
            now=now,
        )
        assert result["capital_ready"] is False
        assert result["capital_state"]["KR"]["funded"] is False
        assert result["capital_state"]["US"]["funded"] is False
        assert client.created == []
        assert any(reason.endswith(":capital-not-funded") for reason in result["skipped"])


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self):
        self.last_headers = None

    def post(self, *_args, **_kwargs):
        return FakeResponse({"access_token": "token", "token_type": "Bearer", "expires_in": 3600})

    def request(self, _method, _url, **kwargs):
        self.last_headers = kwargs["headers"]
        return FakeResponse({"result": {"cashBuyingPower": "300000"}})


def test_toss_client_requires_live_switch_and_sets_account_header() -> None:
    session = FakeSession()
    client = TossOpenApiClient(
        TossCredentials("client", "secret", 7), session=session, live_orders_enabled=False
    )
    assert client.buying_power("KRW")["cashBuyingPower"] == "300000"
    assert session.last_headers == {
        "Authorization": "Bearer token",
        "X-Tossinvest-Account": "7",
    }
    with pytest.raises(LiveOrderDisabledError):
        client.create_order(json.loads('{"symbol":"005930"}'))
