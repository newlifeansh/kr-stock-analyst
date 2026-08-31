from datetime import date, datetime, timedelta
import json
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.collectors import krx, stock_snapshots
from app.config import Settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    DailyPrice,
    IngestionRun,
    InvestorFlow,
    StockCompanySnapshot,
    StockFundamentalSnapshot,
    StockMaster,
    StockNewsSnapshot,
)
from app.services.briefing import BriefingRuntime
from app.services.stock_data_coverage import stock_data_coverage


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_stock_master_refresh_marks_delisted_rows_inactive(monkeypatch):
    rows = [
        {
            "code": "215600",
            "name": "신라젠",
            "market": "KOSDAQ",
            "is_active": True,
            "last_seen_date": date(2026, 7, 24),
        }
    ]
    monkeypatch.setattr(krx, "_stock_rows_from_pykrx", lambda *_args, **_kwargs: rows)

    with _session() as db:
        db.add(StockMaster(code="999999", name="상장종료", market="KOSDAQ", is_active=True))
        db.commit()

        assert krx.collect_stocks(db, "20260724", "KOSDAQ") == 1
        assert db.get(StockMaster, "215600").is_active is True
        assert db.get(StockMaster, "999999").is_active is False


def test_stock_master_refresh_preserves_active_latest_session_price_universe(monkeypatch):
    rows = [
        {
            "code": "215600",
            "name": "신라젠",
            "market": "KOSDAQ",
            "is_active": True,
            "last_seen_date": date(2026, 8, 24),
        }
    ]
    monkeypatch.setattr(krx, "_stock_rows_from_pykrx", lambda *_args, **_kwargs: rows)

    with _session() as db:
        db.add_all(
            [
                StockMaster(
                    code="0005D0",
                    name="SOL 전고체배터리",
                    market="KOSPI",
                    is_active=True,
                    last_seen_date=date(2026, 8, 1),
                ),
                StockMaster(
                    code="023160",
                    name="태광",
                    market="KOSDAQ",
                    is_active=True,
                    last_seen_date=date(2026, 8, 24),
                ),
                StockMaster(
                    code="099999",
                    name="과거 비활성 종목",
                    market="KOSDAQ",
                    is_active=False,
                    last_seen_date=date(2026, 8, 16),
                ),
                StockMaster(
                    code="088888",
                    name="상장종료 후보",
                    market="KOSDAQ",
                    is_active=True,
                    last_seen_date=date(2026, 8, 16),
                ),
                DailyPrice(
                    code="0005D0",
                    trade_date=date(2026, 8, 24),
                    open=10000,
                    high=10500,
                    low=9900,
                    close=10400,
                    volume=100,
                ),
                DailyPrice(
                    code="023160",
                    trade_date=date(2026, 8, 24),
                    open=20000,
                    high=21000,
                    low=19800,
                    close=20800,
                    volume=200,
                ),
                DailyPrice(
                    code="099999",
                    trade_date=date(2026, 8, 24),
                    open=5000,
                    high=5100,
                    low=4900,
                    close=5050,
                    volume=50,
                ),
                DailyPrice(
                    code="088888",
                    trade_date=date(2026, 8, 16),
                    open=5000,
                    high=5100,
                    low=4900,
                    close=5050,
                    volume=50,
                ),
            ]
        )
        db.commit()

        assert krx.collect_stocks(db, "20260824", "KOSPI,KOSDAQ") == 1
        assert db.get(StockMaster, "0005D0").is_active is True
        assert db.get(StockMaster, "023160").is_active is True
        assert db.get(StockMaster, "099999").is_active is False
        assert db.get(StockMaster, "088888").is_active is False


def test_stock_master_refresh_preserves_existing_sector_classification(monkeypatch):
    rows = [
        {
            "code": "215600",
            "name": "신라젠",
            "market": "KOSDAQ",
            "sector": None,
            "industry": None,
            "is_active": True,
            "last_seen_date": date(2026, 8, 13),
        }
    ]
    monkeypatch.setattr(krx, "_stock_rows_from_pykrx", lambda *_args, **_kwargs: rows)

    with _session() as db:
        db.add(
            StockMaster(
                code="215600",
                name="신라젠",
                market="KOSDAQ",
                sector="일반서비스",
                industry="제약",
                is_active=True,
            )
        )
        db.commit()

        krx.collect_stocks(db, "20260813", "KOSDAQ")

        stock = db.get(StockMaster, "215600")
        assert stock.sector == "일반서비스"
        assert stock.industry == "제약"


def test_full_universe_fundamental_snapshot_skips_inactive_stocks(monkeypatch):
    monkeypatch.setattr(
        stock_snapshots,
        "_fetch_naver_snapshot",
        lambda code: {
            "per": "12.3",
            "financial_series": {
                "annual": [{"period": "2025.12", "revenue": "100"}],
                "quarterly": [],
                "unit": "억원",
                "source": "네이버 금융",
            },
        },
    )
    with _session() as db:
        db.add_all(
            [
                StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True),
                StockMaster(code="999999", name="상장종료", market="KOSDAQ", is_active=False),
            ]
        )
        db.commit()

        result = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            refresh_days=0,
            max_workers=1,
        )
        assert result["target"] == 1
        assert result["rows_loaded"] == 1
        assert db.get(StockFundamentalSnapshot, "215600") is not None
        assert db.get(StockFundamentalSnapshot, "999999") is None
        assert stock_data_coverage(db)["active_stocks"] == 1


def test_etf_fundamental_snapshot_is_recorded_as_not_applicable(monkeypatch):
    monkeypatch.setattr(stock_snapshots, "_fetch_naver_snapshot", lambda _code: {})
    with _session() as db:
        db.add(
            StockMaster(
                code="069500",
                name="KODEX 200",
                market="KOSPI",
                is_active=True,
            )
        )
        db.commit()

        result = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            refresh_days=0,
            max_workers=1,
        )
        snapshot = db.get(StockFundamentalSnapshot, "069500")

    assert result["rows_loaded"] == 1
    assert result["failed"] == 0
    assert json.loads(snapshot.payload) == {
        "data_status": "not_applicable",
        "instrument_type": "exchange_traded_fund",
        "unavailable_reason": "ETF는 일반 상장기업용 재무·밸류에이션 표 적용 대상이 아닙니다.",
    }


def test_signal_inputs_refresh_largest_market_caps_first(monkeypatch):
    fetched_codes = []

    def fake_snapshot(code):
        fetched_codes.append(code)
        return {
            "per": "12.3",
            "financial_series": {
                "annual": [{"period": "2025.12", "revenue": "100"}],
                "quarterly": [],
                "unit": "억원",
                "source": "네이버 금융",
            },
        }

    monkeypatch.setattr(stock_snapshots, "_fetch_naver_snapshot", fake_snapshot)
    with _session() as db:
        db.add_all(
            [
                StockMaster(code="000001", name="소형주", market="KOSPI", is_active=True),
                StockMaster(code="000002", name="대형주", market="KOSPI", is_active=True),
                DailyPrice(
                    code="000001",
                    trade_date=date(2026, 8, 20),
                    close=10_000,
                    market_cap=100,
                ),
                DailyPrice(
                    code="000002",
                    trade_date=date(2026, 8, 20),
                    close=20_000,
                    market_cap=1_000,
                ),
                InvestorFlow(
                    code="000001",
                    trade_date=date(2026, 8, 19),
                    investor_type="외국인",
                    net_buy_volume=1,
                ),
                InvestorFlow(
                    code="000002",
                    trade_date=date(2026, 8, 19),
                    investor_type="외국인",
                    net_buy_volume=1,
                ),
            ]
        )
        db.commit()

        result = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            refresh_days=0,
            max_workers=1,
        )
        flow_coverage = BriefingRuntime(Settings())._latest_investor_flow_coverage(
            db,
            now=datetime(2026, 8, 21, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        )

    assert result["rows_loaded"] == 2
    assert fetched_codes == ["000002", "000001"]
    assert flow_coverage["stale_codes"] == ["000002", "000001"]


def test_fundamental_priority_and_full_pass_use_distinct_freshness_cutoffs(monkeypatch):
    fetched_codes = []

    def fake_snapshot(code):
        fetched_codes.append(code)
        return {
            "per": "12.3",
            "financial_series": {
                "annual": [{"period": "2025.12", "revenue": "100"}],
                "quarterly": [],
                "unit": "억원",
                "source": "네이버 금융",
            },
        }

    monkeypatch.setattr(stock_snapshots, "_fetch_naver_snapshot", fake_snapshot)
    now = datetime.utcnow()
    with _session() as db:
        stocks = []
        prices = []
        snapshots = []
        for rank in range(1, 102):
            code = f"{rank:06d}"
            stocks.append(
                StockMaster(code=code, name=f"종목{rank}", market="KOSPI", is_active=True)
            )
            prices.append(
                DailyPrice(
                    code=code,
                    trade_date=date(2026, 8, 28),
                    close=10_000,
                    market_cap=10_000 - rank,
                )
            )
            snapshots.append(
                StockFundamentalSnapshot(
                    stock_code=code,
                    source="naver_finance",
                    payload="{}",
                    fetched_at=(
                        now - timedelta(hours=25)
                        if rank in {1, 101}
                        else now
                    ),
                    updated_at=now,
                )
            )
        db.add_all(stocks + prices + snapshots)
        db.commit()

        priority = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            limit=100,
            refresh_days=1,
            max_workers=1,
        )
        full_before_sla = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            refresh_days=2,
            max_workers=1,
        )

        assert priority["rows_loaded"] == 1
        assert full_before_sla["rows_loaded"] == 0
        assert fetched_codes == ["000001"]

        rank_101 = db.get(StockFundamentalSnapshot, "000101")
        rank_101.fetched_at = now - timedelta(hours=49)
        db.commit()

        full_after_sla = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            refresh_days=2,
            max_workers=1,
        )

        assert full_after_sla["rows_loaded"] == 1
        assert fetched_codes == ["000001", "000101"]


def test_fundamental_priority_ignores_inactive_future_price_and_marks_partial(monkeypatch):
    monkeypatch.setattr(stock_snapshots, "_fetch_naver_snapshot", lambda _code: {})
    with _session() as db:
        db.add_all(
            [
                StockMaster(code="000001", name="정상종목", market="KOSPI", is_active=True),
                StockMaster(code="999999", name="상장종료", market="KOSPI", is_active=False),
                DailyPrice(
                    code="000001",
                    trade_date=date(2026, 8, 28),
                    close=10_000,
                    market_cap=1_000,
                ),
                DailyPrice(
                    code="999999",
                    trade_date=date(2099, 1, 1),
                    close=10_000,
                    market_cap=999_999,
                ),
            ]
        )
        db.commit()

        result = stock_snapshots.collect_stock_fundamental_snapshots(
            db,
            limit=100,
            refresh_days=0,
            max_workers=1,
        )
        latest_run = db.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()))

    assert result["target"] == 1
    assert result["failed"] == 1
    assert latest_run.status == "partial"
    assert "unavailable=1" in latest_run.message


def test_sillajen_search_is_uncached_and_excludes_inactive_stocks():
    db = _session()
    db.add_all(
        [
            StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True),
            StockMaster(code="999999", name="신라젠구주", market="KOSDAQ", is_active=False),
        ]
    )
    db.commit()

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/stocks/search", params={"query": "신라젠", "limit": 30})
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        assert [(item["code"], item["name"]) for item in response.json()] == [("215600", "신라젠")]
        assert db.scalar(select(StockMaster).where(StockMaster.code == "215600")) is not None
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_resolve_reactivates_current_naver_etn_by_exact_name(monkeypatch):
    db = _session()
    db.add(
        StockMaster(
            code="580043",
            name="KB 레버리지 KOSDAQ 150 선물 ETN",
            market="KOSPI",
            is_active=False,
        )
    )
    db.commit()
    monkeypatch.setattr(
        main_module,
        "_fetch_naver_stock_identity",
        lambda code: (
            {
                "code": "580043",
                "name": "KB 레버리지 KOSDAQ 150 선물 ETN",
                "market": "KOSPI",
            }
            if code == "580043"
            else None
        ),
    )

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(
            "/stocks/resolve",
            params={"query": "KB 레버리지 KOSDAQ 150 선물 ETN"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == "580043"
        assert response.json()["is_active"] is True
        assert db.get(StockMaster, "580043").is_active is True
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_full_universe_news_snapshot_persists_empty_result_and_skips_inactive(monkeypatch):
    monkeypatch.setattr(
        stock_snapshots,
        "_fetch_naver_item_news",
        lambda code, strict=False: [] if code == "215600" else [{"title": "should not load"}],
    )
    with _session() as db:
        db.add_all(
            [
                StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True),
                StockMaster(code="999999", name="상장종료", market="KOSDAQ", is_active=False),
            ]
        )
        db.commit()

        result = stock_snapshots.collect_stock_news_snapshots(
            db,
            refresh_hours=0,
            max_workers=1,
        )

        assert result["target"] == 1
        assert result["rows_loaded"] == 1
        assert result["empty"] == 1
        assert db.get(StockNewsSnapshot, "215600").payload == "[]"
        assert db.get(StockNewsSnapshot, "999999") is None


def test_full_universe_company_snapshot_updates_company_description_and_industry(monkeypatch):
    monkeypatch.setattr(
        stock_snapshots,
        "_fetch_naver_company_snapshot",
        lambda code, strict=False: {
            "summary": "항암 신약을 연구개발하는 바이오 기업입니다.",
            "sector": "일반서비스",
            "industry": "제약",
            "source_url": f"https://example.test/{code}",
        },
    )
    with _session() as db:
        db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
        db.commit()

        result = stock_snapshots.collect_stock_company_snapshots(
            db,
            refresh_days=0,
            max_workers=1,
        )

        snapshot = db.get(StockCompanySnapshot, "215600")
        stock = db.get(StockMaster, "215600")
        assert result["rows_loaded"] == 1
        assert snapshot.summary.startswith("항암 신약")
        assert stock.sector == "일반서비스"
        assert stock.industry == "제약"


def test_fresh_company_snapshot_backfills_missing_stock_classification(monkeypatch):
    monkeypatch.setattr(
        stock_snapshots,
        "_fetch_naver_company_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("fresh row must not refetch")),
    )
    with _session() as db:
        db.add(StockMaster(code="215600", name="신라젠", market="KOSDAQ", is_active=True))
        db.add(
            StockCompanySnapshot(
                stock_code="215600",
                source="naver_wisereport",
                summary="항암 신약 연구개발 기업",
                sector="일반서비스",
                industry="제약",
                source_url="https://example.test/215600",
                fetched_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )
        db.commit()

        result = stock_snapshots.collect_stock_company_snapshots(
            db,
            refresh_days=30,
            max_workers=1,
        )

        stock = db.get(StockMaster, "215600")
        assert result["skipped"] == 1
        assert result["rows_loaded"] == 0
        assert stock.sector == "일반서비스"
        assert stock.industry == "제약"
