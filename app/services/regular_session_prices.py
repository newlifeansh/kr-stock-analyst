"""Versioned KRX regular-only prices, independent of mutable display candles.

An exchange selector is not a session selector after the KRX after-market
launch. Evidence is append-only; ambiguous or incomplete inputs cannot silently
fall back to an all-session daily candle. Legacy prices are never overwritten.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.models import DailyPrice, SignalSessionPrice
from app.services.market_calendar import is_scheduled_korea_market_session_date

KST = ZoneInfo("Asia/Seoul")
# v1 local prototype assumed a counter reset at the date boundary. Source
# comparison disproved that assumption for opening cumulative turnover.
# Retain its evidence but never select it for the corrected candidate.
REGULAR_PRICE_BASIS = "krx-regular-session-v4-candidate"
REGULAR_PRICE_EFFECTIVE_DATE = date(2026, 9, 14)
REGULAR_PRICE_SOURCE = "kis_dated_minutes:FHKST03010230:J"
PRICE_FIELDS = ("open", "high", "low", "close", "volume", "trading_value")


class UnverifiedRegularSessionPrice(RuntimeError):
    pass


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _integer(value: Any, *, positive: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not a price")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("invalid non-negative integer") from exc
    if not number.is_finite() or number != number.to_integral_value() or number < (1 if positive else 0):
        raise ValueError("invalid non-negative integer")
    return int(number)


def _verified_naver_closing_auction(
    code: str, day: date, regular: list[dict[str, Any]], payload: dict[str, Any],
) -> dict[str, Any]:
    """Recover only the single-price closing auction, never a missing intraday path.

    Naver's KRX weekly chart has ten-minute buckets.  Every regular bucket
    before the auction must match KIS OHLC and cumulative volume up to a
    constant pre-open offset. The 15:30 bucket ends before 15:40 after-hours;
    its O/H/L/C must be one price and its volume delta strictly positive.
    """
    if payload.get("code") != code or payload.get("stockExchangeType") != "KRX" or payload.get("periodType") != "week":
        raise ValueError("wrong closing-auction source identity")
    if not regular or regular[0]["trade_time"] != "090000" or regular[-1]["trade_time"] != "151900":
        raise ValueError("closing recovery requires the pre-auction session boundaries")
    # Without an observed pre-open volume, the first bucket is the offset
    # anchor. A missing trade there could be absorbed into the constant
    # pre-open offset and escape all subsequent bucket comparisons.
    if [row["trade_time"] for row in regular[:10]] != [f"090{i}00" for i in range(10)]:
        raise ValueError("cross-source coverage requires a complete opening volume anchor")
    candles = (payload.get("priceInfos") or {}).get(day.strftime("%Y%m%d"))
    if not isinstance(candles, list):
        raise ValueError("missing dated closing-auction evidence")
    buckets = {}
    for row in candles:
        stamp = str(row.get("localDateTime") or "")
        if not stamp.startswith(day.strftime("%Y%m%d")) or stamp in buckets:
            raise ValueError("wrong date or duplicate closing-auction bucket")
        buckets[stamp] = row
    cumulative = 0
    offset = None
    last_cumulative = None
    for index in range(0, 380, 10):
        expected_start = datetime.combine(day, time(9)) + timedelta(minutes=index)
        expected_end = expected_start + timedelta(minutes=10)
        minutes = [row for row in regular if expected_start.strftime("%H%M%S") <= row["trade_time"] < expected_end.strftime("%H%M%S")]
        if not minutes:
            raise ValueError("unverified empty pre-auction bucket")
        bucket = buckets.get(expected_start.strftime("%Y%m%d%H%M%S")) or {}
        actual = [_integer(bucket.get(key), positive=True) for key in ("openPrice", "highPrice", "lowPrice", "currentPrice")]
        expected = [_integer(minutes[0]["open"], positive=True), max(_integer(row["high"], positive=True) for row in minutes), min(_integer(row["low"], positive=True) for row in minutes), _integer(minutes[-1]["price"], positive=True)]
        if actual != expected:
            raise ValueError("closing source conflicts with KIS pre-auction OHLC")
        cumulative += sum(_integer(row["volume"], positive=True) for row in minutes)
        last_cumulative = _integer(bucket.get("accumulatedTradingVolume"))
        observed_offset = last_cumulative - cumulative
        if offset is None:
            offset = observed_offset
        if observed_offset < 0 or observed_offset != offset:
            raise ValueError("closing source conflicts with KIS pre-auction volume")
    indicative = buckets.get(day.strftime("%Y%m%d") + "152000")
    if indicative is not None and _integer(indicative.get("accumulatedTradingVolume")) != last_cumulative:
        raise ValueError("unverified positive-volume closing auction interval")
    close = buckets.get(day.strftime("%Y%m%d") + "153000") or {}
    prices = [_integer(close.get(key), positive=True) for key in ("openPrice", "highPrice", "lowPrice", "currentPrice")]
    if len(set(prices)) != 1:
        raise ValueError("closing auction is not a single-price print")
    volume = _integer(close.get("accumulatedTradingVolume")) - int(last_cumulative)
    if volume <= 0:
        raise ValueError("closing auction has no actual volume")
    return {"trade_date": day.strftime("%Y%m%d"), "trade_time": "153000",
            "open": prices[0], "high": prices[0], "low": prices[0], "price": prices[0],
            "volume": volume, "trading_value": _integer(regular[-1]["trading_value"]) + prices[0] * volume}


def regular_session_evidence(
    code: str, trade_date: date, rows: list[dict[str, Any]], *, observed_at: datetime,
    preopen_baseline: dict[str, Any] | None = None,
    closing_auction_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate actual regular trades and preserve the complete source envelope.

    ``trading_value`` in the KIS minute response is cumulative, not minute
    turnover. Its pre-open baseline must be observed; never sum cumulative
    values or use the after-market daily total for an entry liquidity filter.
    """
    if observed_at.tzinfo is None:
        raise ValueError("observed_at must be timezone aware")
    if observed_at.astimezone(KST) < datetime.combine(trade_date, time(15, 31), KST):
        raise ValueError("regular session is not complete")
    if not code or not isinstance(rows, list):
        raise ValueError("code and minute rows are required")
    raw = json.loads(_json(rows))
    result: dict[str, Any] = {
        "code": code, "trade_date": trade_date.isoformat(),
        "basis_version": REGULAR_PRICE_BASIS, "source": REGULAR_PRICE_SOURCE,
        "exchange": "KRX", "session": "regular", "start": "09:00", "end": "15:30",
        "state": "unverified", "reason": None, "prices": None, "turnover_bounds": None,
        "raw_rows": raw, "regular_rows": [], "preopen_baseline": preopen_baseline,
        "closing_auction_evidence": closing_auction_evidence,
        "volume_basis": "sum_actual_regular_minute_volume",
        "trading_value_basis": "closing_cumulative_minus_preopen_cumulative",
        "coverage_basis": "continuous_actual_minutes",
    }
    try:
        parsed = []
        seen = set()
        for row in raw:
            stamp = str(row.get("trade_date") or "").replace("-", "")
            hhmmss = str(row.get("trade_time") or "").zfill(6)
            instant = datetime.strptime(stamp + hhmmss, "%Y%m%d%H%M%S")
            if instant.date() != trade_date or instant.second or hhmmss in seen:
                raise ValueError("wrong date, duplicate or non-minute source row")
            seen.add(hhmmss)
            parsed.append((instant, row))
        parsed.sort(key=lambda pair: pair[0])
        regular = [row for instant, row in parsed if time(9) <= instant.time() <= time(15, 30)]
        actual_prefix = [row for row in regular if "090000" <= row["trade_time"] <= "151900"]
        sparse_prefix_verified = False
        if len(actual_prefix) < 380 and closing_auction_evidence is not None:
            closing = _verified_naver_closing_auction(code, trade_date, actual_prefix, closing_auction_evidence)
            observed_close = next((row for row in regular if row["trade_time"] == "153000"), None)
            if observed_close is not None and _integer(observed_close.get("volume")) > 0 and any(
                _integer(observed_close.get(key)) != _integer(closing[key])
                for key in ("open", "high", "low", "price", "volume", "trading_value")
            ):
                raise ValueError("closing source conflicts with actual KIS closing trade")
            sparse_prefix_verified = True
            result["coverage_basis"] = "naver_38_buckets_with_complete_opening_volume_anchor"
            result["source"] += "+naver_krx_regular_coverage"
        closing_trade_missing = bool(
            regular
            and (
                regular[-1]["trade_time"] != "153000"
                or _integer(regular[-1].get("volume")) <= 0
            )
        )
        if closing_trade_missing and closing_auction_evidence is not None:
            preauction = [row for row in regular if row["trade_time"] <= "151900"]
            regular = preauction + [
                _verified_naver_closing_auction(
                    code, trade_date, preauction, closing_auction_evidence
                )
            ]
            result["source"] += "+naver_krx_closing_auction"
        if not regular or regular[0]["trade_time"] != "090000" or regular[-1]["trade_time"] != "153000":
            raise ValueError("missing regular opening or closing trade")
        executable = []
        for row in regular:
            volume = _integer(row.get("volume"))
            if "152000" <= row["trade_time"] < "153000" and volume == 0:
                continue  # indicative auction prices are not executed trades
            if volume == 0:
                raise ValueError("unverified zero-volume regular minute")
            o, h, l, c = [_integer(row.get(key), positive=True) for key in ("open", "high", "low", "price")]
            if not l <= min(o, c) <= max(o, c) <= h:
                raise ValueError("invalid minute OHLC")
            executable.append(row)
        for prior, following in zip(executable, executable[1:]):
            before = datetime.strptime(prior["trade_time"], "%H%M%S")
            after = datetime.strptime(following["trade_time"], "%H%M%S")
            if after - before != timedelta(minutes=1) and not (
                prior["trade_time"] in {"151900", "152000"} and following["trade_time"] == "153000"
            ) and not (
                sparse_prefix_verified and following["trade_time"] <= "151900"
            ):
                raise ValueError("missing regular minute")
        prices = {
            "open": _integer(executable[0]["open"], positive=True),
            "high": max(_integer(row["high"], positive=True) for row in executable),
            "low": min(_integer(row["low"], positive=True) for row in executable),
            "close": _integer(executable[-1]["price"], positive=True),
            "volume": sum(_integer(row["volume"], positive=True) for row in executable),
            "trading_value": None,
        }
        result.update(prices=prices, regular_rows=executable)
        baseline_rows = [row for instant, row in parsed if instant.time() < time(9)]
        if baseline_rows and baseline_rows[-1]["trade_time"] == "085900":
            baseline = _integer(baseline_rows[-1].get("trading_value"))
        elif (
            isinstance(preopen_baseline, dict)
            and preopen_baseline.get("kind") == "observed_day_boundary"
            and preopen_baseline.get("requested_date") == trade_date.strftime("%Y%m%d")
            and preopen_baseline.get("requested_time") == "085900"
            and datetime.strptime(str(preopen_baseline.get("previous_trade_date")), "%Y%m%d").date() < trade_date
            and datetime.strptime(str(preopen_baseline.get("previous_trade_time")), "%H%M%S")
            and preopen_baseline.get("value") in (None, 0)
        ):
            # The endpoint omits pre-open prints even when its cumulative
            # money counter includes them. Date rollover is NOT proof of a
            # zero pre-open monetary baseline. Preserve a rigorous interval
            # using actual first-minute OHLC/volume and later counter deltas.
            first = executable[0]
            first_value = _integer(first.get("trading_value"))
            later_value = _integer(executable[-1].get("trading_value")) - first_value
            first_volume = _integer(first.get("volume"), positive=True)
            lower = _integer(first["low"], positive=True) * first_volume + later_value
            # Pre-open turnover cannot be negative, so the cumulative first
            # value is an additional upper bound on that minute's turnover.
            upper = min(_integer(first["high"], positive=True) * first_volume, first_value) + later_value
            if lower <= 0 or upper < lower:
                raise ValueError("opening cumulative turnover cannot cover actual trades")
            result["turnover_bounds"] = {"lower": lower, "upper": upper, "basis": "actual_first_minute_ohlcv_plus_later_cumulative_deltas"}
            # First validate every subsequent minute independently of the
            # unknown opening counter baseline.
            previous = first_value
            for row in regular[1:]:
                cumulative = _integer(row.get("trading_value"))
                volume = _integer(row.get("volume"))
                if not _integer(row.get("low")) * volume <= cumulative - previous <= _integer(row.get("high")) * volume:
                    raise ValueError("cumulative turnover does not reconcile with actual trades")
                previous = cumulative
            if lower != upper:
                result.update(
                    state="bounded",
                    reason="exact opening turnover unavailable; validated monetary interval only",
                    trading_value_basis="bounded_actual_regular_turnover",
                )
                return result
            baseline = first_value - _integer(first["low"], positive=True) * first_volume
            if baseline < 0:
                raise ValueError("negative preopen cumulative turnover baseline")
        else:
            raise ValueError("missing preopen cumulative turnover baseline")
        previous = baseline
        for row in regular:
            cumulative = _integer(row.get("trading_value"))
            delta = cumulative - previous
            volume = _integer(row.get("volume"))
            # Real monetary turnover must lie within the traded minute range.
            low = _integer(row.get("low"), positive=True) if volume else 0
            high = _integer(row.get("high"), positive=True) if volume else 0
            if not volume * low <= delta <= volume * high:
                raise ValueError("cumulative turnover does not reconcile with actual trades")
            previous = cumulative
        prices["trading_value"] = previous - baseline
        if prices["trading_value"] <= 0:
            raise ValueError("empty regular turnover")
        result["state"] = "ready"
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        result["reason"] = str(exc)
    return result


def store_regular_session_evidence(
    db: Session, evidence: dict[str, Any], *, observed_at: datetime,
) -> SignalSessionPrice:
    """Append evidence and an untouched legacy-price snapshot; do not commit."""
    verified = regular_session_evidence(
        evidence["code"], date.fromisoformat(evidence["trade_date"]),
        evidence["raw_rows"], observed_at=observed_at,
        preopen_baseline=evidence.get("preopen_baseline"),
        closing_auction_evidence=evidence.get("closing_auction_evidence"),
    )
    if verified != evidence:
        raise ValueError("evidence failed deterministic recomputation")
    digest = sha256(_json(evidence).encode()).hexdigest()
    existing = db.scalar(select(SignalSessionPrice).where(
        SignalSessionPrice.code == evidence["code"],
        SignalSessionPrice.trade_date == date.fromisoformat(evidence["trade_date"]),
        SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS,
        SignalSessionPrice.evidence_hash == digest,
    ))
    if existing is not None:
        return existing
    legacy = db.scalar(select(DailyPrice).where(
        DailyPrice.code == evidence["code"], DailyPrice.trade_date == date.fromisoformat(evidence["trade_date"]),
    ))
    envelope = {
        "evidence": evidence,
        "legacy_display_price_at_capture": {key: getattr(legacy, key) for key in PRICE_FIELDS} if legacy is not None else None,
    }
    record = SignalSessionPrice(
        code=evidence["code"], trade_date=date.fromisoformat(evidence["trade_date"]),
        basis_version=REGULAR_PRICE_BASIS, evidence_hash=digest, state=evidence["state"],
        payload=_json(envelope), observed_at=observed_at.astimezone(timezone.utc).replace(tzinfo=None),
    )
    db.add(record)
    db.flush()
    return record


def load_regular_session_evidence(
    db: Session, code: str, trade_date: date, *, allow_bounded: bool = False,
) -> dict[str, Any]:
    # A default dry-run must also work before the additive table is installed.
    # Do not create schema or write anything as a side effect of a read.
    if not inspect(db.connection()).has_table(SignalSessionPrice.__tablename__):
        raise UnverifiedRegularSessionPrice("정규장 가격 근거 테이블이 없습니다")
    states = ("ready", "bounded") if allow_bounded else ("ready",)
    records = list(db.scalars(select(SignalSessionPrice).where(
        SignalSessionPrice.code == code, SignalSessionPrice.trade_date == trade_date,
        SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS, SignalSessionPrice.state.in_(states),
    )))
    if not records:
        raise UnverifiedRegularSessionPrice(f"{code} {trade_date}: 검증된 정규장 가격이 없습니다")
    accepted = []
    for record in records:
        try:
            evidence = json.loads(record.payload)["evidence"]
            regenerated = regular_session_evidence(code, trade_date, evidence["raw_rows"], observed_at=record.observed_at.replace(tzinfo=timezone.utc), preopen_baseline=evidence.get("preopen_baseline"), closing_auction_evidence=evidence.get("closing_auction_evidence"))
            if evidence != regenerated or sha256(_json(evidence).encode()).hexdigest() != record.evidence_hash or evidence["state"] != record.state or evidence["state"] not in states:
                raise ValueError("integrity mismatch")
        except (ValueError, KeyError, TypeError) as exc:
            raise UnverifiedRegularSessionPrice("정규장 가격 근거의 무결성이 깨졌습니다") from exc
        accepted.append(evidence)
    if len({_json(item["prices"]) for item in accepted}) != 1 or len({_json(item["turnover_bounds"]) for item in accepted}) != 1:
        raise UnverifiedRegularSessionPrice("동일 정규장의 원천 가격 근거가 충돌합니다")
    return accepted[0]


def regular_signal_price_rows(db: Session, rows: list[DailyPrice], *, completed_through: date) -> list[DailyPrice]:
    """Return detached signal inputs; leave display and historical rows intact."""
    result = []
    by_code: dict[str, list[DailyPrice]] = {}
    for row in rows:
        by_code.setdefault(row.code, []).append(row)
        if row.trade_date < REGULAR_PRICE_EFFECTIVE_DATE and row.trade_date <= completed_through:
            result.append(row)
    for code, original in by_code.items():
        first = max(REGULAR_PRICE_EFFECTIVE_DATE, min(row.trade_date for row in original))
        originals = {row.trade_date: row for row in original}
        for day in _session_dates(first, completed_through):
            evidence = load_regular_session_evidence(db, code, day)
            display = originals.get(day)
            result.append(DailyPrice(code=code, trade_date=day, **evidence["prices"],
                                     market_cap=display.market_cap if display else None,
                                     listed_shares=display.listed_shares if display else None))
    # In-progress daily OHLC may include other sessions. Live regular
    # execution must obtain its independently verified current quote.
    result.sort(key=lambda row: (row.code, row.trade_date))
    return result


def _session_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(max(0, (end - start).days + 1))
            if is_scheduled_korea_market_session_date(start + timedelta(days=offset))]


def collect_regular_session_prices(
    db: Session, provider: Any, *, codes: list[str], start: date, end: date,
    observed_at: datetime, persist: bool = False, max_pairs: int = 250,
) -> dict[str, Any]:
    """Bounded, resumable sidecar backfill; never publishes signals or pushes.

    Only supplied symbols and scheduled completed session dates are inspected.
    Each persisted evidence item commits independently so a provider outage
    cannot discard earlier completed work. Unverified evidence remains visible.
    """
    if start < REGULAR_PRICE_EFFECTIVE_DATE or end < start or max_pairs < 1:
        raise ValueError("invalid regular-session backfill range")
    local = observed_at.astimezone(KST) if observed_at.tzinfo is not None else None
    if local is None or end > local.date() or (end == local.date() and local.time() < time(15, 31)):
        raise ValueError("backfill end must be a completed session date")
    pairs = [(code, day) for day in reversed(_session_dates(start, end)) for code in sorted(set(codes))]
    report: dict[str, Any] = {
        "basis_version": REGULAR_PRICE_BASIS, "start": start.isoformat(), "end": end.isoformat(),
        "persist": persist, "total_pairs": len(pairs), "attempted": 0,
        "ready": 0, "already_ready": 0, "bounded": 0, "already_bounded": 0, "unverified": [], "deferred": 0,
        "signal_publication": False, "history_overwrite": False, "notifications_sent": 0,
    }
    has_table = inspect(db.connection()).has_table(SignalSessionPrice.__tablename__)
    if persist and not has_table:
        raise ValueError("create the additive evidence table before persisting")
    for code, day in pairs:
        try:
            prior = load_regular_session_evidence(db, code, day, allow_bounded=True)
        except UnverifiedRegularSessionPrice:
            existing_ready = db.scalar(select(SignalSessionPrice.id).where(
                SignalSessionPrice.code == code, SignalSessionPrice.trade_date == day,
                SignalSessionPrice.basis_version == REGULAR_PRICE_BASIS, SignalSessionPrice.state.in_(("ready", "bounded")),
            ).limit(1)) if has_table else None
            if existing_ready is not None:
                report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": "stored_evidence_conflict_or_corruption"})
                continue
        else:
            report["already_ready" if prior["state"] == "ready" else "already_bounded"] += 1
            continue
        if report["attempted"] >= max_pairs:
            report["deferred"] += 1
            continue
        report["attempted"] += 1
        try:
            source = provider.fetch_regular_session_data(code, day)
            result = regular_session_evidence(code, day, source["rows"], observed_at=observed_at, preopen_baseline=source.get("preopen_baseline"), closing_auction_evidence=source.get("closing_auction_evidence"))
        except Exception as exc:
            # Provider errors can contain credential-bearing URLs; never export
            # their text to a CLI report or public diagnostic.
            report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": "source_unavailable", "error_type": type(exc).__name__})
            continue
        if persist:
            store_regular_session_evidence(db, result, observed_at=observed_at)
            db.commit()
        if result["state"] == "ready":
            report["ready"] += 1
        elif result["state"] == "bounded":
            report["bounded"] += 1
        else:
            report["unverified"].append({"code": code, "trade_date": day.isoformat(), "reason": result["reason"]})
    report["state"] = "ready" if pairs and not report["unverified"] and not report["deferred"] else "incomplete"
    report["exact_turnover_complete"] = report["state"] == "ready" and not (report["bounded"] or report["already_bounded"])
    report["production_ready"] = False  # collection is not a strategy approval
    return report
