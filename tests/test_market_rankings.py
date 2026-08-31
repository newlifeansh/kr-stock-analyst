import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import _ensure_market_ranking_stock_masters, _surge_ranking_snapshot_response
from app.models import DailyPrice, MarketRankingSnapshot, StockMaster
from app.services import market_rankings


def test_surge_ranking_snapshot_keeps_home_and_more_order_identical():
    snapshot = MarketRankingSnapshot(
        snapshot_id="stable-surge-ranking",
        captured_at=datetime(2026, 7, 29, 9, 0),
        expires_at=datetime(2026, 7, 30, 9, 0),
        payload=json.dumps(
            {
                "as_of": "2026-07-29T18:00:00+09:00",
                "markets": {
                    "ALL": {
                        "source": "database",
                        "universe_count": 4,
                        "matching_count": 4,
                        "items": [
                            {"code": "000004", "name": "넷", "change_rate": 30},
                            {"code": "000003", "name": "셋", "change_rate": 20},
                            {"code": "000002", "name": "둘", "change_rate": 10},
                            {"code": "000001", "name": "하나", "change_rate": 5},
                        ],
                    }
                },
            },
            ensure_ascii=False,
        ),
    )

    home = _surge_ranking_snapshot_response(snapshot, market=None, limit=3)
    more = _surge_ranking_snapshot_response(snapshot, market=None, limit=30)

    assert home["snapshot_id"] == more["snapshot_id"] == "stable-surge-ranking"
    assert [item["code"] for item in home["items"]] == [
        item["code"] for item in more["items"][:3]
    ]


def test_market_ranking_items_activate_etf_and_etn_stock_masters():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(
            StockMaster(
                code="580043",
                name="KB 레버리지 KOSDAQ 150 선물 ETN",
                market="KOSPI",
                is_active=False,
            )
        )
        session.commit()

        _ensure_market_ranking_stock_masters(
            session,
            [
                {
                    "code": "580043",
                    "name": "KB 레버리지 KOSDAQ 150 선물 ETN",
                    "market": "KOSPI",
                },
                {
                    "code": "0167A0",
                    "name": "SOL AI반도체TOP2플러스",
                    "market": "KOSPI",
                },
            ],
        )

        assert session.get(StockMaster, "580043").is_active is True
        assert session.get(StockMaster, "0167A0").is_active is True
        assert session.get(StockMaster, "0167A0").name == "SOL AI반도체TOP2플러스"
    finally:
        session.close()


def test_market_ranking_items_include_the_shared_investment_sector():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add_all(
            [
                StockMaster(
                    code="005930",
                    name="삼성전자",
                    market="KOSPI",
                    sector="전기·전자",
                    industry="반도체와반도체장비",
                ),
                StockMaster(
                    code="090430",
                    name="아모레퍼시픽",
                    market="KOSPI",
                    sector="화학",
                    industry="화장품",
                ),
            ]
        )
        session.commit()

        items = market_rankings.enrich_market_ranking_sector_fields(
            session,
            [
                {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
                {"code": "090430", "name": "아모레퍼시픽", "market": "KOSPI"},
            ],
        )

        assert [item["investment_sector"] for item in items] == ["semiconductor", "consumer"]
        assert [item["investment_sector_label"] for item in items] == ["반도체", "소비재"]
        assert items[0]["sector"] == "전기·전자"
        assert items[0]["industry"] == "반도체와반도체장비"
    finally:
        session.close()


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
        monkeypatch.setattr(market_rankings, "_naver_market_rise_items", lambda *_args, **_kwargs: [])

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


def test_after_close_surge_uses_current_market_feed(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        session.add_all(
            [
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 24).date(), close=100, volume=100),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 27).date(), close=110, volume=120),
            ]
        )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 7, 27, 22, 4, tzinfo=market_rankings.KST),
        )
        monkeypatch.setattr(
            market_rankings,
            "_naver_market_rise_items",
            lambda *_args, **_kwargs: [
                {
                    "code": "005930",
                    "name": "삼성전자",
                    "market": "KOSPI",
                    "trade_date": datetime(2026, 7, 27).date(),
                    "price": 101,
                    "change_rate": Decimal("1.00"),
                    "volume": 500,
                    "trading_value": 50_500,
                    "metric_value": Decimal("1.00"),
                    "one_month_return": None,
                    "three_month_return": None,
                }
            ],
        )
        monkeypatch.setattr(market_rankings, "_enrich_market_period_returns", lambda items, max_items: items)

        payload = market_rankings.build_market_rankings(
            session,
            category="surge",
            market=None,
            limit=5,
            refresh_live=True,
        )

        assert payload["source"] == "naver_market_rise"
        assert payload["matching_count"] == 1
        assert payload["items"][0]["trade_date"] == datetime(2026, 7, 27).date()
        assert payload["items"][0]["change_rate"] == Decimal("1.00")
    finally:
        session.close()


def test_preopen_surge_falls_back_to_partial_session_history(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add(StockMaster(code="005930", name="삼성전자", market="KOSPI"))
        session.add_all(
            [
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 24).date(), close=100, volume=100),
                DailyPrice(code="005930", trade_date=datetime(2026, 7, 27).date(), close=110, volume=120),
            ]
        )
        session.commit()
        monkeypatch.setattr(
            market_rankings,
            "_now_kst",
            lambda: datetime(2026, 7, 27, 8, 30, tzinfo=market_rankings.KST),
        )
        monkeypatch.setattr(market_rankings, "_naver_market_rise_items", lambda *_args, **_kwargs: [])

        payload = market_rankings.build_market_rankings(
            session,
            category="surge",
            market="KOSPI",
            limit=5,
        )

        assert payload["source"] == "database"
        assert payload["matching_count"] == 1
        assert [item["code"] for item in payload["items"]] == ["005930"]
        assert payload["items"][0]["change_rate"] == 10
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
        monkeypatch.setattr(market_rankings, "_naver_market_rise_items", lambda *_args, **_kwargs: [])

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


def test_live_market_rise_uses_latest_session_date_on_weekend(monkeypatch):
    sunday = datetime(2026, 8, 9, 12, 0, tzinfo=market_rankings.KST)
    friday = datetime(2026, 8, 7).date()
    monkeypatch.setattr(market_rankings, "_now_kst", lambda: sunday)
    monkeypatch.setattr(market_rankings, "latest_korea_market_session_date", lambda _now=None: friday)
    monkeypatch.setattr(
        market_rankings,
        "_fetch_naver_market_rise",
        lambda market: [
            {
                "code": "000001" if market == "KOSPI" else "000002",
                "name": "코스피상승" if market == "KOSPI" else "코스닥상승",
                "market": market,
                "price": 1200,
                "change_rate": Decimal("12.5"),
                "volume": 100,
                "trading_value": 120000,
            }
        ],
    )
    market_rankings.MARKET_RISE_CACHE.clear()

    items = market_rankings._naver_market_rise_items(None, None)

    assert {item["trade_date"] for item in items} == {friday}


def test_latest_ranking_trade_date_falls_back_to_previous_weekday(monkeypatch):
    sunday = datetime(2026, 8, 9, 12, 0, tzinfo=market_rankings.KST)
    monkeypatch.setattr(market_rankings, "latest_korea_market_session_date", lambda _now=None: None)

    assert market_rankings._latest_ranking_trade_date(None, sunday) == datetime(2026, 8, 7).date()


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

    assert baselines == {
        "latest": 164,
        "one_week": 159,
        "one_month": 143,
        "three_month": 101,
    }


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
            "one_week_return": None,
            "one_month_return": Decimal("20.00"),
            "three_month_return": Decimal("50.0"),
        }
    ]


def test_live_surge_ranking_does_not_require_database(monkeypatch):
    monkeypatch.setattr(
        market_rankings,
        "_now_kst",
        lambda: datetime(2026, 7, 27, 10, 0, tzinfo=market_rankings.KST),
    )
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
    monkeypatch.setattr(
        market_rankings,
        "latest_korea_market_session_date",
        lambda _now=None: datetime(2026, 7, 27).date(),
    )
    market_rankings.MARKET_RISE_CACHE.clear()
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


def test_parse_domestic_top_list_maps_category_specific_live_metrics():
    payload = {
        "isSuccess": True,
        "result": {
            "stocks": [
                {
                    "id": "005930",
                    "name": "삼성전자",
                    "stockExchangeType": "KOSPI",
                    "stockEndType": "stock",
                    "currentPrice": 257_000,
                    "fluctuationsRatio": "-8.70",
                    "accumulatedTradingVolume": 32_451_480,
                    "accumulatedTradingValue": 8_455_947_000_000,
                    "marketValue": 1_502_493_602_256_000,
                }
            ]
        },
    }
    trade_date = datetime(2026, 8, 24).date()

    volume = market_rankings._parse_naver_domestic_list_payload(payload, "volume", trade_date)[0]
    market_cap = market_rankings._parse_naver_domestic_list_payload(payload, "market_cap", trade_date)[0]

    assert volume["metric_value"] == 32_451_480
    assert market_cap["market_cap"] == 1_502_493_602_256_000
    assert market_cap["metric_value"] == 1_502_493_602_256_000
    assert market_cap["change_rate"] == Decimal("-8.70")


def test_parse_low_52_week_list_keeps_only_quoting_kospi_and_kosdaq_items():
    payload = {
        "isSuccess": True,
        "result": {
            "stocks": [
                {
                    "id": "000001",
                    "name": "거래정지종목",
                    "stockExchangeType": "KOSPI",
                    "currentPrice": 0,
                    "fluctuationsRatio": "-100.00",
                },
                {
                    "id": "000002",
                    "name": "52주최저종목",
                    "stockExchangeType": "KOSDAQ",
                    "currentPrice": 8_500,
                    "fluctuationsRatio": "-12.50",
                },
                {
                    "id": "000003",
                    "name": "코넥스종목",
                    "stockExchangeType": "KONEX",
                    "currentPrice": 2_000,
                    "fluctuationsRatio": "-8.00",
                },
            ]
        },
    }

    items = market_rankings._parse_naver_domestic_list_payload(
        payload,
        "low52",
        datetime(2026, 8, 24).date(),
    )

    assert [item["code"] for item in items] == ["000002"]
    assert items[0]["market"] == "KOSDAQ"
    assert items[0]["price"] == 8_500


def test_52_week_rankings_use_separate_low_and_high_source_sorts(monkeypatch):
    calls = []

    def fake_fetch(
        sort_type,
        market_category,
        page_size,
        ranking_category,
        trade_date,
        *,
        fetch_all_pages=False,
    ):
        calls.append((sort_type, ranking_category, fetch_all_pages))
        return [
            {
                "code": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "trade_date": trade_date,
                "price": 100,
                "change_rate": Decimal("-1.0") if ranking_category == "low52" else Decimal("1.0"),
                "metric_value": Decimal("-1.0") if ranking_category == "low52" else Decimal("1.0"),
                "_source_rank": 1,
            }
        ]

    monkeypatch.setattr(market_rankings, "_fetch_naver_domestic_list", fake_fetch)
    monkeypatch.setattr(
        market_rankings,
        "_latest_ranking_trade_date",
        lambda _db: datetime(2026, 8, 24).date(),
    )
    market_rankings.MARKET_TOP_CACHE.clear()

    low = market_rankings._naver_domestic_top_items(None, "low52", None, 5, refresh=True)
    high = market_rankings._naver_domestic_top_items(None, "high52", None, 5, refresh=True)

    assert calls == [
        ("low52week", "low52", True),
        ("high52week", "high52", False),
    ]
    assert low[0]["category"] == "low52"
    assert high[0]["category"] == "high52"


def test_parse_etf_list_uses_won_units_and_selected_metric():
    payload = {
        "result": {
            "etfItemList": [
                {
                    "itemcode": "069500",
                    "itemname": "KODEX 200",
                    "nowVal": 105_995,
                    "changeRate": -3.62,
                    "threeMonthEarnRate": -10.4491,
                    "quant": 14_650_739,
                    "amonut": 1_567_831,
                    "marketSum": 249_459,
                }
            ]
        }
    }

    by_cap = market_rankings._parse_naver_etf_payload(payload, "market_cap", datetime(2026, 8, 24).date())[0]
    by_volume = market_rankings._parse_naver_etf_payload(payload, "volume", datetime(2026, 8, 24).date())[0]

    assert by_cap["market_cap"] == 24_945_900_000_000
    assert by_cap["trading_value"] == 1_567_831_000_000
    assert by_cap["metric_value"] == 24_945_900_000_000
    assert by_volume["metric_value"] == 14_650_739


def test_parse_dividend_list_exposes_yield_and_per_share_amount():
    payload = {
        "result": {
            "dividends": [
                {
                    "id": "338100",
                    "name": "NH프라임리츠",
                    "stockExchangeType": "KOSPI",
                    "dividend": 1462,
                    "dividendRate": "39.57",
                    "dividendDate": "26.05.",
                }
            ]
        }
    }

    item = market_rankings._parse_naver_dividend_payload(
        payload,
        "yield",
        datetime(2026, 8, 24).date(),
    )[0]

    assert item["dividend_yield"] == Decimal("39.57")
    assert item["dividend_per_share"] == 1462
    assert item["metric_value"] == Decimal("39.57")


def test_parse_market_sum_keeps_only_positive_per_candidates():
    html = """
    <html><body><table class="type_2">
      <tr>
        <td class="no">1</td><td><a class="tltle" href="/item/main.naver?code=005930">삼성전자</a></td>
        <td class="number">257,000</td><td class="number">하락 24,500</td><td class="number">-8.70%</td>
        <td class="number">100</td><td class="number">15,024,936</td><td class="number">1</td>
        <td class="number">50.00</td><td class="number">32,451,480</td><td class="number">11.53</td>
      </tr>
      <tr>
        <td class="no">2</td><td><a class="tltle" href="/item/main.naver?code=000001">적자기업</a></td>
        <td class="number">1,000</td><td class="number">0</td><td class="number">0.00%</td>
        <td class="number">100</td><td class="number">100</td><td class="number">1</td>
        <td class="number">0</td><td class="number">10</td><td class="number">N/A</td>
      </tr>
    </table></body></html>
    """.encode("euc-kr")

    items = market_rankings._parse_naver_market_sum(html, "KOSPI", datetime(2026, 8, 24).date())

    assert [item["code"] for item in items] == ["005930"]
    assert items[0]["per"] == Decimal("11.53")
    assert items[0]["market_cap"] == 1_502_493_600_000_000
