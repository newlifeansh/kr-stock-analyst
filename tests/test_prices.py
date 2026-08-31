from datetime import date, timedelta

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import krx, naver_quotes
from app.db import Base
from app.models import DailyPrice, IngestionRun, StockMaster
from app.repository import upsert_many
from app.services.stock_dashboard import (
    PRICE_HISTORY_BACKFILL_CACHE,
    PRICE_HISTORY_QUALITY_CACHE,
    _momentum,
    _prices,
    ensure_stock_price_history,
)


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
    assert krx.is_supported_price_code("0039P0")
    assert not krx.is_supported_price_code("BADCODE")
    assert not krx.is_supported_price_code("삼성전자")


def test_partial_quote_upsert_preserves_existing_daily_ohlc():
    trade_date = date(2026, 6, 19)
    with _session() as db:
        upsert_many(db, DailyPrice, [{
            "code": "005930",
            "trade_date": trade_date,
            "open": 1000,
            "high": 1100,
            "low": 900,
            "close": 1050,
            "volume": 100,
        }])
        db.commit()
        upsert_many(db, DailyPrice, [{
            "code": "005930",
            "trade_date": trade_date,
            "open": None,
            "high": None,
            "low": None,
            "close": 1070,
            "volume": 200,
        }])
        db.commit()

        row = db.query(DailyPrice).one()
        assert (row.open, row.high, row.low) == (1000, 1100, 900)
        assert (row.close, row.volume) == (1050, 100)


def test_complete_daily_candle_replaces_a_partial_quote_atomically():
    trade_date = date(2026, 6, 19)
    with _session() as db:
        upsert_many(db, DailyPrice, [{
            "code": "005930",
            "trade_date": trade_date,
            "open": None,
            "high": None,
            "low": None,
            "close": 1070,
            "volume": 200,
        }])
        db.commit()
        upsert_many(db, DailyPrice, [{
            "code": "005930",
            "trade_date": trade_date,
            "open": 1000,
            "high": 1100,
            "low": 900,
            "close": 1050,
            "volume": 150,
        }])
        db.commit()

        row = db.query(DailyPrice).one()
        assert (row.open, row.high, row.low, row.close, row.volume) == (
            1000,
            1100,
            900,
            1050,
            150,
        )


def test_signal_history_repairs_recent_close_only_rows_even_when_count_is_sufficient(monkeypatch):
    PRICE_HISTORY_BACKFILL_CACHE.clear()
    PRICE_HISTORY_QUALITY_CACHE.clear()
    trade_date = date(2026, 8, 11)
    calls = []

    def fake_repair(db, code: str, *, pages: int):
        calls.append((code, pages))
        upsert_many(db, DailyPrice, [{
            "code": code,
            "trade_date": trade_date,
            "open": 124_700,
            "high": 129_500,
            "low": 123_000,
            "close": 124_100,
            "volume": 758_130,
        }])
        db.commit()
        return 1

    monkeypatch.setattr(
        naver_quotes,
        "collect_naver_price_history_for_code",
        fake_repair,
    )

    with _session() as db:
        db.add(
            DailyPrice(
                code="096770",
                trade_date=trade_date,
                close=128_700,
                volume=190_638,
            )
        )
        db.commit()

        count = ensure_stock_price_history(
            db,
            "096770",
            min_rows=1,
            require_recent_complete_ohlc=True,
        )

        row = db.query(DailyPrice).one()
        assert count == 1
        assert calls == [("096770", 3)]
        assert (row.open, row.high, row.low, row.close) == (
            124_700,
            129_500,
            123_000,
            124_100,
        )


def test_batch_signal_history_repair_fetches_only_requested_codes(monkeypatch):
    calls = []

    def fake_history_page(code: str, page: int):
        calls.append((code, page))
        return [
            {
                "code": code,
                "trade_date": date(2026, 8, 11),
                "open": 100,
                "high": 110,
                "low": 95,
                "close": 105,
                "volume": 1_000,
                "trading_value": 105_000,
                "market_cap": None,
                "listed_shares": None,
            }
        ]

    monkeypatch.setattr(naver_quotes, "_history_rows_for_page", fake_history_page)

    with _session() as db:
        count = naver_quotes.collect_naver_price_history_for_codes(
            db,
            ["005930", "000660", "005930", "invalid"],
            pages=2,
            max_workers=2,
        )

        assert count == 2
        assert sorted(calls) == [
            ("000660", 1),
            ("000660", 2),
            ("005930", 1),
            ("005930", 2),
        ]
        assert db.query(DailyPrice).count() == 2


def test_naver_krx_chart_parser_keeps_exchange_specific_final_candle():
    target = date(2026, 8, 21)
    payload = {
        "stockExchangeType": "KRX",
        "priceInfos": [
            {
                "localDate": "20260821",
                "openPrice": 280_500.0,
                "highPrice": 283_500.0,
                "lowPrice": 259_500.0,
                "closePrice": 265_000.0,
                "accumulatedTradingVolume": 276_693,
            }
        ],
    }

    row = naver_quotes._krx_chart_price_row_from_payload(
        "010060",
        target,
        payload,
    )

    assert row == {
        "code": "010060",
        "trade_date": target,
        "open": 280_500,
        "high": 283_500,
        "low": 259_500,
        "close": 265_000,
        "volume": 276_693,
        "trading_value": 73_323_645_000,
        "market_cap": None,
        "listed_shares": None,
    }
    assert naver_quotes._krx_chart_price_row_from_payload(
        "010060",
        target,
        {**payload, "stockExchangeType": "NXT"},
    ) is None


def test_ensure_stock_price_history_backfills_missing_momentum(monkeypatch):
    PRICE_HISTORY_BACKFILL_CACHE.clear()
    base_date = date(2026, 7, 21)

    def fake_collect_stock_prices(db, code: str, from_yyyymmdd: str, to_yyyymmdd: str):
        rows = []
        for offset in range(90):
            trade_date = base_date - timedelta(days=offset)
            rows.append(
                DailyPrice(
                    code=code,
                    trade_date=trade_date,
                    close=1000 + offset,
                    volume=100,
                )
            )
        db.add_all(rows)
        db.commit()
        return len(rows)

    monkeypatch.setattr(krx, "collect_stock_prices", fake_collect_stock_prices)

    with _session() as db:
        db.add(StockMaster(code="000660", name="SK하이닉스", market="KOSPI"))
        db.commit()

        count = ensure_stock_price_history(db, "000660")
        momentum = _momentum(_prices(db, "000660"))

        assert count == 90
        assert momentum["one_month_return"] is not None
        assert momentum["three_month_return"] is not None


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
