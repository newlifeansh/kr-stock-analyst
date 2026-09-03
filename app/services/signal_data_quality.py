from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
import json
from time import monotonic
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import desc, distinct, func, select
from sqlalchemy.orm import Session

from app.config import Settings
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
from app.services.market_calendar import (
    latest_completed_korea_market_session_date,
)
from app.services.signal_entry_evidence import (
    ENTRY_EVIDENCE_EFFECTIVE_DATE,
    ENTRY_EVIDENCE_STRATEGY_VERSION,
)
from app.services.quant_signals import STRATEGY_VERSION


KST = ZoneInfo("Asia/Seoul")
TOP_UNIVERSE_LIMIT = 100


def _kst(value: Optional[datetime] = None) -> datetime:
    current = value or datetime.now(KST)
    if current.tzinfo is None:
        return current.replace(tzinfo=KST)
    return current.astimezone(KST)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _ratio(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _state_for_coverage(rate: float, *, ready: float = 0.95, caution: float = 0.80) -> str:
    if rate >= ready:
        return "ready"
    if rate >= caution:
        return "caution"
    return "stale"


def _latest_ingestion(
    db: Session,
    *,
    source: str,
    datasets: tuple[str, ...],
) -> Optional[IngestionRun]:
    return db.scalar(
        select(IngestionRun)
        .where(
            IngestionRun.source == source,
            IngestionRun.dataset.in_(datasets),
            IngestionRun.status == "success",
            IngestionRun.finished_at.is_not(None),
        )
        .order_by(desc(IngestionRun.finished_at), desc(IngestionRun.id))
        .limit(1)
    )


def _run_freshness(
    db: Session,
    *,
    source: str,
    datasets: tuple[str, ...],
    now: datetime,
    max_age_seconds: int,
) -> dict[str, Any]:
    run = _latest_ingestion(db, source=source, datasets=datasets)
    age_seconds = (
        max(0.0, (_utc_naive(now) - run.finished_at).total_seconds())
        if run and run.finished_at
        else None
    )
    state = (
        "ready"
        if age_seconds is not None and age_seconds <= max_age_seconds
        else "stale"
        if run
        else "unavailable"
    )
    return {
        "state": state,
        "source": source,
        "dataset": run.dataset if run else datasets[0],
        "last_success_at": run.finished_at if run else None,
        "age_seconds": round(age_seconds) if age_seconds is not None else None,
        "rows_loaded": int(run.rows_loaded or 0) if run else 0,
        "message": run.message if run else "성공한 수집 이력이 없습니다.",
    }


def _complete_ohlc(row: DailyPrice) -> bool:
    if None in (row.open, row.high, row.low, row.close):
        return False
    if min(int(row.open), int(row.high), int(row.low), int(row.close)) <= 0:
        return False
    return bool(row.high >= max(row.open, row.close) and row.low <= min(row.open, row.close))


def _non_trading_placeholder(row: Optional[DailyPrice]) -> bool:
    if row is None or row.close is None or int(row.close) <= 0:
        return False
    return bool(
        not _complete_ohlc(row)
        and int(row.volume or 0) == 0
        and int(row.trading_value or 0) == 0
    )


def _top_codes(db: Session, market_date: date) -> list[str]:
    return list(
        db.scalars(
            select(DailyPrice.code)
            .join(StockMaster, StockMaster.code == DailyPrice.code)
            .where(
                DailyPrice.trade_date == market_date,
                DailyPrice.market_cap.is_not(None),
                DailyPrice.market_cap > 0,
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            )
            .order_by(desc(DailyPrice.market_cap), DailyPrice.code)
            .limit(TOP_UNIVERSE_LIMIT)
        )
    )


def signal_data_quality_status(
    db: Session,
    settings: Settings,
    *,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current = _kst(now)
    # Keep every stored-data coverage check on the same completed session.
    # During trading hours a quote upsert can create today's first DailyPrice
    # row long before the full market candle/universe is available.  Treating
    # that partial date as the Top100 basis makes otherwise healthy flow,
    # fundamental, research, and index coverage collapse together.
    calendar_target = latest_completed_korea_market_session_date(current)
    flow_target = calendar_target
    price_date_statement = (
        select(func.max(DailyPrice.trade_date))
        .join(StockMaster, StockMaster.code == DailyPrice.code)
        .where(
            StockMaster.is_active.is_(True),
            StockMaster.market.in_(("KOSPI", "KOSDAQ")),
            DailyPrice.close.is_not(None),
        )
    )
    if calendar_target is not None:
        price_date_statement = price_date_statement.where(
            DailyPrice.trade_date <= calendar_target
        )
    latest_price_date = db.scalar(
        price_date_statement
    )
    # A daily signal may only use a completed session. Requiring today's
    # still-forming candle before the evening publication window would mark a
    # healthy store stale and, worse, tempt downstream code to freeze partial
    # prices as end-of-day evidence.
    top_codes = _top_codes(db, latest_price_date) if latest_price_date else []
    top_total = len(top_codes)

    price_rows = (
        list(
            db.scalars(
                select(DailyPrice).where(
                    DailyPrice.code.in_(tuple(top_codes)),
                    DailyPrice.trade_date == latest_price_date,
                )
            )
        )
        if top_codes and latest_price_date
        else []
    )
    price_complete = sum(1 for row in price_rows if _complete_ohlc(row))
    placeholder_candidates = {
        row.code for row in price_rows if _non_trading_placeholder(row)
    }
    completed_placeholder_codes: set[str] = set()
    if placeholder_candidates and calendar_target:
        completed_rows = list(
            db.scalars(
                select(DailyPrice).where(
                    DailyPrice.code.in_(tuple(placeholder_candidates)),
                    DailyPrice.trade_date == calendar_target,
                )
            )
        )
        completed_placeholder_codes = {
            row.code for row in completed_rows if _non_trading_placeholder(row)
        }
    price_evaluated_total = max(0, top_total - len(completed_placeholder_codes))
    price_rate = _ratio(price_complete, price_evaluated_total)

    all_active_rows = (
        list(
            db.execute(
                select(StockMaster.code, DailyPrice)
                .outerjoin(
                    DailyPrice,
                    (DailyPrice.code == StockMaster.code)
                    & (DailyPrice.trade_date == latest_price_date),
                )
                .where(
                    StockMaster.is_active.is_(True),
                    StockMaster.market.in_(("KOSPI", "KOSDAQ")),
                )
            )
        )
        if latest_price_date
        else []
    )
    all_active_placeholders = {
        code
        for code, row in all_active_rows
        if _non_trading_placeholder(row)
    }
    all_active_total = max(0, len(all_active_rows) - len(all_active_placeholders))
    all_active_complete = sum(
        1 for _code, row in all_active_rows if row is not None and _complete_ohlc(row)
    )
    all_active_rate = _ratio(all_active_complete, all_active_total)
    price_date_ready = bool(
        latest_price_date
        and (calendar_target is None or latest_price_date >= calendar_target)
    )
    price_state = (
        min(
            (_state_for_coverage(price_rate), _state_for_coverage(all_active_rate)),
            key=("unavailable", "stale", "caution", "ready").index,
        )
        if price_date_ready
        else "stale"
    )

    latest_flow_rows = (
        db.execute(
            select(InvestorFlow.code, func.max(InvestorFlow.trade_date))
            .where(InvestorFlow.code.in_(tuple(top_codes)))
            .group_by(InvestorFlow.code)
        ).all()
        if top_codes
        else []
    )
    latest_flow_by_code = {str(code): latest for code, latest in latest_flow_rows}
    flow_ready = sum(
        1
        for code in top_codes
        if latest_flow_by_code.get(code)
        and (flow_target is None or latest_flow_by_code[code] >= flow_target)
    )
    flow_rate = _ratio(flow_ready, top_total)

    fundamental_cutoff = _utc_naive(current) - timedelta(
        days=max(1, int(settings.fundamental_snapshot_refresh_days))
    )
    fundamental_ready = (
        int(
            db.scalar(
                select(func.count(distinct(StockFundamentalSnapshot.stock_code))).where(
                    StockFundamentalSnapshot.stock_code.in_(tuple(top_codes)),
                    StockFundamentalSnapshot.fetched_at >= fundamental_cutoff,
                )
            )
            or 0
        )
        if top_codes
        else 0
    )
    fundamental_rate = _ratio(fundamental_ready, top_total)
    fundamental_ingestion = _run_freshness(
        db,
        source="naver_finance",
        datasets=("stock_fundamental_snapshot",),
        now=current,
        max_age_seconds=max(
            90_000,
            int(settings.fundamental_snapshot_poll_seconds) * 2,
        ),
    )

    research_since = _utc_naive(current) - timedelta(days=180)
    research_covered = (
        int(
            db.scalar(
                select(func.count(distinct(ResearchReport.stock_code))).where(
                    ResearchReport.stock_code.in_(tuple(top_codes)),
                    ResearchReport.published_at >= research_since,
                )
            )
            or 0
        )
        if top_codes
        else 0
    )
    research_rate = _ratio(research_covered, top_total)
    research_api = _run_freshness(
        db,
        source="research",
        datasets=("naver_finance",),
        now=current,
        max_age_seconds=max(1800, int(settings.research_poll_seconds) * 3),
    )
    disclosure_api = _run_freshness(
        db,
        source="disclosure",
        datasets=("dart_api", "dart_web"),
        now=current,
        max_age_seconds=max(1200, int(settings.disclosure_poll_seconds) * 3),
    )

    index_latest_rows = db.execute(
        select(MacroObservation.series_code, func.max(MacroObservation.period))
        .where(
            MacroObservation.source.in_(("yahoo", "naver_finance")),
            MacroObservation.series_code.in_(("^KS11", "^KQ11")),
            MacroObservation.item_code == "close",
        )
        .group_by(MacroObservation.series_code)
    ).all()
    index_latest = {str(code): period for code, period in index_latest_rows}
    index_target = latest_price_date or calendar_target
    index_ready = sum(
        1
        for code in ("^KS11", "^KQ11")
        if index_latest.get(code)
        and (index_target is None or index_latest[code] >= index_target.isoformat())
    )

    evidence_ready = 0
    evidence_rate: Optional[float] = None
    evidence_state = "not_applicable"
    evidence_target = (
        calendar_target
        if latest_price_date and calendar_target and latest_price_date >= calendar_target
        else latest_price_date
    )
    if evidence_target and evidence_target >= ENTRY_EVIDENCE_EFFECTIVE_DATE and top_codes:
        evidence_ready = int(
            db.scalar(
                select(func.count(distinct(QuantSignalEvidenceSnapshot.stock_code))).where(
                    QuantSignalEvidenceSnapshot.stock_code.in_(tuple(top_codes)),
                    QuantSignalEvidenceSnapshot.signal_date == evidence_target,
                    QuantSignalEvidenceSnapshot.strategy_version == ENTRY_EVIDENCE_STRATEGY_VERSION,
                )
            )
            or 0
        )
        evidence_rate = _ratio(evidence_ready, top_total)
        evidence_state = _state_for_coverage(evidence_rate)

    master_codes = select(StockMaster.code)
    orphan_counts = {
        "price": int(
            db.scalar(
                select(func.count(distinct(DailyPrice.code))).where(
                    ~DailyPrice.code.in_(master_codes)
                )
            )
            or 0
        ),
        "flow": int(
            db.scalar(
                select(func.count(distinct(InvestorFlow.code))).where(
                    ~InvestorFlow.code.in_(master_codes)
                )
            )
            or 0
        ),
        "research": int(
            db.scalar(
                select(func.count(distinct(ResearchReport.stock_code))).where(
                    ResearchReport.stock_code.is_not(None),
                    ~ResearchReport.stock_code.in_(master_codes),
                )
            )
            or 0
        ),
        "disclosure": int(
            db.scalar(
                select(func.count(distinct(DisclosureItem.stock_code))).where(
                    DisclosureItem.stock_code.is_not(None),
                    ~DisclosureItem.stock_code.in_(master_codes),
                )
            )
            or 0
        ),
    }
    signal_window_orphan_counts = {
        "price": (
            int(
                db.scalar(
                    select(func.count(distinct(DailyPrice.code))).where(
                        DailyPrice.trade_date == latest_price_date,
                        ~DailyPrice.code.in_(master_codes),
                    )
                )
                or 0
            )
            if latest_price_date
            else 0
        ),
        "flow": (
            int(
                db.scalar(
                    select(func.count(distinct(InvestorFlow.code))).where(
                        InvestorFlow.trade_date >= flow_target,
                        ~InvestorFlow.code.in_(master_codes),
                    )
                )
                or 0
            )
            if flow_target
            else 0
        ),
    }
    malformed_fundamentals = 0
    if top_codes:
        snapshots = list(
            db.scalars(
                select(StockFundamentalSnapshot).where(
                    StockFundamentalSnapshot.stock_code.in_(tuple(top_codes))
                )
            )
        )
        for snapshot in snapshots:
            try:
                payload = json.loads(snapshot.payload)
            except (TypeError, ValueError):
                malformed_fundamentals += 1
                continue
            if not isinstance(payload, dict):
                malformed_fundamentals += 1

    future_counts = {
        "price": int(
            db.scalar(select(func.count()).select_from(DailyPrice).where(DailyPrice.trade_date > current.date()))
            or 0
        ),
        "flow": int(
            db.scalar(select(func.count()).select_from(InvestorFlow).where(InvestorFlow.trade_date > current.date()))
            or 0
        ),
        "research": int(
            db.scalar(
                select(func.count()).select_from(ResearchReport).where(
                    ResearchReport.published_at > _utc_naive(current) + timedelta(days=1)
                )
            )
            or 0
        ),
        "disclosure": int(
            db.scalar(
                select(func.count()).select_from(DisclosureItem).where(
                    DisclosureItem.published_at > _utc_naive(current) + timedelta(days=1)
                )
            )
            or 0
        ),
    }

    datasets = {
        "price": {
            "state": price_state,
            "target_date": calendar_target,
            "latest_date": latest_price_date,
            "covered": price_complete,
            "total": price_evaluated_total,
            "universe_total": top_total,
            "non_trading_placeholder_count": len(completed_placeholder_codes),
            "non_trading_placeholder_codes": sorted(completed_placeholder_codes),
            "coverage_rate": price_rate,
            "all_active_covered": all_active_complete,
            "all_active_total": all_active_total,
            "all_active_coverage_rate": all_active_rate,
            "all_active_incomplete_count": max(
                0, all_active_total - all_active_complete
            ),
            "source": "KRX/Naver stored OHLC",
        },
        "investor_flow": {
            "state": _state_for_coverage(flow_rate),
            "target_date": flow_target,
            "covered": flow_ready,
            "total": top_total,
            "coverage_rate": flow_rate,
            "source": "Naver investor flow",
        },
        "market_index": {
            "state": "ready" if index_ready == 2 else "stale",
            "target_date": index_target,
            "covered": index_ready,
            "total": 2,
            "coverage_rate": round(index_ready / 2, 4),
            "latest_by_series": index_latest,
            "source": "Yahoo Finance chart API + Naver index close fallback",
        },
        "fundamentals": {
            "state": _state_for_coverage(fundamental_rate),
            "fresh_after": fundamental_cutoff,
            "covered": fundamental_ready,
            "total": top_total,
            "coverage_rate": fundamental_rate,
            "source": "Naver Finance snapshot",
            "api": fundamental_ingestion,
        },
        "research": {
            "state": research_api["state"] if research_api["state"] != "ready" else _state_for_coverage(research_rate, ready=0.80, caution=0.60),
            "covered": research_covered,
            "total": top_total,
            "coverage_rate": research_rate,
            "api": research_api,
        },
        "disclosure": {
            "state": disclosure_api["state"],
            "api": disclosure_api,
        },
        "entry_evidence_snapshot": {
            "state": evidence_state,
            "signal_date": evidence_target,
            "covered": evidence_ready,
            "total": top_total if evidence_rate is not None else 0,
            "coverage_rate": evidence_rate,
        },
    }
    critical_states = [
        datasets["price"]["state"],
        datasets["investor_flow"]["state"],
        datasets["market_index"]["state"],
        datasets["fundamentals"]["state"],
        datasets["research"]["state"],
        datasets["disclosure"]["state"],
    ]
    if evidence_state != "not_applicable":
        critical_states.append(evidence_state)
    coherence_ok = (
        not any(signal_window_orphan_counts.values())
        and not any(future_counts.values())
        and malformed_fundamentals == 0
    )
    status = (
        "ready"
        if all(state == "ready" for state in critical_states) and coherence_ok
        else "degraded"
    )
    return {
        "status": status,
        "strategy_version": STRATEGY_VERSION,
        "as_of": current,
        "universe": {
            "basis": "point-in-time market-cap top 100",
            "date": latest_price_date,
            "count": top_total,
        },
        "datasets": datasets,
        "coherence": {
            "state": "ready" if coherence_ok else "caution",
            "orphan_stock_codes": orphan_counts,
            "signal_window_orphan_stock_codes": signal_window_orphan_counts,
            "orphan_scope_note": (
                "전체 보관 이력의 미매핑 코드는 상장폐지·합병 이력을 포함한 참고치이며, "
                "최신 가격·수급 신호 구간에 존재할 때만 품질 상태를 낮춥니다."
            ),
            "future_dated_rows": future_counts,
            "malformed_fundamental_snapshots": malformed_fundamentals,
            "flow_normalization": "기관합계·외국인합계를 우선하고 세부 주체와 중복 합산하지 않음",
            "date_policy": "신호일 이후 자료는 사용하지 않고 일별 근거 스냅샷을 고정",
        },
    }


def _http_probe(
    key: str,
    source: str,
    url: str,
    *,
    params: Optional[dict[str, object]] = None,
    validator: Optional[Callable[[requests.Response], bool]] = None,
) -> dict[str, Any]:
    started = monotonic()
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.raise_for_status()
        valid = validator(response) if validator else bool(response.content)
        return {
            "key": key,
            "source": source,
            "state": "ready" if valid else "invalid",
            "http_status": response.status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "message": "응답 형식 확인" if valid else "응답은 성공했지만 예상 데이터가 없습니다.",
        }
    except Exception as exc:
        # ``requests`` exception strings can contain the fully prepared URL,
        # including the OpenDART credential in its query string. Public health
        # output must never echo that URL or any caller-supplied secret.
        status_code = (
            exc.response.status_code
            if isinstance(exc, requests.HTTPError) and exc.response is not None
            else None
        )
        return {
            "key": key,
            "source": source,
            "state": "unavailable",
            "http_status": status_code,
            "latency_ms": round((monotonic() - started) * 1000),
            "message": f"{type(exc).__name__}: 외부 원천 응답 확인 실패",
        }


def probe_signal_source_apis(
    settings: Settings,
    *,
    sample_code: str = "005930",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    current = _kst(now)
    yyyymmdd = current.strftime("%Y%m%d")

    def xml_has_rows(response: requests.Response) -> bool:
        return b'data="' in response.content

    def research_has_rows(response: requests.Response) -> bool:
        return "type_1" in response.content.decode("euc-kr", errors="ignore")

    def flow_has_rows(response: requests.Response) -> bool:
        text = response.content.decode("euc-kr", errors="ignore")
        return "기관" in text and "외국인" in text

    def yahoo_has_rows(response: requests.Response) -> bool:
        payload = response.json()
        return bool(((payload.get("chart") or {}).get("result") or []))

    probes: list[tuple[str, str, str, dict[str, object], Callable[[requests.Response], bool]]] = [
        (
            "price",
            "Naver chart",
            "https://fchart.stock.naver.com/sise.nhn",
            {"symbol": sample_code, "timeframe": "day", "count": "5", "requestType": "0"},
            xml_has_rows,
        ),
        (
            "flow",
            "Naver investor flow",
            "https://finance.naver.com/item/frgn.naver",
            {"code": sample_code, "page": 1},
            flow_has_rows,
        ),
        (
            "research",
            "Naver research",
            "https://finance.naver.com/research/company_list.naver",
            {"page": 1},
            research_has_rows,
        ),
        (
            "market_index",
            "Yahoo Finance chart",
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11",
            {"range": "5d", "interval": "1d"},
            yahoo_has_rows,
        ),
    ]
    if settings.dart_api_key:
        begin = (current - timedelta(days=2)).strftime("%Y%m%d")

        def dart_has_rows(response: requests.Response) -> bool:
            payload = response.json()
            return str(payload.get("status")) in {"000", "013"}

        probes.append(
            (
                "disclosure",
                "OpenDART API",
                "https://opendart.fss.or.kr/api/list.json",
                {
                    "crtfc_key": settings.dart_api_key,
                    "bgn_de": begin,
                    "end_de": yyyymmdd,
                    "page_no": 1,
                    "page_count": 10,
                },
                dart_has_rows,
            )
        )
    else:
        probes.append(
            (
                "disclosure",
                "DART web",
                "https://dart.fss.or.kr/dsac001/mainAll.do",
                {},
                lambda response: "공시" in response.text,
            )
        )

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=len(probes)) as executor:
        futures = {
            executor.submit(
                _http_probe,
                key,
                source,
                url,
                params=params,
                validator=validator,
            ): key
            for key, source, url, params, validator in probes
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: item["key"])
    return {
        "status": "ready" if all(item["state"] == "ready" for item in results) else "degraded",
        "as_of": current,
        "sample_code": sample_code,
        "items": results,
    }
