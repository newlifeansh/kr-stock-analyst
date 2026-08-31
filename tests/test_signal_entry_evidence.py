from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import requests

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.collectors.macro import DEFAULT_MACRO_SERIES
from app.db import Base
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
from app.services import quant_signals
from app.services import briefing
from app.services.signal_data_quality import _http_probe, signal_data_quality_status
from app.services.signal_entry_evidence import (
    ENTRY_EVIDENCE_EFFECTIVE_DATE,
    ENTRY_EVIDENCE_STRATEGY_VERSION,
    _macro_index_context,
    build_entry_evidence_payload,
    ensure_entry_evidence_snapshot,
    entry_confirmation_decision,
)


SIGNAL_DATE = ENTRY_EVIDENCE_EFFECTIVE_DATE
GENERATED_AT = datetime(2026, 8, 21, 15, 45)


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _business_dates(count: int, through: date = SIGNAL_DATE) -> list[date]:
    values: list[date] = []
    current = through
    while len(values) < count:
        if current.weekday() < 5:
            values.append(current)
        current -= timedelta(days=1)
    return list(reversed(values))


def _seed_stock_data(db: Session) -> tuple[StockMaster, list[DailyPrice]]:
    stock = StockMaster(
        code="005930",
        name="삼성전자",
        market="KOSPI",
        sector="전기전자",
        industry="반도체",
        is_active=True,
    )
    db.add(stock)
    prices: list[DailyPrice] = []
    for index, trade_date in enumerate(_business_dates(80)):
        close = round(50_000 * (1.006**index))
        row = DailyPrice(
            code=stock.code,
            trade_date=trade_date,
            open=close - 100,
            high=close + 300,
            low=close - 300,
            close=close,
            volume=1_000_000,
            trading_value=10_000_000_000,
            market_cap=500_000_000_000,
        )
        prices.append(row)
        db.add(row)

    for trade_date in _business_dates(20):
        db.add_all(
            [
                InvestorFlow(
                    code=stock.code,
                    trade_date=trade_date,
                    investor_type="외국인",
                    net_buy_value=300_000_000,
                ),
                InvestorFlow(
                    code=stock.code,
                    trade_date=trade_date,
                    investor_type="기관합계",
                    net_buy_value=300_000_000,
                ),
                # These component rows are deliberately huge. The normalized
                # rule must ignore them when aggregate rows are available.
                InvestorFlow(
                    code=stock.code,
                    trade_date=trade_date,
                    investor_type="금융투자",
                    net_buy_value=90_000_000_000,
                ),
                InvestorFlow(
                    code=stock.code,
                    trade_date=trade_date,
                    investor_type="외국계",
                    net_buy_value=90_000_000_000,
                ),
            ]
        )

    db.add_all(
        [
            ResearchReport(
                source="naver_finance",
                source_category="company",
                external_id="r1",
                title="목표가 최초",
                stock_code=stock.code,
                broker_name="테스트증권",
                target_price=Decimal("80000"),
                published_at=datetime(2026, 7, 1, 9, 0),
            ),
            ResearchReport(
                source="naver_finance",
                source_category="company",
                external_id="r2",
                title="목표가 상향",
                stock_code=stock.code,
                broker_name="테스트증권",
                target_price=Decimal("90000"),
                published_at=datetime(2026, 8, 20, 9, 0),
            ),
            StockFundamentalSnapshot(
                stock_code=stock.code,
                source="naver_finance",
                payload=json.dumps(
                    {
                        "revenue_growth": "12.5",
                        "operating_profit_growth": "18.0",
                    }
                ),
                fetched_at=datetime(2026, 8, 21, 6, 20),
            ),
            IngestionRun(
                source="naver_finance",
                dataset="stock_fundamental_snapshot",
                status="success",
                started_at=datetime(2026, 8, 21, 6, 30),
                finished_at=datetime(2026, 8, 21, 6, 32),
                rows_loaded=1,
                message="target=1 refreshed=1 skipped=0 unavailable=0",
            ),
            IngestionRun(
                source="research",
                dataset="naver_finance",
                status="success",
                started_at=datetime(2026, 8, 21, 6, 35),
                finished_at=datetime(2026, 8, 21, 6, 38),
                rows_loaded=10,
            ),
            IngestionRun(
                source="disclosure",
                dataset="dart_api",
                status="success",
                started_at=datetime(2026, 8, 21, 6, 35),
                finished_at=datetime(2026, 8, 21, 6, 40),
                rows_loaded=10,
            ),
        ]
    )
    db.commit()
    return stock, prices


def _relative_context(stock: StockMaster, *, panic: bool = False) -> dict[str, object]:
    sector_key = investment_sector_fields(stock.sector, stock.industry)["investment_sector"]
    return {
        "signal_date": SIGNAL_DATE.isoformat(),
        "market_indices": {
            "KOSPI": {
                "state": "ready",
                "series_code": "^KS11",
                "as_of": SIGNAL_DATE.isoformat(),
                "return20": 0.01,
                "panic": panic,
                "message": "시장지수 최신",
            }
        },
        "sector_returns": {sector_key: 0.02},
        "sector_counts": {sector_key: 8},
        "universe_count": 100,
        "return_count": 100,
    }


def test_v7_uses_independent_evidence_and_does_not_double_count_flow_components():
    db = _session()
    stock, prices = _seed_stock_data(db)

    payload = build_entry_evidence_payload(
        db,
        stock,
        prices,
        signal_date=SIGNAL_DATE,
        now=GENERATED_AT,
        relative_context=_relative_context(stock),
    )

    evidence = {item["key"]: item for item in payload["evidence"]}
    assert payload["quality"]["state"] == "ready"
    assert payload["supportive_count"] == 3
    assert evidence["earnings"]["state"] == "supportive"
    assert evidence["relative_strength"]["state"] == "supportive"
    assert evidence["flow"]["state"] == "supportive"
    assert "+6.00%" in evidence["flow"]["summary"]
    assert entry_confirmation_decision(
        payload,
        "early_turn",
        signal_date=SIGNAL_DATE,
    )["allowed"] is True


def test_v7_hard_disclosure_and_market_panic_are_entry_vetoes():
    db = _session()
    stock, prices = _seed_stock_data(db)
    db.add(
        DisclosureItem(
            source="dart_api",
            external_id="d1",
            disclosure_category="major",
            company_name=stock.name,
            stock_code=stock.code,
            report_name="주주배정 유상증자 결정",
            published_at=datetime(2026, 8, 20, 10, 0),
        )
    )
    db.commit()

    payload = build_entry_evidence_payload(
        db,
        stock,
        prices,
        signal_date=SIGNAL_DATE,
        now=GENERATED_AT,
        relative_context=_relative_context(stock, panic=True),
    )

    assert any("중대 공시" in item for item in payload["vetoes"])
    assert "시장 급락·고변동 국면" in payload["vetoes"]
    decision = entry_confirmation_decision(
        payload,
        "trend_continuation",
        signal_date=SIGNAL_DATE,
    )
    assert decision["allowed"] is False
    assert decision["state"] == "blocked"


def test_v7_missing_or_stale_critical_evidence_never_confirms_a_buy():
    assert entry_confirmation_decision(
        None,
        "trend_continuation",
        signal_date=SIGNAL_DATE,
    )["allowed"] is False
    assert entry_confirmation_decision(
        None,
        "trend_continuation",
        signal_date=ENTRY_EVIDENCE_EFFECTIVE_DATE - timedelta(days=1),
    )["allowed"] is True

    db = _session()
    stock, prices = _seed_stock_data(db)
    payload = build_entry_evidence_payload(
        db,
        stock,
        prices,
        signal_date=SIGNAL_DATE,
        now=datetime(2026, 8, 21, 17, 0),
        relative_context=_relative_context(stock),
    )
    assert payload["quality"]["state"] == "limited"
    assert "disclosure" in payload["quality"]["critical_failures"]
    assert entry_confirmation_decision(
        payload,
        "trend_continuation",
        signal_date=SIGNAL_DATE,
    )["allowed"] is False


def test_v7_evidence_snapshot_is_immutable_after_it_is_created():
    db = _session()
    stock, prices = _seed_stock_data(db)
    first = ensure_entry_evidence_snapshot(
        db,
        stock,
        prices,
        signal_date=SIGNAL_DATE,
        now=GENERATED_AT,
        relative_context=_relative_context(stock),
    )
    assert first and first["vetoes"] == []

    db.add(
        DisclosureItem(
            source="dart_api",
            external_id="d-after",
            disclosure_category="major",
            company_name=stock.name,
            stock_code=stock.code,
            report_name="전환사채권 발행 결정",
            published_at=datetime(2026, 8, 21, 11, 0),
        )
    )
    db.commit()
    second = ensure_entry_evidence_snapshot(
        db,
        stock,
        prices,
        signal_date=SIGNAL_DATE,
        now=GENERATED_AT,
        relative_context=_relative_context(stock),
    )

    assert second == first
    assert db.scalar(select(QuantSignalEvidenceSnapshot).where(
        QuantSignalEvidenceSnapshot.strategy_version == ENTRY_EVIDENCE_STRATEGY_VERSION
    )) is not None


def test_quant_lifecycle_only_schedules_v7_buy_after_evidence_approval(monkeypatch):
    rows: list[DailyPrice] = []
    for index, trade_date in enumerate(_business_dates(68, date(2026, 8, 24))):
        close = 10_000 + index * 10
        rows.append(
            DailyPrice(
                code="005930",
                trade_date=trade_date,
                open=close,
                high=close + 100,
                low=close - 100,
                close=close,
                volume=1_000_000,
                trading_value=10_000_000_000,
            )
        )
    bars = quant_signals._normalize_prices(rows)
    indicators = quant_signals._indicator_rows(bars)
    monkeypatch.setattr(
        quant_signals,
        "_entry_signal",
        lambda bar, _indicator: bar.trade_date == SIGNAL_DATE,
    )
    monkeypatch.setattr(
        quant_signals,
        "_entry_setup_kind",
        lambda bar, _indicator: "trend_continuation" if bar.trade_date == SIGNAL_DATE else None,
    )

    blocked = quant_signals._simulate(bars, indicators, {})
    assert blocked["performance"]["rejected_evidence_entries"] == 1
    assert not any(event["side"] == "buy" for event in blocked["events"])

    approved_evidence = {
        "quality": {"state": "ready", "reasons": []},
        "supportive_count": 1,
        "caution_count": 0,
        "vetoes": [],
        "required_supports": {"trend_continuation": 1, "early_turn": 2},
    }
    approved = quant_signals._simulate(
        bars,
        indicators,
        {SIGNAL_DATE: approved_evidence},
    )
    buy_events = [event for event in approved["events"] if event["side"] == "buy"]
    assert len(buy_events) == 1
    assert buy_events[0]["signal_date"] == SIGNAL_DATE
    assert buy_events[0]["entry_confirmation"]["allowed"] is True


def test_signal_data_quality_reports_cross_source_coherence(monkeypatch):
    db = _session()
    stock, _prices = _seed_stock_data(db)
    for series_code in ("^KS11", "^KQ11"):
        db.add(
            MacroObservation(
                source="yahoo",
                series_code=series_code,
                item_code="close",
                period=SIGNAL_DATE.isoformat(),
                value=Decimal("3000"),
            )
        )
    db.add(
        QuantSignalEvidenceSnapshot(
            stock_code=stock.code,
            signal_date=SIGNAL_DATE,
            strategy_version=ENTRY_EVIDENCE_STRATEGY_VERSION,
            policy_version="test",
            quality_state="ready",
            payload="{}",
            generated_at=datetime(2026, 8, 21, 6, 45),
        )
    )
    db.commit()
    monkeypatch.setattr(
        "app.services.signal_data_quality.latest_completed_korea_market_session_date",
        lambda _now: SIGNAL_DATE,
    )

    payload = signal_data_quality_status(
        db,
        Settings(fundamental_snapshot_refresh_days=2),
        now=datetime(2026, 8, 21, 15, 45),
    )
    assert payload["status"] == "ready"
    assert payload["datasets"]["fundamentals"]["api"]["last_success_at"] == datetime(
        2026, 8, 21, 6, 32
    )
    assert payload["datasets"]["entry_evidence_snapshot"]["coverage_rate"] == 1.0
    assert payload["coherence"]["state"] == "ready"

    db.add(
        InvestorFlow(
            code="999999",
            trade_date=SIGNAL_DATE,
            investor_type="외국인",
            net_buy_value=1,
        )
    )
    db.commit()
    degraded = signal_data_quality_status(
        db,
        Settings(fundamental_snapshot_refresh_days=2),
        now=datetime(2026, 8, 21, 15, 45),
    )
    assert degraded["status"] == "degraded"
    assert degraded["coherence"]["orphan_stock_codes"]["flow"] == 1


def test_fundamental_quality_keeps_two_day_sla_while_collector_uses_headroom():
    db = _session()
    stock, _prices = _seed_stock_data(db)
    reference = datetime(2026, 8, 21, 15, 45)
    reference_utc = reference - timedelta(hours=9)

    db.execute(
        update(StockFundamentalSnapshot)
        .where(StockFundamentalSnapshot.stock_code == stock.code)
        .values(fetched_at=reference_utc - timedelta(hours=47))
    )
    db.commit()
    db.expire_all()
    ready = signal_data_quality_status(
        db,
        Settings(fundamental_snapshot_refresh_days=2),
        now=reference,
    )

    db.execute(
        update(StockFundamentalSnapshot)
        .where(StockFundamentalSnapshot.stock_code == stock.code)
        .values(fetched_at=reference_utc - timedelta(hours=49))
    )
    db.commit()
    db.expire_all()
    stale = signal_data_quality_status(
        db,
        Settings(fundamental_snapshot_refresh_days=2),
        now=reference,
    )

    assert ready["datasets"]["fundamentals"]["state"] == "ready"
    assert stale["datasets"]["fundamentals"]["state"] == "stale"


def test_signal_data_quality_does_not_require_evidence_for_a_forming_session(monkeypatch):
    db = _session()
    _seed_stock_data(db)
    db.commit()
    completed_session = SIGNAL_DATE - timedelta(days=1)
    monkeypatch.setattr(
        "app.services.signal_data_quality.latest_completed_korea_market_session_date",
        lambda _now: completed_session,
    )

    payload = signal_data_quality_status(
        db,
        Settings(),
        now=datetime(2026, 8, 21, 9, 24),
    )

    evidence = payload["datasets"]["entry_evidence_snapshot"]
    assert payload["datasets"]["price"]["latest_date"] == SIGNAL_DATE
    assert evidence["signal_date"] == completed_session
    assert evidence["state"] == "not_applicable"
    assert evidence["coverage_rate"] is None


def test_signal_data_quality_excludes_confirmed_non_trading_placeholders(monkeypatch):
    db = _session()
    for code, name in (("005930", "삼성전자"), ("000880", "한화")):
        db.add(
            StockMaster(
                code=code,
                name=name,
                market="KOSPI",
                is_active=True,
            )
        )
    db.add_all(
        [
            DailyPrice(
                code="005930",
                trade_date=SIGNAL_DATE,
                open=80_000,
                high=81_000,
                low=79_000,
                close=80_500,
                volume=1_000_000,
                trading_value=80_500_000_000,
                market_cap=500_000_000_000,
            ),
            DailyPrice(
                code="000880",
                trade_date=SIGNAL_DATE,
                open=0,
                high=0,
                low=0,
                close=83_800,
                volume=0,
                trading_value=0,
                market_cap=100_000_000_000,
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(
        "app.services.signal_data_quality.latest_completed_korea_market_session_date",
        lambda _now: SIGNAL_DATE,
    )

    payload = signal_data_quality_status(
        db,
        Settings(),
        now=datetime(2026, 8, 21, 18, 0),
    )

    price = payload["datasets"]["price"]
    assert price["state"] == "ready"
    assert price["universe_total"] == 2
    assert price["total"] == 1
    assert price["covered"] == 1
    assert price["coverage_rate"] == 1.0
    assert price["non_trading_placeholder_count"] == 1
    assert price["non_trading_placeholder_codes"] == ["000880"]


def test_signal_data_quality_requires_complete_ohlc_for_all_active_stocks(monkeypatch):
    db = _session()
    for code, cap, complete in (
        ("005930", 500_000_000_000, True),
        ("000660", 100_000_000_000, False),
    ):
        db.add(StockMaster(code=code, name=code, market="KOSPI", is_active=True))
        db.add(
            DailyPrice(
                code=code,
                trade_date=SIGNAL_DATE,
                open=80_000 if complete else None,
                high=81_000 if complete else None,
                low=79_000 if complete else None,
                close=80_500,
                volume=1_000_000,
                trading_value=80_500_000_000,
                market_cap=cap,
            )
        )
    db.add(StockMaster(code="247540", name="247540", market="KOSDAQ", is_active=True))
    db.commit()
    monkeypatch.setattr(
        "app.services.signal_data_quality.TOP_UNIVERSE_LIMIT",
        1,
    )
    monkeypatch.setattr(
        "app.services.signal_data_quality.latest_completed_korea_market_session_date",
        lambda _now: SIGNAL_DATE,
    )

    payload = signal_data_quality_status(
        db,
        Settings(),
        now=datetime(2026, 8, 21, 18, 0),
    )

    price = payload["datasets"]["price"]
    assert price["covered"] == 1
    assert price["total"] == 1
    assert price["coverage_rate"] == 1.0
    assert price["all_active_covered"] == 1
    assert price["all_active_total"] == 3
    assert price["all_active_coverage_rate"] == 0.3333
    assert price["all_active_incomplete_count"] == 2
    assert price["state"] == "stale"


def test_macro_collector_treats_stale_korea_index_as_missing_even_within_seven_days(monkeypatch):
    db = _session()
    market_target = SIGNAL_DATE - timedelta(days=1)
    for item in DEFAULT_MACRO_SERIES:
        period = "2026-08-18" if item["symbol"] in {"^KS11", "^KQ11"} else "2026-08-20"
        db.add(
            MacroObservation(
                source="yahoo",
                series_code=item["symbol"],
                item_code="close",
                period=period,
                value=Decimal("100"),
            )
        )
    db.commit()
    monkeypatch.setattr(
        briefing,
        "latest_korea_market_session_date",
        lambda _now=None: market_target,
    )
    runtime = briefing.BriefingRuntime(Settings())

    coverage = runtime._latest_macro_coverage(
        db,
        now=datetime(2026, 8, 21, 1, 0),
    )

    assert coverage["market_target"] == market_target
    assert set(coverage["stale_series"]) == {"^KS11", "^KQ11"}
    assert coverage["fresh"] == len(DEFAULT_MACRO_SERIES) - 2


def test_entry_market_context_prefers_confirmed_naver_index_close():
    db = _session()
    dates = _business_dates(65)
    for index, period in enumerate(dates):
        db.add(
            MacroObservation(
                source="naver_finance",
                series_code="^KS11",
                item_code="close",
                period=period.isoformat(),
                value=Decimal(3000 + index),
            )
        )
        if period < SIGNAL_DATE:
            db.add(
                MacroObservation(
                    source="yahoo",
                    series_code="^KS11",
                    item_code="close",
                    period=period.isoformat(),
                    value=Decimal(2000 + index),
                )
            )
    db.commit()

    context = _macro_index_context(
        db,
        series_code="^KS11",
        signal_date=SIGNAL_DATE,
    )

    assert context["state"] == "ready"
    assert context["source"] == "naver_finance"
    assert context["as_of"] == SIGNAL_DATE.isoformat()
    assert context["current"] == 3064.0


def test_source_probe_never_echoes_a_credential_from_request_error(monkeypatch):
    response = requests.Response()
    response.status_code = 403
    response.url = "https://example.test/api?crtfc_key=SUPER-SECRET"
    error = requests.HTTPError(
        "403 Client Error for url containing crtfc_key=SUPER-SECRET",
        response=response,
    )
    monkeypatch.setattr(
        "app.services.signal_data_quality.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(error),
    )

    result = _http_probe(
        "disclosure",
        "OpenDART API",
        response.url,
    )

    assert result["http_status"] == 403
    assert result["state"] == "unavailable"
    assert "SUPER-SECRET" not in result["message"]
    assert response.url not in result["message"]
