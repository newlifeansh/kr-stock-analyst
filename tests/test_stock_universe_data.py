from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.collectors import krx, stock_snapshots
from app.db import Base, get_db
from app.main import app
from app.models import StockCompanySnapshot, StockFundamentalSnapshot, StockMaster, StockNewsSnapshot
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
