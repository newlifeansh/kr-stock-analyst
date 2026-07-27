from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import DailyPrice, StockMaster
from app.services import market_rankings


def test_preopen_surge_uses_last_completed_session(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        session.add_all(
            [
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 20).date(), close=100, volume=100),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 21).date(), close=110, volume=120),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 22).date(), close=110, volume=0),
            ]
        )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 7, 22, 8, 30, tzinfo=market_rankings.KST),
        )

        items = market_rankings._latest_session_surge_items(session, "KOSPI")

        assert items[0]["trade_date"] == datetime(2026, 7, 21).date()
        assert items[0]["change_rate"] == 10
    finally:
        session.close()


def test_surge_ranking_scans_full_market_and_keeps_only_risers(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add_all(
            [
                StockMaster(code="000001", name="상승코스피", market="KOSPI"),
                StockMaster(code="000002", name="상승코스닥", market="KOSDAQ"),
                StockMaster(code="000003", name="하락종목", market="KOSPI"),
            ]
        )
        for code, previous, latest in [("000001", 100, 110), ("000002", 100, 120), ("000003", 100, 90)]:
            session.add_all(
                [
                    DailyPrice(code=code, trade_date=datetime(2026, 7, 20).date(), close=previous, volume=100),
                    DailyPrice(code=code, trade_date=datetime(2026, 7, 21).date(), close=latest, volume=100),
                ]
            )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 7, 22, 8, 30, tzinfo=market_rankings.KST),
        )

        payload = market_rankings.build_market_rankings(session, category="surge", market=None, limit=3000)

        assert payload["universe_count"] == 3
        assert payload["matching_count"] == 2
        assert [item["code"] for item in payload["items"]] == ["000002", "000001"]
        assert {item["market"] for item in payload["items"]} == {"KOSPI", "KOSDAQ"}
    finally:
        session.close()


def test_weekend_snapshot_uses_last_completed_weekday(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        session.add_all(
            [
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 23).date(), close=100, volume=100),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 24).date(), close=110, volume=120),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 25).date(), close=110, volume=120),
            ]
        )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 7, 26, 10, 0, tzinfo=market_rankings.KST),
        )

        items = market_rankings._latest_session_surge_items(session, "KOSPI")

        assert items[0]["trade_date"] == datetime(2026, 7, 24).date()
        assert items[0]["change_rate"] == 10
    finally:
        session.close()


def test_database_surge_rankings_include_period_returns(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        for index in range(64):
            session.add(
                DailyPrice(
                    code="005930",
                    trade_date=(datetime(2026, 4, 21) + timedelta(days=index)).date(),
                    close=100 + index,
                    volume=100,
                )
            )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 6, 24, 18, 0, tzinfo=market_rankings.KST),
        )

        payload = market_rankings.build_market_rankings(
            session,
            category="surge",
            market="KOSPI",
            limit=30,
        )

        assert payload["items"][0]["one_month_return"] is not None
        assert payload["items"][0]["three_month_return"] is not None
    finally:
        session.close()


def test_parse_naver_market_rise_uses_quote_cells():
    html = """
    <html><body><table class="type_2"><tr>
      <td class="no">1</td><td><a href="/item/main.naver?code=005930" class="tltle">삼성전자</a></td>
      <td class="number">250,000</td><td class="number">상승 5,000</td>
      <td class="number"><span>+2.04%</span></td><td class="number">1,234,567</td>
    </tr></table></body></html>
    """.encode("euc-kr")

    rows = market_rankings._parse_naver_market_rise(html, "KOSPI")

    assert rows == [
        {
            "code": "005930",
            "name": "삼성전자",
            "market": "KOSPI",
            "price": 250000,
            "change_rate": Decimal("2.04"),
            "volume": 1234567,
            "trading_value": 308641750000,
        }
    ]


def test_parse_naver_chart_baselines_uses_22_and_64_session_closes():
    items = "".join(
        f'<item data="202601{index:02d}|100|110|90|{100 + index}|1000" />'
        for index in range(1, 65)
    )
    payload = (
        '<?xml version="1.0" encoding="EUC-KR" ?>'
        f"<protocol><chartdata>{items}</chartdata></protocol>"
    ).encode("euc-kr")

    baselines = market_rankings._parse_naver_chart_baselines(payload)

    assert baselines == {"latest": 164, "one_month": 143, "three_month": 101}


def test_market_period_returns_calculates_cached_chart_history(monkeypatch):
    monkeypatch.setattr(
        market_rankings,
        "_naver_chart_baselines",
        lambda code: {"latest": 120, "one_month": 100, "three_month": 80},
    )

    items = market_rankings.build_market_period_returns(["005930", "005930", "invalid"])

    assert items == [
        {
            "code": "005930",
            "one_month_return": Decimal("20.00"),
            "three_month_return": Decimal("50.0"),
        }
    ]


def test_live_surge_ranking_does_not_require_database(monkeypatch):
    monkeypatch.setattr(
        market_rankings,
        "_fetch_naver_market_rise",
        lambda market: [
            {
                "code": "000001" if market == "KOSPI" else "000002",
                "name": "코스피상승" if market == "KOSPI" else "코스닥상승",
                "market": market,
                "price": 1200,
                "change_rate": Decimal("12.5") if market == "KOSPI" else Decimal("20.0"),
                "volume": 100,
                "trading_value": 120000,
            }
        ],
    )
    monkeypatch.setattr(market_rankings, "_enrich_market_period_returns", lambda items, max_items: items)

    payload = market_rankings.build_market_rankings(
        None,
        category="surge",
        market=None,
        limit=5,
        refresh_live=True,
    )

    assert payload["source"] == "naver_market_rise"
    assert payload["matching_count"] == 2
    assert [item["code"] for item in payload["items"]] == ["000002", "000001"]
