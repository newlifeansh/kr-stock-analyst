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
from app.models import AutoTradeOrder, AutoTradePosition
from app.services.auto_trading import (
    AutoTradePolicy,
    account_capital_state,
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
                    "signal_date": "2026-10-22",
                    "signal_at": "2026-10-22T11:00:00+09:00",
                    "confirmed_at": "2026-10-22T10:00:00+09:00",
                    "decision_minute_at": "2026-10-22T09:59:00+09:00",
                    "price": "100000",
                    "intraday_execution_verified": True,
                    "intraday_order_verified": True,
                    "state_after": "entered",
                    "entry_confirmation": {"allowed": True},
                    "public_reasons": [
                        {"key": "trend_20d", "state": "positive", "available": True},
                        {"key": "trend_60d", "state": "positive", "available": True},
                        {"key": "flow", "state": "positive", "available": True},
                    ],
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
    assert policy.kr_budget_krw == Decimal("174000")
    assert policy.us_budget_krw == Decimal("406000")
    assert policy.daily_loss_limit_krw == Decimal("5800")
    assert AutoTradePolicy(
        kr_budget_krw=Decimal("300000"),
        us_budget_krw=Decimal("700000"),
    ).budget("US") == Decimal("700000")
    with pytest.raises(ValueError, match="30% / US 70%"):
        AutoTradePolicy(kr_budget_krw=Decimal("500000"), us_budget_krw=Decimal("500000"))


def test_funding_check_allows_small_fx_buffer_without_raising_order_limits() -> None:
    policy = AutoTradePolicy()
    state = account_capital_state(
        holdings={"items": []},
        open_orders=[],
        krw_buying_power=Decimal("198125"),
        usd_buying_power=Decimal("301.57"),
        fx=Decimal("1326.3"),
        policy=policy,
    )

    assert state["KR"]["funded"] is True
    assert state["US"]["funded"] is True
    assert state["US"]["budget_krw"] == Decimal("406000")


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
    kr_now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    unverified = _payload(kr_now, "KR")
    unverified["items"][0]["intraday_execution_verified"] = False
    assert extract_actionable_events(
        unverified, market_scope="KR", now=kr_now, max_age_seconds=180
    ) == []
    assert len(extract_actionable_events(
        _payload(kr_now, "KR"),
        market_scope="KR",
        now=kr_now.replace(tzinfo=None),
        max_age_seconds=180,
    )) == 1


def test_domestic_buy_requires_same_session_quant_prechecks() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    mutations = [
        ("signal_date", "2026-10-21"),
        ("signal_at", "2026-10-22T15:40:00+09:00"),
        ("entry_confirmation", {"allowed": False}),
        ("public_reasons", []),
        (
            "public_reasons",
            [
                {"key": "trend_20d", "state": "positive", "available": True},
                {"key": "trend_60d", "state": "positive", "available": True},
                {"key": "flow", "state": "unavailable", "available": False},
            ],
        ),
    ]
    for mutation, value in mutations:
        payload = _payload(now, "KR")
        payload["items"][0][mutation] = value
        assert extract_actionable_events(
            payload, market_scope="KR", now=now, max_age_seconds=180
        ) == [], mutation


def test_domestic_sell_remains_allowed_when_buy_prechecks_are_unavailable() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    payload = _payload(now, "KR")
    payload["items"][0].update(
        event_side="sell",
        side="sell",
        public_reasons=[],
        entry_confirmation=None,
    )

    events = extract_actionable_events(
        payload, market_scope="KR", now=now, max_age_seconds=180
    )

    assert [event.side for event in events] == ["SELL"]


@pytest.mark.parametrize(
    "changes",
    [
        {"intraday_order_verified": False},
        {"confirmed_at": None, "decision_minute_at": None},
        {"confirmed_at": "2026-10-22T09:56:59+09:00"},
        {"confirmed_at": "2026-10-22T10:00:01+09:00"},
    ],
)
def test_domestic_broker_path_calls_live_order_guard(changes) -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    payload = _payload(now, "KR")
    payload["items"][0].update(changes)

    assert extract_actionable_events(
        payload, market_scope="KR", now=now, max_age_seconds=180
    ) == []


@pytest.mark.parametrize("event_side", ["buy", "partial_sell", "sell"])
def test_domestic_broker_path_rejects_orders_at_close(event_side) -> None:
    now = datetime(2026, 10, 22, 6, 30, tzinfo=timezone.utc)
    payload = _payload(now, "KR")
    payload["items"][0].update(
        event_side=event_side,
        side=event_side,
        confirmed_at="2026-10-22T15:29:00+09:00",
        decision_minute_at="2026-10-22T15:29:00+09:00",
    )

    assert extract_actionable_events(
        payload, market_scope="KR", now=now, max_age_seconds=180
    ) == []


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
    kr_now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    us_now = datetime(2026, 10, 22, 14, 0, tzinfo=timezone.utc)
    client = FakeTossClient()
    with _session() as db:
        kr_first = execute_cycle(
            db,
            client,
            kr_payload=_payload(kr_now, "KR"),
            us_payload={"status": "ready", "data_state": "ready", "as_of": kr_now.isoformat(), "items": []},
            policy=AutoTradePolicy(),
            now=kr_now,
        )
        us_first = execute_cycle(
            db,
            client,
            kr_payload={"status": "ready", "data_state": "ready", "as_of": us_now.isoformat(), "items": []},
            us_payload=_payload(us_now, "US"),
            policy=AutoTradePolicy(),
            now=us_now,
        )
        assert len(kr_first["submitted"]) == 1
        assert len(us_first["submitted"]) == 1
        assert client.created[0]["symbol"] == "005930"
        assert client.created[0]["quantity"] == "1"
        assert client.created[1]["symbol"] == "AAPL"
        assert client.created[1]["orderAmount"] == "143.55"
        assert sum(
            Decimal(str(row.requested_notional_krw))
            for row in db.scalars(select(AutoTradeOrder).where(AutoTradeOrder.market_scope == "KR"))
        ) <= Decimal("174000")
        assert sum(
            Decimal(str(row.requested_notional_krw))
            for row in db.scalars(select(AutoTradeOrder).where(AutoTradeOrder.market_scope == "US"))
        ) <= Decimal("406000")
        kr_second = execute_cycle(
            db,
            client,
            kr_payload=_payload(kr_now, "KR"),
            us_payload={"status": "ready", "data_state": "ready", "as_of": kr_now.isoformat(), "items": []},
            policy=AutoTradePolicy(),
            now=kr_now,
        )
        us_second = execute_cycle(
            db,
            client,
            kr_payload={"status": "ready", "data_state": "ready", "as_of": us_now.isoformat(), "items": []},
            us_payload=_payload(us_now, "US"),
            policy=AutoTradePolicy(),
            now=us_now,
        )
        assert kr_second["submitted"] == []
        assert us_second["submitted"] == []
        assert len(client.created) == 2
        assert all(reason.endswith(":duplicate") for reason in kr_second["skipped"])
        assert all(reason.endswith(":duplicate") for reason in us_second["skipped"])


def test_managed_kr_position_guard_requires_two_broker_checks_before_hard_stop() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    empty = {"status": "ready", "data_state": "ready", "as_of": now.isoformat(), "items": []}
    client = FakeTossClient()
    client.holding_items = [{
        "symbol": "138040", "marketCountry": "KR", "lastPrice": "126100",
        "marketValue": {"purchaseAmount": "131400", "amount": "126100"},
    }]
    with _session() as db:
        db.add(AutoTradePosition(
            market_scope="KR", symbol="138040", currency="KRW",
            initial_quantity=Decimal("1"), remaining_quantity=Decimal("1"),
            average_entry_price=Decimal("131400"),
        ))
        db.commit()
        first = execute_cycle(
            db, client, kr_payload=empty, us_payload=empty,
            policy=AutoTradePolicy(), now=now,
        )
        assert first["submitted"] == []
        assert any(item["trigger"] == "hard_stop" and item["state"] == "candidate"
                   for item in first["position_guards"])
        second = execute_cycle(
            db, client, kr_payload=empty, us_payload=empty,
            policy=AutoTradePolicy(), now=now + timedelta(seconds=30),
        )
        assert len(second["submitted"]) == 1
        assert client.created[-1]["symbol"] == "138040"
        assert client.created[-1]["side"] == "SELL"
        assert client.created[-1]["quantity"] == "1"


def test_one_share_position_skips_three_percent_partial_and_exits_at_five_percent() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    empty = {"status": "ready", "data_state": "ready", "as_of": now.isoformat(), "items": []}
    client = FakeTossClient()
    with _session() as db:
        db.add(AutoTradePosition(
            market_scope="KR", symbol="138040", currency="KRW",
            initial_quantity=Decimal("1"), remaining_quantity=Decimal("1"),
            average_entry_price=Decimal("131400"),
        ))
        db.commit()
        client.holding_items = [{
            "symbol": "138040", "marketCountry": "KR", "lastPrice": "135400",
            "marketValue": {"purchaseAmount": "131400", "amount": "135400"},
        }]
        at_three = execute_cycle(
            db, client, kr_payload=empty, us_payload=empty,
            policy=AutoTradePolicy(), now=now,
        )
        assert at_three["submitted"] == []
        assert all(item.get("trigger") != "partial_profit" for item in at_three["position_guards"])
        client.holding_items[0]["lastPrice"] = "138000"
        first = execute_cycle(
            db, client, kr_payload=empty, us_payload=empty,
            policy=AutoTradePolicy(), now=now + timedelta(seconds=30),
        )
        second = execute_cycle(
            db, client, kr_payload=empty, us_payload=empty,
            policy=AutoTradePolicy(), now=now + timedelta(seconds=60),
        )
        assert first["submitted"] == []
        assert len(second["submitted"]) == 1
        assert client.created[-1]["side"] == "SELL"
        assert client.created[-1]["quantity"] == "1"


def test_quant_sell_and_position_guard_never_submit_two_sells_for_one_symbol() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
    empty = {"status": "ready", "data_state": "ready", "as_of": now.isoformat(), "items": []}
    client = FakeTossClient()
    client.holding_items = [{
        "symbol": "138040", "marketCountry": "KR", "lastPrice": "126100",
        "marketValue": {"purchaseAmount": "131400", "amount": "126100"},
    }]
    with _session() as db:
        db.add(AutoTradePosition(
            market_scope="KR", symbol="138040", currency="KRW",
            initial_quantity=Decimal("1"), remaining_quantity=Decimal("1"),
            average_entry_price=Decimal("131400"),
        ))
        db.commit()
        execute_cycle(db, client, kr_payload=empty, us_payload=empty,
                      policy=AutoTradePolicy(), now=now)
        quant_sell = _payload(now + timedelta(seconds=30), "KR")
        quant_sell["items"][0].update({
            "code": "138040", "event_side": "sell", "side": "sell",
            "price": "126100", "state_after": "exited",
        })
        result = execute_cycle(
            db, client, kr_payload=quant_sell, us_payload=empty,
            policy=AutoTradePolicy(), now=now + timedelta(seconds=30),
        )
        assert len(result["submitted"]) == 1
        assert len(client.created) == 1
        assert client.created[0]["symbol"] == "138040"
        assert any(reason.endswith(":sell-already-scheduled") for reason in result["skipped"])


def test_partial_fill_sync_drives_original_quantity_partial_sell() -> None:
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
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
    now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
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
