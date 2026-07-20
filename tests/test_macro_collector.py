from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

from app.collectors import macro
from app.db import Base
from app.models import IngestionRun, MacroObservation


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "chart": {
                "result": [
                    {
                        "timestamp": [1782259200, 1782345600],
                        "indicators": {"quote": [{"close": [1400.5, None]}]},
                    }
                ]
            }
        }


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_fetch_yahoo_macro_rows_skips_empty_close(monkeypatch):
    monkeypatch.setattr(macro.requests, "get", lambda *args, **kwargs: _Response())

    rows = macro.fetch_yahoo_macro_rows("USDKRW=X", "USD/KRW", "KRW", range_="5d")

    assert len(rows) == 1
    assert rows[0]["source"] == "yahoo"
    assert rows[0]["series_code"] == "USDKRW=X"
    assert rows[0]["item_code"] == "close"
    assert rows[0]["value"] == 1400.5


def test_collect_yahoo_macro_observations_upserts_rows(monkeypatch):
    monkeypatch.setattr(
        macro,
        "fetch_yahoo_macro_rows",
        lambda symbol, name, unit, range_: [
            {
                "source": "yahoo",
                "series_code": symbol,
                "item_code": "close",
                "period": "2026-06-24",
                "value": 1,
                "unit": unit,
                "name": name,
            }
        ],
    )

    with _session() as db:
        count = macro.collect_yahoo_macro_observations(
            db,
            series=[{"symbol": "USDKRW=X", "name": "USD/KRW", "unit": "KRW"}],
        )

        assert count == 1
        assert db.query(func.count(MacroObservation.id)).scalar() == 1
        assert db.query(IngestionRun).one().status == "success"
