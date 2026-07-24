from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main
from app.db import Base


def _points(trade_date: str = "20260724", count: int = 30) -> list[dict[str, object]]:
    return [
        {
            "trade_date": trade_date,
            "trade_time": f"09{index:02d}00",
            "price": 100_000 + index,
            "volume": 100 + index,
        }
        for index in range(count)
    ]


class _Provider:
    def __init__(self) -> None:
        self.calls = 0

    @staticmethod
    def is_configured() -> bool:
        return True

    def fetch_intraday_chart(self, code: str, *, max_points: int) -> list[dict[str, object]]:
        self.calls += 1
        return _points(count=min(max_points, 30))


def test_closed_intraday_endpoint_reuses_confirmed_snapshot(monkeypatch):
    provider = _Provider()
    records: dict[str, dict[str, object]] = {}

    def load_snapshot(_db, code, limit, _now):
        record = records.get(code)
        return (record, "memory") if record and int(record["max_points"]) >= limit else (None, None)

    def save_snapshot(_db, code, points, limit, now):
        record = {
            "points": points,
            "trade_date": date(2026, 7, 24),
            "validated_on": now.date(),
            "max_points": limit,
            "fetched_at": datetime(2026, 7, 25, 1, 0),
        }
        records[code] = record
        return record

    monkeypatch.setattr(main, "kis_rest_provider", provider)
    monkeypatch.setattr(main, "_korea_regular_market_open", lambda _now=None: False)
    monkeypatch.setattr(main, "_load_closed_intraday_snapshot", load_snapshot)
    monkeypatch.setattr(main, "_save_closed_intraday_snapshot", save_snapshot)

    client = TestClient(main.app)
    first = client.get("/stocks/000660/intraday?limit=30")
    second = client.get("/stocks/000660/intraday?limit=30")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_state"] == "miss"
    assert second.json()["cache_state"] == "memory"
    assert second.json()["market_state"] == "closed"
    assert second.headers["x-intraday-cache"] == "memory"
    assert second.headers["cache-control"].startswith("private, max-age=")
    assert provider.calls == 1


def test_regular_market_intraday_endpoint_never_uses_snapshot(monkeypatch):
    provider = _Provider()

    monkeypatch.setattr(main, "kis_rest_provider", provider)
    monkeypatch.setattr(main, "_korea_regular_market_open", lambda _now=None: True)
    monkeypatch.setattr(
        main,
        "_load_closed_intraday_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live request used cache")),
    )

    client = TestClient(main.app)
    first = client.get("/stocks/000660/intraday?limit=30")
    second = client.get("/stocks/000660/intraday?limit=30")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_state"] == "live"
    assert second.json()["market_state"] == "regular"
    assert first.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert provider.calls == 2


def test_closed_intraday_snapshot_survives_memory_cache_clear():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    now = datetime(2026, 7, 25, 18, 0, tzinfo=main.KST)

    with Session(engine) as db:
        saved = main._save_closed_intraday_snapshot(db, "000660", _points(), 30, now)
        assert saved is not None
        main.intraday_chart_cache.clear()

        loaded, cache_state = main._load_closed_intraday_snapshot(db, "000660", 30, now)

    assert cache_state == "database"
    assert loaded is not None
    assert len(loaded["points"]) == 30
    assert loaded["trade_date"] == date(2026, 7, 24)

