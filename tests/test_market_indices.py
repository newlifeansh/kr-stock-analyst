from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import MacroObservation
from app.services.market_indices import build_market_indices


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
