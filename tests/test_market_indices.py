from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import MacroObservation
from app.services.market_indices import (
    build_market_indices,
    empty_market_indices,
    korean_market_session,
    merge_live_market_indices,
)


def test_market_indices_use_latest_real_observations_and_history():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        session.add_all(
            [
                MacroObservation(
                    source="yahoo",
                    series_code="^KS11",
                    item_code="close",
                    period="2026-07-21",
                    value=Decimal("7000.00"),
                    unit="index",
                    name="KOSPI Index",
                ),
                MacroObservation(
                    source="yahoo",
                    series_code="^KS11",
                    item_code="close",
                    period="2026-07-22",
                    value=Decimal("7050.00"),
                    unit="index",
                    name="KOSPI Index",
                ),
                MacroObservation(
                    source="yahoo",
                    series_code="^KS11",
                    item_code="close",
                    period="2026-07-23",
                    value=Decimal("7040.00"),
                    unit="index",
                    name="KOSPI Index",
                ),
                MacroObservation(
                    source="yahoo",
                    series_code="^KQ11",
                    item_code="close",
                    period="2026-07-22",
                    value=Decimal("790.00"),
                    unit="index",
                    name="KOSDAQ Index",
                ),
                MacroObservation(
                    source="yahoo",
                    series_code="^KQ11",
                    item_code="close",
                    period="2026-07-23",
                    value=Decimal("780.00"),
                    unit="index",
                    name="KOSDAQ Index",
                ),
            ]
        )
        session.commit()

        payload = build_market_indices(session, limit=30)

        assert [item["code"] for item in payload["items"]] == ["KOSPI", "KOSDAQ"]
        kospi = payload["items"][0]
        assert kospi["as_of"] == "2026-07-23"
        assert kospi["current"] == 7040.0
        assert kospi["previous_close"] == 7050.0
        assert kospi["change"] == -10.0
        assert kospi["change_rate"] == pytest.approx(-0.14184397)
        assert [point["date"] for point in kospi["points"]] == [
            "2026-07-21",
            "2026-07-22",
            "2026-07-23",
        ]
    finally:
        session.close()


def test_live_market_indices_replace_current_values_and_append_basis_point():
    stored = {
        "items": [
            {
                "code": "KOSPI",
                "source": "yahoo",
                "as_of": "2026-07-23",
                "current": 7049.47,
                "previous_close": 6747.95,
                "change": 301.52,
                "change_rate": 4.47,
                "points": [
                    {"date": "2026-07-22", "value": 6747.95},
                    {"date": "2026-07-23", "value": 7049.47},
                ],
            }
        ]
    }

    payload = merge_live_market_indices(
        stored,
        [
            {
                "code": "KOSPI",
                "source": "kis",
                "current": Decimal("6603.61"),
                "previous_close": Decimal("6690.62"),
                "change": Decimal("-87.01"),
                "change_rate": Decimal("-1.30"),
            }
        ],
        as_of="2026-07-27",
        now=datetime(2026, 7, 27, 14, 5, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    kospi = payload["items"][0]
    assert kospi["source"] == "kis"
    assert kospi["as_of"] == "2026-07-27"
    assert kospi["current"] == 6603.61
    assert kospi["previous_close"] == 6690.62
    assert kospi["change"] == -87.01
    assert kospi["change_rate"] == -1.3
    assert kospi["is_live"] is True
    assert kospi["is_realtime"] is True
    assert kospi["market_session"] == "open"
    assert kospi["updated_at"] == "2026-07-27T14:05:00+09:00"
    assert kospi["points"][-1] == {"date": "2026-07-27", "value": 6603.61}
    assert payload["source"] == "kis"
    assert payload["updated_at"] == "2026-07-27T14:05:00+09:00"


def test_empty_market_indices_preserves_live_merge_shape():
    payload = empty_market_indices()

    assert [item["code"] for item in payload["items"]] == ["KOSPI", "KOSDAQ"]
    assert all(item["current"] is None for item in payload["items"])
    assert all(item["points"] == [] for item in payload["items"])


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (6, 59, "closed"),
        (7, 0, "preopen"),
        (8, 59, "preopen"),
        (9, 0, "open"),
        (15, 30, "closed"),
    ],
)
def test_korean_market_session_uses_two_hour_preopen_window(hour, minute, expected):
    observed_at = datetime(2026, 7, 27, hour, minute, tzinfo=ZoneInfo("Asia/Seoul"))

    assert korean_market_session(observed_at) == expected
