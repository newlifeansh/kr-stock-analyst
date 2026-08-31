from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import json
from math import sqrt
import re
from statistics import median
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    DailyPrice,
    DisclosureItem,
    IngestionRun,
    InvestorFlow,
    MacroObservation,
    QuantSignalEvidenceSnapshot,
    ResearchReport,
    StockFundamentalSnapshot,
    StockMaster,
)
from app.services.sector_taxonomy import investment_sector_fields


KST = ZoneInfo("Asia/Seoul")
ENTRY_EVIDENCE_STRATEGY_VERSION = "position-lifecycle-v7.0"
ENTRY_EVIDENCE_POLICY_VERSION = "independent-entry-confirmation-v1"
ENTRY_EVIDENCE_EFFECTIVE_DATE = date(2026, 8, 21)

FLOW_LOOKBACK_BARS = 20
FLOW_SHORT_BARS = 5
FLOW_SUPPORT_INTENSITY_PERCENT = 0.50
RESEARCH_LOOKBACK_DAYS = 180
DISCLOSURE_RISK_LOOKBACK_DAYS = 14
FUNDAMENTAL_FRESH_DAYS = 2
DISCLOSURE_INGESTION_MAX_AGE_MINUTES = 30
RESEARCH_INGESTION_MAX_AGE_MINUTES = 45
RELATIVE_STRENGTH_MARGIN = 0.02
SECTOR_MIN_PEERS = 3
RELATIVE_UNIVERSE_LIMIT = 100

FOREIGN_AGGREGATES = ("외국인합계", "외국인")
INSTITUTION_AGGREGATES = ("기관합계", "기관")
FOREIGN_COMPONENTS = ("외국계",)
INSTITUTION_COMPONENTS = (
    "금융투자",
    "보험",
    "투신",
    "사모",
    "은행",
    "기타금융",
    "연기금",
    "국가",
)

HARD_DISCLOSURE_RISK_TOKENS = (
    "유상증자결정",
    "전환사채권발행결정",
    "신주인수권부사채권발행결정",
    "교환사채권발행결정",
    "회생절차",
    "파산신청",
    "감사의견거절",
    "감사범위제한",
    "상장폐지",
    "거래정지",
    "횡령",
    "배임",
)


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Unsupported evidence value: {type(value)!r}")


def _float(value: object) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _kst(value: Optional[datetime] = None) -> datetime:
    current = value or datetime.now(KST)
    if current.tzinfo is None:
        return current.replace(tzinfo=KST)
    return current.astimezone(KST)


def _signal_cutoff(signal_date: date) -> datetime:
    return datetime.combine(signal_date, time(15, 40), tzinfo=KST)


def _iso(value: Optional[date | datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _normalize_text(value: object) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "")).casefold()


def _latest_successful_ingestion(
    db: Session,
    *,
    source: str,
    datasets: Iterable[str],
) -> Optional[IngestionRun]:
    dataset_values = tuple(dict.fromkeys(str(item) for item in datasets if str(item)))
    if not dataset_values:
        return None
    return db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.source == source,
            IngestionRun.dataset.in_(dataset_values),
            IngestionRun.status == "success",
            IngestionRun.finished_at.is_not(None),
        )
        .order_by(desc(IngestionRun.finished_at), desc(IngestionRun.id))
        .limit(1)
    )


def _source_check(
    key: str,
    label: str,
    *,
    state: str,
    source: str,
    as_of: Optional[date | datetime],
    message: str,
    critical: bool,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "state": state,
        "source": source,
        "as_of": _iso(as_of),
        "message": message,
        "critical": critical,
    }


def _evidence_item(
    key: str,
    label: str,
    state: str,
    summary: str,
    source: str,
    *,
    as_of: Optional[date | datetime] = None,
    score: Optional[float] = None,
    available: bool = True,
    used_for_entry: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "state": state,
        "summary": summary,
        "source": source,
        "as_of": _iso(as_of),
        "score": round(float(score), 2) if score is not None else None,
        "available": available,
        "used_for_entry": used_for_entry,
    }


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append((value * alpha) + (result[-1] * (1.0 - alpha)))
    return result


def _return_over_rows(rows: list[DailyPrice], bars: int = 20) -> Optional[float]:
    complete = [
        row
        for row in sorted(rows, key=lambda item: item.trade_date)
        if row.close is not None and float(row.close) > 0
    ]
    if len(complete) <= bars:
        return None
    start = float(complete[-(bars + 1)].close)
    end = float(complete[-1].close)
    return (end / start) - 1.0 if start > 0 else None


def _macro_index_context(
    db: Session,
    *,
    series_code: str,
    signal_date: date,
) -> dict[str, Any]:
    rows: list[MacroObservation] = []
    selected_source = "naver_finance"
    for source in ("naver_finance", "yahoo"):
        candidate_rows = list(
            reversed(
                list(
                    db.scalars(
                        select(MacroObservation)
                        .where(
                            MacroObservation.source == source,
                            MacroObservation.series_code == series_code,
                            MacroObservation.item_code == "close",
                            MacroObservation.period <= signal_date.isoformat(),
                        )
                        .order_by(desc(MacroObservation.period))
                        .limit(80)
                    )
                )
            )
        )
        if candidate_rows:
            rows = candidate_rows
            selected_source = source
        if len(candidate_rows) >= 61 and candidate_rows[-1].period == signal_date.isoformat():
            break
    values = [float(row.value) for row in rows if row.value is not None and float(row.value) > 0]
    periods = [row.period for row in rows if row.value is not None and float(row.value) > 0]
    if len(values) < 61 or not periods:
        return {
            "state": "unavailable",
            "series_code": series_code,
            "source": selected_source,
            "as_of": periods[-1] if periods else None,
            "message": "시장지수 60거래일 이력이 부족합니다.",
        }
    latest_date = date.fromisoformat(periods[-1])
    if latest_date != signal_date:
        return {
            "state": "stale",
            "series_code": series_code,
            "source": selected_source,
            "as_of": latest_date.isoformat(),
            "message": f"시장지수가 신호일 {signal_date.isoformat()}까지 갱신되지 않았습니다.",
        }
    return20 = (values[-1] / values[-21]) - 1.0
    ema60 = _ema(values, 60)[-1]
    daily_returns = [
        (values[index] / values[index - 1]) - 1.0
        for index in range(max(1, len(values) - 20), len(values))
        if values[index - 1] > 0
    ]
    mean_return = sum(daily_returns) / len(daily_returns) if daily_returns else 0.0
    variance = (
        sum((item - mean_return) ** 2 for item in daily_returns) / (len(daily_returns) - 1)
        if len(daily_returns) > 1
        else 0.0
    )
    annualized_volatility = sqrt(max(0.0, variance)) * sqrt(252.0)
    panic = bool(
        return20 <= -0.05
        and values[-1] < ema60
        and annualized_volatility >= 0.25
    )
    return {
        "state": "ready",
        "series_code": series_code,
        "source": selected_source,
        "as_of": latest_date.isoformat(),
        "return20": return20,
        "current": values[-1],
        "ema60": ema60,
        "annualized_volatility20": annualized_volatility,
        "panic": panic,
        "message": "시장지수 종가와 20일 국면이 최신입니다.",
    }


def build_relative_strength_context(
    db: Session,
    signal_date: date,
) -> dict[str, Any]:
    """Build one normalized market/sector benchmark shared by every stock.

    The sector return is the median 20-session return of the point-in-time
    market-cap top 100.  Using one shared benchmark prevents a detail request
    and the market signal feed from silently using different peer universes.
    """

    market_indices = {
        "KOSPI": _macro_index_context(db, series_code="^KS11", signal_date=signal_date),
        "KOSDAQ": _macro_index_context(db, series_code="^KQ11", signal_date=signal_date),
    }
    top_codes = list(
        db.scalars(
            select(DailyPrice.code)
            .join(StockMaster, StockMaster.code == DailyPrice.code)
            .where(
                DailyPrice.trade_date == signal_date,
                DailyPrice.market_cap.is_not(None),
                DailyPrice.market_cap > 0,
                DailyPrice.close.is_not(None),
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            )
            .order_by(desc(DailyPrice.market_cap), DailyPrice.code)
            .limit(RELATIVE_UNIVERSE_LIMIT)
        )
    )
    if not top_codes:
        return {
            "signal_date": signal_date.isoformat(),
            "market_indices": market_indices,
            "sector_returns": {},
            "sector_counts": {},
            "universe_count": 0,
            "return_count": 0,
        }

    cutoff = signal_date - timedelta(days=50)
    price_rows = list(
        db.scalars(
            select(DailyPrice)
            .where(
                DailyPrice.code.in_(tuple(top_codes)),
                DailyPrice.trade_date >= cutoff,
                DailyPrice.trade_date <= signal_date,
            )
            .order_by(DailyPrice.code, DailyPrice.trade_date)
        )
    )
    rows_by_code: dict[str, list[DailyPrice]] = defaultdict(list)
    for row in price_rows:
        rows_by_code[str(row.code)].append(row)
    stocks = {
        stock.code: stock
        for stock in db.scalars(select(StockMaster).where(StockMaster.code.in_(tuple(top_codes))))
    }
    sector_values: dict[str, list[float]] = defaultdict(list)
    return_count = 0
    for code in top_codes:
        rows = rows_by_code.get(str(code), [])
        if not rows or rows[-1].trade_date != signal_date:
            continue
        value = _return_over_rows(rows, 20)
        stock = stocks.get(str(code))
        if value is None or stock is None:
            continue
        sector_key = investment_sector_fields(stock.sector, stock.industry)["investment_sector"]
        sector_values[str(sector_key)].append(value)
        return_count += 1
    sector_returns = {
        key: median(values)
        for key, values in sector_values.items()
        if len(values) >= SECTOR_MIN_PEERS
    }
    return {
        "signal_date": signal_date.isoformat(),
        "market_indices": market_indices,
        "sector_returns": sector_returns,
        "sector_counts": {key: len(values) for key, values in sector_values.items()},
        "universe_count": len(top_codes),
        "return_count": return_count,
    }


def _canonical_flow_value(rows: list[InvestorFlow], *, institution: bool) -> int:
    aggregate_names = INSTITUTION_AGGREGATES if institution else FOREIGN_AGGREGATES
    component_names = INSTITUTION_COMPONENTS if institution else FOREIGN_COMPONENTS
    normalized = {str(row.investor_type or "").strip(): row for row in rows}
    for name in aggregate_names:
        row = normalized.get(name)
        if row is not None:
            return int(row.net_buy_value or 0)
    return sum(
        int(row.net_buy_value or 0)
        for row in rows
        if any(token == str(row.investor_type or "").strip() for token in component_names)
    )


def _flow_evidence(
    db: Session,
    *,
    stock_code: str,
    prices: list[DailyPrice],
    signal_date: date,
) -> tuple[dict[str, Any], dict[str, Any]]:
    eligible_prices = [
        row
        for row in sorted(prices, key=lambda item: item.trade_date)
        if row.trade_date <= signal_date and row.trading_value is not None
    ]
    if len(eligible_prices) < FLOW_LOOKBACK_BARS:
        evidence = _evidence_item(
            "flow",
            "정규화 수급",
            "unavailable",
            "20거래일 거래대금 이력이 부족합니다.",
            "네이버금융 투자자별 매매동향",
            available=False,
        )
        return evidence, _source_check(
            "flow",
            "투자자 수급",
            state="unavailable",
            source="naver_finance",
            as_of=None,
            message=evidence["summary"],
            critical=False,
        )

    window_prices = eligible_prices[-FLOW_LOOKBACK_BARS:]
    required_date = window_prices[-2].trade_date if len(window_prices) > 1 else window_prices[-1].trade_date
    first_date = window_prices[0].trade_date
    flow_rows = list(
        db.scalars(
            select(InvestorFlow)
            .where(
                InvestorFlow.code == stock_code,
                InvestorFlow.trade_date >= first_date,
                InvestorFlow.trade_date <= signal_date,
            )
            .order_by(InvestorFlow.trade_date, InvestorFlow.id)
        )
    )
    by_date: dict[date, list[InvestorFlow]] = defaultdict(list)
    for row in flow_rows:
        by_date[row.trade_date].append(row)
    latest_date = max(by_date) if by_date else None
    if latest_date is None or latest_date < required_date:
        message = (
            f"수급 최신일 {latest_date or '-'}이 필요 기준일 {required_date}보다 오래됐습니다."
        )
        evidence = _evidence_item(
            "flow",
            "정규화 수급",
            "unavailable",
            message,
            "네이버금융 투자자별 매매동향",
            as_of=latest_date,
            available=False,
        )
        return evidence, _source_check(
            "flow",
            "투자자 수급",
            state="stale",
            source="naver_finance",
            as_of=latest_date,
            message=message,
            critical=False,
        )

    flow_dates = sorted(by_date)
    recent_dates = flow_dates[-FLOW_LOOKBACK_BARS:]
    short_dates = flow_dates[-FLOW_SHORT_BARS:]

    def sums(target_dates: list[date]) -> tuple[int, int]:
        foreign = sum(_canonical_flow_value(by_date[item], institution=False) for item in target_dates)
        institution = sum(_canonical_flow_value(by_date[item], institution=True) for item in target_dates)
        return foreign, institution

    foreign20, institution20 = sums(recent_dates)
    foreign5, institution5 = sums(short_dates)
    trading_value_by_date = {
        row.trade_date: int(row.trading_value or 0)
        for row in window_prices
    }
    total20 = sum(trading_value_by_date.get(item, 0) for item in recent_dates)
    total5 = sum(trading_value_by_date.get(item, 0) for item in short_dates)
    intensity20 = ((foreign20 + institution20) / total20 * 100.0) if total20 > 0 else None
    intensity5 = ((foreign5 + institution5) / total5 * 100.0) if total5 > 0 else None
    if intensity20 is None or intensity5 is None:
        state = "unavailable"
        available = False
        score = None
    elif intensity20 >= FLOW_SUPPORT_INTENSITY_PERCENT and intensity5 > 0:
        state = "supportive"
        available = True
        score = min(100.0, intensity20 * 20.0)
    elif intensity20 <= -FLOW_SUPPORT_INTENSITY_PERCENT and intensity5 < 0:
        state = "caution"
        available = True
        score = max(-100.0, intensity20 * 20.0)
    else:
        state = "neutral"
        available = True
        score = max(-100.0, min(100.0, (intensity20 or 0.0) * 20.0))
    summary = (
        f"20일 외국인 {foreign20 / 100_000_000:+,.0f}억·기관 {institution20 / 100_000_000:+,.0f}억, "
        f"거래대금 대비 합산 {intensity20:+.2f}%·최근 5일 {intensity5:+.2f}%"
        if intensity20 is not None and intensity5 is not None
        else "수급을 거래대금으로 정규화할 수 없습니다."
    )
    evidence = _evidence_item(
        "flow",
        "정규화 수급",
        state,
        summary,
        "네이버금융 투자자별 매매동향 + 저장 거래대금",
        as_of=latest_date,
        score=score,
        available=available,
    )
    return evidence, _source_check(
        "flow",
        "투자자 수급",
        state="ready" if available else "unavailable",
        source="naver_finance",
        as_of=latest_date,
        message="종목별 수급을 동일 기간 거래대금으로 정규화했습니다.",
        critical=False,
    )


def _fundamental_payload(row: Optional[StockFundamentalSnapshot]) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _earnings_evidence(
    db: Session,
    *,
    stock_code: str,
    signal_date: date,
    generated_at: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    since = datetime.combine(signal_date - timedelta(days=RESEARCH_LOOKBACK_DAYS), time.min)
    through = datetime.combine(signal_date, time.max)
    reports = list(
        db.scalars(
            select(ResearchReport)
            .where(
                ResearchReport.stock_code == stock_code,
                ResearchReport.published_at.is_not(None),
                ResearchReport.published_at >= since,
                ResearchReport.published_at <= through,
            )
            .order_by(ResearchReport.published_at, ResearchReport.id)
        )
    )
    prior_by_broker: dict[str, float] = {}
    revision_up = 0
    revision_down = 0
    for report in reports:
        target = _float(report.target_price)
        if target is None:
            continue
        broker = str(report.broker_name or "unknown").strip().casefold()
        previous = prior_by_broker.get(broker)
        if previous is not None:
            revision_up += int(target > previous)
            revision_down += int(target < previous)
        prior_by_broker[broker] = target

    fundamental = db.get(StockFundamentalSnapshot, stock_code)
    fundamental_payload = _fundamental_payload(fundamental)
    fundamental_fresh = bool(
        fundamental
        and fundamental.fetched_at.date() <= signal_date
        and (generated_at.date() - fundamental.fetched_at.date()).days <= FUNDAMENTAL_FRESH_DAYS
    )
    revenue_growth = _float(fundamental_payload.get("revenue_growth")) if fundamental_fresh else None
    operating_growth = (
        _float(fundamental_payload.get("operating_profit_growth")) if fundamental_fresh else None
    )
    revision_score = (1 if revision_up > revision_down else -1 if revision_down > revision_up else 0)
    fundamental_score = 0
    if operating_growth is not None:
        fundamental_score += 1 if operating_growth >= 10.0 else -1 if operating_growth <= -10.0 else 0
    if revenue_growth is not None:
        fundamental_score += 1 if revenue_growth > 0 else -1 if revenue_growth < 0 else 0
    total_score = revision_score + fundamental_score
    available = bool(reports or fundamental_fresh)
    state = (
        "supportive"
        if available and total_score > 0
        else "caution"
        if available and total_score < 0
        else "neutral"
        if available
        else "unavailable"
    )
    latest_report_at = reports[-1].published_at if reports else None
    latest_as_of: Optional[date | datetime] = latest_report_at
    if fundamental and fundamental_fresh and (
        latest_report_at is None or fundamental.fetched_at > latest_report_at
    ):
        latest_as_of = fundamental.fetched_at
    growth_text = (
        f"매출 {revenue_growth:+.1f}%·영업이익 {operating_growth:+.1f}%"
        if revenue_growth is not None and operating_growth is not None
        else "실적 성장률 자료 제한"
    )
    summary = (
        f"증권사 목표가 상향 {revision_up}·하향 {revision_down}, {growth_text}"
        if available
        else "신호일 기준 사용 가능한 실적·컨센서스 자료가 없습니다."
    )
    evidence = _evidence_item(
        "earnings",
        "실적·컨센서스 변화",
        state,
        summary,
        "저장 증권사 리포트 + 네이버금융 실적 스냅샷",
        as_of=latest_as_of,
        score=max(-100.0, min(100.0, total_score * 35.0)) if available else None,
        available=available,
    )

    checks: list[dict[str, Any]] = []
    research_run = _latest_successful_ingestion(
        db,
        source="research",
        datasets=("naver_finance",),
    )
    research_age = (
        (_utc_naive(generated_at) - research_run.finished_at).total_seconds() / 60.0
        if research_run and research_run.finished_at
        else None
    )
    research_state = (
        "ready"
        if research_age is not None and research_age <= RESEARCH_INGESTION_MAX_AGE_MINUTES
        else "stale"
        if research_run
        else "unavailable"
    )
    checks.append(
        _source_check(
            "research",
            "증권사 리포트 API",
            state=research_state,
            source="naver_finance",
            as_of=research_run.finished_at if research_run else None,
            message=(
                f"최근 수집 성공 후 {research_age:.0f}분"
                if research_age is not None
                else "성공한 수집 이력이 없습니다."
            ),
            critical=False,
        )
    )
    checks.append(
        _source_check(
            "fundamentals",
            "실적 스냅샷",
            state="ready" if fundamental_fresh else "stale" if fundamental else "unavailable",
            source=fundamental.source if fundamental else "naver_finance",
            as_of=fundamental.fetched_at if fundamental else None,
            message=(
                f"{FUNDAMENTAL_FRESH_DAYS}일 이내 실적 스냅샷"
                if fundamental_fresh
                else "실적 스냅샷이 없거나 최신성 기준을 벗어났습니다."
            ),
            critical=False,
        )
    )
    return evidence, checks


def _disclosure_evidence(
    db: Session,
    *,
    stock_code: str,
    signal_date: date,
    generated_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    run = _latest_successful_ingestion(
        db,
        source="disclosure",
        datasets=("dart_api", "dart_web"),
    )
    age_minutes = (
        (_utc_naive(generated_at) - run.finished_at).total_seconds() / 60.0
        if run and run.finished_at
        else None
    )
    source_ready = bool(
        age_minutes is not None
        and age_minutes <= DISCLOSURE_INGESTION_MAX_AGE_MINUTES
    )
    cutoff = datetime.combine(
        signal_date - timedelta(days=DISCLOSURE_RISK_LOOKBACK_DAYS),
        time.min,
    )
    through = datetime.combine(signal_date, time.max)
    disclosures = list(
        db.scalars(
            select(DisclosureItem)
            .where(
                DisclosureItem.stock_code == stock_code,
                DisclosureItem.published_at.is_not(None),
                DisclosureItem.published_at >= cutoff,
                DisclosureItem.published_at <= through,
            )
            .order_by(desc(DisclosureItem.published_at), desc(DisclosureItem.id))
            .limit(50)
        )
    )
    risks = [
        item
        for item in disclosures
        if any(token.casefold() in _normalize_text(item.report_name) for token in HARD_DISCLOSURE_RISK_TOKENS)
    ]
    vetoes = [f"중대 공시: {item.report_name}" for item in risks[:3]]
    if not source_ready:
        state = "unavailable"
        summary = "공시 API 최신성을 확인하지 못해 신규 매수를 보류합니다."
        available = False
    elif risks:
        state = "caution"
        summary = f"최근 {DISCLOSURE_RISK_LOOKBACK_DAYS}일 중대 공시 {len(risks)}건 · {risks[0].report_name}"
        available = True
    else:
        state = "neutral"
        summary = f"최근 {DISCLOSURE_RISK_LOOKBACK_DAYS}일 신규매수 차단 공시 없음"
        available = True
    evidence = _evidence_item(
        "disclosure_risk",
        "중대 공시 위험",
        state,
        summary,
        "OpenDART 공시",
        as_of=run.finished_at if run else None,
        score=-100.0 if risks else 0.0 if source_ready else None,
        available=available,
        used_for_entry=True,
    )
    check = _source_check(
        "disclosure",
        "OpenDART 공시 API",
        state="ready" if source_ready else "stale" if run else "unavailable",
        source=(run.dataset if run else "OpenDART"),
        as_of=run.finished_at if run else None,
        message=(
            f"최근 수집 성공 후 {age_minutes:.0f}분"
            if age_minutes is not None
            else "성공한 수집 이력이 없습니다."
        ),
        critical=True,
    )
    return evidence, check, vetoes


def _relative_strength_evidence(
    *,
    stock: StockMaster,
    prices: list[DailyPrice],
    signal_date: date,
    relative_context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    eligible = [row for row in prices if row.trade_date <= signal_date]
    stock_return = _return_over_rows(eligible, 20)
    index_context = (relative_context.get("market_indices") or {}).get(stock.market) or {}
    index_ready = index_context.get("state") == "ready"
    market_return = _float(index_context.get("return20")) if index_ready else None
    sector_key = investment_sector_fields(stock.sector, stock.industry)["investment_sector"]
    sector_return = _float((relative_context.get("sector_returns") or {}).get(str(sector_key)))
    peer_count = int((relative_context.get("sector_counts") or {}).get(str(sector_key)) or 0)
    benchmarks = [item for item in (market_return, sector_return) if item is not None]
    available = stock_return is not None and index_ready and bool(benchmarks)
    benchmark_return = sum(benchmarks) / len(benchmarks) if benchmarks else None
    excess = stock_return - benchmark_return if stock_return is not None and benchmark_return is not None else None
    if available and excess is not None and excess >= RELATIVE_STRENGTH_MARGIN:
        state = "supportive"
    elif available and excess is not None and excess <= -RELATIVE_STRENGTH_MARGIN:
        state = "caution"
    elif available:
        state = "neutral"
    else:
        state = "unavailable"
    summary = (
        f"종목 20일 {stock_return * 100:+.1f}%·시장 {market_return * 100:+.1f}%"
        + (f"·섹터 {sector_return * 100:+.1f}%({peer_count}종목)" if sector_return is not None else "·섹터 표본 부족")
        + f"·초과 {excess * 100:+.1f}%p"
        if stock_return is not None and market_return is not None and excess is not None
        else "시장지수 또는 비교 종목 자료가 최신이 아닙니다."
    )
    evidence = _evidence_item(
        "relative_strength",
        "시장·섹터 상대강도",
        state,
        summary,
        "저장 일봉 + Yahoo Finance 시장지수",
        as_of=date.fromisoformat(str(index_context["as_of"])) if index_context.get("as_of") else None,
        score=max(-100.0, min(100.0, (excess or 0.0) * 1000.0)) if available else None,
        available=available,
    )
    vetoes = ["시장 급락·고변동 국면"] if index_context.get("panic") else []
    check = _source_check(
        "market_index",
        f"{stock.market} 시장지수",
        state=str(index_context.get("state") or "unavailable"),
        source=str(index_context.get("source") or index_context.get("series_code") or "yahoo"),
        as_of=date.fromisoformat(str(index_context["as_of"])) if index_context.get("as_of") else None,
        message=str(index_context.get("message") or "시장지수 자료가 없습니다."),
        critical=True,
    )
    return evidence, check, vetoes


def build_entry_evidence_payload(
    db: Session,
    stock: StockMaster,
    prices: list[DailyPrice],
    *,
    signal_date: date,
    now: Optional[datetime] = None,
    relative_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    generated_at = _kst(now)
    sorted_prices = sorted(prices, key=lambda item: item.trade_date)
    eligible_prices = [row for row in sorted_prices if row.trade_date <= signal_date]
    latest_price_date = eligible_prices[-1].trade_date if eligible_prices else None
    price_ready = latest_price_date == signal_date
    price_check = _source_check(
        "price",
        "확정 일봉",
        state="ready" if price_ready else "stale" if latest_price_date else "unavailable",
        source="저장 일봉",
        as_of=latest_price_date,
        message=(
            "신호일의 완전한 종가가 있습니다."
            if price_ready
            else f"최신 종가 {latest_price_date or '-'}와 신호일 {signal_date}이 다릅니다."
        ),
        critical=True,
    )
    shared_relative = relative_context or build_relative_strength_context(db, signal_date)
    relative, market_check, market_vetoes = _relative_strength_evidence(
        stock=stock,
        prices=eligible_prices,
        signal_date=signal_date,
        relative_context=shared_relative,
    )
    flow, flow_check = _flow_evidence(
        db,
        stock_code=stock.code,
        prices=eligible_prices,
        signal_date=signal_date,
    )
    earnings, earnings_checks = _earnings_evidence(
        db,
        stock_code=stock.code,
        signal_date=signal_date,
        generated_at=generated_at,
    )
    disclosure, disclosure_check, disclosure_vetoes = _disclosure_evidence(
        db,
        stock_code=stock.code,
        signal_date=signal_date,
        generated_at=generated_at,
    )
    evidence = [earnings, relative, flow, disclosure]
    source_checks = [price_check, market_check, flow_check, *earnings_checks, disclosure_check]
    supporting = [item["key"] for item in evidence if item.get("used_for_entry") and item.get("state") == "supportive"]
    caution = [item["key"] for item in evidence if item.get("used_for_entry") and item.get("state") == "caution"]
    vetoes = [*market_vetoes, *disclosure_vetoes]
    critical_failures = [
        check["key"]
        for check in source_checks
        if check.get("critical") and check.get("state") != "ready"
    ]
    independent_available = sum(
        1
        for item in evidence
        if item["key"] in {"earnings", "relative_strength", "flow"} and item.get("available")
    )
    quality_state = (
        "blocked"
        if vetoes
        else "limited"
        if critical_failures or independent_available < 2
        else "ready"
    )
    quality_reasons: list[str] = []
    if critical_failures:
        quality_reasons.append(f"핵심 자료 미확인: {', '.join(critical_failures)}")
    if independent_available < 2:
        quality_reasons.append(f"독립 근거 {independent_available}/3개만 사용 가능")
    quality_reasons.extend(vetoes)
    if not quality_reasons:
        quality_reasons.append("가격·시장·공시 최신성과 독립 근거가 확인됐습니다.")
    return {
        "policy_version": ENTRY_EVIDENCE_POLICY_VERSION,
        "strategy_version": ENTRY_EVIDENCE_STRATEGY_VERSION,
        "effective_date": ENTRY_EVIDENCE_EFFECTIVE_DATE.isoformat(),
        "stock_code": stock.code,
        "signal_date": signal_date.isoformat(),
        "generated_at": generated_at.isoformat(),
        "quality": {
            "state": quality_state,
            "reasons": quality_reasons,
            "critical_failures": critical_failures,
            "independent_available": independent_available,
            "source_checks": source_checks,
        },
        "supportive_keys": supporting,
        "caution_keys": caution,
        "supportive_count": len(supporting),
        "caution_count": len(caution),
        "vetoes": vetoes,
        "required_supports": {
            "trend_continuation": 1,
            "early_turn": 2,
        },
        "evidence": evidence,
    }


def entry_confirmation_decision(
    payload: Optional[dict[str, Any]],
    setup: Optional[str],
    *,
    signal_date: date,
) -> dict[str, Any]:
    normalized_setup = setup or "trend_continuation"
    if signal_date < ENTRY_EVIDENCE_EFFECTIVE_DATE:
        return {
            "allowed": True,
            "state": "legacy",
            "required_supports": 0,
            "supportive_count": 0,
            "reason": "v7 독립 근거 적용일 이전의 가격 전략 신호",
        }
    if not payload:
        return {
            "allowed": False,
            "state": "limited",
            "required_supports": 2 if normalized_setup == "early_turn" else 1,
            "supportive_count": 0,
            "reason": "신호일의 고정된 매수 확인 스냅샷이 없어 확정매수를 보류",
        }
    required = int((payload.get("required_supports") or {}).get(normalized_setup) or 1)
    supportive_count = int(payload.get("supportive_count") or 0)
    caution_count = int(payload.get("caution_count") or 0)
    quality_state = str((payload.get("quality") or {}).get("state") or "limited")
    vetoes = [str(item) for item in payload.get("vetoes") or []]
    allowed = bool(
        quality_state == "ready"
        and not vetoes
        and supportive_count >= required
        and caution_count < 2
    )
    if vetoes:
        reason = f"신규매수 차단: {vetoes[0]}"
    elif quality_state != "ready":
        reasons = [str(item) for item in (payload.get("quality") or {}).get("reasons") or []]
        reason = reasons[0] if reasons else "핵심 자료 최신성을 확인하는 중"
    elif supportive_count < required:
        reason = f"독립 우호 근거 {supportive_count}/{required}개로 매수 확인 부족"
    elif caution_count >= 2:
        reason = f"주의 근거 {caution_count}개로 신규매수 보류"
    else:
        reason = f"독립 우호 근거 {supportive_count}/{required}개와 최신성 확인 완료"
    return {
        "allowed": allowed,
        "state": "approved" if allowed else "blocked" if vetoes else "limited",
        "required_supports": required,
        "supportive_count": supportive_count,
        "caution_count": caution_count,
        "reason": reason,
    }


def confirmation_response_payload(
    payload: Optional[dict[str, Any]],
    *,
    setup: Optional[str],
    signal_date: Optional[date],
) -> dict[str, Any]:
    effective_signal_date = signal_date or ENTRY_EVIDENCE_EFFECTIVE_DATE
    decision = entry_confirmation_decision(payload, setup, signal_date=effective_signal_date)
    if not payload:
        return {
            "state": "limited",
            "label": "매수 근거 확인 중",
            "score": None,
            "available_count": 0,
            "total_count": 4,
            "note": decision["reason"],
            "entry_allowed": decision["allowed"],
            "required_supports": decision["required_supports"],
            "supportive_count": 0,
            "caution_count": 0,
            "vetoes": [],
            "quality_state": "limited",
            "source_checks": [],
            "evidence": [],
        }
    evidence = list(payload.get("evidence") or [])
    available_count = sum(1 for item in evidence if item.get("available"))
    quality = payload.get("quality") or {}
    state = (
        "supportive"
        if decision["allowed"]
        else "caution"
        if payload.get("vetoes") or int(payload.get("caution_count") or 0) >= 2
        else "limited"
    )
    label = (
        "매수 근거 확인 완료"
        if decision["allowed"]
        else "신규매수 차단"
        if payload.get("vetoes")
        else "매수 근거 확인 중"
    )
    return {
        "state": state,
        "label": label,
        "score": float(payload.get("supportive_count") or 0) - float(payload.get("caution_count") or 0),
        "available_count": available_count,
        "total_count": len(evidence),
        "note": decision["reason"],
        "entry_allowed": decision["allowed"],
        "required_supports": decision["required_supports"],
        "supportive_count": decision["supportive_count"],
        "caution_count": decision.get("caution_count", 0),
        "vetoes": list(payload.get("vetoes") or []),
        "quality_state": str(quality.get("state") or "limited"),
        "source_checks": list(quality.get("source_checks") or []),
        "evidence": evidence,
    }


def _decode_snapshot(row: QuantSignalEvidenceSnapshot) -> Optional[dict[str, Any]]:
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def load_entry_evidence_timeline(
    db: Session,
    stock_code: str,
) -> dict[date, dict[str, Any]]:
    rows = list(
        db.scalars(
            select(QuantSignalEvidenceSnapshot)
            .where(
                QuantSignalEvidenceSnapshot.stock_code == stock_code,
                QuantSignalEvidenceSnapshot.strategy_version == ENTRY_EVIDENCE_STRATEGY_VERSION,
                QuantSignalEvidenceSnapshot.signal_date >= ENTRY_EVIDENCE_EFFECTIVE_DATE,
            )
            .order_by(QuantSignalEvidenceSnapshot.signal_date)
        )
    )
    timeline: dict[date, dict[str, Any]] = {}
    for row in rows:
        payload = _decode_snapshot(row)
        if payload:
            timeline[row.signal_date] = payload
    return timeline


def ensure_entry_evidence_snapshot(
    db: Session,
    stock: StockMaster,
    prices: list[DailyPrice],
    *,
    signal_date: date,
    now: Optional[datetime] = None,
    relative_context: Optional[dict[str, Any]] = None,
    persist: bool = True,
    commit_on_persist: bool = True,
    latest_market_date_override: Optional[date] = None,
) -> Optional[dict[str, Any]]:
    if signal_date < ENTRY_EVIDENCE_EFFECTIVE_DATE:
        return None
    existing = db.scalar(
        select(QuantSignalEvidenceSnapshot).where(
            QuantSignalEvidenceSnapshot.stock_code == stock.code,
            QuantSignalEvidenceSnapshot.signal_date == signal_date,
            QuantSignalEvidenceSnapshot.strategy_version == ENTRY_EVIDENCE_STRATEGY_VERSION,
        )
    )
    if existing:
        return _decode_snapshot(existing)

    latest_market_date = latest_market_date_override
    if latest_market_date is None:
        latest_market_date = db.scalar(
            select(func.max(DailyPrice.trade_date))
            .join(StockMaster, StockMaster.code == DailyPrice.code)
            .where(
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(("KOSPI", "KOSDAQ")),
                DailyPrice.close.is_not(None),
            )
        )
    if latest_market_date != signal_date:
        # Never reconstruct a missing historical snapshot from today's newer
        # mutable research/fundamental tables.
        return None
    payload = build_entry_evidence_payload(
        db,
        stock,
        prices,
        signal_date=signal_date,
        now=now,
        relative_context=relative_context,
    )
    if not persist:
        return payload
    generated_at = _kst(now)
    row = QuantSignalEvidenceSnapshot(
        stock_code=stock.code,
        signal_date=signal_date,
        strategy_version=ENTRY_EVIDENCE_STRATEGY_VERSION,
        policy_version=ENTRY_EVIDENCE_POLICY_VERSION,
        quality_state=str((payload.get("quality") or {}).get("state") or "limited"),
        payload=json.dumps(payload, ensure_ascii=False, default=_json_default),
        generated_at=_utc_naive(generated_at),
    )
    db.add(row)
    if not commit_on_persist:
        # Market-wide refreshes can hold more than 100,000 price ORM objects.
        # Committing one stock at a time expires that full identity map on every
        # iteration. The caller batches these inserts into one final commit.
        return payload
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(QuantSignalEvidenceSnapshot).where(
                QuantSignalEvidenceSnapshot.stock_code == stock.code,
                QuantSignalEvidenceSnapshot.signal_date == signal_date,
                QuantSignalEvidenceSnapshot.strategy_version == ENTRY_EVIDENCE_STRATEGY_VERSION,
            )
        )
        return _decode_snapshot(existing) if existing else payload
    return payload
