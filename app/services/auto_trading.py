from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.integrations.toss_openapi import TossOpenApiClient, TossOpenApiError
from app.models import AutoTradeOrder, AutoTradePosition, AutoTradePositionGuard
from app.services.live_order_guard import (
    evaluate_live_order_candidate,
    evaluate_us_live_order_candidate,
)


TERMINAL_ORDER_STATES = {
    "FILLED",
    "CANCELED",
    "REJECTED",
    "REPLACED",
    "CANCEL_REJECTED",
    "REPLACE_REJECTED",
    "PARTIAL_FILLED_CLOSED",
}

POSITION_GUARD_VERSION = "managed-position-guard-v1"
POSITION_GUARD_CONFIRMATIONS = 2
POSITION_GUARD_STOP_PERCENT = Decimal("0.04")
POSITION_GUARD_PARTIAL_TARGET_PERCENT = Decimal("0.03")
POSITION_GUARD_FULL_TARGET_PERCENT = Decimal("0.05")


@dataclass(frozen=True)
class AutoTradePolicy:
    kr_budget_krw: Decimal = Decimal("174000")
    us_budget_krw: Decimal = Decimal("406000")
    daily_loss_limit_krw: Decimal = Decimal("5800")
    max_positions_per_market: int = 2
    signal_max_age_seconds: int = 180
    order_retry_window_seconds: int = 480
    minimum_funding_ratio: Decimal = Decimal("0.98")

    def __post_init__(self) -> None:
        object.__setattr__(self, "kr_budget_krw", _decimal(self.kr_budget_krw))
        object.__setattr__(self, "us_budget_krw", _decimal(self.us_budget_krw))
        object.__setattr__(self, "daily_loss_limit_krw", _decimal(self.daily_loss_limit_krw))
        object.__setattr__(self, "minimum_funding_ratio", _decimal(self.minimum_funding_ratio))
        if (
            self.kr_budget_krw <= 0
            or self.us_budget_krw <= 0
            or self.kr_budget_krw * Decimal("7")
            != self.us_budget_krw * Decimal("3")
        ):
            raise ValueError("This strategy requires an exact KR 30% / US 70% capital split")
        if self.daily_loss_limit_krw <= 0:
            raise ValueError("daily_loss_limit_krw must be positive")
        if not Decimal("0") < self.minimum_funding_ratio <= Decimal("1"):
            raise ValueError("minimum_funding_ratio must be greater than 0 and at most 1")
        if self.max_positions_per_market < 1:
            raise ValueError("max_positions_per_market must be positive")

    def budget(self, market_scope: str) -> Decimal:
        return self.kr_budget_krw if market_scope == "KR" else self.us_budget_krw

    def daily_loss_limit(self, market_scope: str) -> Decimal:
        return self.daily_loss_limit_krw * (
            Decimal("0.3") if market_scope == "KR" else Decimal("0.7")
        )


@dataclass(frozen=True)
class SignalEvent:
    event_id: str
    strategy_version: str
    market_scope: str
    symbol: str
    side: str
    event_side: str
    execution_date: str
    price: Decimal
    sell_fraction_original: Decimal | None = None


def _decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception:
        return default
    return result if result.is_finite() else default


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _event_key(parts: Iterable[Any]) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return "signal-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _new_buys_allowed(payload: dict[str, Any], scope: str) -> bool:
    """Honor each market feed's published entry-safety contract.

    The US feed publishes an explicit fail-closed ``new_entries_allowed`` flag.
    The domestic feed predates that field and publishes ``entry_safety_guard``
    instead; an active guard downgrades unexecuted entries before publication.
    If the domestic feed later adds the explicit flag, it takes precedence.
    """

    if "new_entries_allowed" in payload:
        return payload.get("new_entries_allowed") is True
    if scope != "KR":
        return False
    guard = payload.get("entry_safety_guard")
    return isinstance(guard, dict) and guard.get("active") is False


def _kr_intraday_quant_prechecks_passed(
    item: dict[str, Any],
    row: dict[str, Any],
) -> bool:
    """Fail closed unless a KR buy is a same-session supported setup."""

    execution_date = str(row.get("execution_date") or "")[:10]
    signal_date = str(row.get("signal_date") or item.get("signal_date") or "")[:10]
    if not execution_date or signal_date != execution_date:
        return False

    signal_at = _parse_time(row.get("signal_at") or item.get("signal_at"))
    if signal_at is None:
        return False
    local_signal_at = signal_at.astimezone(ZoneInfo("Asia/Seoul"))
    if (
        local_signal_at.date().isoformat() != execution_date
        or not time(9, 0) <= local_signal_at.time().replace(tzinfo=None) <= time(15, 30)
    ):
        return False

    confirmation = row.get("entry_confirmation") or item.get("entry_confirmation")
    if isinstance(confirmation, dict) and confirmation.get("allowed") is not True:
        return False

    reasons = item.get("public_reasons") or row.get("public_reasons") or []
    by_key = {
        str(reason.get("key") or ""): reason
        for reason in reasons
        if isinstance(reason, dict)
    }
    for key in ("trend_20d", "trend_60d", "flow"):
        reason = by_key.get(key)
        if not reason or reason.get("available") is not True:
            return False
        if str(reason.get("state") or "").lower() not in {"positive", "supportive"}:
            return False
    return True


def extract_actionable_events(
    payload: dict[str, Any],
    *,
    market_scope: str,
    now: datetime,
    max_age_seconds: int,
) -> list[SignalEvent]:
    """Convert only today's verified, fresh transitions into broker events."""

    scope = market_scope.upper()
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    strategy = str(payload.get("strategy_version") or "").strip()
    if payload.get("status") != "ready" or payload.get("data_state", "ready") != "ready":
        return []
    as_of = _parse_time(payload.get("as_of") or payload.get("snapshot_generated_at"))
    if as_of is None or not (
        0 <= (current.astimezone(timezone.utc) - as_of).total_seconds() <= max_age_seconds
    ):
        return []
    market_zone = ZoneInfo("Asia/Seoul" if scope == "KR" else "America/New_York")
    today = current.astimezone(market_zone).date().isoformat()
    output: list[SignalEvent] = []
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        candidates = item.get("events") if scope == "US" else None
        rows = candidates if isinstance(candidates, list) and candidates else [item]
        for row in rows:
            if not isinstance(row, dict):
                continue
            event_side = str(row.get("event_side") or row.get("side") or "").lower()
            side = "BUY" if event_side == "buy" else "SELL" if event_side in {"sell", "partial_sell"} else ""
            execution_date = str(row.get("execution_date") or "")[:10]
            verified = row.get("intraday_execution_verified") is True
            kr_order_candidate = {**item, **row}
            if scope == "KR":
                kr_order_candidate["event_side"] = event_side
                kr_order_candidate["side"] = event_side
                kr_order_candidate["execution_date"] = execution_date
                kr_order_candidate["price"] = row.get("price") or item.get("price")
            kr_order_eligible = (
                scope != "KR"
                or evaluate_live_order_candidate(kr_order_candidate, now=current)["eligible"]
            )
            us_order_eligible = (
                scope != "US"
                or evaluate_us_live_order_candidate(row, now=current)["eligible"]
            )
            if (
                not side
                or execution_date != today
                or not verified
                or not kr_order_eligible
                or not us_order_eligible
                or (scope == "KR" and item.get("status") != "confirmed")
                or (side == "BUY" and not _new_buys_allowed(payload, scope))
                or (
                    scope == "KR"
                    and side == "BUY"
                    and not _kr_intraday_quant_prechecks_passed(
                        item,
                        row,
                    )
                )
            ):
                continue
            symbol = str(row.get("code") or item.get("code") or "").upper().strip()
            price = _decimal(row.get("price") or item.get("price"))
            if not symbol or price <= 0:
                continue
            identity = str(row.get("event_id") or "") or _event_key(
                (scope, strategy, symbol, event_side, execution_date, price, row.get("state_after"))
            )
            fraction = _decimal(row.get("sell_fraction_original"), Decimal("0"))
            if event_side == "partial_sell" and fraction <= 0:
                fraction = Decimal("0.5")
            output.append(
                SignalEvent(
                    event_id=identity,
                    strategy_version=strategy,
                    market_scope=scope,
                    symbol=symbol,
                    side=side,
                    event_side=event_side,
                    execution_date=execution_date,
                    price=price,
                    sell_fraction_original=fraction if fraction > 0 else None,
                )
            )
    unique = {event.event_id: event for event in output}
    return sorted(unique.values(), key=lambda event: (event.side == "BUY", event.event_id))


def _client_order_id(event_id: str) -> str:
    return "sn-" + hashlib.sha256(event_id.encode("utf-8")).hexdigest()[:32]


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _market_exposure_krw(holdings: dict[str, Any], scope: str, fx: Decimal) -> Decimal:
    total = Decimal("0")
    for item in holdings.get("items") or []:
        if str(item.get("marketCountry") or "").upper() != scope:
            continue
        market_value = item.get("marketValue") or {}
        native = max(
            _decimal(market_value.get("purchaseAmount")),
            _decimal(market_value.get("amount")),
        )
        total += native if scope == "KR" else native * fx
    return total


def _open_buy_reserve_krw(orders: list[dict[str, Any]], scope: str, fx: Decimal) -> Decimal:
    reserve = Decimal("0")
    for order in orders:
        if str(order.get("side") or "").upper() != "BUY":
            continue
        currency = str(order.get("currency") or "").upper()
        if (scope == "KR" and currency != "KRW") or (scope == "US" and currency != "USD"):
            continue
        execution = order.get("execution") or {}
        quantity = _decimal(order.get("quantity")) - _decimal(execution.get("filledQuantity"))
        native = _decimal(order.get("orderAmount"))
        if native <= 0:
            native = max(Decimal("0"), quantity) * _decimal(order.get("price"))
        reserve += native if scope == "KR" else native * fx
    return reserve


def _local_buy_reserve_krw(db: Session, scope: str) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(AutoTradeOrder.requested_notional_krw), 0)).where(
            AutoTradeOrder.market_scope == scope,
            AutoTradeOrder.side == "BUY",
            AutoTradeOrder.status.not_in(TERMINAL_ORDER_STATES | {"AMBIGUOUS_BLOCKED"}),
        )
    )
    return _decimal(value)


def account_capital_state(
    *,
    holdings: dict[str, Any],
    open_orders: list[dict[str, Any]],
    krw_buying_power: Decimal,
    usd_buying_power: Decimal,
    fx: Decimal,
    policy: AutoTradePolicy,
    local_reserve_krw: dict[str, Decimal] | None = None,
) -> dict[str, dict[str, Any]]:
    local_reserve = local_reserve_krw or {}
    rate = _decimal(fx)
    result: dict[str, dict[str, Any]] = {}
    for scope, cash_krw in (
        ("KR", _decimal(krw_buying_power)),
        ("US", _decimal(usd_buying_power) * rate),
    ):
        exposure = _market_exposure_krw(holdings, scope, rate)
        reserve = max(
            _open_buy_reserve_krw(open_orders, scope, rate),
            _decimal(local_reserve.get(scope)),
        )
        total = exposure + reserve + cash_krw
        result[scope] = {
            "budget_krw": policy.budget(scope),
            "cash_krw": cash_krw,
            "exposure_krw": exposure,
            "open_buy_reserve_krw": reserve,
            "total_capital_krw": total,
            "funded": total >= policy.budget(scope) * policy.minimum_funding_ratio,
        }
    return result


def _daily_realized_loss(db: Session, scope: str, now: datetime) -> Decimal:
    market_zone = ZoneInfo("Asia/Seoul" if scope == "KR" else "America/New_York")
    aware_now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    start_local = datetime.combine(
        aware_now.astimezone(market_zone).date(),
        datetime.min.time(),
        tzinfo=market_zone,
    )
    start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    pnl = db.scalar(
        select(func.coalesce(func.sum(AutoTradeOrder.realized_pnl_krw), 0)).where(
            AutoTradeOrder.market_scope == scope,
            AutoTradeOrder.updated_at >= start,
        )
    )
    return max(Decimal("0"), -_decimal(pnl))


def _update_order_from_broker(
    db: Session,
    local: AutoTradeOrder,
    broker: dict[str, Any],
    *,
    fx: Decimal,
) -> None:
    execution = broker.get("execution") or {}
    prior_filled = _decimal(local.applied_filled_quantity)
    filled = _decimal(execution.get("filledQuantity"))
    delta = max(Decimal("0"), filled - prior_filled)
    average = _decimal(execution.get("averageFilledPrice"))
    prior_commission = _decimal(local.commission)
    prior_tax = _decimal(local.tax)
    commission = _decimal(execution.get("commission"))
    tax = _decimal(execution.get("tax"))
    local.status = str(broker.get("status") or local.status).upper()
    if local.status == "PARTIAL_FILLED" and broker.get("canceledAt"):
        local.status = "PARTIAL_FILLED_CLOSED"
    local.response_payload = _json(broker)
    local.filled_quantity = filled
    local.average_filled_price = average or None
    local.filled_amount = _decimal(execution.get("filledAmount")) or None
    local.commission = commission or None
    local.tax = tax or None
    if delta > 0 and average > 0:
        position = db.scalar(
            select(AutoTradePosition).where(
                AutoTradePosition.market_scope == local.market_scope,
                AutoTradePosition.symbol == local.symbol,
            )
        )
        multiplier = Decimal("1") if local.market_scope == "KR" else fx
        if local.side == "BUY":
            if position is None:
                position = AutoTradePosition(
                    market_scope=local.market_scope,
                    symbol=local.symbol,
                    currency="KRW" if local.market_scope == "KR" else "USD",
                    initial_quantity=Decimal("0"),
                    remaining_quantity=Decimal("0"),
                    average_entry_price=Decimal("0"),
                )
                db.add(position)
            if _decimal(position.remaining_quantity) <= 0:
                position.initial_quantity = Decimal("0")
                position.average_entry_price = Decimal("0")
                position.realized_pnl_krw = Decimal("0")
                position.opened_at = datetime.utcnow()
                position.closed_at = None
            old_quantity = _decimal(position.remaining_quantity)
            position.average_entry_price = (
                (_decimal(position.average_entry_price) * old_quantity + average * delta)
                / (old_quantity + delta)
            )
            position.initial_quantity = _decimal(position.initial_quantity) + delta
            position.remaining_quantity = old_quantity + delta
        elif position is not None:
            sold = min(delta, _decimal(position.remaining_quantity))
            cost_delta = max(Decimal("0"), commission - prior_commission) + max(
                Decimal("0"), tax - prior_tax
            )
            realized_native = (average - _decimal(position.average_entry_price)) * sold - cost_delta
            realized_krw = realized_native * multiplier
            local.realized_pnl_krw = _decimal(local.realized_pnl_krw) + realized_krw
            position.realized_pnl_krw = _decimal(position.realized_pnl_krw) + realized_krw
            position.remaining_quantity = max(Decimal("0"), _decimal(position.remaining_quantity) - sold)
            if position.remaining_quantity == 0:
                position.closed_at = datetime.utcnow()
        local.applied_filled_quantity = filled


def synchronize_orders(db: Session, client: TossOpenApiClient, *, fx: Decimal) -> list[str]:
    messages: list[str] = []
    rows = list(
        db.scalars(
            select(AutoTradeOrder).where(
                AutoTradeOrder.broker_order_id.is_not(None),
                AutoTradeOrder.status.not_in(TERMINAL_ORDER_STATES),
            )
        )
    )
    for row in rows:
        broker = client.order(str(row.broker_order_id))
        _update_order_from_broker(db, row, broker, fx=fx)
        messages.append(f"synced:{row.client_order_id}:{row.status}")
    db.commit()
    return messages


def _recover_or_block_intents(
    db: Session,
    client: TossOpenApiClient,
    *,
    now: datetime,
    retry_window_seconds: int,
) -> list[str]:
    messages: list[str] = []
    rows = list(db.scalars(select(AutoTradeOrder).where(AutoTradeOrder.status == "SUBMITTING")))
    for row in rows:
        age = now.replace(tzinfo=None) - row.created_at
        if age > timedelta(seconds=retry_window_seconds):
            row.status = "AMBIGUOUS_BLOCKED"
            row.failure_reason = "Broker result unknown after the Toss 10-minute idempotency window"
            messages.append(f"blocked:{row.client_order_id}:ambiguous")
            continue
        try:
            result = client.create_order(json.loads(row.request_payload))
        except TossOpenApiError as exc:
            row.failure_reason = str(exc)
            if exc.status_code in {400, 409, 422}:
                row.status = "REJECTED"
                messages.append(f"rejected:{row.client_order_id}:{exc.code or exc.status_code}")
                continue
            messages.append(f"retry-pending:{row.client_order_id}")
            continue
        order_id = str(result.get("orderId") or "")
        if not order_id:
            row.failure_reason = "Toss order response did not include orderId"
            messages.append(f"retry-pending:{row.client_order_id}")
            continue
        row.broker_order_id = order_id
        row.response_payload = _json(result)
        row.status = "SUBMITTED"
        row.submitted_at = datetime.utcnow()
        messages.append(f"recovered:{row.client_order_id}")
    db.commit()
    return messages


def _sell_quantity(position: AutoTradePosition, event: SignalEvent) -> Decimal:
    remaining = _decimal(position.remaining_quantity)
    if event.event_side != "partial_sell":
        return remaining
    target = _decimal(position.initial_quantity) * (event.sell_fraction_original or Decimal("0.5"))
    return min(remaining, target)


def _krx_tick(price: Decimal) -> Decimal:
    for upper, tick in (
        (Decimal("2000"), Decimal("1")),
        (Decimal("5000"), Decimal("5")),
        (Decimal("20000"), Decimal("10")),
        (Decimal("50000"), Decimal("50")),
        (Decimal("200000"), Decimal("100")),
        (Decimal("500000"), Decimal("500")),
    ):
        if price < upper:
            return tick
    return Decimal("1000")


def _krx_trigger_price(price: Decimal, *, upward: bool) -> Decimal:
    rounding = ROUND_CEILING if upward else ROUND_DOWN
    tick = _krx_tick(price)
    return (price / tick).to_integral_value(rounding=rounding) * tick


def _managed_position_guard_events(
    db: Session,
    holdings: dict[str, Any],
    *,
    now: datetime,
) -> tuple[list[SignalEvent], list[dict[str, Any]]]:
    """Create KR/US exits after two independent in-session broker-price checks."""

    aware_now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    kr_now = aware_now.astimezone(ZoneInfo("Asia/Seoul"))
    from app.services.us_market_calendar import us_signal_session_state

    active_scopes: dict[str, datetime] = {}
    if kr_now.weekday() < 5 and time(9, 0) <= kr_now.time().replace(tzinfo=None) < time(15, 30):
        active_scopes["KR"] = kr_now
    us_state = us_signal_session_state(aware_now)
    if us_state.get("is_regular") is True:
        active_scopes["US"] = aware_now.astimezone(ZoneInfo("America/New_York"))
    if not active_scopes:
        return [], []
    broker_by_scope = {
        scope: {
            str(item.get("symbol") or "").upper(): item
            for item in holdings.get("items") or []
            if str(item.get("marketCountry") or "").upper() == scope
        }
        for scope in active_scopes
    }
    events: list[SignalEvent] = []
    statuses: list[dict[str, Any]] = []
    positions = list(db.scalars(select(AutoTradePosition).where(
        AutoTradePosition.market_scope.in_(tuple(active_scopes)),
        AutoTradePosition.remaining_quantity > 0,
    )))
    observed_at = aware_now.astimezone(timezone.utc).replace(tzinfo=None)
    for position in positions:
        scope = str(position.market_scope).upper()
        market_now = active_scopes[scope]
        broker = broker_by_scope[scope].get(position.symbol.upper())
        price = _decimal((broker or {}).get("lastPrice"))
        entry = _decimal(position.average_entry_price)
        if price <= 0 or entry <= 0:
            statuses.append({"symbol": position.symbol, "state": "price_unavailable"})
            continue
        initial = _decimal(position.initial_quantity)
        def threshold(multiple: Decimal, *, upward: bool) -> Decimal:
            raw = entry * multiple
            return _krx_trigger_price(raw, upward=upward) if scope == "KR" else raw

        stop_threshold = threshold(Decimal("1") - POSITION_GUARD_STOP_PERCENT, upward=False)
        full_threshold = threshold(Decimal("1") + POSITION_GUARD_FULL_TARGET_PERCENT, upward=True)
        triggers = [
            ("hard_stop", stop_threshold, price <= stop_threshold, "sell", None),
            ("full_profit", full_threshold, price >= full_threshold, "sell", None),
        ]
        if initial >= 2 or (scope == "US" and initial > 0):
            partial_threshold = threshold(
                Decimal("1") + POSITION_GUARD_PARTIAL_TARGET_PERCENT, upward=True
            )
            triggers.insert(1, ("partial_profit", partial_threshold, price >= partial_threshold, "partial_sell", Decimal("0.5")))
        for key, threshold, breached, event_side, fraction in triggers:
            row = db.scalar(select(AutoTradePositionGuard).where(
                AutoTradePositionGuard.market_scope == scope,
                AutoTradePositionGuard.symbol == position.symbol,
                AutoTradePositionGuard.trigger_key == key,
            ))
            if row is None:
                row = AutoTradePositionGuard(
                    market_scope=scope, symbol=position.symbol, trigger_key=key,
                    consecutive_breaches=0, last_price=price, threshold_price=threshold,
                    last_observed_at=observed_at,
                )
                db.add(row)
            row.last_price = price
            row.threshold_price = threshold
            row.last_observed_at = observed_at
            if breached:
                if row.consecutive_breaches == 0:
                    row.first_breached_at = observed_at
                row.consecutive_breaches += 1
            else:
                row.consecutive_breaches = 0
                row.first_breached_at = None
            state = "confirmed" if row.consecutive_breaches >= POSITION_GUARD_CONFIRMATIONS else "candidate" if breached else "clear"
            statuses.append({
                "market_scope": scope, "symbol": position.symbol,
                "trigger": key, "state": state,
                "price": str(price), "threshold": str(threshold),
                "checks": row.consecutive_breaches,
            })
            if state == "confirmed":
                opened = position.opened_at.isoformat(timespec="seconds")
                events.append(SignalEvent(
                    event_id=f"{POSITION_GUARD_VERSION}:{scope}:{position.symbol}:{opened}:{key}",
                    strategy_version=POSITION_GUARD_VERSION,
                    market_scope=scope, symbol=position.symbol, side="SELL",
                    event_side=event_side, execution_date=market_now.date().isoformat(),
                    price=price, sell_fraction_original=fraction,
                ))
    db.commit()
    return events, statuses


def execute_cycle(
    db: Session,
    client: TossOpenApiClient,
    *,
    kr_payload: dict[str, Any],
    us_payload: dict[str, Any],
    policy: AutoTradePolicy,
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now().astimezone()
    fx = _decimal(client.exchange_rate().get("rate"))
    if fx <= 0:
        raise TossOpenApiError("A positive USD/KRW exchange rate is required")
    messages = _recover_or_block_intents(
        db,
        client,
        now=current,
        retry_window_seconds=policy.order_retry_window_seconds,
    )
    messages.extend(synchronize_orders(db, client, fx=fx))
    holdings = client.holdings()
    open_orders = client.orders("OPEN")
    cash_krw = _decimal(client.buying_power("KRW").get("cashBuyingPower"))
    cash_usd = _decimal(client.buying_power("USD").get("cashBuyingPower"))
    capital_state = account_capital_state(
        holdings=holdings,
        open_orders=open_orders,
        krw_buying_power=cash_krw,
        usd_buying_power=cash_usd,
        fx=fx,
        policy=policy,
        local_reserve_krw={
            scope: _local_buy_reserve_krw(db, scope) for scope in ("KR", "US")
        },
    )
    reserved_by_scope = {
        scope: _decimal(capital_state[scope]["open_buy_reserve_krw"])
        for scope in ("KR", "US")
    }
    all_markets_funded = all(capital_state[scope]["funded"] for scope in ("KR", "US"))
    guard_events, position_guards = _managed_position_guard_events(
        db, holdings, now=current
    )
    events = extract_actionable_events(
        kr_payload,
        market_scope="KR",
        now=current,
        max_age_seconds=policy.signal_max_age_seconds,
    ) + extract_actionable_events(
        us_payload,
        market_scope="US",
        now=current,
        max_age_seconds=policy.signal_max_age_seconds,
    ) + guard_events
    submitted: list[str] = []
    skipped: list[str] = []
    sell_symbols_scheduled = set(db.scalars(select(AutoTradeOrder.symbol).where(
        AutoTradeOrder.side == "SELL",
        AutoTradeOrder.status.not_in(TERMINAL_ORDER_STATES | {"AMBIGUOUS_BLOCKED"}),
    )))
    for event in events:
        if db.scalar(select(AutoTradeOrder.id).where(AutoTradeOrder.signal_event_id == event.event_id)):
            skipped.append(f"{event.event_id}:duplicate")
            continue
        position = db.scalar(
            select(AutoTradePosition).where(
                AutoTradePosition.market_scope == event.market_scope,
                AutoTradePosition.symbol == event.symbol,
            )
        )
        request: dict[str, Any]
        notional_krw = Decimal("0")
        if event.side == "SELL":
            if event.symbol in sell_symbols_scheduled:
                skipped.append(f"{event.event_id}:sell-already-scheduled")
                continue
            if position is None or _decimal(position.remaining_quantity) <= 0:
                skipped.append(f"{event.event_id}:no-managed-position")
                continue
            quantity = _sell_quantity(position, event)
            if event.market_scope == "KR":
                quantity = Decimal(math.floor(quantity))
            else:
                quantity = quantity.quantize(Decimal("0.000001"), rounding=ROUND_DOWN)
            if quantity <= 0:
                skipped.append(f"{event.event_id}:zero-sell-quantity")
                continue
            request = {
                "clientOrderId": _client_order_id(event.event_id),
                "symbol": event.symbol,
                "side": "SELL",
                "orderType": "MARKET",
                "quantity": format(quantity, "f"),
            }
            notional_krw = quantity * event.price * (
                Decimal("1") if event.market_scope == "KR" else fx
            )
        else:
            if not all_markets_funded:
                skipped.append(f"{event.event_id}:capital-not-funded")
                continue
            if position is not None and _decimal(position.remaining_quantity) > 0:
                skipped.append(f"{event.event_id}:position-exists")
                continue
            if _daily_realized_loss(db, event.market_scope, current) >= policy.daily_loss_limit(event.market_scope):
                skipped.append(f"{event.event_id}:daily-loss-limit")
                continue
            position_count = db.scalar(
                select(func.count()).select_from(AutoTradePosition).where(
                    AutoTradePosition.market_scope == event.market_scope,
                    AutoTradePosition.remaining_quantity > 0,
                )
            ) or 0
            pending_count = db.scalar(
                select(func.count()).select_from(AutoTradeOrder).where(
                    AutoTradeOrder.market_scope == event.market_scope,
                    AutoTradeOrder.side == "BUY",
                    AutoTradeOrder.status.not_in(
                        TERMINAL_ORDER_STATES | {"AMBIGUOUS_BLOCKED"}
                    ),
                )
            ) or 0
            if position_count + pending_count >= policy.max_positions_per_market:
                skipped.append(f"{event.event_id}:position-limit")
                continue
            exposure = _market_exposure_krw(holdings, event.market_scope, fx)
            reserve = reserved_by_scope[event.market_scope]
            available = max(Decimal("0"), policy.budget(event.market_scope) - exposure - reserve)
            allocation = min(
                available,
                policy.budget(event.market_scope) / policy.max_positions_per_market,
            ) * Decimal("0.99")
            if event.market_scope == "KR":
                if event.price <= min(available, cash_krw) * Decimal("0.99"):
                    allocation = max(allocation, event.price)
                quantity = Decimal(math.floor(min(allocation, cash_krw) / event.price))
                if quantity <= 0:
                    skipped.append(f"{event.event_id}:insufficient-kr-budget")
                    continue
                request = {
                    "clientOrderId": _client_order_id(event.event_id),
                    "symbol": event.symbol,
                    "side": "BUY",
                    "orderType": "MARKET",
                    "quantity": format(quantity, "f"),
                }
                notional_krw = quantity * event.price
            else:
                amount_usd = min(allocation / fx, cash_usd).quantize(
                    Decimal("0.01"), rounding=ROUND_DOWN
                )
                if amount_usd <= 0:
                    skipped.append(f"{event.event_id}:insufficient-us-budget")
                    continue
                request = {
                    "clientOrderId": _client_order_id(event.event_id),
                    "symbol": event.symbol,
                    "side": "BUY",
                    "orderType": "MARKET",
                    "orderAmount": format(amount_usd, "f"),
                }
                notional_krw = amount_usd * fx
        local = AutoTradeOrder(
            signal_event_id=event.event_id,
            client_order_id=request["clientOrderId"],
            strategy_version=event.strategy_version,
            market_scope=event.market_scope,
            symbol=event.symbol,
            side=event.side,
            status="SUBMITTING",
            request_payload=_json(request),
            requested_notional_krw=notional_krw,
        )
        db.add(local)
        db.commit()
        try:
            result = client.create_order(request)
        except TossOpenApiError as exc:
            local.failure_reason = str(exc)
            if exc.status_code in {400, 409, 422}:
                local.status = "REJECTED"
            db.commit()
            if local.status == "REJECTED":
                skipped.append(f"{event.event_id}:broker-rejected:{exc.code or exc.status_code}")
                continue
            raise
        order_id = str(result.get("orderId") or "")
        if not order_id:
            local.failure_reason = "Toss order response did not include orderId"
            db.commit()
            raise TossOpenApiError(local.failure_reason)
        local.broker_order_id = order_id
        local.response_payload = _json(result)
        local.status = "SUBMITTED"
        local.submitted_at = datetime.utcnow()
        db.commit()
        if event.side == "BUY":
            reserved_by_scope[event.market_scope] += notional_krw
        else:
            sell_symbols_scheduled.add(event.symbol)
        submitted.append(local.client_order_id)
    return {
        "mode": "live",
        "capital": {
            "KR": f"{policy.kr_budget_krw} KRW",
            "US": f"{policy.us_budget_krw} KRW",
        },
        "exchange_rate": str(fx),
        "capital_ready": all_markets_funded,
        "capital_state": {
            scope: {
                key: str(value) if isinstance(value, Decimal) else value
                for key, value in capital_state[scope].items()
            }
            for scope in ("KR", "US")
        },
        "submitted": submitted,
        "skipped": skipped,
        "reconciliation": messages,
        "position_guards": position_guards,
    }
