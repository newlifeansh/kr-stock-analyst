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
    trading_value: int = 10_000_000_000,
    market_cap: int = 1_000_000_000_000,
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
                trading_value=trading_value,
                market_cap=market_cap,
            )
        )


def _seed_relationships(db: Session) -> None:
    target_returns = [
        0.018
        if index % 4 == 0
        else -0.014
        if index % 4 == 1
        else 0.011
        if index % 4 == 2
        else -0.019
        for index in range(80)
    ]
    db.add_all(
        [
            StockMaster(code="000001", name="기준종목", market="KOSPI", is_active=True),
            StockMaster(
                code="000002",
                name="반대종목",
                market="KOSDAQ",
                sector="반도체·반도체장비",
                industry="반도체 제조",
                is_active=True,
            ),
            StockMaster(code="000003", name="같은종목", market="KOSPI", is_active=True),
        ]
    )
    _add_price_series(db, "000001", target_returns)
    _add_price_series(db, "000002", [-rate for rate in target_returns])
    _add_price_series(db, "000003", target_returns)
    db.commit()


def test_opposite_moves_only_returns_stable_top_market_cap_inverse_candidate():
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
        assert candidate["sector"] == "반도체·반도체장비"
        assert candidate["industry"] == "반도체 제조"
        assert candidate["market_cap_rank"] == 2
        assert candidate["correlation"] < -0.99
        assert candidate["recent_correlation"] < -0.99
        assert (
            candidate["candidate_up_on_target_down_days"]
            == candidate["target_down_days"]
        )
        assert candidate["down_day_opposite_rate"] == 1.0
    finally:
        db.close()


def test_opposite_moves_fills_missing_slots_from_ranks_101_to_200():
    db = _session()
    try:
        _seed_relationships(db)
        latest_date = date(2026, 3, 23)
        for index in range(100):
            code = str(100_000 + index)
            db.add(
                StockMaster(
                    code=code,
                    name=f"상위종목{index + 1}",
                    market="KOSPI",
                    is_active=True,
                )
            )
            db.add(
                DailyPrice(
                    code=code,
                    trade_date=latest_date,
                    close=100_000,
                    trading_value=20_000_000_000,
                    market_cap=2_000_000_000_000 - index,
                )
            )
        inverse_returns = [
            -rate
            for rate in [
                0.018
                if index % 4 == 0
                else -0.014
                if index % 4 == 1
                else 0.011
                if index % 4 == 2
                else -0.019
                for index in range(80)
            ]
        ]
        db.add(
            StockMaster(
                code="000004",
                name="거래부족중형주",
                market="KOSPI",
                is_active=True,
            )
        )
        _add_price_series(
            db,
            "000004",
            inverse_returns,
            trading_value=1,
            market_cap=900_000_000_000,
        )
        db.commit()

        payload = build_opposite_moves(db, "000001", limit=3)

        assert payload["status"] == "ready"
        assert [item["code"] for item in payload["items"]] == ["000002"]
        assert payload["items"][0]["market_cap_rank"] == 102
        assert "200위까지" in payload["message"]
    finally:
        db.close()


def test_opposite_moves_does_not_extend_when_three_top_100_candidates_are_ready():
    db = _session()
    try:
        target_returns = [0.018 if index % 2 == 0 else -0.014 for index in range(80)]
        inverse_returns = [-rate for rate in target_returns]
        latest_date = date(2026, 3, 23)
        db.add(
            StockMaster(code="020000", name="기준종목", market="KOSPI", is_active=True)
        )
        _add_price_series(db, "020000", target_returns, market_cap=10_000_000_000_000)
        primary_codes = ["020001", "020002", "020003"]
        for offset, code in enumerate(primary_codes):
            db.add(
                StockMaster(
                    code=code,
                    name=f"상위반대종목{offset + 1}",
                    market="KOSPI",
                    is_active=True,
                )
            )
            _add_price_series(
                db,
                code,
                inverse_returns,
                market_cap=9_900_000_000_000 - offset,
            )
        for index in range(96):
            code = str(200_000 + index)
            db.add(
                StockMaster(
                    code=code,
                    name=f"상위채움종목{index + 1}",
                    market="KOSPI",
                    is_active=True,
                )
            )
            db.add(
                DailyPrice(
                    code=code,
                    trade_date=latest_date,
                    close=100_000,
                    trading_value=20_000_000_000,
                    market_cap=9_000_000_000_000 - index,
                )
            )
        db.add(
            StockMaster(
                code="020004",
                name="확장반대종목",
                market="KOSPI",
                is_active=True,
            )
        )
        _add_price_series(
            db,
            "020004",
            inverse_returns,
            market_cap=7_000_000_000_000,
        )
        db.commit()

        payload = build_opposite_moves(db, "020000", limit=3)

        assert payload["status"] == "ready"
        assert [item["code"] for item in payload["items"]] == primary_codes
        assert all(item["market_cap_rank"] <= 100 for item in payload["items"])
    finally:
        db.close()


def test_opposite_moves_excludes_inverse_candidate_outside_top_200_ordinary_shares():
    db = _session()
    try:
        _seed_relationships(db)
        latest_date = date(2026, 3, 23)
        for index in range(200):
            code = str(300_000 + index)
            db.add(
                StockMaster(
                    code=code,
                    name=f"200위채움종목{index + 1}",
                    market="KOSPI",
                    is_active=True,
                )
            )
            db.add(
                DailyPrice(
                    code=code,
                    trade_date=latest_date,
                    close=100_000,
                    trading_value=20_000_000_000,
                    market_cap=2_000_000_000_000 - index,
                )
            )
        db.commit()

        payload = build_opposite_moves(db, "000001", limit=3)

        assert payload["status"] == "no_stable_opposite"
        assert payload["items"] == []
        assert "시총 상위 200개" in payload["message"]
    finally:
        db.close()


def test_opposite_moves_top_100_excludes_funds_spacs_and_preferred_shares():
    db = _session()
    try:
        target_returns = [0.018 if index % 2 == 0 else -0.014 for index in range(80)]
        candidates = [
            ("010001", "KODEX 인버스"),
            ("010002", "삼성 인버스 2X WTI원유 선물 ETN"),
            ("010003", "테스트제1호스팩"),
            ("010004", "삼성전자우"),
            ("010005", "일반대형주"),
        ]
        db.add(
            StockMaster(code="010000", name="기준종목", market="KOSPI", is_active=True)
        )
        _add_price_series(db, "010000", target_returns, market_cap=10_000_000_000_000)
        for offset, (code, name) in enumerate(candidates):
            db.add(StockMaster(code=code, name=name, market="KOSPI", is_active=True))
            _add_price_series(
                db,
                code,
                [-rate for rate in target_returns],
                market_cap=9_000_000_000_000 - offset,
            )
        db.commit()

        payload = build_opposite_moves(db, "010000", limit=3)

        assert payload["status"] == "ready"
        assert [item["code"] for item in payload["items"]] == ["010005"]
        assert payload["items"][0]["market_cap_rank"] == 2
    finally:
        db.close()


def test_opposite_moves_fail_closed_when_history_is_short():
    db = _session()
    try:
        db.add(
            StockMaster(code="000010", name="신규종목", market="KOSPI", is_active=True)
        )
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
        assert payload["items"][0]["sector"] == "반도체·반도체장비"
        assert payload["items"][0]["industry"] == "반도체 제조"
        assert payload["items"][0]["market_cap_rank"] == 2
        assert payload["items"][0]["comparison_end"] == "2026-03-23"
        assert payload["items"][0]["logo_url"] == "/stock-logos/000002.png"
    finally:
        main_module.api_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()
