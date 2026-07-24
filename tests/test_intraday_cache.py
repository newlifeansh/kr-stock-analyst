from __future__ import annotations

from datetime import date, datetime, timedelta
from threading import Lock
from time import sleep

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import main
from app.collectors.briefing import KisRestBriefingProvider
from app.config import Settings
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


def test_closed_intraday_collection_fetches_time_windows_in_parallel(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    active = 0
    max_active = 0
    lock = Lock()

    monkeypatch.setattr(provider, "_ensure_token", lambda: "token")
    monkeypatch.setattr("app.collectors.briefing.current_market_status", lambda _now=None: "closed")

    def fake_get(_path, _tr_id, params):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        sleep(0.01)
        cursor = datetime.strptime(params["FID_INPUT_HOUR_1"], "%H%M%S")
        rows = []
        for offset in range(30):
            point_time = cursor - timedelta(minutes=offset)
            if point_time.time() < datetime.strptime("090100", "%H%M%S").time():
                continue
            rows.append(
                {
                    "stck_bsop_date": "20260724",
                    "stck_cntg_hour": point_time.strftime("%H%M%S"),
                    "stck_prpr": "100000",
                    "cntg_vol": "100",
                }
            )
        with lock:
            active -= 1
        return {"output2": rows}

    monkeypatch.setattr(provider, "_get", fake_get)
    rows = provider.fetch_intraday_chart("000660", max_points=390)

    assert max_active > 1
    assert len(rows) == 390
    assert rows[0]["trade_time"] == "090100"
    assert rows[-1]["trade_time"] == "153000"


def test_intraday_warmup_does_not_run_during_regular_market(monkeypatch):
    monkeypatch.setattr(main, "_korea_regular_market_open", lambda _now=None: True)
    monkeypatch.setattr(
        main.kis_rest_provider,
        "is_configured",
        lambda: (_ for _ in ()).throw(AssertionError("provider should not be checked")),
    )

    assert main._warm_closed_intraday_snapshots(datetime(2026, 7, 27, 10, 0, tzinfo=main.KST)) == 0
