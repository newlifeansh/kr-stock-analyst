from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import QuantSignalIntradayPathSnapshot, QuantSignalObservedEntry
from app.services import observed_entry, quant_signals as qs
from app.services.confirmed_path_repair import corroborate_confirmed_placeholder_path
from app.services.regular_session_prices import (
    UnverifiedRegularSessionPrice,
    regular_session_evidence,
    store_regular_session_evidence,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _fixture(code):
    data = json.loads(Path("tests/fixtures/kr_2026-11_confirmed_placeholder.json").read_text())
    proof = json.loads(Path("app/evidence/kr_2026-11_confirmed_placeholder_proof.json").read_text())
    return data[code], proof[code]


def _seed(db, code, fixture):
    day = date.fromisoformat(fixture["trade_date"])
    observed = datetime(2026, 11, 12, 9, 30, tzinfo=qs.KST)
    source = fixture["source"]
    evidence = regular_session_evidence(
        code, day, source["rows"], observed_at=observed,
        preopen_baseline=source.get("preopen_baseline"),
        closing_auction_evidence=source.get("closing_auction_evidence"),
        minute_coverage_evidence=source.get("minute_coverage_evidence"),
        bucket_open_proof=source.get("bucket_open_proof"),
    )
    assert evidence["state"] in {"ready", "bounded"}, evidence["reason"]
    store_regular_session_evidence(db, evidence, observed_at=observed)
    db.add(QuantSignalIntradayPathSnapshot(
        stock_code=code, trade_date=day, strategy_version=qs.STRATEGY_VERSION,
        source="kis_rest", payload=json.dumps(fixture["prior_path"]),
        is_final=False, observed_at=datetime(2026, 11, 5),
    ))
    db.add(QuantSignalObservedEntry(
        stock_code=code, trade_date=day,
        policy_version=observed_entry.POLICY_VERSION,
        status="confirmed", payload=json.dumps({
            "decision_minute_at": fixture["watcher"]["decision_minute_at"],
        }), updated_at=datetime(2026, 11, 5),
    ))
    db.commit()
    return day, observed


@pytest.mark.parametrize("code", ["000810", "138040"])
def test_confirmed_entry_path_seals_only_after_independent_placeholder_proof(db, code):
    fixture, proof = _fixture(code)
    day, observed = _seed(db, code, fixture)
    dry = corroborate_confirmed_placeholder_path(
        db, code, day, observed_at=observed, source_proof=proof,
    )
    assert dry["state"] == "verified" and dry["persisted"] is False
    assert db.get(QuantSignalIntradayPathSnapshot, (code, day)).is_final is False
    report = corroborate_confirmed_placeholder_path(
        db, code, day, observed_at=observed, source_proof=proof, persist=True,
    )
    assert report["persisted"] is True
    assert report["notifications_sent"] == 0
    assert report["signal_publication"] is False
    assert db.get(QuantSignalIntradayPathSnapshot, (code, day)).is_final is True
    assert db.get(QuantSignalObservedEntry, (code, day)).status == "confirmed"


@pytest.mark.parametrize("mutate", ["naver_close", "naver_volume", "yahoo_low", "decision_time"])
def test_confirmed_placeholder_rejects_unproven_or_pre_entry_revision(db, mutate):
    code = "138040"
    fixture, proof = _fixture(code)
    day, observed = _seed(db, code, fixture)
    proof = deepcopy(proof)
    if mutate == "naver_close":
        proof["naver"]["rows"][100]["close"] += 1
    elif mutate == "naver_volume":
        proof["naver"]["rows"][100]["cumulative_volume"] += 1
    elif mutate == "yahoo_low":
        proof["yahoo"]["low"] -= 100
    else:
        watcher = db.get(QuantSignalObservedEntry, (code, day))
        watcher.payload = json.dumps({"decision_minute_at": "2026-11-05T11:45:00+09:00"})
        db.commit()
    with pytest.raises((UnverifiedRegularSessionPrice, qs.UnverifiedIntradayPathError)):
        corroborate_confirmed_placeholder_path(
            db, code, day, observed_at=observed, source_proof=proof, persist=True,
        )
    assert db.get(QuantSignalIntradayPathSnapshot, (code, day)).is_final is False
