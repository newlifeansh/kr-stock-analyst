"""Forward-only regular-session cutover. Never rewrite the legacy ledger.

Pre-cutover candles are frozen *legacy warm-up*, not relabelled regular OHLC.
Post-cutover candles must have independently verified regular-session evidence.
Turnover interval endpoints are calculation scenarios, never displayed amounts.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone, timedelta
from hashlib import sha256
import json
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import DailyPrice, MarketQuantSignalSnapshot, QuantSignalTransitionBaseline, QuantSignalIntradayPathSnapshot
from app.services.regular_session_prices import PRICE_FIELDS, UnverifiedRegularSessionPrice

REGULAR_FORWARD_VERSION = "krx-regular-forward-v1"
REGULAR_FORWARD_STRATEGY_VERSION = "position-lifecycle-v8.1"
REGULAR_FORWARD_START = date(2026, 10, 13)
REGULAR_FORWARD_ENTRY_POLICY = "independent-entry-regular-forward-v1"
LEGACY_MARKET_SNAPSHOT_VERSIONS = ("v36", "v35")


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=lambda value: value.isoformat() if isinstance(value, (date, datetime)) else str(value))


def _load(db: Session, key: str) -> Any | None:
    record = db.get(QuantSignalTransitionBaseline, key)
    if record is None:
        return None
    if record.policy_version != REGULAR_FORWARD_VERSION or sha256(record.payload.encode()).hexdigest() != record.payload_hash:
        raise UnverifiedRegularSessionPrice("전환 기준선의 무결성이 깨졌습니다")
    return json.loads(record.payload)


def _freeze(db: Session, key: str, payload: Any) -> Any:
    existing = _load(db, key)
    if existing is not None:
        return existing
    encoded = _json(payload)
    # The caller owns its transaction. A concurrent unique-key conflict must
    # roll back/retry; it must never replace the winner with newer source data.
    db.add(QuantSignalTransitionBaseline(
        baseline_key=key, policy_version=REGULAR_FORWARD_VERSION,
        payload=encoded, payload_hash=sha256(encoded.encode()).hexdigest(),
        captured_at=datetime.now(timezone.utc).replace(tzinfo=None),
    ))
    db.flush()
    return json.loads(encoded)


def frozen_legacy_price_rows(db: Session, code: str, rows: list[DailyPrice]) -> list[DailyPrice]:
    key = f"{REGULAR_FORWARD_VERSION}:prices:{code}"
    data = _load(db, key)
    if data is None:
        eligible = sorted((row for row in rows if row.trade_date < REGULAR_FORWARD_START), key=lambda row: row.trade_date)
        if any(row.code != code for row in rows) or len({row.trade_date for row in eligible}) != len(eligible):
            raise UnverifiedRegularSessionPrice("전환 가격 기준선의 종목·날짜가 잘못됐습니다")
        from app.services import quant_signals as qs
        from app.services.regular_session_prices import _session_dates
        prior_sessions = _session_dates(REGULAR_FORWARD_START - timedelta(days=14), REGULAR_FORWARD_START - timedelta(days=1))
        normalized = qs._normalize_prices(eligible)
        last_incomplete = max((index for index, bar in enumerate(normalized) if not bar.ohlc_complete), default=-1)
        if (not eligible or not prior_sessions or eligible[-1].trade_date != prior_sessions[-1]
                or len(normalized[last_incomplete + 1:]) < qs.MIN_HISTORY_ROWS):
            raise UnverifiedRegularSessionPrice("전환 직전까지 최소 125개 완전 일봉 준비 자료가 필요합니다")
        data = _freeze(db, key, [{
            "code":code, "trade_date":row.trade_date,
            **{field:getattr(row, field) for field in (*PRICE_FIELDS, "market_cap", "listed_shares")},
        } for row in eligible])
    result = []
    for item in data:
        day = date.fromisoformat(item["trade_date"])
        if item["code"] != code or day >= REGULAR_FORWARD_START:
            raise UnverifiedRegularSessionPrice("과거 준비 자료에 전환 이후 가격이 섞였습니다")
        result.append(DailyPrice(**{**item,"trade_date":day}))
    return result


def forward_price_envelope(db: Session, code: str, rows: list[DailyPrice], *, completed_through: date):
    # Lazy import avoids a quant_signals -> transition -> replay import cycle.
    from app.services.regular_price_replay import regular_price_envelope, turnover_decision_certificate

    frozen = frozen_legacy_price_rows(db, code, rows)
    from app.services.regular_session_prices import _session_dates
    prior_sessions = _session_dates(REGULAR_FORWARD_START - timedelta(days=14), REGULAR_FORWARD_START - timedelta(days=1))
    if not frozen or (prior_sessions and frozen[-1].trade_date != prior_sessions[-1]):
        raise UnverifiedRegularSessionPrice("전환 직전 완료 거래일까지의 가격 준비 자료가 없습니다")
    forward = [row for row in rows if row.trade_date >= REGULAR_FORWARD_START]
    result = regular_price_envelope(db, code, frozen + forward, completed_through=completed_through, effective_from=REGULAR_FORWARD_START)
    if any(item["state"] == "bounded" for item in result.evidence.values()):
        certificate = turnover_decision_certificate(result)
        if certificate["state"] != "invariant":
            raise UnverifiedRegularSessionPrice("정규장 거래대금 범위가 진입·비용 임계값을 가로지릅니다")
    return result


def freeze_legacy_market_publication(db: Session, universe_limit: int, limit: int, recent_days: int) -> dict[str, Any]:
    scope = f"{int(universe_limit)}:{int(limit)}:{int(recent_days)}"
    key = f"{REGULAR_FORWARD_VERSION}:market:{scope}"
    stored = _load(db, key)
    if stored is not None:
        return stored
    candidates = [db.get(MarketQuantSignalSnapshot, f"{version}:{scope}") for version in LEGACY_MARKET_SNAPSHOT_VERSIONS]
    candidates = [row for row in candidates if row is not None]
    if not candidates:
        candidates = [db.get(MarketQuantSignalSnapshot, f"{version}:150:0:{recent_days}") for version in LEGACY_MARKET_SNAPSHOT_VERSIONS]
        candidates = [row for row in candidates if row is not None]
    if not candidates:
        return _freeze(db, key, {"source_key":None,"payload":{"items":[]},"history_available":False})
    source = max(candidates, key=lambda row: row.generated_at)
    payload = json.loads(source.payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise UnverifiedRegularSessionPrice("기존 공개 시그널 이력을 읽을 수 없습니다")
    payload["items"] = [item for item in payload["items"]
                        if int(item.get("market_cap_rank") or 0) <= universe_limit]
    return _freeze(db, key, {"source_key":source.cache_key,"source_generated_at":source.generated_at,"payload":payload,"history_available":True})


def archived_market_items(archive: dict[str, Any], *, as_of: date, recent_days: int) -> list[dict[str, Any]]:
    from datetime import timedelta

    cutoff = as_of - timedelta(days=recent_days)
    result = []
    for original in archive["payload"].get("items", []):
        if not isinstance(original, dict) or original.get("is_preliminary"):
            continue
        raw_date = original.get("execution_date") or original.get("signal_date")
        try:
            day = date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            continue
        if not cutoff <= day <= as_of or day >= REGULAR_FORWARD_START:
            continue
        item = deepcopy(original)
        item.update(history_frozen=True, alert_eligible=False,
                    price_basis_version="legacy-frozen-publication",
                    source_strategy_version=archive["payload"].get("strategy_version"))
        # Preserve all prices/returns. These are archived observations, never
        # today's live position or an intraday notification candidate.
        item["intraday_execution_verified"] = False
        item["intraday_order_verified"] = False
        item.pop("current", None)
        item.pop("holding_context", None)
        item["is_current_holding"] = False
        for field in ("execution_date", "signal_date", "entry_date"):
            if item.get(field):
                item[field] = date.fromisoformat(str(item[field])[:10])
        result.append(item)
    return result


def legacy_open_codes(archive: dict[str, Any]) -> set[str]:
    return {str(item["code"]) for item in archive["payload"].get("items", [])
            if isinstance(item, dict) and item.get("code") and (
                (item.get("current") or {}).get("position_open")
                or item.get("is_current_holding") or item.get("holding_context"))}


def forward_basis_metadata() -> dict[str, Any]:
    return {
        "version":REGULAR_FORWARD_VERSION,
        "strategy_version":REGULAR_FORWARD_STRATEGY_VERSION,
        "effective_from":REGULAR_FORWARD_START,
        "regular_session":"09:00–15:30 Asia/Seoul",
        "history_policy":"frozen_legacy_publications_separate_from_forward_model",
        "warmup_basis":"frozen_legacy_before_cutover_regular_only_after_cutover",
        "turnover_basis":"verified_interval_decisions_never_displayed_as_exact",
        "flow_basis":"full_session_net_flow_over_full_session_turnover_separate_from_regular_prices",
        "retroactive_notifications":False,
    }


def prepare_forward_inputs(db: Session, code: str, rows: list[DailyPrice], *, now: datetime, include_paths: bool = True):
    from app.services import quant_signals as qs
    from app.services.regular_price_replay import regular_ordered_paths

    completed = qs.latest_completed_korea_market_session_date(now)
    if now.hour * 60 + now.minute >= 15 * 60 + 40 and qs.is_korea_market_session_date(now.date(), now):
        completed = now.date()
    if completed is None:
        raise UnverifiedRegularSessionPrice("최근 완료 정규장을 확인할 수 없습니다")
    envelope = forward_price_envelope(db, code, rows, completed_through=completed)
    if not include_paths:
        # Peer benchmarks retain candles, not months of minute dictionaries for
        # every stock. Execution paths are revalidated one stock at a time.
        from app.services.regular_price_replay import RegularPriceEnvelope
        return RegularPriceEnvelope(envelope.lower, envelope.upper, {}), {}
    paths = regular_ordered_paths(envelope)
    for day, evidence in envelope.evidence.items():
        stored = db.get(QuantSignalIntradayPathSnapshot, (code, day))
        if stored is not None:
            try:
                qs._store_verified_intraday_path(db, code, day, evidence["regular_rows"], observed_at=now, is_final=True)
            except qs.UnverifiedIntradayPathError as exc:
                raise UnverifiedRegularSessionPrice(str(exc)) from exc
    return envelope, paths


def forward_relative_context(db: Session, signal_date: date, *, now: datetime) -> dict[str, Any]:
    from app.services.signal_entry_evidence import build_relative_strength_context
    from app.models import StockMaster

    codes = list(db.scalars(select(DailyPrice.code).join(StockMaster, StockMaster.code == DailyPrice.code).where(
        DailyPrice.trade_date == signal_date, DailyPrice.market_cap > 0,
        StockMaster.is_active.is_(True), StockMaster.market.in_(("KOSPI", "KOSDAQ")),
    ).order_by(DailyPrice.market_cap.desc(), DailyPrice.code).limit(100)))
    peers = {}
    for code in codes:
        rows = list(reversed(list(db.scalars(select(DailyPrice).where(DailyPrice.code == code)
                    .order_by(DailyPrice.trade_date.desc()).limit(900)))))
        try:
            peers[code] = prepare_forward_inputs(db, code, rows, now=now, include_paths=False)[0].lower
        except UnverifiedRegularSessionPrice:
            continue
    return build_relative_strength_context(db, signal_date, prices_by_code=peers)


def forward_entry_timeline(db: Session, stock, rows: list[DailyPrice], *,
                           flow_prices: list[DailyPrice], now: datetime,
                           relative_context: dict[str, Any] | None = None,
                           latest_market_date: date | None = None):
    from app.services.signal_entry_evidence import load_entry_evidence_timeline, ensure_entry_evidence_snapshot

    timeline = load_entry_evidence_timeline(db, stock.code, strategy_version=REGULAR_FORWARD_STRATEGY_VERSION)
    if not rows or rows[-1].trade_date < REGULAR_FORWARD_START:
        return {}
    day = rows[-1].trade_date
    if day not in timeline:
        context = relative_context if relative_context is not None else forward_relative_context(db, day, now=now)
        snapshot = ensure_entry_evidence_snapshot(
            db, stock, rows, signal_date=day, now=now, relative_context=context,
            strategy_version=REGULAR_FORWARD_STRATEGY_VERSION, policy_version=REGULAR_FORWARD_ENTRY_POLICY,
            flow_prices=flow_prices, price_basis=forward_basis_metadata(),
            commit_on_persist=False, latest_market_date_override=latest_market_date,
        )
        if snapshot:
            timeline[day] = snapshot
    return {day: payload for day, payload in timeline.items()
            if day >= REGULAR_FORWARD_START
            and payload.get("strategy_version") == REGULAR_FORWARD_STRATEGY_VERSION
            and payload.get("policy_version") == REGULAR_FORWARD_ENTRY_POLICY}


def publish_forward_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    payload["price_basis"] = forward_basis_metadata()
    payload["strategy_version"] = REGULAR_FORWARD_STRATEGY_VERSION
    # No interval endpoint may masquerade as an observed exact amount.
    for item in payload.get("items", []):
        if not item.get("history_frozen"):
            item["price_basis_version"] = REGULAR_FORWARD_VERSION
            item["average_trading_value_20"] = None
            item["turnover_basis"] = "verified_interval_predicate"
    return payload


def collect_forward_session(db: Session, provider, *, now: datetime, universe_limit: int = 150) -> dict[str, Any]:
    """Incremental, bounded evidence collection before publishing the next close."""
    from app.services import quant_signals as qs
    from app.services.regular_session_prices import collect_regular_session_prices
    from sqlalchemy import func

    completed = qs.latest_completed_korea_market_session_date(now)
    if now.hour * 60 + now.minute >= 15 * 60 + 40 and qs.is_korea_market_session_date(now.date(), now):
        completed = now.date()
    if completed is None or completed < REGULAR_FORWARD_START:
        return {"state":"awaiting_first_regular_close", "attempted":0}
    latest_rank_date = db.scalar(select(func.max(DailyPrice.trade_date)).where(DailyPrice.market_cap > 0))
    codes = list(db.scalars(select(DailyPrice.code).where(DailyPrice.trade_date == latest_rank_date,
                      DailyPrice.market_cap > 0).order_by(DailyPrice.market_cap.desc()).limit(universe_limit)))
    for days in (30, 90):
        codes.extend(qs._market_signal_retention_state(db, universe_limit=universe_limit, limit=0, recent_days=days))
    cohort = _load(db, f"{REGULAR_FORWARD_VERSION}:shadow-cohort:100")
    if cohort:
        codes.extend(cohort["codes"])
    return collect_regular_session_prices(db, provider, codes=sorted(set(codes)), start=REGULAR_FORWARD_START,
                                          end=completed, observed_at=now, persist=True, max_pairs=250)


def frozen_shadow_cohort(db: Session, *, limit: int, day: date, codes: list[str]) -> dict[str, Any]:
    return _freeze(db, f"{REGULAR_FORWARD_VERSION}:shadow-cohort:{limit}",
                   {"trade_date":day, "codes":codes})


def regular_intraday_quote(quote: dict[str, Any]) -> dict[str, Any]:
    """Scope the forming candle to same-day regular minutes + the live print.

    This is only a candidate. The existing closed-minute continuity, freshness,
    date, venue and prior-touch validators still authorize every execution.
    """
    rows = quote.get("intraday_minutes") or []
    if not rows:
        return quote
    try:
        selected = sorted((row for row in rows if "090000" <= str(row.get("trade_time", "")).zfill(6) <= "153000"
                           and int(row.get("volume") or 0) > 0), key=lambda row: row["trade_time"])
        if not selected or str(selected[0]["trade_time"]).zfill(6) > "090200":
            return quote
        price = float(quote["price"])
        high, low = max(float(row["high"]) for row in selected), min(float(row["low"]) for row in selected)
        if high > float(quote["high"]) or low < float(quote["low"]):
            return quote
        return {**quote, "open":selected[0]["open"], "high":max(high, price), "low":min(low, price),
                "volume":sum(int(row["volume"]) for row in selected)}
    except (TypeError, ValueError, KeyError):
        return quote
