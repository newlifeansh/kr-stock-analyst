from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import DailyPrice, StockMaster
from app.services.recommendations import build_recommendations, universe_cache


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _seed_prices(db: Session, code: str, name: str, latest_close: int, volume: int):
    db.add(StockMaster(code=code, name=name, market="KOSPI"))
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

        payload = build_recommendations(db, limit=2, candidate_limit=10, refresh_live=True)

        assert payload["universe_count"] == 2
        assert payload["candidate_count"] == 2
        assert len(payload["items"]) == 2
        assert all(item["trading_value"] for item in payload["items"])


def test_recommendations_only_expand_to_small_diversity_pool():
    with _session() as db:
        for idx in range(8):
            code = f"{100000 + idx:06d}"
            _seed_prices(db, code, f"종목{idx}", 10000 + idx * 500, 300_000 + idx * 50_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(db, limit=2, candidate_limit=2, refresh_live=False)

        assert payload["candidate_count"] == 4
        assert len(payload["items"]) == 2


def test_fast_recommendations_only_score_observed_components_and_never_render_none_percent():
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 1_000_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(db, limit=1, candidate_limit=10, refresh_live=False)
        item = payload["items"][0]

        assert set(item["component_scores"]) == {"price_momentum", "trading_value"}
        assert all("None%" not in reason for reason in item["reasons"])
        assert "매수" not in item["action"]


def test_recommendations_diversify_same_family_names_on_first_pass():
    with _session() as db:
        _seed_prices(db, "005930", "삼성전자", 80000, 2_000_000)
        _seed_prices(db, "032830", "삼성생명", 120000, 1_600_000)
        _seed_prices(db, "000660", "SK하이닉스", 280000, 900_000)
        _seed_prices(db, "035420", "NAVER", 230000, 850_000)
        db.commit()

        universe_cache.clear()
        payload = build_recommendations(db, limit=3, candidate_limit=3, refresh_live=False)
        names = [str(item["name"]) for item in payload["items"]]

        assert len(payload["items"]) == 3
        assert sum(name.startswith("삼성") for name in names) == 1
