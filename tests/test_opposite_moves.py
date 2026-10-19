from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main as main_module
from app.db import Base, get_db
from app.main import app
from app.models import DailyPrice, StockMaster
from app.services.opposite_moves import build_opposite_moves


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _add_price_series(
    db: Session,
    code: str,
    returns: list[float],
    *,
    start: date = date(2026, 1, 2),
) -> None:
    close = 100_000.0
    closes = [round(close)]
    for rate in returns:
        close *= 1.0 + rate
        closes.append(max(1, round(close)))
    for offset, value in enumerate(closes):
        db.add(
            DailyPrice(
                code=code,
                trade_date=start + timedelta(days=offset),
                open=value,
                high=value,
                low=value,
                close=value,
                volume=100_000,
                trading_value=10_000_000_000,
                market_cap=1_000_000_000_000,
            )
        )


def _seed_relationships(db: Session) -> None:
    target_returns = [
        0.018 if index % 4 == 0 else -0.014 if index % 4 == 1 else 0.011 if index % 4 == 2 else -0.019
        for index in range(80)
    ]
    db.add_all(
        [
            StockMaster(code="000001", name="기준종목", market="KOSPI", is_active=True),
            StockMaster(code="000002", name="반대종목", market="KOSDAQ", is_active=True),
            StockMaster(code="000003", name="같은종목", market="KOSPI", is_active=True),
            StockMaster(code="000004", name="저유동성", market="KOSPI", is_active=True),
        ]
    )
    _add_price_series(db, "000001", target_returns)
    _add_price_series(db, "000002", [-rate for rate in target_returns])
    _add_price_series(db, "000003", target_returns)
    _add_price_series(db, "000004", [-rate for rate in target_returns])
    db.flush()
    for row in db.query(DailyPrice).filter(DailyPrice.code == "000004"):
        row.trading_value = 1_000
        row.market_cap = 1_000_000
    db.commit()


def test_opposite_moves_only_returns_liquid_stable_inverse_candidate():
    db = _session()
    try:
        _seed_relationships(db)

        payload = build_opposite_moves(db, "000001", limit=3)

        assert payload["status"] == "ready"
        assert payload["lookback_sessions"] == 120
        assert payload["observations"] == 80
        assert [item["code"] for item in payload["items"]] == ["000002"]
        candidate = payload["items"][0]
        assert candidate["relationship_label"] == "자주 반대로 움직임"
        assert candidate["correlation"] < -0.99
        assert candidate["recent_correlation"] < -0.99
        assert candidate["candidate_up_on_target_down_days"] == candidate["target_down_days"]
        assert candidate["down_day_opposite_rate"] == 1.0
    finally:
        db.close()


def test_opposite_moves_fail_closed_when_history_is_short():
    db = _session()
    try:
        db.add(StockMaster(code="000010", name="신규종목", market="KOSPI", is_active=True))
        _add_price_series(db, "000010", [0.01, -0.01] * 10)
        db.commit()

        payload = build_opposite_moves(db, "000010")

        assert payload["status"] == "insufficient_history"
        assert payload["items"] == []
        assert payload["observations"] == 20
    finally:
        db.close()


def test_opposite_moves_excludes_unfinished_daily_row():
    db = _session()
    try:
        _seed_relationships(db)
        completed_through = date(2026, 3, 23)
        for code, close in (("000001", 10_000), ("000002", 1_000_000)):
            db.add(
                DailyPrice(
                    code=code,
                    trade_date=completed_through + timedelta(days=1),
                    close=close,
                    trading_value=10_000_000_000,
                    market_cap=1_000_000_000_000,
                )
            )
        db.commit()

        payload = build_opposite_moves(
            db,
            "000001",
            completed_through=completed_through,
        )

        assert payload["status"] == "ready"
        assert payload["as_of"] == completed_through
        assert payload["items"][0]["comparison_end"] == completed_through
        assert payload["items"][0]["correlation"] < -0.99
    finally:
        db.close()


def test_opposite_moves_api_returns_completed_close_relationship_contract():
    db = _session()
    _seed_relationships(db)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    main_module.api_cache.clear()
    try:
        response = TestClient(app).get("/stocks/000001/opposite-moves?limit=3")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "public, max-age=900"
        payload = response.json()
        assert payload["code"] == "000001"
        assert payload["name"] == "기준종목"
        assert payload["status"] == "ready"
        assert payload["items"][0]["code"] == "000002"
        assert payload["items"][0]["comparison_end"] == "2026-03-23"
        assert payload["items"][0]["logo_url"] == "/stock-logos/000002.png"
    finally:
        main_module.api_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()
