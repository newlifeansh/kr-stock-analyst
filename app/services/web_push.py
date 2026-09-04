from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import logging
import re
from typing import Optional
from urllib.parse import quote

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import PushSessionLocal
from app.models import (
    DisclosureItem,
    PushDelivery,
    PushNotificationHistory,
    PushSubscription,
    ResearchReport,
    StockMaster,
    WatchlistItem,
)
from app.services.stock_dashboard import _naver_snapshot
from app.services.market_calendar import (
    is_korea_daily_signal_window,
    is_korea_market_session_date,
    is_korea_regular_market_session,
)
from app.services.recommendations import build_recommendations
from app.services.quant_signals import (
    MARKET_SIGNAL_UNIVERSE_LIMIT,
    load_external_market_quant_signal_feed,
    load_market_quant_signal_snapshot,
    load_quant_signal_payload,
    load_reference_quant_signal_payload,
)
from app.services.signal_reconciliations import (
    apply_market_signal_reconciliations,
    apply_stock_signal_reconciliations,
)
from app.services.trends import (
    _matched_template_sectors,
    _stock_sectors,
    _template_by_id,
    build_trend_analysis,
)

logger = logging.getLogger(__name__)
KST = timezone(timedelta(hours=9))
NOTIFICATION_HISTORY_RETENTION = timedelta(days=3)
# A long Web Push TTL lets APNs/FCM hold stale alerts while the device is
# offline, which then makes several old market events arrive at once. Pushes
# are time-sensitive; send each event immediately or let it expire quickly.
PUSH_DELIVERY_TTL_SECONDS = 120
# A successor notification is held until the predecessor can no longer be
# queued by APNs/FCM.  Provider acceptance is not device delivery, so merely
# sending two pushes in order is insufficient to prevent visible reordering.
SIGNAL_SUCCESSOR_DELAY = timedelta(seconds=PUSH_DELIVERY_TTL_SECONDS)
PUSH_DELIVERY_HEADERS = {"Urgency": "high"}
MONEY_BRIEFING_PUSH_TTL_SECONDS = 5 * 60
MONEY_BRIEFING_PUSH_WINDOWS = (
    (
        time(8, 0),
        time(8, 5),
        "morning",
        "아침에 보는 돈이 되는 소식",
        "밤사이 핵심 뉴스와 오늘 체크할 일정을 정리했어요.",
    ),
    (
        time(12, 0),
        time(12, 5),
        "midday",
        "점심에 보는 돈이 되는 소식",
        "오전 9시부터 낮 12시까지의 핵심 소식과 투자 포인트를 정리했어요.",
    ),
    (
        time(16, 0),
        time(16, 5),
        "afternoon",
        "오후에 보는 돈이 되는 소식",
        "낮 12시부터 오후 4시까지의 핵심 소식과 투자 포인트를 정리했어요.",
    ),
)

IMPORTANT_DISCLOSURE_CATEGORIES = {
    "earnings_flash",
    "supply_contract",
    "rights_offering",
    "dividend",
    "treasury_stock",
    "facility_investment",
    "major_holder",
}
IMPORTANT_DISCLOSURE_KEYWORDS = (
    "잠정실적",
    "영업실적",
    "공급계약",
    "단일판매",
    "유상증자",
    "무상증자",
    "배당",
    "자기주식",
    "자사주",
    "합병",
    "분할",
    "최대주주",
    "영업정지",
    "회생절차",
    "횡령",
    "배임",
    "시설투자",
)
LEGACY_DEFAULT_PUSH_CONDITIONS = {"ai_signal", "price_move", "disclosure_report", "major_event"}
DEFAULT_PUSH_CONDITIONS = (
    "morning_briefing",
    "market_session",
    "ai_signal",
    "market_ai_signal",
    "recommendation_update",
    "price_move",
    "disclosure_report",
    "major_event",
)
REQUIRED_PUSH_CONDITIONS = {"ai_signal", "morning_briefing"}
SIGNAL_NOTIFICATION_KINDS = frozenset({"ai_signal", "market_ai_signal"})
MARKET_NOTIFICATION_KINDS = frozenset({*SIGNAL_NOTIFICATION_KINDS, "market_session", "price_move"})
SIGNAL_EVENT_DATE_PATTERN = re.compile(r":(\d{4}-\d{2}-\d{2})$")
PRICE_EVENT_DATE_PATTERN = re.compile(r"^price:(\d{4}-\d{2}-\d{2}):")
MARKET_PRELIMINARY_SIGNAL_EVENT_PATTERN = re.compile(
    r"^market-ai-preliminary:([^:]+):(buy|sell):(\d{4}-\d{2}-\d{2})$"
)
WATCHLIST_SIGNAL_EVENT_PATTERN = re.compile(
    r"^ai-signal:([^:]+):"
    r"(entry_watch|entry_pending|partial_exit_pending|full_exit_pending|entered|partially_exited|exited):"
    r"(\d{4}-\d{2}-\d{2})$"
)
PUSH_KIND_TO_CONDITION = {
    "morning_briefing": "morning_briefing",
    "market_session": "market_session",
    "ai_signal": "ai_signal",
    "market_ai_signal": "market_ai_signal",
    "recommendation_update": "recommendation_update",
    "price_move": "price_move",
    "report": "disclosure_report",
    "disclosure": "disclosure_report",
    "major_event": "major_event",
}

RECOMMENDATION_PUSH_LIMIT = 10
RECOMMENDATION_BATCH_THRESHOLD = 3
RECOMMENDATION_STATE_KIND = "recommendation_state"
SIGNAL_NOTIFICATION_ICON_BY_STATE = {
    "entry_watch": "🔎",
    "entry_pending": "✨",
    "buy-pending": "✨",
    "preliminary_buy": "✨",
    "entered": "✅",
    "holding": "✅",
    "confirmed_buy": "✅",
    "partial_exit_pending": "⏳",
    "partially_exited": "💰",
    "partial_sell": "💰",
    "full_exit_pending": "⚠️",
    "sell-pending": "⚠️",
    "preliminary_sell": "⚠️",
    "exited": "🚨",
    "sold": "🚨",
    "confirmed_sell": "🚨",
}
SIGNAL_NOTIFICATION_TITLE_PATTERN = re.compile(r"^\S*\s*\[[^\]]+\]\s*(.+)$")


def _signal_notification_icon(state: str) -> str:
    if state.startswith("partial-sell-pending-"):
        return "⏳"
    if state.startswith("partial-sold-"):
        return "💰"
    return SIGNAL_NOTIFICATION_ICON_BY_STATE.get(state, "🔔")


def _signal_notification_title(name: str, label: str, state: str) -> str:
    return f"{_signal_notification_icon(state)} [{label}] {name}"


def notification_history_signal_name(title: str) -> str:
    """Read stock names from both the current and legacy signal title formats."""

    normalized = str(title or "").strip()
    current_match = SIGNAL_NOTIFICATION_TITLE_PATTERN.fullmatch(normalized)
    if current_match:
        return current_match.group(1).strip()
    return normalized.split(" 시장 AI 시그널", 1)[0].split(" AI 시그널", 1)[0].strip()


def notification_history_event_date(kind: str, event_key: str) -> Optional[date]:
    if kind not in MARKET_NOTIFICATION_KINDS:
        return None
    pattern = PRICE_EVENT_DATE_PATTERN if kind == "price_move" else SIGNAL_EVENT_DATE_PATTERN
    match = pattern.search(event_key or "")
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def notification_history_signal_context(
    kind: str,
    event_key: str,
) -> Optional[dict[str, str]]:
    """Return public, structured signal metadata without exposing event keys."""

    if kind not in SIGNAL_NOTIFICATION_KINDS:
        return None
    market_match = MARKET_PRELIMINARY_SIGNAL_EVENT_PATTERN.fullmatch(event_key or "")
    if market_match:
        code, side, event_date = market_match.groups()
        return {
            "code": code,
            "side": side,
            "phase": "preliminary",
            "action": "entry_pending" if side == "buy" else "full_exit_pending",
            "event_date": event_date,
        }
    watchlist_match = WATCHLIST_SIGNAL_EVENT_PATTERN.fullmatch(event_key or "")
    if not watchlist_match:
        return None
    code, action, event_date = watchlist_match.groups()
    preliminary = action in {
        "entry_watch",
        "entry_pending",
        "partial_exit_pending",
        "full_exit_pending",
    }
    return {
        "code": code,
        "side": "buy" if action in {"entry_watch", "entry_pending", "entered"} else "sell",
        "phase": "preliminary" if preliminary else "confirmed",
        "action": action,
        "event_date": event_date,
    }


def notification_history_is_valid(
    kind: str,
    event_key: str,
    created_at: datetime,
) -> bool:
    if kind not in MARKET_NOTIFICATION_KINDS:
        return True
    event_date = notification_history_event_date(kind, event_key)
    if event_date is None:
        return False
    received_at = created_at
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    return event_date.weekday() < 5 and event_date == received_at.astimezone(KST).date()


def _prune_invalid_signal_notification_history(db: Session) -> int:
    rows = list(
        db.execute(
            select(
                PushNotificationHistory.id,
                PushNotificationHistory.notification_kind,
                PushNotificationHistory.event_key,
                PushNotificationHistory.created_at,
            ).where(PushNotificationHistory.notification_kind.in_(MARKET_NOTIFICATION_KINDS))
        ).all()
    )
    invalid_ids = [
        row.id
        for row in rows
        if not notification_history_is_valid(
            row.notification_kind,
            row.event_key,
            row.created_at,
        )
    ]
    if invalid_ids:
        db.execute(
            delete(PushNotificationHistory).where(PushNotificationHistory.id.in_(invalid_ids))
        )
    return len(invalid_ids)


@dataclass(frozen=True)
class NotificationCandidate:
    event_key: str
    kind: str
    title: str
    body: str
    url: str
    tag: str
    occurred_at: Optional[datetime] = None
    stock_codes: tuple[str, ...] = ()
    ttl_seconds: int = PUSH_DELIVERY_TTL_SECONDS
    predecessor_event_key: Optional[str] = None


@dataclass(frozen=True)
class RecommendationAlertItem:
    code: str
    name: str
    rank: int
    score_text: str
    decision: str
    signal_state: str
    signal_label: Optional[str]
    signal_detail: str
    predecessor_event_key: Optional[str]


def subscription_conditions(subscription: PushSubscription) -> set[str]:
    raw = subscription.notification_preferences
    if not raw:
        return set(DEFAULT_PUSH_CONDITIONS)
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return set(DEFAULT_PUSH_CONDITIONS)
    if not isinstance(parsed, list):
        return set(DEFAULT_PUSH_CONDITIONS)
    allowed = set(DEFAULT_PUSH_CONDITIONS)
    parsed_values = {str(item) for item in parsed}
    normalized = {item for item in parsed_values if item in allowed}
    if LEGACY_DEFAULT_PUSH_CONDITIONS.issubset(parsed_values):
        normalized.update({"market_ai_signal", "market_session"})
    return REQUIRED_PUSH_CONDITIONS | (normalized or set(DEFAULT_PUSH_CONDITIONS))


def candidate_enabled(subscription: PushSubscription, candidate: NotificationCandidate) -> bool:
    if candidate.kind == "test":
        return True
    condition = PUSH_KIND_TO_CONDITION.get(candidate.kind)
    if not condition:
        return True
    return condition in subscription_conditions(subscription)


def _signal_date(value: object) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


PROFIT_STAGE_PATTERN = re.compile(r"(\d+)\s*차\s*수익확정")
ORDERED_AFTER_MARKET_ACTIONS = frozenset(
    {
        "entered",
        "holding",
        "partial_exit_pending",
        "partially_exited",
        "full_exit_pending",
        "exited",
    }
)


def _profit_steps_total(current: dict[str, object]) -> int:
    try:
        return max(1, int(current.get("profit_steps_total") or 3))
    except (TypeError, ValueError):
        return 3


def _bounded_profit_stage(value: object, total: int) -> Optional[int]:
    try:
        stage = int(value)
    except (TypeError, ValueError):
        return None
    if stage < 1:
        return None
    return min(stage, total)


def _profit_stage_from_label(value: object, total: int) -> Optional[int]:
    match = PROFIT_STAGE_PATTERN.search(str(value or ""))
    return _bounded_profit_stage(match.group(1), total) if match else None


def _pending_profit_stage(current: dict[str, object]) -> int:
    total = _profit_steps_total(current)
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    explicit = _bounded_profit_stage(current.get("pending_profit_stage"), total)
    if explicit is not None:
        return explicit
    for value in (current.get("label"), lifecycle.get("label")):
        stage = _profit_stage_from_label(value, total)
        if stage is not None:
            return stage
    reasons = current.get("reasons") if isinstance(current.get("reasons"), list) else []
    for reason in reasons:
        stage = _profit_stage_from_label(reason, total)
        if stage is not None:
            return stage
    try:
        completed_stage = max(0, int(current.get("profit_stage") or 0))
    except (TypeError, ValueError):
        completed_stage = 0
    return min(total, max(1, completed_stage + 1))


def _confirmed_profit_stage(
    current: dict[str, object],
    transition: dict[str, object],
) -> int:
    total = _profit_steps_total(current)
    for value in (
        transition.get("profit_stage"),
        _profit_stage_from_label(transition.get("label"), total),
        current.get("profit_stage"),
        _profit_stage_from_label(current.get("label"), total),
    ):
        stage = _bounded_profit_stage(value, total)
        if stage is not None:
            return stage
    return 1


def _same_day_market_predecessor_event_key(
    code: str,
    current: dict[str, object],
    now: datetime,
) -> Optional[str]:
    action = str(current.get("action") or "").strip()
    if action not in ORDERED_AFTER_MARKET_ACTIONS:
        return None
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    transition = (
        lifecycle.get("latest_transition")
        if isinstance(lifecycle.get("latest_transition"), dict)
        else {}
    )
    transition_at = _signal_date(transition.get("transition_date"))
    current_date = now.astimezone(KST).date() if now.tzinfo else now.date()
    if transition_at is None or transition_at.date() != current_date:
        return None
    event_side = str(transition.get("side") or "").strip()
    if event_side not in {"buy", "partial_sell", "sell"}:
        return None
    return f"market-ai-signal:{code}:{event_side}:{current_date.isoformat()}"


def _ai_signal_candidate(
    item: WatchlistItem,
    payload: Optional[dict[str, object]],
    now: datetime,
) -> Optional[NotificationCandidate]:
    current = payload.get("current") if payload else None
    if not isinstance(current, dict):
        return None
    action = str(current.get("action") or "")
    intraday_preliminary = bool(current.get("live_observation")) and action in {
        "entry_pending",
        "partial_exit_pending",
        "full_exit_pending",
    }
    preliminary = action == "entry_watch" or intraday_preliminary
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    transition = lifecycle.get("latest_transition") if isinstance(lifecycle.get("latest_transition"), dict) else {}
    transition_label = str(transition.get("label") or "")
    effective_action = (
        "exited"
        if action == "entry_pending" and not preliminary and any(token in transition_label for token in ("매도", "청산"))
        else action
    )
    pending_profit_stage = _pending_profit_stage(current)
    confirmed_profit_stage = _confirmed_profit_stage(current, transition)
    partial_transition_label = (
        transition_label
        if "수익확정" in transition_label
        else f"{confirmed_profit_stage}차 수익확정"
    )
    signal_labels = {
        "entry_watch": "예비 포착",
        "entry_pending": "예비 매수",
        "entered": "매수 확정",
        "partial_exit_pending": f"{pending_profit_stage}차 수익확정 대기",
        "partially_exited": partial_transition_label,
        "full_exit_pending": "전량 매도 대기",
        "exited": "전량 매도",
    }
    label = signal_labels.get(effective_action)
    if not label:
        return None
    completed = effective_action in {"entered", "partially_exited", "exited"}
    basis_value = (
        current.get("as_of")
        if intraday_preliminary
        else transition.get("transition_date") if completed else payload.get("price_through")
    )
    basis = _signal_date(basis_value)
    if basis is None or basis.date() != now.date():
        return None
    detail = str(current.get("next_confirmation") or "종목 상세에서 시그널 기준을 확인하세요.")
    return NotificationCandidate(
        event_key=f"ai-signal:{item.code}:{effective_action}:{basis.date().isoformat()}",
        kind="ai_signal",
        title=_signal_notification_title(item.name, label, effective_action),
        body=f"{detail} 장 마감 전에는 바뀔 수 있어요." if intraday_preliminary else detail,
        url=_stock_url(item.name),
        tag=f"ai-signal-{item.code}",
        occurred_at=now,
        stock_codes=(item.code,),
    )


def _stock_url(name: str) -> str:
    return f"/dashboard/{quote(name, safe='')}"


def _is_important_disclosure(item: DisclosureItem) -> bool:
    if item.disclosure_category in IMPORTANT_DISCLOSURE_CATEGORIES:
        return True
    return any(keyword in item.report_name for keyword in IMPORTANT_DISCLOSURE_KEYWORDS)


def _price_candidate(
    item: WatchlistItem,
    snapshot: dict[str, object],
    now: datetime,
    threshold: Decimal,
) -> Optional[NotificationCandidate]:
    raw_rate = snapshot.get("change_rate_abs")
    if raw_rate is None:
        return None
    change_rate = Decimal(str(raw_rate))
    if abs(change_rate) < threshold:
        return None
    direction = "rise" if change_rate > 0 else "fall"
    direction_label = "급등" if change_rate > 0 else "급락"
    price = snapshot.get("price")
    price_text = f" · {int(price):,}원" if price is not None else ""
    return NotificationCandidate(
        event_key=f"price:{now.date().isoformat()}:{item.code}:{direction}:{threshold}",
        kind="price_move",
        title=f"{item.name} {direction_label} {change_rate:+.2f}%",
        body=f"관심종목 변동이 {threshold:.0f}% 기준을 넘었습니다{price_text}.",
        url=_stock_url(item.name),
        tag=f"price-{item.code}-{direction}",
        occurred_at=now,
        stock_codes=(item.code,),
    )


def _report_candidate(item: ResearchReport, stock_name: str) -> NotificationCandidate:
    details = [item.broker_name or "증권사 리포트"]
    if item.opinion:
        details.append(item.opinion)
    if item.target_price:
        details.append(f"목표가 {int(item.target_price):,}원")
    return NotificationCandidate(
        event_key=f"report:{item.source}:{item.external_id}",
        kind="report",
        title=f"{stock_name} 새 애널리스트 리포트",
        body=f"{' · '.join(details)} | {item.title}",
        url=_stock_url(stock_name),
        tag=f"report-{item.stock_code or item.external_id}",
        occurred_at=item.updated_at,
        stock_codes=(item.stock_code,) if item.stock_code else (),
    )


def _recommendation_score_text(value: object) -> str:
    try:
        score = Decimal(str(value))
    except Exception:
        return "-"
    if not score.is_finite():
        return "-"
    if score == score.to_integral_value():
        return str(int(score))
    return f"{score:.1f}"


def _recommendation_signal_state(item: dict[str, object]) -> tuple[str, Optional[str], str]:
    signal = item.get("ai_trade_signal")
    current = signal.get("current") if isinstance(signal, dict) else None
    if not isinstance(current, dict):
        return "unavailable", None, "종목 상세에서 최신 AI 판단을 확인하세요."

    action = str(current.get("action") or "unavailable").strip() or "unavailable"
    lifecycle = current.get("lifecycle") if isinstance(current.get("lifecycle"), dict) else {}
    transition = (
        lifecycle.get("latest_transition")
        if isinstance(lifecycle.get("latest_transition"), dict)
        else {}
    )
    detail = str(current.get("next_confirmation") or "종목 상세에서 다음 확인 조건을 확인하세요.")

    if action == "entry_pending":
        return "buy-pending", "예비 매수", detail
    if action in {"entered", "holding"}:
        return "holding", "매수 확정·보유", detail
    if action == "partial_exit_pending":
        stage = _pending_profit_stage(current)
        return f"partial-sell-pending-{stage}", f"{stage}차 수익확정 대기", detail
    if action == "partially_exited":
        stage = _confirmed_profit_stage(current, transition)
        return f"partial-sold-{stage}", f"{stage}차 수익확정", detail
    if action == "full_exit_pending":
        return "sell-pending", "전량 매도 대기", detail
    if action == "exited":
        return "sold", "전량 매도", detail
    return action.replace(":", "-")[:80], None, detail


def _recommendation_alert_items(
    payload: object,
    now: datetime,
) -> list[RecommendationAlertItem]:
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        return []
    output: list[RecommendationAlertItem] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            continue
        code = str(raw_item.get("code") or "").strip()
        name = str(raw_item.get("name") or code).strip()
        if not code or not name or code in seen:
            continue
        seen.add(code)
        try:
            rank = max(1, int(raw_item.get("rank") or (index + 1)))
        except (TypeError, ValueError):
            rank = index + 1
        signal = raw_item.get("ai_trade_signal")
        signal_current = signal.get("current") if isinstance(signal, dict) else None
        signal_state, signal_label, signal_detail = _recommendation_signal_state(raw_item)
        output.append(
            RecommendationAlertItem(
                code=code,
                name=name,
                rank=rank,
                score_text=_recommendation_score_text(raw_item.get("score")),
                decision=str(raw_item.get("action") or "").strip(),
                signal_state=signal_state,
                signal_label=signal_label,
                signal_detail=signal_detail,
                predecessor_event_key=_same_day_market_predecessor_event_key(
                    code,
                    signal_current if isinstance(signal_current, dict) else {},
                    now,
                ),
            )
        )
        if len(output) >= RECOMMENDATION_PUSH_LIMIT:
            break
    return output


def _recommendation_detail_url(code: str) -> str:
    return f"/dashboard?view=recommend-detail&code={quote(code, safe='')}"


def _recommendation_entry_candidate(
    item: RecommendationAlertItem,
    now: datetime,
) -> NotificationCandidate:
    details = [f"현재 {item.rank}위", f"추천 점수 {item.score_text}점"]
    if item.decision:
        details.append(item.decision)
    return NotificationCandidate(
        event_key=f"recommendation-entry:{item.code}:{now.date().isoformat()}",
        kind="recommendation_update",
        title=f"{item.name} 추천 상위 10 신규 진입",
        body=f"{' · '.join(details)}. 추천 근거를 확인하세요.",
        url=_recommendation_detail_url(item.code),
        tag=f"recommendation-entry-{item.code}",
        occurred_at=now,
        stock_codes=(item.code,),
    )


def _recommendation_signal_candidate(
    item: RecommendationAlertItem,
    now: datetime,
) -> Optional[NotificationCandidate]:
    if not item.signal_label:
        return None
    return NotificationCandidate(
        event_key=(
            f"recommendation-signal:{item.code}:{item.signal_state}:"
            f"{now.date().isoformat()}"
        ),
        kind="recommendation_update",
        title=_signal_notification_title(item.name, item.signal_label, item.signal_state),
        body=item.signal_detail,
        url=_recommendation_detail_url(item.code),
        tag=f"recommendation-signal-{item.code}",
        occurred_at=now,
        stock_codes=(item.code,),
        predecessor_event_key=item.predecessor_event_key,
    )


def _recommendation_batch_candidate(
    candidates: list[NotificationCandidate],
    now: datetime,
) -> NotificationCandidate:
    representative = candidates[0]
    additional_count = len(candidates) - 1
    representative_name = representative.title.split(" 추천", 1)[0]
    if representative_name == representative.title:
        representative_name = notification_history_signal_name(representative.title)
    digest_source = "|".join(sorted(candidate.event_key for candidate in candidates))
    digest = hashlib.sha256(digest_source.encode("utf-8")).hexdigest()[:16]
    stock_codes = tuple(
        dict.fromkeys(
            code
            for candidate in candidates
            for code in candidate.stock_codes
        )
    )
    return NotificationCandidate(
        event_key=f"recommendation-batch:{now.date().isoformat()}:{digest}",
        kind="recommendation_update",
        title=f"{representative_name} 외 {additional_count}건의 추천종목이 업데이트되었어요",
        body=(
            f"추천종목 {len(candidates)}건이 변경되었어요. "
            f"{representative_name}의 상세에서 변경 내용을 확인하세요."
        ),
        url=representative.url,
        tag=f"recommendation-batch-{now.date().isoformat()}-{digest}",
        occurred_at=now,
        stock_codes=stock_codes,
    )


def _disclosure_candidate(item: DisclosureItem, stock_name: str) -> NotificationCandidate:
    return NotificationCandidate(
        event_key=f"disclosure:{item.source}:{item.external_id}",
        kind="disclosure",
        title=f"{stock_name} 중요 공시",
        body=item.report_name,
        url=_stock_url(stock_name),
        tag=f"disclosure-{item.stock_code or item.external_id}",
        occurred_at=item.updated_at,
        stock_codes=(item.stock_code,) if item.stock_code else (),
    )


class WebPushRuntime:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.task: Optional[asyncio.Task] = None
        self.running = False
        self.last_success_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_recommendation_scan_at: Optional[datetime] = None

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.web_push_enabled
            and self.settings.web_push_vapid_private_key
            and self.settings.web_push_vapid_public_key
        )

    async def start(self) -> None:
        if self.running or not self.configured:
            return
        self.running = True
        self.task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _loop(self) -> None:
        while self.running:
            try:
                await asyncio.to_thread(self.run_once)
                self.last_success_at = datetime.utcnow()
                self.last_error = None
            except Exception as exc:  # pragma: no cover - operational safeguard
                self.last_error = str(exc)
                logger.exception("Web push scan failed")
            await asyncio.sleep(max(30, self.settings.web_push_poll_seconds))

    def _quote_snapshots(self, codes: set[str]) -> dict[str, dict[str, object]]:
        if not codes:
            return {}
        output: dict[str, dict[str, object]] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(codes))) as executor:
            futures = {executor.submit(_naver_snapshot, code, True): code for code in codes}
            for future in as_completed(futures):
                try:
                    output[futures[future]] = future.result()
                except Exception:
                    continue
        return output

    @staticmethod
    def _morning_briefing_candidates(now: datetime) -> list[NotificationCandidate]:
        """Create the KST 08:00, 12:00, and 16:00 edition alert once per device."""

        current = now.astimezone(KST) if now.tzinfo else now.replace(tzinfo=KST)
        for starts_at, ends_at, edition, notification_title, body in MONEY_BRIEFING_PUSH_WINDOWS:
            if not starts_at <= current.time() < ends_at:
                continue
            publication_date = current.date().isoformat()
            legacy_morning = edition == "morning"
            event_suffix = "" if legacy_morning else f":{starts_at.hour:02d}"
            tag_suffix = "" if legacy_morning else f"-{starts_at.hour:02d}"
            return [
                NotificationCandidate(
                    event_key=f"morning-briefing:{publication_date}{event_suffix}",
                    kind="morning_briefing",
                    title=notification_title,
                    body=body,
                    url="/dashboard?view=morning-briefing",
                    tag=f"morning-briefing-{publication_date}{tag_suffix}",
                    occurred_at=current,
                    ttl_seconds=MONEY_BRIEFING_PUSH_TTL_SECONDS,
                )
            ]
        return []

    @staticmethod
    def _market_session_candidates(now: datetime) -> list[NotificationCandidate]:
        """Create one short-lived reminder during each five-minute market lead window."""
        current = now.astimezone(KST) if now.tzinfo else now.replace(tzinfo=KST)
        if not is_korea_market_session_date(current.date(), current):
            return []

        windows = (
            (
                time(8, 55),
                time(9, 0),
                "open",
                "국내장 시작 5분 전",
                "잠시 뒤 국내 정규장이 시작돼요",
            ),
            (
                time(15, 25),
                time(15, 30),
                "close",
                "국내장 마감 5분 전",
                "잠시 뒤 국내 정규장이 마감돼요",
            ),
        )
        for starts_at, ends_at, session, title, body in windows:
            if starts_at <= current.time() < ends_at:
                session_date = current.date().isoformat()
                return [
                    NotificationCandidate(
                        event_key=f"market-session:{session}:{session_date}",
                        kind="market_session",
                        title=title,
                        body=body,
                        url="/dashboard?view=home",
                        tag=f"market-session-{session}-{session_date}",
                        occurred_at=current,
                    )
                ]
        return []

    def _content_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
    ) -> dict[str, list[NotificationCandidate]]:
        all_codes = {item.code for items in watchlists.values() for item in items}
        output = {share_id: [] for share_id in watchlists}
        if not all_codes:
            return output
        cutoff = now - timedelta(hours=24)
        reports = list(
            db.scalars(
                select(ResearchReport)
                .where(ResearchReport.stock_code.in_(all_codes))
                .where(ResearchReport.updated_at >= cutoff)
                .order_by(ResearchReport.updated_at.desc())
                .limit(200)
            )
        )
        disclosures = list(
            db.scalars(
                select(DisclosureItem)
                .where(DisclosureItem.stock_code.in_(all_codes))
                .where(DisclosureItem.updated_at >= cutoff)
                .order_by(DisclosureItem.updated_at.desc())
                .limit(200)
            )
        )
        for share_id, items in watchlists.items():
            names = {item.code: item.name for item in items}
            output[share_id].extend(
                _report_candidate(report, names[report.stock_code])
                for report in reports
                if report.stock_code in names
            )
            output[share_id].extend(
                _disclosure_candidate(disclosure, names[disclosure.stock_code])
                for disclosure in disclosures
                if disclosure.stock_code in names and _is_important_disclosure(disclosure)
            )
        return output

    def _event_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
    ) -> dict[str, list[NotificationCandidate]]:
        output = {share_id: [] for share_id in watchlists}
        analysis = build_trend_analysis(db, days=7)
        lead_time = timedelta(hours=max(1, self.settings.web_push_event_lead_hours))
        stocks = {
            stock.code: stock
            for stock in db.scalars(
                select(StockMaster).where(
                    StockMaster.code.in_({item.code for items in watchlists.values() for item in items})
                )
            )
        }
        for event in analysis.get("events", []):
            starts_at = event.get("starts_at")
            if not isinstance(starts_at, datetime) or starts_at < now or starts_at - now > lead_time:
                continue
            if event.get("importance") not in {"중요", "매우 중요"}:
                continue
            template, _ = _template_by_id(str(event.get("id") or ""))
            if template is None:
                continue
            for share_id, items in watchlists.items():
                matched_names = []
                matched_codes = []
                for item in items:
                    stock = stocks.get(item.code)
                    if stock and _matched_template_sectors(template, _stock_sectors(stock)):
                        matched_names.append(item.name)
                        matched_codes.append(item.code)
                if not matched_names:
                    continue
                names_text = ", ".join(matched_names[:3])
                if len(matched_names) > 3:
                    names_text += f" 외 {len(matched_names) - 3}개"
                output[share_id].append(
                    NotificationCandidate(
                        event_key=f"event:{event['id']}",
                        kind="major_event",
                        title=f"주요 이벤트 임박 · {event['title']}",
                        body=f"{names_text}에 영향을 줄 수 있습니다. 발표 전 확인하세요.",
                        url="/dashboard?view=trend",
                        tag=f"event-{event['id']}",
                        occurred_at=now,
                        stock_codes=tuple(matched_codes),
                    )
                )
        return output

    def _ai_signal_candidates(
        self,
        db: Session,
        watchlists: dict[str, list[WatchlistItem]],
        now: datetime,
        live_quotes: Optional[dict[str, dict[str, object]]] = None,
    ) -> dict[str, list[NotificationCandidate]]:
        output = {share_id: [] for share_id in watchlists}
        confirmed_window = is_korea_daily_signal_window(now)
        preliminary_window = not confirmed_window and is_korea_regular_market_session(now)
        if not confirmed_window and not preliminary_window:
            return output
        quotes = live_quotes or {}
        payloads: dict[str, Optional[dict[str, object]]] = {}
        for items in watchlists.values():
            for item in items:
                if item.code not in payloads:
                    try:
                        signal_kwargs = {
                            "live_quote": quotes.get(item.code) if preliminary_window else None,
                            "now": now,
                            "include_context": False,
                            "include_stored_intraday": preliminary_window,
                        }
                        if self.settings.market_quant_signal_source_url:
                            payloads[item.code] = load_reference_quant_signal_payload(
                                db,
                                item.code,
                                source_url=self.settings.market_quant_signal_source_url,
                                source_timeout_seconds=self.settings.market_quant_signal_source_timeout_seconds,
                                **signal_kwargs,
                            )
                        else:
                            local_payload = load_quant_signal_payload(
                                db,
                                item.code,
                                **signal_kwargs,
                            )
                            payloads[item.code] = apply_stock_signal_reconciliations(
                                local_payload,
                                now=now,
                            )
                    except Exception:
                        logger.exception("AI signal calculation failed for %s", item.code)
                        payloads[item.code] = None
        for share_id, items in watchlists.items():
            for item in items:
                candidate = _ai_signal_candidate(item, payloads.get(item.code), now)
                if candidate:
                    output[share_id].append(candidate)
        return output

    def _market_ai_signal_candidates(
        self,
        db: Session,
        now: Optional[datetime] = None,
    ) -> list[NotificationCandidate]:
        current = now or datetime.now(KST)
        confirmed_window = is_korea_daily_signal_window(current)
        preliminary_window = not confirmed_window and is_korea_regular_market_session(current)
        if not confirmed_window and not preliminary_window:
            return []
        current_date = current.date()
        snapshot = load_external_market_quant_signal_feed(
            self.settings.market_quant_signal_source_url,
            universe_limit=MARKET_SIGNAL_UNIVERSE_LIMIT,
            limit=0,
            recent_days=30,
            timeout_seconds=self.settings.market_quant_signal_source_timeout_seconds,
        )
        if snapshot is None:
            snapshot = load_market_quant_signal_snapshot(
                db,
                universe_limit=MARKET_SIGNAL_UNIVERSE_LIMIT,
                limit=0,
                recent_days=30,
            )
        if not snapshot:
            return []
        snapshot = apply_market_signal_reconciliations(snapshot, now=current) or snapshot
        candidates: list[NotificationCandidate] = []
        for item in snapshot.get("items") or []:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            name = str(item.get("name") or code).strip()
            side = str(item.get("side") or "").strip()
            preliminary = bool(item.get("is_preliminary")) or item.get("status") == "preliminary"
            if preliminary:
                if not preliminary_window:
                    continue
                signal_date = str(item.get("signal_date") or "").strip()
                try:
                    preliminary_date = date.fromisoformat(signal_date)
                except ValueError:
                    continue
                if preliminary_date != current_date or not code or side not in {"buy", "sell"}:
                    continue
                action = "예비 매수" if side == "buy" else "예비 매도"
                notification_state = "preliminary_buy" if side == "buy" else "preliminary_sell"
                candidates.append(
                    NotificationCandidate(
                        event_key=f"market-ai-preliminary:{code}:{side}:{signal_date}",
                        kind="market_ai_signal",
                        title=_signal_notification_title(name, action, notification_state),
                        body=f"{current.strftime('%H:%M')} 기준 장중 관찰 신호예요. 15:40 확정 전에는 바뀔 수 있어요.",
                        url=_stock_url(name),
                        tag=f"market-ai-signal-{code}",
                        occurred_at=current,
                        stock_codes=(code,),
                    )
                )
                continue
            if not confirmed_window:
                continue
            execution_date = str(item.get("execution_date") or "").strip()
            event_side = str(item.get("event_side") or side).strip()
            if not code or side not in {"buy", "sell"} or not execution_date:
                continue
            try:
                signal_date = date.fromisoformat(execution_date)
            except ValueError:
                continue
            # Confirmed notifications announce only the transition that executes
            # today. Intraday preliminary candidates use a separate key above.
            if signal_date != current_date:
                continue
            action = (
                str(item.get("signal") or "수익확정")
                if event_side == "partial_sell"
                else "매수 확정" if side == "buy" else "전량 매도"
            )
            notification_state = (
                "partial_sell"
                if event_side == "partial_sell"
                else "confirmed_buy" if side == "buy" else "confirmed_sell"
            )
            candidates.append(
                NotificationCandidate(
                    event_key=f"market-ai-signal:{code}:{event_side}:{execution_date}",
                    kind="market_ai_signal",
                    title=_signal_notification_title(name, action, notification_state),
                    body=f"{execution_date} {action} 신호예요. 종목 상세에서 가격과 기준을 확인하세요.",
                    url=_stock_url(name),
                    tag=f"market-ai-signal-{code}",
                )
            )
        return candidates

    def _recommendation_snapshot(
        self,
        db: Session,
        now: datetime,
    ) -> Optional[dict[str, object]]:
        interval = max(60, int(self.settings.web_push_recommendation_poll_seconds))
        if (
            self.last_recommendation_scan_at is not None
            and (now - self.last_recommendation_scan_at).total_seconds() < interval
        ):
            return None
        self.last_recommendation_scan_at = now
        try:
            return build_recommendations(
                db,
                limit=RECOMMENDATION_PUSH_LIMIT,
                candidate_limit=45,
                refresh_live=False,
                ensure_signal_history=False,
            )
        except Exception:
            logger.exception("Recommendation push scan failed")
            return None

    @staticmethod
    def _recommendation_state_namespace(subscription: PushSubscription) -> str:
        preference_epoch = (subscription.updated_at or subscription.created_at).isoformat(
            timespec="microseconds"
        )
        return f"recommendation-state:{subscription.id}:{preference_epoch}"

    def _recommendation_state(
        self,
        db: Session,
        subscription: PushSubscription,
    ) -> tuple[bool, set[str], dict[str, str]]:
        namespace = self._recommendation_state_namespace(subscription)
        initialized_key = f"{namespace}:initialized"
        member_prefix = f"{namespace}:member:"
        signal_prefix = f"{namespace}:signal:"
        event_keys = list(
            db.scalars(
                select(PushDelivery.event_key).where(
                    PushDelivery.subscription_id == subscription.id,
                    PushDelivery.notification_kind == RECOMMENDATION_STATE_KIND,
                    PushDelivery.status == "baseline",
                )
            )
        )
        initialized = initialized_key in event_keys
        codes = {
            event_key.removeprefix(member_prefix)
            for event_key in event_keys
            if event_key.startswith(member_prefix)
        }
        signal_states: dict[str, str] = {}
        for event_key in event_keys:
            if not event_key.startswith(signal_prefix):
                continue
            remainder = event_key.removeprefix(signal_prefix)
            code, separator, state = remainder.partition(":")
            if separator and code and state:
                signal_states[code] = state
        return initialized, codes, signal_states

    def _replace_recommendation_state(
        self,
        db: Session,
        subscription: PushSubscription,
        items: list[RecommendationAlertItem],
    ) -> None:
        namespace = self._recommendation_state_namespace(subscription)
        db.execute(
            delete(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.notification_kind == RECOMMENDATION_STATE_KIND,
            )
        )
        db.flush()
        markers = [
            PushDelivery(
                subscription_id=subscription.id,
                event_key=f"{namespace}:initialized",
                notification_kind=RECOMMENDATION_STATE_KIND,
                title="추천 업데이트 알림 기준선",
                status="baseline",
                attempts=0,
            )
        ]
        for item in items:
            markers.extend(
                [
                    PushDelivery(
                        subscription_id=subscription.id,
                        event_key=f"{namespace}:member:{item.code}",
                        notification_kind=RECOMMENDATION_STATE_KIND,
                        title=f"{item.name} 추천 목록 기준선",
                        status="baseline",
                        attempts=0,
                    ),
                    PushDelivery(
                        subscription_id=subscription.id,
                        event_key=f"{namespace}:signal:{item.code}:{item.signal_state}",
                        notification_kind=RECOMMENDATION_STATE_KIND,
                        title=f"{item.name} 추천 AI 판단 기준선",
                        status="baseline",
                        attempts=0,
                    ),
                ]
            )
        db.add_all(markers)

    def _recommendation_changes(
        self,
        db: Session,
        subscription: PushSubscription,
        payload: dict[str, object],
        now: datetime,
    ) -> tuple[list[RecommendationAlertItem], list[NotificationCandidate], bool]:
        items = _recommendation_alert_items(payload, now)
        if not items:
            return [], [], False
        initialized, previous_codes, previous_signals = self._recommendation_state(
            db,
            subscription,
        )
        if not initialized:
            return items, [], False

        candidates: list[NotificationCandidate] = []
        for item in items:
            if item.code not in previous_codes:
                candidates.append(_recommendation_entry_candidate(item, now))
                continue
            if previous_signals.get(item.code) == item.signal_state:
                continue
            signal_candidate = _recommendation_signal_candidate(item, now)
            if signal_candidate:
                candidates.append(signal_candidate)
        return items, candidates, True

    @staticmethod
    def _recommendation_candidate_handled(
        db: Session,
        subscription: PushSubscription,
        candidate: NotificationCandidate,
    ) -> bool:
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        return bool(
            delivery
            and (
                delivery.status in {"sent", "baseline", "expired"}
                or delivery.attempts >= 3
            )
        )

    @staticmethod
    def _predecessor_delivery_ready(
        db: Session,
        subscription: PushSubscription,
        candidate: NotificationCandidate,
    ) -> bool:
        predecessor_key = candidate.predecessor_event_key
        if not predecessor_key:
            return True
        # Users who intentionally disabled the shared market-signal channel
        # must not lose recommendation updates.  When it is enabled,
        # however, a successor may never overtake its confirmed transition.
        if "market_ai_signal" not in subscription_conditions(subscription):
            return True
        predecessor = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == predecessor_key,
            )
        )
        if predecessor is None:
            return False
        if predecessor.status == "baseline":
            return True
        if predecessor.status != "sent" or predecessor.sent_at is None:
            return False

        attempt_at = candidate.occurred_at or datetime.now(KST)
        if attempt_at.tzinfo is None:
            attempt_at = attempt_at.replace(tzinfo=KST)
        attempt_utc = attempt_at.astimezone(timezone.utc).replace(tzinfo=None)
        predecessor_sent_at = predecessor.sent_at
        if predecessor_sent_at.tzinfo is not None:
            predecessor_sent_at = predecessor_sent_at.astimezone(timezone.utc).replace(tzinfo=None)
        return attempt_utc - predecessor_sent_at >= SIGNAL_SUCCESSOR_DELAY

    def _process_recommendation_updates(
        self,
        db: Session,
        subscription: PushSubscription,
        payload: dict[str, object],
        now: datetime,
    ) -> int:
        items, candidates, initialized = self._recommendation_changes(
            db,
            subscription,
            payload,
            now,
        )
        if not items:
            return 0
        if not initialized:
            self._replace_recommendation_state(db, subscription, items)
            db.commit()
            return 0

        if len(candidates) >= RECOMMENDATION_BATCH_THRESHOLD:
            # Keep recommendation updates behind every required market-signal
            # predecessor before collapsing them into one customer-facing push.
            # Otherwise the summary could overtake a signal notification that
            # is intentionally waiting for its provider TTL to elapse.
            if any(
                not self._predecessor_delivery_ready(db, subscription, candidate)
                for candidate in candidates
            ):
                return 0
            candidates = [_recommendation_batch_candidate(candidates, now)]

        sent = 0
        handled = True
        for candidate in candidates:
            delivered = self._send(db, subscription, candidate)
            sent += int(delivered)
            handled = handled and (
                delivered
                or self._recommendation_candidate_handled(db, subscription, candidate)
            )
        if handled:
            self._replace_recommendation_state(db, subscription, items)
            db.commit()
        return sent

    def _send(self, db: Session, subscription: PushSubscription, candidate: NotificationCandidate) -> bool:
        if not candidate_enabled(subscription, candidate):
            return False
        if not self._predecessor_delivery_ready(db, subscription, candidate):
            return False
        if candidate.kind in {"report", "disclosure"} and candidate.occurred_at:
            if candidate.occurred_at < subscription.created_at:
                return False
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        if delivery and (delivery.status in {"sent", "baseline"} or delivery.attempts >= 3):
            return False
        if delivery is None:
            delivery = PushDelivery(
                subscription_id=subscription.id,
                event_key=candidate.event_key,
                notification_kind=candidate.kind,
                title=candidate.title,
                status="pending",
            )
            try:
                with db.begin_nested():
                    db.add(delivery)
                    db.flush()
            except IntegrityError:
                # Another collector already claimed this subscription/event.
                return False
        delivery.attempts = (delivery.attempts or 0) + 1
        payload = json.dumps(
            {
                "title": candidate.title,
                "body": candidate.body,
                "url": candidate.url,
                "tag": candidate.tag,
                "kind": candidate.kind,
            },
            ensure_ascii=False,
        )
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=payload,
                vapid_private_key=self.settings.web_push_vapid_private_key,
                vapid_claims={"sub": self.settings.web_push_vapid_subject},
                content_encoding=subscription.content_encoding,
                ttl=max(0, candidate.ttl_seconds),
                timeout=12,
                headers=PUSH_DELIVERY_HEADERS,
            )
            delivery.status = "sent"
            delivery.sent_at = datetime.utcnow()
            delivery.error = None
            history_cutoff = datetime.utcnow() - NOTIFICATION_HISTORY_RETENTION
            db.execute(
                delete(PushNotificationHistory).where(
                    PushNotificationHistory.created_at < history_cutoff
                )
            )
            history = db.scalar(
                select(PushNotificationHistory).where(
                    PushNotificationHistory.share_id == subscription.share_id,
                    PushNotificationHistory.event_key == candidate.event_key,
                )
            )
            if history is None:
                db.add(
                    PushNotificationHistory(
                        share_id=subscription.share_id,
                        event_key=candidate.event_key,
                        notification_kind=candidate.kind,
                        title=candidate.title,
                        body=candidate.body,
                        url=candidate.url,
                    )
                )
            db.commit()
            return True
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            delivery.status = "expired" if status_code in {404, 410} else "failed"
            delivery.error = str(exc)[:2000]
            if status_code in {404, 410}:
                subscription.enabled = False
            db.commit()
            return False
        except Exception as exc:
            delivery.status = "failed"
            delivery.error = str(exc)[:2000]
            db.commit()
            return False

    @staticmethod
    def _baseline_marker_key(subscription: PushSubscription, item: WatchlistItem) -> str:
        subscription_epoch = subscription.created_at.isoformat(timespec="microseconds")
        watch_epoch = item.created_at.isoformat(timespec="microseconds")
        return f"watch-baseline:{item.code}:{subscription_epoch}:{watch_epoch}"

    def _initialized_watch_codes(
        self,
        db: Session,
        subscription: PushSubscription,
        items: list[WatchlistItem],
    ) -> set[str]:
        marker_by_code = {
            item.code: self._baseline_marker_key(subscription, item)
            for item in items
        }
        if not marker_by_code:
            return set()
        existing = set(
            db.scalars(
                select(PushDelivery.event_key).where(
                    PushDelivery.subscription_id == subscription.id,
                    PushDelivery.event_key.in_(tuple(marker_by_code.values())),
                    PushDelivery.status == "baseline",
                )
            )
        )
        return {code for code, marker in marker_by_code.items() if marker in existing}

    @staticmethod
    def _record_candidate_baseline(
        db: Session,
        subscription: PushSubscription,
        candidate: NotificationCandidate,
    ) -> None:
        delivery = db.scalar(
            select(PushDelivery).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == candidate.event_key,
            )
        )
        if delivery is None:
            db.add(
                PushDelivery(
                    subscription_id=subscription.id,
                    event_key=candidate.event_key,
                    notification_kind=candidate.kind,
                    title=candidate.title,
                    status="baseline",
                    attempts=0,
                )
            )
        elif delivery.status not in {"sent", "baseline"}:
            delivery.status = "baseline"
            delivery.error = None

    def _mark_watchlist_initialized(
        self,
        db: Session,
        subscription: PushSubscription,
        items: list[WatchlistItem],
        initialized_codes: set[str],
    ) -> None:
        for item in items:
            if item.code in initialized_codes:
                continue
            db.add(
                PushDelivery(
                    subscription_id=subscription.id,
                    event_key=self._baseline_marker_key(subscription, item),
                    notification_kind="baseline",
                    title=f"{item.name} 알림 기준선",
                    status="baseline",
                    attempts=0,
                )
            )

    @staticmethod
    def _market_signal_baseline_marker_key(subscription: PushSubscription) -> str:
        preference_epoch = (subscription.updated_at or subscription.created_at).isoformat(
            timespec="microseconds"
        )
        return f"market-ai-baseline:{subscription.id}:{preference_epoch}"

    def _market_signal_initialized(
        self,
        db: Session,
        subscription: PushSubscription,
    ) -> bool:
        marker = self._market_signal_baseline_marker_key(subscription)
        return db.scalar(
            select(PushDelivery.id).where(
                PushDelivery.subscription_id == subscription.id,
                PushDelivery.event_key == marker,
                PushDelivery.status == "baseline",
            )
        ) is not None

    def _mark_market_signal_initialized(
        self,
        db: Session,
        subscription: PushSubscription,
    ) -> None:
        if self._market_signal_initialized(db, subscription):
            return
        db.add(
            PushDelivery(
                subscription_id=subscription.id,
                event_key=self._market_signal_baseline_marker_key(subscription),
                notification_kind="baseline",
                title="시장 AI 시그널 알림 기준선",
                status="baseline",
                attempts=0,
            )
        )

    def run_once(self) -> int:
        if not self.configured:
            return 0
        now_utc = datetime.utcnow()
        now_kst = datetime.now(KST).replace(tzinfo=None)
        with PushSessionLocal() as db:
            db.execute(
                delete(PushNotificationHistory).where(
                    PushNotificationHistory.created_at < now_utc - NOTIFICATION_HISTORY_RETENTION
                )
            )
            _prune_invalid_signal_notification_history(db)
            db.commit()
            subscriptions = list(
                db.scalars(
                    select(PushSubscription)
                    .where(PushSubscription.enabled.is_(True))
                    .order_by(PushSubscription.id)
                )
            )
            if not subscriptions:
                return 0
            recommendation_subscriptions = [
                subscription
                for subscription in subscriptions
                if "recommendation_update" in subscription_conditions(subscription)
            ]
            recommendation_snapshot = (
                self._recommendation_snapshot(db, now_kst)
                if recommendation_subscriptions
                else None
            )
            share_ids = sorted({item.share_id for item in subscriptions})
            watch_items = list(
                db.scalars(
                    select(WatchlistItem)
                    .where(WatchlistItem.share_id.in_(share_ids))
                    .order_by(WatchlistItem.share_id, WatchlistItem.sort_order)
                )
            )
            watchlists = {share_id: [] for share_id in share_ids}
            for item in watch_items:
                watchlists[item.share_id].append(item)

            regular_market_open = is_korea_regular_market_session(now_kst)
            snapshots = self._quote_snapshots({item.code for item in watch_items}) if regular_market_open else {}
            candidates_by_share = {share_id: [] for share_id in share_ids}
            threshold = Decimal(str(self.settings.web_push_price_threshold))
            if regular_market_open:
                for share_id, items in watchlists.items():
                    for item in items:
                        candidate = _price_candidate(item, snapshots.get(item.code, {}), now_kst, threshold)
                        if candidate:
                            candidates_by_share[share_id].append(candidate)
            for source in (
                self._ai_signal_candidates(db, watchlists, now_kst, snapshots),
                self._content_candidates(db, watchlists, now_utc),
                self._event_candidates(db, watchlists, now_kst),
            ):
                for share_id, candidates in source.items():
                    candidates_by_share[share_id].extend(candidates)

            market_signal_candidates = self._market_ai_signal_candidates(db, now_kst)
            morning_briefing_candidates = self._morning_briefing_candidates(now_kst)
            market_session_candidates = self._market_session_candidates(now_kst)

            sent = 0
            for subscription in subscriptions:
                items = watchlists.get(subscription.share_id, [])
                initialized_codes = self._initialized_watch_codes(db, subscription, items)
                for candidate in candidates_by_share.get(subscription.share_id, []):
                    related_codes = set(candidate.stock_codes)
                    if related_codes and not (related_codes & initialized_codes):
                        self._record_candidate_baseline(db, subscription, candidate)
                        continue
                    sent += int(self._send(db, subscription, candidate))
                self._mark_watchlist_initialized(db, subscription, items, initialized_codes)
                for candidate in morning_briefing_candidates:
                    sent += int(self._send(db, subscription, candidate))
                for candidate in market_session_candidates:
                    sent += int(self._send(db, subscription, candidate))
                if "market_ai_signal" in subscription_conditions(subscription):
                    if self._market_signal_initialized(db, subscription):
                        for candidate in market_signal_candidates:
                            sent += int(self._send(db, subscription, candidate))
                    else:
                        for candidate in market_signal_candidates:
                            self._record_candidate_baseline(db, subscription, candidate)
                        self._mark_market_signal_initialized(db, subscription)
                if (
                    recommendation_snapshot is not None
                    and "recommendation_update" in subscription_conditions(subscription)
                ):
                    sent += self._process_recommendation_updates(
                        db,
                        subscription,
                        recommendation_snapshot,
                        now_kst,
                    )
                db.commit()
            return sent

    def send_test(self, db: Session, subscription: PushSubscription) -> bool:
        now = datetime.utcnow()
        return self._send(
            db,
            subscription,
            NotificationCandidate(
                event_key=f"test:{subscription.id}:{now.isoformat(timespec='seconds')}",
                kind="test",
                title="알림 설정 완료",
                body="추천 업데이트, AI 시그널, 급등락, 중요 공시·리포트를 알려드립니다.",
                url="/dashboard?view=watchlist",
                tag="push-test",
                occurred_at=now,
            ),
        )


web_push_runtime = WebPushRuntime()
