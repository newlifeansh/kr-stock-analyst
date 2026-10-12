from __future__ import annotations

from datetime import date, datetime, timedelta
from threading import Lock
from time import sleep
from zoneinfo import ZoneInfo

import requests
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
        self.market_divisions: list[str] = []

    @staticmethod
    def is_configured() -> bool:
        return True

    def fetch_intraday_chart(
        self,
        code: str,
        *,
        max_points: int,
        market_division: str = "J",
    ) -> list[dict[str, object]]:
        self.calls += 1
        self.market_divisions.append(market_division)
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
    monkeypatch.setattr(
        main,
        "_korea_intraday_session",
        lambda _now=None: {
            "is_live": False,
            "market_state": "closed",
            "market_session": "closed",
            "market_session_label": "장 마감",
            "market_venue": "KRX",
            "market_division": "J",
        },
    )
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
    monkeypatch.setattr(
        main,
        "_korea_intraday_session",
        lambda _now=None: {
            "is_live": True,
            "market_state": "regular",
            "market_session": "integrated_regular",
            "market_session_label": "통합 정규장",
            "market_venue": "INTEGRATED",
            "market_division": "UN",
        },
    )
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
    assert provider.market_divisions == ["UN", "UN"]


def test_nxt_pre_market_intraday_endpoint_uses_live_nxt_minutes(monkeypatch):
    provider = _Provider()
    monkeypatch.setattr(main, "kis_rest_provider", provider)
    monkeypatch.setattr(
        main,
        "_korea_intraday_session",
        lambda _now=None: {
            "is_live": True,
            "market_state": "pre_market",
            "market_session": "nxt_pre_market",
            "market_session_label": "NXT 프리마켓",
            "market_venue": "NXT",
            "market_division": "NX",
        },
    )

    response = TestClient(main.app).get("/stocks/000660/intraday?limit=30")

    assert response.status_code == 200
    assert response.json()["market_state"] == "pre_market"
    assert response.json()["market_session_label"] == "NXT 프리마켓"
    assert response.json()["market_division"] == "NX"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert provider.market_divisions == ["NX"]


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


def test_kis_premarket_chart_discards_future_same_day_minutes(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    now = datetime(2026, 10, 8, 8, 30, tzinfo=ZoneInfo("Asia/Seoul"))
    output = [
        {"stck_bsop_date": "20261008", "stck_cntg_hour": "153000",
         "stck_prpr": "100000", "cntg_vol": "100"},
        {"stck_bsop_date": "20261007", "stck_cntg_hour": "153000",
         "stck_prpr": "99000", "cntg_vol": "100"},
    ]
    monkeypatch.setattr("app.collectors.briefing.current_market_status", lambda _now=None: "closed")
    monkeypatch.setattr(provider, "_get", lambda *_args: {"output2": output})

    rows = provider.fetch_intraday_chart("247540", max_points=30, now=now)
    assert [(row["trade_date"], row["trade_time"]) for row in rows] == [
        ("20261007", "153000")
    ]

    output.pop()
    assert provider.fetch_intraday_chart("247540", max_points=30, now=now) == []


def test_premarket_future_chart_is_neither_cached_nor_published(monkeypatch):
    now = datetime(2026, 10, 8, 8, 30, tzinfo=main.KST)
    future = [{
        "trade_date": "20261008", "trade_time": "153000",
        "price": 100_000, "volume": 100,
    }]
    record = {
        "points": future, "trade_date": now.date(),
        "validated_on": now.date(), "max_points": 390,
        "fetched_at": datetime(2026, 10, 7, 23, 30),
    }
    assert main._intraday_points_after_now(future, now) is True
    assert main._intraday_record_is_usable(
        record, limit=30, now=now, latest_daily_date=None
    ) is False
    assert main._intraday_record_is_usable(
        record, limit=30,
        now=datetime(2026, 10, 8, 16, tzinfo=main.KST),
        latest_daily_date=now.date(),
    ) is False
    assert main._save_closed_intraday_snapshot(None, "247540", future, 390, now) is None

    class FutureProvider:
        @staticmethod
        def is_configured():
            return True

        @staticmethod
        def fetch_intraday_chart(*_args, **_kwargs):
            return future

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(main, "datetime", FixedDatetime)
    monkeypatch.setattr(main, "kis_rest_provider", FutureProvider())
    monkeypatch.setattr(
        main, "_korea_intraday_session",
        lambda _now=None: {
            "is_live": False, "market_state": "closed",
            "market_session": "closed", "market_session_label": "장 마감",
            "market_venue": "KRX", "market_division": "J",
        },
    )
    monkeypatch.setattr(
        main, "_load_closed_intraday_snapshot", lambda *_args: (None, None)
    )
    response = TestClient(main.app).get("/stocks/247540/intraday?limit=390")
    assert response.status_code == 200
    assert response.json()["source"] == "unavailable"
    assert response.json()["trade_date"] is None
    assert response.json()["points"] == []


def test_kis_request_retries_transient_http_error(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    statuses = [500, 200]
    sleeps: list[float] = []

    class Response:
        def __init__(self, status_code: int):
            self.status_code = status_code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.HTTPError(f"{self.status_code} Server Error")

        @staticmethod
        def json():
            return {"rt_cd": "0", "output2": []}

    monkeypatch.setattr(provider, "_headers", lambda _tr_id: {})
    monkeypatch.setattr(provider, "_wait_for_request_slot", lambda: None)
    monkeypatch.setattr(
        "app.collectors.briefing.requests.get",
        lambda *_args, **_kwargs: Response(statuses.pop(0)),
    )
    monkeypatch.setattr("app.collectors.briefing.time_module.sleep", sleeps.append)

    payload = provider._get("/chart", "tr", {"code": "068270"})

    assert payload["rt_cd"] == "0"
    assert statuses == []
    assert sleeps == [0.25]


def test_open_intraday_collection_keeps_points_when_later_window_fails(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    calls = 0

    monkeypatch.setattr("app.collectors.briefing.current_market_status", lambda _now=None: "open")

    def fake_get(_path, _tr_id, params):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise requests.HTTPError("500 Server Error")
        cursor = datetime.strptime(params["FID_INPUT_HOUR_1"], "%H%M%S")
        return {
            "output2": [
                {
                    "stck_bsop_date": "20260810",
                    "stck_cntg_hour": (cursor - timedelta(minutes=offset)).strftime("%H%M%S"),
                    "stck_prpr": "180000",
                    "cntg_vol": "100",
                }
                for offset in range(30)
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)

    rows = provider.fetch_intraday_chart(
        "068270",
        max_points=390,
        now=datetime(2026, 8, 10, 10, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert calls == 2
    assert len(rows) == 30
    assert all(row["trade_date"] == "20260810" for row in rows)


def test_nxt_intraday_collection_starts_at_8_and_uses_nx_market(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    calls: list[dict[str, str]] = []

    def fake_get(_path, _tr_id, params):
        calls.append(dict(params))
        return {
            "output2": [
                {
                    "stck_bsop_date": "20260827",
                    "stck_cntg_hour": "080100",
                    "stck_prpr": "268000",
                    "cntg_vol": "100",
                },
                {
                    "stck_bsop_date": "20260827",
                    "stck_cntg_hour": "080000",
                    "stck_prpr": "267500",
                    "cntg_vol": "80",
                },
            ]
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    rows = provider.fetch_intraday_chart(
        "005930",
        max_points=30,
        market_division="NX",
        now=datetime(2026, 8, 27, 8, 10, tzinfo=main.KST),
    )

    assert calls[0]["FID_COND_MRKT_DIV_CODE"] == "NX"
    assert calls[0]["FID_INPUT_HOUR_1"] == "081000"
    assert [row["trade_time"] for row in rows] == ["080000", "080100"]


def test_historical_intraday_chart_uses_dated_krx_endpoint_and_paginates(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    calls: list[tuple[str, str, dict[str, str]]] = []

    def fake_get(path, tr_id, params):
        calls.append((path, tr_id, dict(params)))
        times = (
            ["090300", "090200"]
            if params["FID_INPUT_HOUR_1"] == "153000"
            else ["090100", "090000"]
        )
        return {
            "output2": [
                {
                    "stck_bsop_date": "20261007",
                    "stck_cntg_hour": minute,
                    "stck_prpr": "101",
                    "stck_oprc": "100",
                    "stck_hgpr": "102",
                    "stck_lwpr": "99",
                    "cntg_vol": "10",
                }
                for minute in times
            ] + [{"stck_bsop_date": "20261006", "stck_cntg_hour": "090000"}]
        }

    monkeypatch.setattr(provider, "_get", fake_get)
    rows = provider.fetch_historical_intraday_chart("005930", date(2026, 10, 7))

    assert [row["trade_time"] for row in rows] == [
        "090000", "090100", "090200", "090300"
    ]
    assert len(calls) == 2
    assert all(call[0].endswith("/inquire-time-dailychartprice") for call in calls)
    assert all(call[1] == "FHKST03010230" for call in calls)
    assert all(call[2]["FID_INPUT_DATE_1"] == "20261007" for call in calls)
    assert all(call[2]["FID_COND_MRKT_DIV_CODE"] == "J" for call in calls)


def test_krx_closing_auction_trade_requires_live_window_and_consistent_prints(monkeypatch):
    provider = KisRestBriefingProvider(Settings(kis_app_key="key", kis_app_secret="secret"))
    calls = []
    rows = [
        {"stck_cntg_hour": "153000", "stck_prpr": "103000", "cntg_vol": "100"},
        {"stck_cntg_hour": "153017", "stck_prpr": "103000", "cntg_vol": "50"},
        {"stck_cntg_hour": "151900", "stck_prpr": "102000", "cntg_vol": "9"},
    ]

    def fake_get(path, tr_id, params):
        calls.append((path, tr_id, params))
        return {"output": rows}

    monkeypatch.setattr(provider, "_get", fake_get)
    now = datetime(2026, 10, 8, 15, 34, tzinfo=main.KST)
    assert provider.fetch_krx_closing_auction_trade("005930", now=now) == {
        "trade_date": "20261008", "trade_time": "153000", "open": 103000,
        "high": 103000, "low": 103000, "price": 103000,
        "volume": 150, "trading_value": 0,
    }
    assert calls[0][0].endswith("/inquire-ccnl")
    assert calls[0][1] == "FHKST01010300"
    assert calls[0][2]["FID_COND_MRKT_DIV_CODE"] == "J"
    assert provider.fetch_krx_closing_auction_trade(
        "005930", now=now.replace(hour=20)
    ) is None
    assert len(calls) == 1
    rows[1]["stck_prpr"] = "104000"
    assert provider.fetch_krx_closing_auction_trade("005930", now=now) is None
    rows[1]["stck_prpr"] = "103000"
    rows[0]["cntg_vol"] = "0"
    rows[1]["cntg_vol"] = "0"
    assert provider.fetch_krx_closing_auction_trade("005930", now=now) is None


def test_intraday_warmup_does_not_run_during_regular_market(monkeypatch):
    monkeypatch.setattr(main, "_korea_intraday_session", lambda _now=None: {"is_live": True})
    monkeypatch.setattr(
        main.kis_rest_provider,
        "is_configured",
        lambda: (_ for _ in ()).throw(AssertionError("provider should not be checked")),
    )

    assert main._warm_closed_intraday_snapshots(datetime(2026, 7, 27, 10, 0, tzinfo=main.KST)) == 0
