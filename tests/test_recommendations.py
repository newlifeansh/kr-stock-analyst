from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import DailyPrice, StockMaster
from app.schemas import MarketRecommendationOut
from app.services import recommendations
from app.services.recommendations import _action, _decision_reason, build_recommendations, universe_cache


def test_high_recommendation_score_produces_an_actionable_but_measured_decision():
    action = _action(Decimal("82.12"), Decimal("80"))

    assert action == "분할 접근"
    assert "추격 대신 나눠 접근" in _decision_reason(
        action,
        Decimal("82.12"),
        Decimal("80"),
        Decimal("30.55"),
    )


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _seed_prices(
    db: Session,
    code: str,
    name: str,
    latest_close: int,
    volume: int,
    *,
    sector=None,
    industry=None,
):
    db.add(
        StockMaster(
            code=code,
            name=name,
            market="KOSPI",
            sector=sector,
            industry=industry,
        )
    )
    start = date(2026, 3, 2)
    for offset in range(70):
        close = latest_close - (69 - offset) * 10
        db.add(
            DailyPrice(
                code=code,
                trade_date=start + timedelta(days=offset),
                open=close - 5,
                high=close + 20,
                low=close - 20,
                close=close,
                volume=volume,
                trading_value=None,
                market_cap=None,
                listed_shares=None,
            )
        )


def test_recommendations_fall_back_to_close_times_volume_without_market_cap():
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        _seed_prices(db, "000660", "SK하이닉스", 280000, 700_000)
        db.commit()

        payload = build_recommendations(
            db,
            limit=2,
            candidate_limit=10,
            refresh_live=True,
            ensure_signal_history=False,
        )

        assert payload["universe_count"] == 2
        assert payload["candidate_count"] == 2
        assert len(payload["items"]) == 2
        assert all(item["trading_value"] for item in payload["items"])
        assert all(item["ai_trade_signal"] for item in payload["items"])
        assert all(item["ai_trade_signal"]["entry_score_threshold"] == Decimal("62.00") for item in payload["items"])


def test_recommendations_only_expand_to_small_diversity_pool():
    with _session() as db:
        for idx in range(8):
            code = f"{100000 + idx:06d}"
            _seed_prices(db, code, f"종목{idx}", 10000 + idx * 500, 300_000 + idx * 50_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=2,
            candidate_limit=2,
            refresh_live=False,
            ensure_signal_history=False,
        )

        assert payload["candidate_count"] == 4
        assert len(payload["items"]) == 2


def test_fast_recommendations_only_score_observed_components_and_never_render_none_percent():
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=1,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )
        item = payload["items"][0]

        assert set(item["component_scores"]) == {"price_momentum", "trading_value"}
        assert all("None%" not in reason for reason in item["reasons"])
        assert "매수" not in item["action"]
        assert item["ai_trade_signal"]["data_state"] == "insufficient"


def test_recommendations_backfill_signal_history_before_calculating_ai_stage(monkeypatch):
    calls = []

    def ensure_history(
        _db,
        code,
        min_rows,
        lookback_days,
        *,
        require_recent_complete_ohlc,
    ):
        calls.append((code, min_rows, lookback_days, require_recent_complete_ohlc))
        return min_rows

    monkeypatch.setattr(recommendations, "ensure_stock_price_history", ensure_history)
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        universe_cache.clear()
        build_recommendations(db, limit=1, candidate_limit=10, refresh_live=False)

    assert calls == [
        ("005930", recommendations.MIN_BACKTEST_HISTORY_ROWS, 600, True)
    ]


def test_recommendations_link_compact_signal_stage_and_released_preliminary(monkeypatch):
    signal_as_of = datetime(2026, 8, 20, 13, 8, tzinfo=recommendations.KST)
    signal_payload = {
        "data_state": "ready",
        "data_message": "ready",
        "as_of": signal_as_of,
        "price_through": date(2026, 8, 20),
        "strategy_version": "position-lifecycle-test",
        "signal_source": "local",
        "entry_score_threshold": Decimal("62"),
        "display_return_rate": Decimal("4.25"),
        "display_return_kind": "open_position",
        "current": {
            "action": "holding",
            "label": "전략상 보유 중",
            "score": Decimal("78.5"),
            "price": 81_000,
            "as_of": signal_as_of,
            "live_observation": False,
            "position_open": True,
            "model_exposure_percent": Decimal("100"),
            "lifecycle": {
                "state": "holding",
                "label": "전략상 보유 중",
                "stage_index": 2,
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"],
                "latest_transition": {
                    "label": "확정 매수",
                    "side": "buy",
                    "signal_at": signal_as_of,
                    "transition_date": date(2026, 8, 20),
                    "price": 80_000,
                },
            },
            "entry_date": date(2026, 8, 20),
            "entry_price": 80_000,
            "target_sell_price": 92_000,
            "partial_exit_date": None,
            "partial_exit_price": None,
            "profit_stage": 2,
            "pending_profit_stage": 3,
            "profit_steps_total": 3,
            "partial_exit_reference": 96_000,
            "locked_profit_reference": 89_000,
            "stop_reference": 88_500,
            "unrealized_return": Decimal("4.25"),
            "reasons": ["상승 추세 유지"],
            "next_confirmation": "1차 수익확정 가격을 확인",
        },
    }
    preliminary_snapshot = {
        "preliminary_history": [
            {
                "code": "005930",
                "side": "buy",
                "signal_date": "2026-08-20",
                "first_seen_at": "2026-08-20T09:35:00+09:00",
                "last_seen_at": "2026-08-20T10:05:00+09:00",
                "active": False,
                "price": 79_500,
                "score": "72.1",
                "reason": "장중 조건 해제",
            }
        ]
    }
    monkeypatch.setattr(recommendations, "load_quant_signal_payload", lambda *_args, **_kwargs: signal_payload)
    monkeypatch.setattr(recommendations, "load_reference_quant_signal_payload", lambda *_args, **_kwargs: signal_payload)
    monkeypatch.setattr(
        recommendations,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: preliminary_snapshot,
    )

    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80_000, 1_000_000)
        db.commit()
        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=1,
            candidate_limit=10,
            refresh_live=False,
            ensure_signal_history=False,
        )

    item = payload["items"][0]
    compact = item["ai_trade_signal"]
    assert item["recommended_at"] == payload["as_of"]
    assert compact["current"]["lifecycle"]["state"] == "holding"
    assert compact["current"]["entry_price"] == 80_000
    assert compact["current"]["profit_stage"] == 2
    assert compact["current"]["pending_profit_stage"] == 3
    assert compact["current"]["partial_exit_reference"] == 96_000
    assert compact["current"]["locked_profit_reference"] == 89_000
    assert compact["display_return_rate"] == Decimal("4.25")
    assert compact["latest_preliminary"]["active"] is False
    assert compact["latest_preliminary"]["last_seen_at"] == "2026-08-20T10:05:00+09:00"
    validated = MarketRecommendationOut.model_validate(payload)
    assert validated.items[0].ai_trade_signal.current.lifecycle.state == "holding"
    assert validated.items[0].ai_trade_signal.current.pending_profit_stage == 3


def test_recommendations_diversify_same_family_names_on_first_pass():
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 2_000_000)
        _seed_prices(db, "032830", "삼성생명", 120000, 1_600_000)
        _seed_prices(db, "000660", "SK하이닉스", 280000, 900_000)
        _seed_prices(db, "035420", "NAVER", 230000, 850_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=3,
            candidate_limit=3,
            refresh_live=False,
            ensure_signal_history=False,
        )
        names = [str(item["name"]) for item in payload["items"]]

        assert len(payload["items"]) == 3
        assert sum(name.startswith("삼성") for name in names) == 1


def test_recommendations_limit_same_investment_sector_when_alternatives_exist():
    with _session() as db:
        for index in range(3):
            _seed_prices(
                db,
                f"10{index:04d}",
                f"칩기업{index}",
                20_000 + index * 100,
                1_000_000 - index * 10_000,
                sector="전기·전자",
                industry="반도체와반도체장비",
            )
        for index in range(2):
            _seed_prices(
                db,
                f"20{index:04d}",
                f"금융기업{index}",
                18_000 + index * 100,
                900_000 - index * 10_000,
                sector="금융",
                industry="은행",
            )
        _seed_prices(
            db,
            "300000",
            "소비기업",
            16_000,
            800_000,
            sector="음식료·담배",
            industry="식품",
        )
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(
            db,
            limit=5,
            candidate_limit=6,
            refresh_live=False,
            ensure_signal_history=False,
        )

        sectors = [item["investment_sector"] for item in payload["items"]]
        assert len(sectors) == 5
        assert sectors.count("semiconductor") <= 2
        assert sectors.count("financials") <= 2
        assert "consumer" in sectors
