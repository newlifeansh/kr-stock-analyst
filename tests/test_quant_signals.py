from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.db import Base, get_db
from app.main import app
from app.models import DailyPrice, DisclosureItem, InvestorFlow, NewsItem, ResearchReport, StockMaster, WatchlistItem
from app.services.quant_signals import (
    MARKET_SIGNAL_RECENT_DAYS,
    MIN_HISTORY_ROWS,
    STRATEGY_VERSION,
    build_quant_signal_payload,
    load_market_quant_signal_feed,
    load_quant_signal_payload,
)
from app.services import quant_signals


def _price_rows(code: str, count: int = 340) -> list[DailyPrice]:
    rows: list[DailyPrice] = []
    value = 10_000.0
    start = date(2025, 1, 2)
    for index in range(count):
        if index < 80:
            daily_return = 0.0004
        elif index < 155:
            daily_return = 0.009
        elif index < 190:
            daily_return = -0.014
        elif index < 275:
            daily_return = 0.008
        else:
            daily_return = -0.009
        previous = value
        value *= 1.0 + daily_return
        open_price = previous * (1.0 + (daily_return * 0.25))
        rows.append(
            DailyPrice(
                code=code,
                trade_date=start + timedelta(days=index),
                open=round(open_price),
                high=round(max(open_price, value) * 1.012),
                low=round(min(open_price, value) * 0.988),
                close=round(value),
                volume=1_000_000 + (index % 23) * 50_000,
                trading_value=50_000_000_000 + (index % 7) * 1_000_000_000,
            )
        )
    return rows


def _stock(code: str = "005930", name: str = "삼성전자") -> StockMaster:
    return StockMaster(code=code, name=name, market="KOSPI", is_active=True)


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_quant_signals_execute_on_the_next_bar_and_include_costs():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930"),
        now=datetime(2026, 7, 25, 12, 0),
    )

    assert payload["data_state"] == "ready"
    assert payload["strategy_version"] == STRATEGY_VERSION
    assert payload["events"]
    assert {event["side"] for event in payload["events"]} == {"buy", "partial_sell", "sell"}
    assert all(event["execution_date"] > event["signal_date"] for event in payload["events"])
    partial_events = [event for event in payload["events"] if event["side"] == "partial_sell"]
    assert partial_events
    assert all(event["position_percent"] == Decimal("50.00") for event in partial_events)
    for trade in (item for item in payload["trades"] if item["status"] == "closed"):
        assert trade["net_return"] <= trade["gross_return"]
        assert trade["holding_days"] >= 1
        assert trade["partial_exit_date"] is not None
    assert Decimal("0.12") <= payload["performance"]["transaction_cost_per_side"] <= Decimal("0.50")
    assert payload["performance"]["max_drawdown"] <= 0
    assert "hypothetical_start" not in payload["performance"]
    assert any("최대 낙폭" in item for item in payload["applied_principles"])
    assert any("생존편향" in item for item in payload["excluded_principles"])


def test_quant_lifecycle_keeps_half_exposure_after_partial_exit():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930", 150),
        now=datetime(2026, 7, 25, 12, 0),
    )

    current = payload["current"]
    assert current["lifecycle"]["state"] == "partially_exited"
    assert current["model_exposure_percent"] == Decimal("50.00")
    assert current["partial_exit_date"] is not None
    assert current["partial_exit_price"] is not None
    assert [level["key"] for level in current["levels"]] == ["full_exit"]
    assert payload["events"][-1]["label"] == "1차 분할매도"


def test_future_price_changes_do_not_rewrite_past_signals():
    rows = _price_rows("005930")
    changed_rows = _price_rows("005930")
    cutoff_index = 285
    for index in range(cutoff_index + 1, len(changed_rows)):
        changed_rows[index].open = max(1, changed_rows[index].open // 4)
        changed_rows[index].high = max(1, changed_rows[index].high // 4)
        changed_rows[index].low = max(1, changed_rows[index].low // 4)
        changed_rows[index].close = max(1, changed_rows[index].close // 4)

    original = build_quant_signal_payload(_stock(), rows, now=datetime(2026, 7, 25, 12, 0))
    changed = build_quant_signal_payload(_stock(), changed_rows, now=datetime(2026, 7, 25, 12, 0))
    cutoff = rows[cutoff_index].trade_date

    def past_events(payload):
        return [
            (event["signal_date"], event["execution_date"], event["side"], event["price"])
            for event in payload["events"]
            if event["execution_date"] <= cutoff
        ]

    assert past_events(original) == past_events(changed)


def test_quant_signals_report_insufficient_history_without_fake_result():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930", MIN_HISTORY_ROWS - 1),
        now=datetime(2026, 7, 25, 12, 0),
    )

    assert payload["data_state"] == "insufficient"
    assert payload["current"] is None
    assert payload["performance"] is None
    assert payload["events"] == []


def test_quant_signal_endpoint_uses_same_engine_for_multiple_stocks(monkeypatch):
    db = _session()
    db.add_all([_stock(), _stock("000660", "SK하이닉스")])
    db.add_all(_price_rows("005930") + _price_rows("000660"))
    db.commit()

    def override_db():
        yield db

    monkeypatch.setattr(main, "ensure_stock_price_history", lambda *_args, **_kwargs: 340)
    monkeypatch.setattr(
        main,
        "_fetch_kis_current_quote",
        lambda code: {
            "trade_date": date(2026, 7, 25),
            "price": 25_000 if code == "005930" else 30_000,
            "volume": 2_000_000,
        },
    )
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        samsung = client.get("/stocks/005930/quant-signals")
        hynix = client.get("/stocks/000660/quant-signals")
        assert samsung.status_code == 200
        assert hynix.status_code == 200
        assert samsung.headers["cache-control"].startswith("no-store")
        assert samsung.json()["strategy_version"] == hynix.json()["strategy_version"]
        assert samsung.json()["code"] == "005930"
        assert hynix.json()["code"] == "000660"
        assert samsung.json()["current"]["live_observation"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_watchlist_quant_signal_endpoint_aggregates_the_same_strategy_without_cache(monkeypatch):
    db = _session()
    db.add_all([_stock(), _stock("000660", "SK하이닉스")])
    db.add_all(_price_rows("005930") + _price_rows("000660"))
    db.add_all(
        [
            WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI", sort_order=0),
            WatchlistItem(share_id="tester", code="000660", name="SK하이닉스", market="KOSPI", sort_order=1),
        ]
    )
    db.commit()
    today = datetime.now(main.KST).date()

    def fake_signal_payload(_db, code, **_kwargs):
        return {
            "data_state": "ready",
            "data_message": "",
            "as_of": datetime.now(main.KST),
            "price_through": today,
            "current": {
                "action": "entered",
                "entry_date": today,
                "position_open": True,
                "lifecycle": {"latest_transition": {"transition_date": today}},
            },
        }

    monkeypatch.setattr(main, "load_quant_signal_payload", fake_signal_payload)
    main.watchlist_quant_signal_cache.clear()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/watchlists/tester/quant-signals")
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        payload = response.json()
        assert payload["share_id"] == "tester"
        assert payload["recent_days"] == MARKET_SIGNAL_RECENT_DAYS
        assert [item["code"] for item in payload["items"]] == ["005930", "000660"]
        assert all(item["current"] for item in payload["items"])
        assert all(item["data_state"] == "ready" for item in payload["items"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        main.watchlist_quant_signal_cache.clear()
        db.close()


def test_watchlist_quant_signal_endpoint_only_returns_signals_from_the_last_two_weeks(monkeypatch):
    db = _session()
    db.add_all([_stock(), _stock("000660", "SK하이닉스")])
    db.add_all(
        [
            WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI", sort_order=0),
            WatchlistItem(share_id="tester", code="000660", name="SK하이닉스", market="KOSPI", sort_order=1),
        ]
    )
    db.commit()
    today = datetime.now(main.KST).date()

    def fake_signal_payload(_db, code, **_kwargs):
        signal_date = today - timedelta(days=MARKET_SIGNAL_RECENT_DAYS if code == "005930" else MARKET_SIGNAL_RECENT_DAYS + 1)
        return {
            "data_state": "ready",
            "data_message": "",
            "as_of": datetime.now(main.KST),
            "price_through": signal_date,
            "current": {
                "action": "entered",
                "entry_date": signal_date,
                "position_open": True,
                "lifecycle": {"latest_transition": {"transition_date": signal_date}},
            },
        }

    monkeypatch.setattr(main, "load_quant_signal_payload", fake_signal_payload)

    def override_db():
        yield db

    main.watchlist_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/watchlists/tester/quant-signals")
        assert response.status_code == 200
        assert [item["code"] for item in response.json()["items"]] == ["005930"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        main.watchlist_quant_signal_cache.clear()
        db.close()


def test_market_quant_signal_feed_uses_market_cap_top_universe_and_normalizes_sell(monkeypatch):
    db = _session()
    stocks = [_stock("000001", "대형주"), _stock("000002", "중형주"), _stock("000003", "소형주")]
    trade_date = date(2026, 7, 25)
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=trade_date, close=100_000, market_cap=300_000_000),
            DailyPrice(code="000002", trade_date=trade_date, close=50_000, market_cap=200_000_000),
            DailyPrice(code="000003", trade_date=trade_date, close=10_000, market_cap=100_000_000),
        ]
    )
    db.commit()

    monkeypatch.setattr(
        quant_signals,
        "build_quant_signal_payload",
        lambda stock, _rows, **_kwargs: {
            "events": [
                {
                    "signal_date": trade_date - timedelta(days=1),
                    "execution_date": trade_date,
                    "side": "buy" if stock.code == "000001" else "partial_sell",
                    "price": 100_000,
                }
            ]
        },
    )
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=10,
        recent_days=MARKET_SIGNAL_RECENT_DAYS,
        now=datetime(2026, 7, 26, 9, 0),
    )

    assert payload["universe_count"] == 2
    assert [item["code"] for item in payload["items"]] == ["000001", "000002"]
    assert [item["signal"] for item in payload["items"]] == ["매수", "매도"]
    assert [item["market_cap_rank"] for item in payload["items"]] == [1, 2]
    db.close()


def test_market_quant_signal_feed_includes_lower_ranked_active_stocks(monkeypatch):
    db = _session()
    stocks = [_stock("000001", "대형주"), _stock("000002", "중형주"), _stock("000003", "SK텔레콤")]
    trade_date = date(2026, 7, 25)
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=trade_date, close=100_000, market_cap=300_000_000),
            DailyPrice(code="000002", trade_date=trade_date, close=50_000, market_cap=200_000_000),
            DailyPrice(code="000003", trade_date=trade_date, close=10_000, market_cap=100_000_000),
        ]
    )
    db.commit()

    monkeypatch.setattr(
        quant_signals,
        "build_quant_signal_payload",
        lambda stock, _rows, **_kwargs: {
            "events": [
                {
                    "signal_date": trade_date,
                    "execution_date": trade_date,
                    "side": "buy" if stock.code == "000003" else "sell",
                    "price": 100_000,
                }
            ]
        },
    )
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=3,
        limit=10,
        recent_days=7,
        now=datetime(2026, 7, 26, 9, 0),
    )

    assert payload["universe_count"] == 3
    assert {item["code"] for item in payload["items"]} == {"000001", "000002", "000003"}
    assert next(item for item in payload["items"] if item["code"] == "000003")["market_cap_rank"] == 3
    db.close()


def test_market_quant_signal_feed_uses_latest_complete_price_date_not_partial_cap_date(monkeypatch):
    db = _session()
    stocks = [_stock("000001", "대형주"), _stock("000002", "중형주"), _stock("000003", "SK텔레콤")]
    complete_date = date(2026, 7, 25)
    partial_date = date(2026, 7, 26)
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=complete_date, close=100_000, market_cap=300_000_000),
            DailyPrice(code="000002", trade_date=complete_date, close=50_000),
            DailyPrice(code="000003", trade_date=complete_date, close=10_000),
            DailyPrice(code="000001", trade_date=partial_date, close=101_000, market_cap=301_000_000),
        ]
    )
    db.commit()

    monkeypatch.setattr(
        quant_signals,
        "build_quant_signal_payload",
        lambda stock, _rows, **_kwargs: {
            "events": [
                {
                    "signal_date": complete_date,
                    "execution_date": complete_date,
                    "side": "buy",
                    "price": 100_000,
                }
            ]
        },
    )
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=3,
        limit=10,
        recent_days=7,
        now=datetime(2026, 7, 26, 18, 0),
    )

    assert payload["universe_as_of"] == complete_date
    assert payload["universe_count"] == 3
    assert {item["code"] for item in payload["items"]} == {"000001", "000002", "000003"}
    db.close()


def test_market_quant_signal_endpoint_is_no_store(monkeypatch):
    db = _session()

    def override_db():
        yield db

    monkeypatch.setattr(
        main,
        "load_market_quant_signal_feed",
        lambda *_args, **_kwargs: {
            "as_of": datetime(2026, 7, 26, 9, 0),
            "universe_as_of": date(2026, 7, 25),
            "universe_count": 100,
            "recent_days": MARKET_SIGNAL_RECENT_DAYS,
            "items": [],
        },
    )
    main.market_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/market/quant-signals")
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        assert response.json()["status"] == "preparing"
        assert response.json()["universe_count"] == 0
    finally:
        main.market_quant_signal_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_current_context_uses_connected_sources_without_rewriting_backtest():
    db = _session()
    stock = _stock()
    prices = _price_rows("005930")
    latest_date = prices[-1].trade_date
    db.add(stock)
    db.add_all(prices)
    db.add_all(
        [
            InvestorFlow(
                code="005930",
                trade_date=latest_date,
                investor_type="외국인",
                net_buy_value=12_000_000_000,
            ),
            InvestorFlow(
                code="005930",
                trade_date=latest_date,
                investor_type="기관합계",
                net_buy_value=-3_000_000_000,
            ),
            NewsItem(
                source="test",
                source_category="company",
                external_id="news-1",
                title="삼성전자 실적 개선과 성장 전망",
                published_at=datetime(2026, 7, 24, 9, 0),
            ),
            ResearchReport(
                source="test",
                source_category="company",
                external_id="report-1",
                title="삼성전자 전망",
                stock_code="005930",
                broker_name="테스트증권",
                opinion="매수",
                target_price=Decimal("50000"),
                published_at=datetime(2026, 7, 23, 9, 0),
            ),
            DisclosureItem(
                source="dart",
                external_id="disclosure-1",
                disclosure_category="공시목록",
                company_name="삼성전자",
                stock_code="005930",
                report_name="공급계약 수주 증가",
                published_at=datetime(2026, 7, 22, 9, 0),
            ),
        ]
    )
    db.commit()

    baseline = build_quant_signal_payload(stock, prices, now=datetime(2026, 7, 25, 12, 0))
    enriched = load_quant_signal_payload(db, "005930", now=datetime(2026, 7, 25, 12, 0))

    assert enriched is not None
    assert enriched["confirmation"]["available_count"] == 5
    assert {item["key"] for item in enriched["confirmation"]["evidence"]} == {
        "flow",
        "news",
        "research",
        "disclosure",
        "liquidity",
    }
    assert [
        (event["signal_date"], event["execution_date"], event["side"], event["price"])
        for event in enriched["events"]
    ] == [
        (event["signal_date"], event["execution_date"], event["side"], event["price"])
        for event in baseline["events"]
    ]
    db.close()
