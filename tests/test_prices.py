from datetime import date

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import krx, naver_quotes
from app.db import Base
from app.models import DailyPrice, IngestionRun, StockMaster


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_collect_prices_for_codes_filters_invalid_codes_and_upserts(monkeypatch):
    def fake_price_rows(code: str, from_yyyymmdd: str, to_yyyymmdd: str):
        return [
            {
                "code": code,
                "trade_date": date(2026, 6, 19),
                "open": 1000,
                "high": 1100,
                "low": 900,
                "close": 1050 if code == "005930" else 2050,
                "volume": 12345,
                "trading_value": 45678,
                "market_cap": None,
                "listed_shares": None,
            }
        ]

    monkeypatch.setattr(krx, "_price_rows_for_code", fake_price_rows)

    with _session() as db:
        count = krx.collect_prices_for_codes(
            db,
            ["005930", "BADCODE", "005930", "000660"],
            from_yyyymmdd="20260616",
            to_yyyymmdd="20260619",
            max_workers=2,
        )

        assert count == 2
        assert db.query(func.count(DailyPrice.id)).scalar() == 2
        assert db.query(func.count(IngestionRun.id)).scalar() == 1
        rows = db.query(DailyPrice).order_by(DailyPrice.code.asc()).all()
        assert [row.code for row in rows] == ["000660", "005930"]
        assert [row.close for row in rows] == [2050, 1050]


def test_is_supported_price_code():
    assert krx.is_supported_price_code("005930")
    assert not krx.is_supported_price_code("0001A0")
    assert not krx.is_supported_price_code("삼성전자")


def test_collect_naver_quotes_commits_batches_and_skips_failed_codes(monkeypatch):
    def fake_quote_row(code: str, trade_date):
        if code == "000660":
            raise RuntimeError("temporary failure")
        return {
            "code": code,
            "trade_date": trade_date,
            "open": None,
            "high": None,
            "low": None,
            "close": 1000 if code == "005930" else 2000,
            "volume": 100,
            "trading_value": 100000,
            "market_cap": None,
            "listed_shares": None,
        }

    monkeypatch.setattr(naver_quotes, "_quote_row", fake_quote_row)

    with _session() as db:
        db.add_all(
            [
                StockMaster(code="005930", name="삼성전자", market="KOSPI"),
                StockMaster(code="000660", name="SK하이닉스", market="KOSPI"),
                StockMaster(code="035420", name="NAVER", market="KOSPI"),
            ]
        )
        db.commit()

        count = naver_quotes.collect_naver_quotes(
            db,
            "20260624",
            markets="KOSPI",
            limit=None,
            max_workers=2,
            batch_size=1,
        )

        assert count == 2
        rows = db.query(DailyPrice).order_by(DailyPrice.code.asc()).all()
        assert [row.code for row in rows] == ["005930", "035420"]
        run = db.query(IngestionRun).one()
        assert run.status == "success"
        assert run.message == "failed_codes=1"
