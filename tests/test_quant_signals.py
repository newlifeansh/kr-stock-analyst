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
from app.models import DailyPrice, StockMaster
from app.services.quant_signals import MIN_HISTORY_ROWS, STRATEGY_VERSION, build_quant_signal_payload


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
    assert {event["side"] for event in payload["events"]} == {"buy", "sell"}
    assert all(event["execution_date"] > event["signal_date"] for event in payload["events"])
    for trade in (item for item in payload["trades"] if item["status"] == "closed"):
        assert trade["net_return"] <= trade["gross_return"]
        assert trade["holding_days"] >= 1
    assert payload["performance"]["transaction_cost_per_side"] == Decimal("0.20")
    assert payload["performance"]["max_drawdown"] <= 0


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
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
