from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import MacroObservation
from app.services import global_market_assets
from app.services.global_market_assets import (
    build_stored_global_market_assets,
    merge_global_market_assets,
)


def test_stored_global_market_assets_preserve_definition_order_and_history():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add_all(
            [
                MacroObservation(
                    source="yahoo",
                    series_code="^IXIC",
                    item_code="close",
                    period="2026-07-24",
                    value=Decimal("25000.00"),
                    unit="index",
                    name="NASDAQ Composite",
                ),
                MacroObservation(
                    source="yahoo",
                    series_code="^IXIC",
                    item_code="close",
                    period="2026-07-27",
                    value=Decimal("24900.00"),
                    unit="index",
                    name="NASDAQ Composite",
                ),
            ]
        )
        session.commit()

        payload = build_stored_global_market_assets(session, limit=30)

        assert [item["code"] for item in payload["items"]] == [
            "SP500",
            "NASDAQ",
            "SOX",
            "DOW",
            "GOLD",
            "OIL",
        ]
        nasdaq = next(item for item in payload["items"] if item["code"] == "NASDAQ")
        assert nasdaq["current"] == 24900.0
        assert nasdaq["previous_close"] == 25000.0
        assert nasdaq["change"] == -100.0
        assert nasdaq["change_rate"] == pytest.approx(-0.4)
        assert nasdaq["points"][-1] == {"date": "2026-07-27", "value": 24900.0}
    finally:
        session.close()


def test_live_global_asset_calculates_session_and_intraday_points(monkeypatch):
    monkeypatch.setattr(
        global_market_assets,
        "_fetch_yahoo_chart",
        lambda _symbol: {
            "meta": {
                "regularMarketPrice": 7420.0,
                "previousClose": 7400.0,
                "regularMarketTime": 1785240000,
                "currentTradingPeriod": {
                    "regular": {"start": 1785230000, "end": 1785250000}
                },
            },
            "timestamp": [1785231000, 1785240000],
            "indicators": {"quote": [{"close": [7410.0, 7420.0]}]},
        },
    )

    item = global_market_assets._live_asset(
        ("SP500", "S&P 500", "^GSPC", "index"),
        datetime.fromtimestamp(1785240000, tz=timezone.utc),
    )

    assert item["current"] == 7420.0
    assert item["change"] == 20.0
    assert item["change_rate"] == pytest.approx(20 / 7400 * 100)
    assert item["market_session"] == "open"
    assert item["is_realtime"] is True
    assert [point["value"] for point in item["points"]] == [7410.0, 7420.0]


def test_live_global_index_marks_only_two_hours_before_regular_open_as_preopen(monkeypatch):
    regular_start = 1_785_230_000
    monkeypatch.setattr(
        global_market_assets,
        "_fetch_yahoo_chart",
        lambda _symbol: {
            "meta": {
                "regularMarketPrice": 7728.2,
                "previousClose": 7700.0,
                "regularMarketTime": regular_start - 16 * 60 * 60,
                "currentTradingPeriod": {
                    "regular": {"start": regular_start, "end": regular_start + 6 * 60 * 60 + 30 * 60}
                },
            },
            "timestamp": [],
            "indicators": {"quote": [{"close": []}]},
        },
    )

    preopen = global_market_assets._live_asset(
        ("SP500", "S&P 500", "^GSPC", "index"),
        datetime.fromtimestamp(regular_start - 60 * 60, tz=timezone.utc),
    )
    too_early = global_market_assets._live_asset(
        ("SP500", "S&P 500", "^GSPC", "index"),
        datetime.fromtimestamp(regular_start - 2 * 60 * 60 - 1, tz=timezone.utc),
    )

    assert preopen["current"] == 7728.2
    assert preopen["market_session"] == "preopen"
    assert preopen["is_realtime"] is False
    assert too_early["market_session"] == "closed"


def test_merge_global_market_assets_replaces_only_available_live_items():
    stored = {
        "items": [
            {"code": "NASDAQ", "current": 24900.0, "updated_at": None},
            {"code": "SP500", "current": 7400.0, "updated_at": None},
        ]
    }
    live = [
        {
            "code": "NASDAQ",
            "current": 24932.08,
            "updated_at": "2026-07-28T00:00+00:00",
        }
    ]

    payload = merge_global_market_assets(stored, live)

    assert payload["items"][0]["current"] == 24932.08
    assert payload["items"][1]["current"] == 7400.0
    assert payload["updated_at"] == "2026-07-28T00:00+00:00"


def test_merge_global_market_assets_marks_stored_index_preopen_when_live_feed_is_missing():
    stored = {
        "items": [
            {
                "code": "SP500",
                "unit": "index",
                "current": 7728.2,
                "market_session": "closed",
                "is_realtime": False,
            },
            {
                "code": "GOLD",
                "unit": "USD",
                "current": 3400.0,
                "market_session": "closed",
                "is_realtime": False,
            },
        ]
    }

    payload = merge_global_market_assets(
        stored,
        [],
        now=datetime(2026, 8, 12, 8, 30, tzinfo=global_market_assets.NEW_YORK_TZ),
    )

    assert payload["items"][0]["market_session"] == "preopen"
    assert payload["items"][0]["current"] == 7728.2
    assert payload["items"][1]["market_session"] == "closed"
