from copy import deepcopy
from datetime import date
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import DailyPrice, QuantSignalTransitionBaseline
from app.services.legacy_warmup_repair import restore_legacy_warmup
from app.services.regular_session_prices import UnverifiedRegularSessionPrice
from app.services.regular_signal_transition import frozen_legacy_price_rows


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _seed(db, code):
    old = json.loads(Path("tests/fixtures/kr_2026-10_warmup_existing.json").read_text())
    for row in old[code]:
        db.add(DailyPrice(
            code=code, trade_date=date.fromisoformat(row["date"]),
            open=row["open"], high=row["high"], low=row["low"],
            close=row["close"], volume=row["volume"],
            trading_value=row["close"] * row["volume"],
        ))
    db.commit()
    return json.loads(Path("app/evidence/kr_2026-10-12_warmup_history.json").read_text())[code]


@pytest.mark.parametrize("code", ["0043B0", "423160", "036460", "273130"])
def test_missing_warmup_is_frozen_without_rewriting_display_history(db, code):
    proof = _seed(db, code)
    before = [(row.trade_date, row.close, row.volume) for row in db.query(DailyPrice).all()]
    dry = restore_legacy_warmup(db, code, proof)
    assert dry["state"] == "verified" and dry["persisted"] is False
    assert db.query(QuantSignalTransitionBaseline).count() == 0
    report = restore_legacy_warmup(db, code, proof, persist=True)
    assert report["warmup_rows"] == 150 and report["existing_matching_rows"] >= 20
    assert report["history_overwrite"] is False and report["notifications_sent"] == 0
    assert [(row.trade_date, row.close, row.volume) for row in db.query(DailyPrice).all()] == before
    assert len(frozen_legacy_price_rows(db, code, list(db.query(DailyPrice).all()))) == 150


@pytest.mark.parametrize("mutation", ["source", "symbol", "close", "overlap"])
def test_warmup_repair_rejects_unverified_price_history(db, mutation):
    code = "423160"
    proof = deepcopy(_seed(db, code))
    if mutation == "source":
        proof["source"] = "unknown"
    elif mutation == "symbol":
        proof["rows"][10]["code"] = "005930"
    elif mutation == "close":
        proof["rows"][-1]["close"] += 5
    else:
        proof["rows"][110]["close"] += 5
        # A pre-September overlap would fail the 20-day check only if more
        # rows are changed; this assertion tests the hard boundary directly.
        for row in proof["rows"]:
            if row["trade_date"] <= "2026-09-11":
                row["open"] += 1
    with pytest.raises(UnverifiedRegularSessionPrice):
        restore_legacy_warmup(db, code, proof, persist=True)
    assert db.query(QuantSignalTransitionBaseline).count() == 0
