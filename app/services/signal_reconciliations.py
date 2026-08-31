from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.services.signal_entry_evidence import ENTRY_EVIDENCE_STRATEGY_VERSION


KST = ZoneInfo("Asia/Seoul")
COMPATIBLE_POSITION_STRATEGY_VERSIONS = {
    ENTRY_EVIDENCE_STRATEGY_VERSION,
    "position-lifecycle-v7.1",
    "position-lifecycle-v7.2",
    "position-lifecycle-v7.3",
}

# These records close positions that were exposed by a legacy strategy but are
# absent from the canonical strategy after a version migration.  They are kept
# separate from model-generated events so every API and client can explain why
# the transition exists instead of presenting it as a fresh model decision.
SIGNAL_RECONCILIATIONS: tuple[dict[str, Any], ...] = (
    {
        "id": "legacy-v2-oci-010060-close-20260820",
        "code": "010060",
        "name": "OCI홀딩스",
        "market": "KOSPI",
        "market_cap_rank": 94,
        "signal_origin": "legacy_reconciliation",
        "source_strategy_version": "position-lifecycle-v2.0",
        "target_strategy_version": ENTRY_EVIDENCE_STRATEGY_VERSION,
        "side": "sell",
        "label": "확정 매도 · 전략 버전 통일",
        "signal_date": date(2026, 8, 20),
        "signal_at": datetime(2026, 8, 20, 12, 35, 52, tzinfo=KST),
        "execution_date": date(2026, 8, 20),
        "price": 293_500,
        "entry_price": 273_500,
        "target_sell_price": 345_283,
        "target_sell_status": "missed",
        "target_sell_delta": -51_783,
        "score": None,
        "reason": "전략 버전 v2.0→v7.0 통일에 따라 구버전 매수 신호의 포지션을 종료함",
        "return_rate": Decimal("6.83"),
        "holding_days": 2,
        "position_percent": Decimal("0.00"),
        "state_after": "exited",
    },
)


def _normalized_now(value: Optional[datetime]) -> datetime:
    candidate = value or datetime.now(KST)
    if candidate.tzinfo is None:
        return candidate.replace(tzinfo=KST)
    return candidate.astimezone(KST)


def _as_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _event_date(item: dict[str, Any]) -> date:
    return (
        _as_date(item.get("execution_date"))
        or _as_date(item.get("transition_date"))
        or _as_date(item.get("signal_date"))
        or date.min
    )


def _active_records(
    now: Optional[datetime],
    *,
    code: Optional[str] = None,
    target_strategy_version: Optional[str] = None,
) -> list[dict[str, Any]]:
    current_date = _normalized_now(now).date()
    normalized_code = str(code or "").strip()
    return [
        record
        for record in SIGNAL_RECONCILIATIONS
        if _event_date(record) <= current_date
        and (not normalized_code or record["code"] == normalized_code)
        and (
            not target_strategy_version
            or record["target_strategy_version"] == target_strategy_version
            or (
                record["target_strategy_version"] == ENTRY_EVIDENCE_STRATEGY_VERSION
                and target_strategy_version in COMPATIBLE_POSITION_STRATEGY_VERSIONS
            )
        )
    ]


def _public_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "code": record["code"],
        "signal_origin": record["signal_origin"],
        "source_strategy_version": record["source_strategy_version"],
        "target_strategy_version": record["target_strategy_version"],
        "signal_at": record["signal_at"],
        "execution_date": record["execution_date"],
        "price": record["price"],
        "entry_price": record["entry_price"],
        "reason": record["reason"],
    }


def _stock_event(record: dict[str, Any]) -> dict[str, Any]:
    event = {
        key: deepcopy(value)
        for key, value in record.items()
        if key not in {"id", "code", "name", "market", "market_cap_rank", "target_strategy_version"}
    }
    event["reconciliation_id"] = record["id"]
    return event


def _reconciled_current(
    payload: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    previous = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    previous_lifecycle = (
        previous.get("lifecycle")
        if isinstance(previous.get("lifecycle"), dict)
        else {}
    )
    current_score = previous.get("score")
    if current_score is None:
        current_score = Decimal("0.00")
    return {
        "action": "exited",
        "label": "전략 버전 통일 확정매도",
        "score": current_score,
        "price": previous.get("price") or record["price"],
        "as_of": previous.get("as_of") or payload.get("as_of") or record["signal_at"],
        "live_observation": False,
        "position_open": False,
        "model_exposure_percent": Decimal("0.00"),
        "signal_origin": record["signal_origin"],
        "reconciliation_id": record["id"],
        "lifecycle": {
            "state": "exited",
            "label": "전략상 전량 매도 후 관망",
            "stage_index": 5,
            "stages": previous_lifecycle.get("stages")
            or ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
            "latest_transition": {
                "label": record["label"],
                "side": "sell",
                "signal_at": record["signal_at"],
                "signal_date": record["signal_date"],
                "transition_date": record["execution_date"],
                "price": record["price"],
                "entry_price": record["entry_price"],
                "target_sell_price": record["target_sell_price"],
                "target_sell_status": record["target_sell_status"],
                "target_sell_delta": record["target_sell_delta"],
                "signal_origin": record["signal_origin"],
                "reconciliation_id": record["id"],
            },
        },
        "entry_date": None,
        "entry_price": None,
        "target_sell_price": record["target_sell_price"],
        "target_sell_status": record["target_sell_status"],
        "target_sell_delta": record["target_sell_delta"],
        "partial_exit_date": None,
        "partial_exit_price": None,
        "partial_exits": [],
        "profit_stage": 0,
        "profit_steps_total": 3,
        "entry_setup": None,
        "holding_days": None,
        "unrealized_return": None,
        "return_basis": None,
        "stop_reference": None,
        "locked_profit_reference": None,
        "partial_exit_reference": None,
        "levels": [],
        "reasons": [record["reason"]],
        "next_confirmation": "현재 전략의 신규 진입 조건이 다시 확정될 때까지 관망",
    }


def apply_stock_signal_reconciliations(
    payload: Optional[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Overlay an audited legacy close without changing model calculations."""

    if not isinstance(payload, dict):
        return payload
    strategy_version = str(payload.get("strategy_version") or "").strip()
    records = _active_records(
        now,
        code=str(payload.get("code") or ""),
        target_strategy_version=strategy_version,
    )
    if not records:
        return payload

    result = deepcopy(payload)
    events = [deepcopy(item) for item in result.get("events") or [] if isinstance(item, dict)]
    existing_ids = {str(item.get("reconciliation_id") or "") for item in events}
    for record in records:
        if record["id"] not in existing_ids:
            events.append(_stock_event(record))
    events.sort(key=lambda item: (_event_date(item), str(item.get("signal_at") or "")))
    result["events"] = events
    result["signal_reconciliations"] = [_public_metadata(record) for record in records]

    latest_record = max(records, key=_event_date)
    later_model_event = any(
        not event.get("reconciliation_id")
        and _event_date(event) > _event_date(latest_record)
        for event in events
    )
    if later_model_event:
        return result

    result["current"] = _reconciled_current(result, latest_record)
    result.update(
        {
            "display_return_rate": latest_record["return_rate"],
            "display_return_kind": "closed_trade",
            "display_return_event_date": latest_record["execution_date"],
            "display_return_event_side": "sell",
        }
    )
    data_message = str(result.get("data_message") or "").strip()
    reconciliation_note = "구버전 매수 신호의 전략 통일 종료 이력을 반영했습니다."
    if reconciliation_note not in data_message:
        result["data_message"] = " ".join(item for item in (data_message, reconciliation_note) if item)
    return result


def apply_market_signal_reconciliations(
    payload: Optional[dict[str, Any]],
    *,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    """Merge audited legacy closes into the canonical recent market feed."""

    if not isinstance(payload, dict):
        return payload
    strategy_version = str(payload.get("strategy_version") or "").strip()
    current_time = _normalized_now(now)
    recent_days = max(1, min(int(payload.get("recent_days") or 30), 90))
    cutoff = current_time.date() - timedelta(days=recent_days)
    records = [
        record
        for record in _active_records(now, target_strategy_version=strategy_version)
        if cutoff <= record["execution_date"] <= current_time.date()
    ]
    if not records:
        return payload

    result = deepcopy(payload)
    items = [deepcopy(item) for item in result.get("items") or [] if isinstance(item, dict)]
    for record in records:
        item = {
            key: deepcopy(value)
            for key, value in record.items()
            if key not in {"target_strategy_version"}
        }
        item.update(
            {
                "reconciliation_id": record["id"],
                "signal": record["label"],
                "event_side": record["side"],
                "status": "confirmed",
                "is_preliminary": False,
                "is_current_holding": False,
                "display_return_rate": record["return_rate"],
                "display_return_kind": "closed_trade",
                "display_return_event_date": record["execution_date"],
                "display_return_event_side": "sell",
            }
        )
        existing_index = next(
            (
                index
                for index, existing in enumerate(items)
                if str(existing.get("reconciliation_id") or "") == record["id"]
            ),
            None,
        )
        if existing_index is None:
            items.append(item)
        else:
            # A persisted snapshot may have been built with an older public
            # label contract. Reapply the canonical reconciliation fields so
            # list and stock-detail responses cannot drift until regeneration.
            items[existing_index] = {**items[existing_index], **item}

    items.sort(
        key=lambda item: (
            _event_date(item),
            int(bool(item.get("is_preliminary"))),
            -(int(item.get("market_cap_rank") or 10_000)),
        ),
        reverse=True,
    )
    result["items"] = items
    result["signal_reconciliations"] = [_public_metadata(record) for record in records]
    result["preliminary_count"] = sum(1 for item in items if item.get("is_preliminary"))
    result["confirmed_count"] = len(items) - int(result["preliminary_count"])
    return result
