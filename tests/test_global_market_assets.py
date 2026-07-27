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

        assert [item["code"] for item in payload["items"]] == ["NASDAQ", "SP500", "GOLD", "OIL"]
        nasdaq = payload["items"][0]
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
