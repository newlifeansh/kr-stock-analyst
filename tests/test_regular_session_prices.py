from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.db import Base
from app.models import DailyPrice, SignalSessionPrice
from app.services import regular_session_prices as rsp

DAY = date(2026, 10, 12)
OBSERVED = datetime(2026, 10, 12, 21, tzinfo=rsp.KST)


def minute_rows():
    rows = []
    instant = datetime(2026, 10, 12, 8, 59)
    cumulative = 50_000  # deliberately non-zero pre-open turnover
    while instant.time() <= datetime(2026, 10, 12, 15, 30).time():
        hhmmss = instant.strftime("%H%M%S")
        volume = 0 if "152000" <= hhmmss < "153000" or hhmmss < "090000" else 10
        cumulative += 100 * volume
        rows.append({"trade_date": "20261012", "trade_time": hhmmss, "open": 100, "high": 100, "low": 100, "price": 100, "volume": volume, "trading_value": cumulative})
        instant += timedelta(minutes=1)
    return rows


def evidence(rows=None):
    return rsp.regular_session_evidence("005930", DAY, minute_rows() if rows is None else rows, observed_at=OBSERVED)


@pytest.fixture(scope="module")
def toss_dated_fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "kr_regular_toss_dated_202610.json").read_text())


@pytest.fixture(scope="module")
def auction_reconciliation_fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "kr_regular_auction_reconciled_202610.json").read_text())


@pytest.fixture(scope="module")
def auction_postmarket_fixture():
    return json.loads((Path(__file__).parent / "fixtures" / "kr_regular_auction_postmarket_202610.json").read_text())


def _toss_dated_evidence(case):
    proof = case["toss_dated_minute_proof"]
    return rsp.regular_session_evidence(
        proof["code"], date.fromisoformat(proof["date"]), case["raw_rows"],
        observed_at=datetime(2026, 11, 13, 2, tzinfo=rsp.KST),
        preopen_baseline=case["preopen_baseline"], toss_dated_minute_proof=proof,
    )


def test_toss_dated_complete_krx_minute_path_recovers_halts_and_late_open(toss_dated_fixture, db):
    for key, opening, closing in (
        ("001040_2026-10-14", "090000", 125400),
        ("273130_2026-10-22", "090200", 111770),
        ("273130_2026-10-21", "090000", 111730),
    ):
        case = toss_dated_fixture[key]
        without_proof = rsp.regular_session_evidence(
            key[:6], date.fromisoformat(key[7:]), case["raw_rows"],
            observed_at=datetime(2026, 11, 13, 2, tzinfo=rsp.KST),
            preopen_baseline=case["preopen_baseline"],
        )
        assert without_proof["state"] == "unverified"
        result = _toss_dated_evidence(case)
        assert result["state"] == "bounded"
        assert result["coverage_basis"] == rsp.TOSS_DATED_MINUTE_PATH_BASIS
        assert result["regular_rows"][0]["trade_time"] == opening
        assert result["prices"]["close"] == closing
        if key == "273130_2026-10-21":
            assert result["regular_rows"][-1]["trade_time"] == "151900"
        assert result["prices"]["volume"] == sum(row["volume"] for row in result["regular_rows"])
        record = rsp.store_regular_session_evidence(db, result, observed_at=datetime(2026, 11, 13, 2, tzinfo=rsp.KST))
        db.commit()
        assert record.evidence_hash
        assert rsp.load_regular_session_evidence(db, key[:6], date.fromisoformat(key[7:]), allow_bounded=True)["prices"] == result["prices"]


@pytest.mark.parametrize("mutation", ["date", "venue", "cursor", "gap", "hidden_trade", "minute_price", "auction_volume", "after_close_trade"])
def test_toss_dated_proof_fails_closed_on_identity_path_and_auction_conflicts(toss_dated_fixture, mutation):
    case = deepcopy(toss_dated_fixture["001040_2026-10-14"])
    proof = case["toss_dated_minute_proof"]
    candles = proof["candles"]
    if mutation == "date": proof["date"] = "2026-10-15"
    elif mutation == "venue": proof["exchange"] = "nxt"
    elif mutation == "cursor": proof["pages"][1]["requested_from"] = "2026-10-14T12:12:00+09:00"
    elif mutation == "gap": candles.pop(150)
    elif mutation == "hidden_trade": next(c for c in candles if c["dt"].endswith("09:22:00+09:00"))["volume"] = 1
    elif mutation == "minute_price": next(c for c in candles if c["dt"].endswith("09:01:00+09:00"))["close"] += 100
    elif mutation == "auction_volume": next(c for c in candles if c["dt"].endswith("15:30:00+09:00"))["volume"] += 1
    elif mutation == "after_close_trade": next(c for c in candles if c["dt"].endswith("15:31:00+09:00"))["volume"] = 1
    assert _toss_dated_evidence(case)["state"] == "unverified"


def test_toss_dated_absent_auction_requires_both_sources_to_show_no_trade(toss_dated_fixture):
    case = deepcopy(toss_dated_fixture["273130_2026-10-21"])
    assert _toss_dated_evidence(case)["state"] == "bounded"
    next(c for c in case["toss_dated_minute_proof"]["candles"] if c["dt"].endswith("15:30:00+09:00"))["volume"] = 1
    assert _toss_dated_evidence(case)["state"] == "unverified"
    case = deepcopy(toss_dated_fixture["273130_2026-10-21"])
    prior = case["raw_rows"][-1]
    case["raw_rows"].append({**prior, "trade_time": "153000", "volume": 0, "trading_value": prior["trading_value"] + 1})
    assert _toss_dated_evidence(case)["state"] == "unverified"


def test_dated_auction_undercount_requires_complete_no_postmarket_reconciliation(auction_reconciliation_fixture, db):
    for key, state, volume in (
        ("0043B0_2026-10-13", "ready", 168055),
        ("395160_2026-10-15", "bounded", 7177323),
    ):
        case = auction_reconciliation_fixture[key]
        original = case["raw_rows"][-1]
        assert original["trade_time"] == "153000"
        without_proof = deepcopy(case)
        without_proof["toss_dated_minute_proof"].pop("auction_reconciliation")
        assert _toss_dated_evidence(without_proof)["state"] == "unverified"
        result = _toss_dated_evidence(case)
        assert result["state"] == state
        assert result["coverage_basis"] == rsp.TOSS_AUCTION_RECONCILIATION_BASIS
        assert result["prices"]["volume"] == volume
        assert result["raw_rows"][-1]["volume"] == original["volume"]
        assert result["regular_rows"][-1]["volume"] > original["volume"]
        record = rsp.store_regular_session_evidence(db, result, observed_at=datetime(2026, 11, 13, 2, tzinfo=rsp.KST))
        db.commit()
        assert record.evidence_hash
        assert rsp.load_regular_session_evidence(db, key[:6], date.fromisoformat(key[7:]), allow_bounded=True)["prices"] == result["prices"]


@pytest.mark.parametrize("mutation", [
    "daily_market", "daily_date", "daily_volume", "daily_turnover", "late_request_market",
    "late_first_time", "late_auction_volume", "toss_late_venue", "toss_late_first_time",
    "toss_late_next", "corrected_auction_volume",
])
def test_dated_auction_reconciliation_rejects_conflicting_or_later_trades(auction_reconciliation_fixture, mutation):
    case = deepcopy(auction_reconciliation_fixture["0043B0_2026-10-13"])
    chart = case["toss_dated_minute_proof"]
    proof = chart["auction_reconciliation"]
    daily = proof["kis_daily"]
    late = proof["kis_late"]
    toss_late = proof["toss_late"]
    if mutation == "daily_market": daily["market"] = "UN"
    elif mutation == "daily_date": daily["row"]["stck_bsop_date"] = "20261014"
    elif mutation == "daily_volume": daily["row"]["acml_vol"] = str(int(daily["row"]["acml_vol"]) + 1)
    elif mutation == "daily_turnover": daily["row"]["acml_tr_pbmn"] = str(int(daily["row"]["acml_tr_pbmn"]) + 1)
    elif mutation == "late_request_market": late["request"]["FID_COND_MRKT_DIV_CODE"] = "UN"
    elif mutation == "late_first_time": late["output2"][0]["stck_cntg_hour"] = "160000"
    elif mutation == "late_auction_volume": late["output2"][0]["cntg_vol"] = str(int(late["output2"][0]["cntg_vol"]) + 1)
    elif mutation == "toss_late_venue": toss_late["exchange"] = "nxt"
    elif mutation == "toss_late_first_time": toss_late["candles"][0]["dt"] = "2026-10-13T16:00:00+09:00"
    elif mutation == "toss_late_next": toss_late["next"] = "2026-10-13T12:09:00+09:00"
    elif mutation == "corrected_auction_volume": next(c for c in chart["candles"] if c["dt"].endswith("15:30:00+09:00"))["volume"] += 1
    assert _toss_dated_evidence(case)["state"] == "unverified"


def test_dated_auction_reconciliation_separates_all_verified_postmarket_trades(auction_postmarket_fixture, db):
    assert len(auction_postmarket_fixture) == 13
    for key, case in auction_postmarket_fixture.items():
        without_proof = deepcopy(case)
        without_proof["toss_dated_minute_proof"].pop("auction_reconciliation")
        assert _toss_dated_evidence(without_proof)["state"] == "unverified"
        result = _toss_dated_evidence(case)
        assert result["state"] == "bounded", (key, result["reason"])
        assert result["coverage_basis"] == rsp.TOSS_AUCTION_RECONCILIATION_BASIS
        assert result["regular_rows"][-1]["volume"] > case["raw_rows"][-1]["volume"]
        assert result["raw_rows"] == case["raw_rows"]
        stored = rsp.store_regular_session_evidence(
            db, result, observed_at=datetime(2026, 11, 13, 2, tzinfo=rsp.KST),
        )
        db.commit()
        assert stored.evidence_hash
        assert rsp.load_regular_session_evidence(db, key[:6], date.fromisoformat(key[7:]), allow_bounded=True)["prices"] == result["prices"]


@pytest.mark.parametrize("mutation", [
    "daily_volume", "daily_cash", "late_cursor", "late_gap", "late_close",
    "late_volume", "late_cash", "toss_gap", "toss_venue", "toss_volume",
    "toss_price", "toss_auction", "extra_toss_trade",
])
def test_dated_auction_postmarket_reconciliation_fails_closed(auction_postmarket_fixture, mutation):
    case = deepcopy(auction_postmarket_fixture["008930_2026-10-13"])
    proof = case["toss_dated_minute_proof"]["auction_reconciliation"]
    daily = proof["kis_daily"]["row"]
    late = proof["kis_late_pages"]
    toss = proof["toss_postmarket"]
    if mutation == "daily_volume": daily["acml_vol"] = str(int(daily["acml_vol"]) + 1)
    elif mutation == "daily_cash": daily["acml_tr_pbmn"] = str(int(daily["acml_tr_pbmn"]) + 1)
    elif mutation == "late_cursor": late[1]["request"]["FID_INPUT_HOUR_1"] = "170000"
    elif mutation == "late_gap": late[0]["output2"].pop(20)
    elif mutation == "late_close": next(r for r in late[1]["output2"] if r["stck_cntg_hour"] == "153000")["cntg_vol"] = "1"
    elif mutation == "late_volume": late[0]["output2"][0]["cntg_vol"] = "1"
    elif mutation == "late_cash": late[0]["output2"][0]["acml_tr_pbmn"] = "1"
    elif mutation == "toss_gap": toss["candles"].pop(20)
    elif mutation == "toss_venue": toss["exchange"] = "nxt"
    elif mutation == "toss_volume": toss["candles"][20]["volume"] += 1
    elif mutation == "toss_price": toss["candles"][20]["close"] += 50
    elif mutation == "toss_auction": toss["candles"][-1]["volume"] += 1
    elif mutation == "extra_toss_trade": next(c for c in toss["candles"] if c["dt"].endswith("15:45:00+09:00"))["volume"] = 1
    assert _toss_dated_evidence(case)["state"] == "unverified"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_regular_session_excludes_after_market_and_subtracts_preopen_turnover():
    rows = minute_rows()
    rows.append({**rows[-1], "trade_time": "160000", "price": 90, "low": 90, "volume": 500, "trading_value": 999_999_999})
    result = evidence(rows)
    assert result["state"] == "ready"
    assert result["prices"] == {"open": 100, "high": 100, "low": 100, "close": 100, "volume": 3810, "trading_value": 381000}
    assert len(result["regular_rows"]) == 381
    assert result["raw_rows"][-1]["trade_time"] == "160000"


def test_regular_session_rejects_missing_corrupt_and_unreconciled_evidence():
    corruptions = []
    rows = minute_rows()
    corruptions.append(rows[:-1])
    corruptions.append(rows[:50] + rows[51:])
    corruptions.append(rows[1:])  # no observed turnover baseline
    corruptions.append(rows + [rows[-1]])
    for field, value in (("trade_date", "20261013"), ("volume", -1), ("price", float("nan")), ("price", float("inf")), ("price", True), ("low", 101), ("trading_value", 123), ("volume", 0)):
        changed = deepcopy(rows)
        changed[50][field] = value
        corruptions.append(changed)
    for changed in corruptions:
        assert evidence(changed)["state"] == "unverified"
    assert "baseline" in evidence(rows[1:])["reason"]


def test_regular_session_requires_completed_aware_source_timestamp():
    for stamp in (datetime(2026, 10, 12, 16), datetime(2026, 10, 12, 15, 30, tzinfo=rsp.KST)):
        with pytest.raises(ValueError):
            rsp.regular_session_evidence("005930", DAY, minute_rows(), observed_at=stamp)


def test_regular_evidence_is_append_only_idempotent_and_preserves_display_price(db):
    daily = DailyPrice(code="005930", trade_date=DAY, open=100, high=120, low=90, close=110, volume=5000, trading_value=550000)
    db.add(daily)
    db.commit()
    first = rsp.store_regular_session_evidence(db, evidence(), observed_at=OBSERVED)
    db.commit()
    again = rsp.store_regular_session_evidence(db, evidence(), observed_at=OBSERVED + timedelta(hours=1))
    assert first.id == again.id
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 1
    payload = json.loads(first.payload)
    assert payload["legacy_display_price_at_capture"]["close"] == 110
    detached = rsp.regular_signal_price_rows(db, [daily], completed_through=DAY)
    assert detached[0].close == 100
    assert daily.close == 110
    assert detached[0] not in db
    daily.close = 115
    db.commit()
    assert json.loads(first.payload)["legacy_display_price_at_capture"]["close"] == 110


def test_regular_loader_rejects_missing_tampered_or_conflicting_ready_records(db):
    with pytest.raises(rsp.UnverifiedRegularSessionPrice):
        rsp.load_regular_session_evidence(db, "005930", DAY)
    record = rsp.store_regular_session_evidence(db, evidence(), observed_at=OBSERVED)
    db.commit()
    original = record.payload
    altered = json.loads(original)
    altered["evidence"]["prices"]["close"] = 120
    record.payload = json.dumps(altered)
    db.commit()
    with pytest.raises(rsp.UnverifiedRegularSessionPrice, match="무결성"):
        rsp.load_regular_session_evidence(db, "005930", DAY)
    record.payload = original
    db.commit()
    changed = minute_rows()
    changed[-1].update(open=101, high=101, low=101, price=101, trading_value=changed[-1]["trading_value"] + 10)
    alternate = rsp.store_regular_session_evidence(db, evidence(changed), observed_at=OBSERVED)
    db.commit()
    assert alternate.id != record.id
    with pytest.raises(rsp.UnverifiedRegularSessionPrice, match="충돌"):
        rsp.load_regular_session_evidence(db, "005930", DAY)


def test_regular_loader_reuses_only_identical_validated_content(db, monkeypatch):
    record = rsp.store_regular_session_evidence(db, evidence(), observed_at=OBSERVED)
    db.commit()
    with rsp._validated_evidence_cache_lock:
        rsp._validated_evidence_cache.clear()
        rsp._validated_evidence_cache_bytes = 0
    original_payload = record.payload
    original_hash = record.evidence_hash
    recomputations = 0
    original_validator = rsp.regular_session_evidence

    def count_validation(*args, **kwargs):
        nonlocal recomputations
        recomputations += 1
        return original_validator(*args, **kwargs)

    monkeypatch.setattr(rsp, "regular_session_evidence", count_validation)
    first = rsp.load_regular_session_evidence(db, "005930", DAY)
    first["prices"]["close"] = -1
    second = rsp.load_regular_session_evidence(db, "005930", DAY)
    assert second["prices"]["close"] == 100
    assert recomputations == 1

    altered = json.loads(original_payload)
    altered["evidence"]["prices"]["close"] = 120
    record.payload = json.dumps(altered)
    db.commit()
    with pytest.raises(rsp.UnverifiedRegularSessionPrice, match="무결성"):
        rsp.load_regular_session_evidence(db, "005930", DAY)
    assert recomputations == 2

    record.payload = original_payload
    record.evidence_hash = "0" * len(original_hash)
    db.commit()
    with pytest.raises(rsp.UnverifiedRegularSessionPrice, match="무결성"):
        rsp.load_regular_session_evidence(db, "005930", DAY)
    assert recomputations == 3

    record.evidence_hash = original_hash
    db.commit()
    with rsp._validated_evidence_cache_lock:
        rsp._validated_evidence_cache.clear()
        rsp._validated_evidence_cache_bytes = 0
    monkeypatch.setattr(rsp, "_VALIDATED_EVIDENCE_CACHE_MAX_BYTES", 1)
    rsp.load_regular_session_evidence(db, "005930", DAY)
    rsp.load_regular_session_evidence(db, "005930", DAY)
    assert recomputations == 5
    assert rsp._validated_evidence_cache_bytes == 0


def test_regular_prices_leave_legacy_fixtures_intact_and_never_fallback(db):
    legacy = DailyPrice(code="005930", trade_date=date(2026, 9, 11), close=95)
    missing = DailyPrice(code="005930", trade_date=DAY, close=100)
    assert rsp.regular_signal_price_rows(db, [legacy], completed_through=date(2026, 9, 11)) == [legacy]
    with pytest.raises(rsp.UnverifiedRegularSessionPrice):
        rsp.regular_signal_price_rows(db, [legacy, missing], completed_through=DAY)
    assert rsp.regular_signal_price_rows(db, [missing], completed_through=date(2026, 10, 8)) == []


def test_unverified_evidence_is_preserved_but_not_accepted_as_signal_input(db):
    invalid = evidence(minute_rows()[:-1])
    record = rsp.store_regular_session_evidence(db, invalid, observed_at=OBSERVED)
    db.commit()
    assert record.state == "unverified"
    with pytest.raises(rsp.UnverifiedRegularSessionPrice):
        rsp.load_regular_session_evidence(db, "005930", DAY)


def test_store_recomputes_evidence_and_rejects_forged_ready_state(db):
    payload = evidence(minute_rows()[:-1])
    payload["state"] = "ready"
    with pytest.raises(ValueError, match="recomputation"):
        rsp.store_regular_session_evidence(db, payload, observed_at=OBSERVED)


def test_dated_regular_source_keeps_closing_auction_and_preopen_baseline(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings
    provider = KisRestBriefingProvider(Settings(kis_app_key="fixture", kis_app_secret="fixture"))
    calls = []
    source = [{"stck_bsop_date": row["trade_date"], "stck_cntg_hour": row["trade_time"], "stck_oprc": row["open"], "stck_hgpr": row["high"], "stck_lwpr": row["low"], "stck_prpr": row["price"], "cntg_vol": row["volume"], "acml_tr_pbmn": row["trading_value"]} for row in minute_rows()]

    def get(path, tr_id, params):
        calls.append(params)
        assert tr_id == "FHKST03010230"
        assert params["FID_COND_MRKT_DIV_CODE"] == "J"
        assert params["FID_INPUT_DATE_1"] == "20261012"
        return {"output2": [row for row in reversed(source) if row["stck_cntg_hour"] <= params["FID_INPUT_HOUR_1"]][:120]}

    monkeypatch.setattr(provider, "_get", get)
    rows = provider.fetch_regular_session_minutes("005930", DAY)
    assert calls[0]["FID_INPUT_HOUR_1"] == "153100"
    assert len(calls) == 4
    assert len(rows) == 392
    assert rows[-1]["trade_time"] == "153000"
    assert rows[0]["trade_time"] == "085900"
    assert evidence(rows)["state"] == "ready"


def test_dated_regular_source_pages_past_five_sparse_responses(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings

    provider = KisRestBriefingProvider(
        Settings(kis_app_key="fixture", kis_app_secret="fixture")
    )
    calls = []
    source = [
        {
            "stck_bsop_date": row["trade_date"],
            "stck_cntg_hour": row["trade_time"],
            "stck_oprc": row["open"],
            "stck_hgpr": row["high"],
            "stck_lwpr": row["low"],
            "stck_prpr": row["price"],
            "cntg_vol": row["volume"],
            "acml_tr_pbmn": row["trading_value"],
        }
        for row in minute_rows()
        if row["trade_time"] >= "090000"
    ]

    def get(_path, _tr_id, params):
        calls.append(params["FID_INPUT_HOUR_1"])
        if params["FID_INPUT_HOUR_1"] == "085900":
            return {
                "output2": [
                    {
                        "stck_bsop_date": "20261008",
                        "stck_cntg_hour": "195900",
                        "acml_tr_pbmn": "999999",
                    }
                ]
            }
        return {
            "output2": [
                row
                for row in reversed(source)
                if row["stck_cntg_hour"] <= params["FID_INPUT_HOUR_1"]
            ][:75]
        }

    monkeypatch.setattr(provider, "_get", get)

    result = provider.fetch_regular_session_data("005930", DAY)

    assert len(calls) == 7
    assert result["rows"][0]["trade_time"] == "090000"
    assert result["rows"][-1]["trade_time"] == "153000"
    assert result["preopen_baseline"]["kind"] == "observed_day_boundary"


def test_dated_regular_source_fetches_cross_source_close_for_zero_volume_1530(
    monkeypatch,
):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings

    provider = KisRestBriefingProvider(
        Settings(kis_app_key="fixture", kis_app_secret="fixture")
    )
    source = [
        {
            "stck_bsop_date": row["trade_date"],
            "stck_cntg_hour": row["trade_time"],
            "stck_oprc": row["open"],
            "stck_hgpr": row["high"],
            "stck_lwpr": row["low"],
            "stck_prpr": row["price"],
            "cntg_vol": row["volume"],
            "acml_tr_pbmn": row["trading_value"],
        }
        for row in minute_rows()
    ]
    source[-1]["cntg_vol"] = 0
    source[-1]["acml_tr_pbmn"] = source[-2]["acml_tr_pbmn"]

    def get(_path, _tr_id, params):
        return {
            "output2": [
                row
                for row in reversed(source)
                if row["stck_cntg_hour"] <= params["FID_INPUT_HOUR_1"]
            ][:120]
        }

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return naver_auction_fixture()

    requested = []

    def request(url, **kwargs):
        requested.append((url, kwargs))
        return Response()

    monkeypatch.setattr(provider, "_get", get)
    monkeypatch.setattr("app.collectors.briefing.requests.get", request)

    result = provider.fetch_regular_session_data("005930", DAY)

    assert result["rows"][-1]["trade_time"] == "153000"
    assert result["rows"][-1]["volume"] == 0
    assert result["closing_auction_evidence"] == naver_auction_fixture()
    assert requested[0][1]["params"] == {"periodType": "week"}


def test_dated_regular_source_fetches_cross_source_for_sparse_tail(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings

    provider = KisRestBriefingProvider(
        Settings(kis_app_key="fixture", kis_app_secret="fixture")
    )
    source = [
        {
            "stck_bsop_date": row["trade_date"],
            "stck_cntg_hour": row["trade_time"],
            "stck_oprc": row["open"],
            "stck_hgpr": row["high"],
            "stck_lwpr": row["low"],
            "stck_prpr": row["price"],
            "cntg_vol": row["volume"],
            "acml_tr_pbmn": row["trading_value"],
        }
        for row in minute_rows()
        if row["trade_time"] != "151900"
    ]

    def get(_path, _tr_id, params):
        return {
            "output2": [
                row
                for row in reversed(source)
                if row["stck_cntg_hour"] <= params["FID_INPUT_HOUR_1"]
            ][:120]
        }

    class Response:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return naver_auction_fixture()

    requested = []

    def request(url, **kwargs):
        requested.append((url, kwargs))
        return Response()

    monkeypatch.setattr(provider, "_get", get)
    monkeypatch.setattr("app.collectors.briefing.requests.get", request)

    result = provider.fetch_regular_session_data("005930", DAY)

    assert "151900" not in {row["trade_time"] for row in result["rows"]}
    assert result["closing_auction_evidence"] == naver_auction_fixture()
    assert len(requested) == 1


def test_dated_regular_source_does_not_relabel_wrong_dates(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings
    provider = KisRestBriefingProvider(Settings())
    monkeypatch.setattr(provider, "_get", lambda *_args: {"output2": [{"stck_bsop_date": "20261013", "stck_cntg_hour": "153000"}]})
    assert provider.fetch_regular_session_minutes("005930", DAY) == []


def test_regular_backfill_is_scoped_resumable_and_does_not_publish(db):
    from types import SimpleNamespace
    for code in ("005930", "000660", "373220"):
        db.add(DailyPrice(code=code, trade_date=DAY, close=110))
    db.commit()
    calls = []

    def fetch(code, day):
        calls.append((code, day))
        return {"rows": minute_rows()}

    provider = SimpleNamespace(fetch_regular_session_data=fetch)
    kwargs = dict(codes=["005930", "000660"], start=DAY, end=DAY, observed_at=OBSERVED, max_pairs=1)
    dry_run = rsp.collect_regular_session_prices(db, provider, **kwargs)
    assert dry_run["ready"] == 1 and dry_run["deferred"] == 1
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 0
    first = rsp.collect_regular_session_prices(db, provider, persist=True, **kwargs)
    second = rsp.collect_regular_session_prices(db, provider, persist=True, **kwargs)
    assert first["state"] == "incomplete"
    assert second["state"] == "ready"
    assert second["already_ready"] == 1
    assert second["notifications_sent"] == 0 and not second["signal_publication"]
    assert {item[0] for item in calls} == {"005930", "000660"}
    assert all(row.close == 110 for row in db.scalars(select(DailyPrice)))


def test_regular_backfill_redacts_source_errors_and_keeps_failures_visible(db):
    from types import SimpleNamespace
    db.add(DailyPrice(code="005930", trade_date=DAY, close=110))
    db.commit()

    def unavailable(*_args):
        raise RuntimeError("https://provider.example?app_secret=do-not-export")

    result = rsp.collect_regular_session_prices(db, SimpleNamespace(fetch_regular_session_data=unavailable), codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED, persist=True)
    assert result["state"] == "incomplete"
    assert result["unverified"][0]["reason"] == "source_unavailable"
    assert "do-not-export" not in json.dumps(result)


def test_regular_backfill_prioritizes_old_unverified_session_under_pair_cap(db):
    from types import SimpleNamespace

    bad = rsp.regular_session_evidence("005930", DAY, [], observed_at=OBSERVED)
    assert bad["state"] == "unverified"
    rsp.store_regular_session_evidence(db, bad, observed_at=OBSERVED)
    db.commit()
    calls = []

    def fetch(code, day):
        calls.append((code, day))
        return {"rows": minute_rows()}

    result = rsp.collect_regular_session_prices(
        db, SimpleNamespace(fetch_regular_session_data=fetch),
        codes=["005930"], start=DAY, end=DAY + timedelta(days=1),
        observed_at=OBSERVED + timedelta(days=1), persist=True, max_pairs=1,
    )
    assert calls == [("005930", DAY)]
    assert result["attempted"] == 1 and result["deferred"] == 1
    assert rsp.load_regular_session_evidence(db, "005930", DAY)["state"] == "ready"


def test_regular_backfill_cools_down_unverified_source_without_hiding_failure(db):
    from types import SimpleNamespace

    bad = rsp.regular_session_evidence("005930", DAY, [], observed_at=OBSERVED)
    rsp.store_regular_session_evidence(db, bad, observed_at=OBSERVED)
    db.commit()
    calls = []

    def fetch(code, day):
        calls.append((code, day))
        return {"rows": minute_rows()}

    result = rsp.collect_regular_session_prices(
        db, SimpleNamespace(fetch_regular_session_data=fetch),
        codes=["000660", "005930"], start=DAY, end=DAY,
        observed_at=OBSERVED + timedelta(minutes=10), persist=True, max_pairs=2,
    )
    assert calls == [("000660", DAY)]
    assert result["attempted"] == 1
    assert {item["reason"] for item in result["unverified"]} == {"retry_cooldown"}
    assert result["state"] == "incomplete"


def test_regular_backfill_accepts_only_two_matching_rechecks_after_volatile_minute(db, monkeypatch):
    from types import SimpleNamespace

    original = rsp.regular_session_evidence
    evidence_calls = 0
    source_calls = 0

    def intermittently_incomplete(*args, **kwargs):
        nonlocal evidence_calls
        evidence_calls += 1
        evidence = original(*args, **kwargs)
        if evidence_calls == 1:
            return {
                **evidence,
                "state": "unverified",
                "reason": "cumulative turnover does not reconcile with actual trades",
            }
        return evidence

    def fetch(*_args):
        nonlocal source_calls
        source_calls += 1
        return {"rows": minute_rows()}

    monkeypatch.setattr(rsp, "regular_session_evidence", intermittently_incomplete)
    result = rsp.collect_regular_session_prices(
        db, SimpleNamespace(fetch_regular_session_data=fetch),
        codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED,
        persist=True,
    )
    assert source_calls == 3
    assert result["ready"] == 1 and result["unverified"] == []
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 1
    assert rsp.load_regular_session_evidence(db, "005930", DAY)["state"] == "ready"


def test_regular_backfill_keeps_volatile_minute_isolated_if_rechecks_disagree(db, monkeypatch):
    from types import SimpleNamespace

    original = rsp.regular_session_evidence
    evidence_calls = 0
    source_calls = 0

    def inconsistent(*args, **kwargs):
        nonlocal evidence_calls
        evidence_calls += 1
        evidence = original(*args, **kwargs)
        if evidence_calls == 1:
            return {
                **evidence,
                "state": "unverified",
                "reason": "closing source conflicts with KIS pre-auction OHLC",
            }
        if evidence_calls == 3:
            return {**evidence, "source": "different dated source"}
        return evidence

    def fetch(*_args):
        nonlocal source_calls
        source_calls += 1
        return {"rows": minute_rows()}

    monkeypatch.setattr(rsp, "regular_session_evidence", inconsistent)
    result = rsp.collect_regular_session_prices(
        db, SimpleNamespace(fetch_regular_session_data=fetch),
        codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED,
    )
    assert source_calls == 3
    assert result["ready"] == 0
    assert result["unverified"][0]["reason"] == "closing source conflicts with KIS pre-auction OHLC"
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 0


def test_regular_backfill_reserves_capacity_for_new_sessions_when_old_failures_accumulate(db):
    from types import SimpleNamespace

    for code in ("000660", "005930"):
        bad = rsp.regular_session_evidence(code, DAY, [], observed_at=OBSERVED)
        rsp.store_regular_session_evidence(db, bad, observed_at=OBSERVED)
    db.commit()
    calls = []

    def fetch(code, day):
        calls.append((code, day))
        return {"rows": minute_rows()}

    result = rsp.collect_regular_session_prices(
        db, SimpleNamespace(fetch_regular_session_data=fetch),
        codes=["000660", "005930"], start=DAY, end=DAY + timedelta(days=1),
        observed_at=OBSERVED + timedelta(days=1), persist=True, max_pairs=2,
    )
    assert calls == [("000660", DAY), ("000660", DAY + timedelta(days=1))]
    assert result["attempted"] == 2
    assert result["deferred"] == 2


def test_gap_summary_excludes_unverified_day_and_tampered_other_date(db):
    from app.services.regular_session_gap import verified_sessions_around_gap

    observed = datetime(2026, 11, 11, 6, tzinfo=rsp.KST)
    gap = date(2026, 11, 6)
    bad = rsp.regular_session_evidence("005930", gap, [], observed_at=observed)
    rsp.store_regular_session_evidence(db, bad, observed_at=observed)
    for day in (date(2026, 11, 9), date(2026, 11, 10)):
        rows = minute_rows()
        for row in rows:
            row["trade_date"] = day.strftime("%Y%m%d")
        ready = rsp.regular_session_evidence("005930", day, rows, observed_at=observed)
        rsp.store_regular_session_evidence(db, ready, observed_at=observed)
    db.commit()
    record = db.scalar(select(SignalSessionPrice).where(
        SignalSessionPrice.code == "005930",
        SignalSessionPrice.trade_date == date(2026, 11, 9),
    ))
    corrupted = json.loads(record.payload)
    corrupted["evidence"]["prices"]["close"] = 101
    record.payload = json.dumps(corrupted)
    db.commit()

    summary = verified_sessions_around_gap(db, "005930", gap)
    assert [row["trade_date"] for row in summary] == ["2026-11-10"]
    assert summary[0]["close"] == 100 and summary[0]["volume"] == 3810


def test_regular_turnover_accepts_observed_day_boundary_not_assumed_zero():
    rows = minute_rows()[1:]
    for row in rows:
        row["trading_value"] -= 50_000
    baseline = {"kind": "observed_day_boundary", "requested_date": "20261012", "requested_time": "085900", "previous_trade_date": "20261008", "previous_trade_time": "195900", "value": 0}
    result = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, preopen_baseline=baseline)
    assert result["state"] == "ready"
    assert result["prices"]["trading_value"] == 381000
    for field, value in (("previous_trade_date", "20261012"), ("previous_trade_time", "bad"), ("requested_date", "20261008"), ("requested_time", "100000"), ("value", 5)):
        altered = {**baseline, field: value}
        assert rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, preopen_baseline=altered)["state"] == "unverified"
    assert rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED)["state"] == "unverified"
    # A day-boundary response alone cannot separate a non-single-price first
    # minute from pre-open turnover. Do not bless a plausible cumulative sum.
    changed = deepcopy(rows)
    changed[0].update(high=101, low=99)
    bounded = rsp.regular_session_evidence("005930", DAY, changed, observed_at=OBSERVED, preopen_baseline=baseline)
    assert bounded["state"] == "bounded"
    assert bounded["prices"]["trading_value"] is None
    assert bounded["turnover_bounds"]["lower"] == 380990
    assert bounded["turnover_bounds"]["upper"] == 381000


def test_dated_regular_source_records_previous_day_rollover_separately(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings
    provider = KisRestBriefingProvider(Settings())

    def get(_path, _tr_id, params):
        if params["FID_INPUT_HOUR_1"] == "085900":
            return {"output2": [{"stck_bsop_date": "20261008", "stck_cntg_hour": "195900", "acml_tr_pbmn": "999999"}]}
        return {"output2": [{"stck_bsop_date": "20261012", "stck_cntg_hour": "090000", "stck_prpr": "100", "stck_oprc": "100", "stck_hgpr": "100", "stck_lwpr": "100", "cntg_vol": "10", "acml_tr_pbmn": "1000"}]}

    monkeypatch.setattr(provider, "_get", get)
    result = provider.fetch_regular_session_data("005930", DAY)
    assert result["preopen_baseline"]["kind"] == "observed_day_boundary"
    assert result["preopen_baseline"]["previous_trade_date"] == "20261008"
    assert len(result["rows"]) == 1
    assert result["rows"][0]["trade_date"] == "20261012"


def naver_auction_fixture():
    prefix = [row for row in minute_rows() if "090000" <= row["trade_time"] <= "151900"]
    buckets = []
    for index in range(0, len(prefix), 10):
        buckets.append({"localDateTime": "20261012" + prefix[index]["trade_time"], "openPrice": 100, "highPrice": 100, "lowPrice": 100, "currentPrice": 100, "accumulatedTradingVolume": 5 + (index + 10) * 10})
    buckets.append({"localDateTime": "20261012153000", "openPrice": 110, "highPrice": 110, "lowPrice": 110, "currentPrice": 110, "accumulatedTradingVolume": 3905})
    return {"code": "005930", "stockExchangeType": "KRX", "periodType": "week", "priceInfos": {"20261012": buckets}}


def test_closing_auction_time_formatting_is_bounded_per_bucket(monkeypatch):
    # Twenty recommendation cards replay several sessions each. Keep the
    # unchanged cross-source validation from formatting bounds per minute.
    rows = [row for row in minute_rows() if "090000" <= row["trade_time"] <= "151900"]
    source = naver_auction_fixture()
    calls = []
    class CountedDatetime(datetime):
        def strftime(self, fmt):
            calls.append(fmt)
            return super().strftime(fmt)
    monkeypatch.setattr(rsp, "datetime", CountedDatetime)
    close = rsp._verified_naver_closing_auction("005930", DAY, rows, source)
    assert close["trade_time"] == "153000"
    assert close["price"] == 110
    assert close["volume"] == 100
    assert len(calls) < 500


def test_missing_auction_requires_cross_source_prefix_and_actual_single_price(db):
    rows = [row for row in minute_rows() if row["trade_time"] <= "151900"]
    naver = naver_auction_fixture()
    result = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, closing_auction_evidence=naver)
    assert result["state"] == "ready"
    assert result["prices"] == {"open": 100, "high": 110, "low": 100, "close": 110, "volume": 3900, "trading_value": 391000}
    assert result["source"].endswith("+naver_krx_closing_auction")
    assert result["raw_rows"][-1]["trade_time"] == "151900"
    assert result["regular_rows"][-1]["trade_time"] == "153000"
    rsp.store_regular_session_evidence(db, result, observed_at=OBSERVED)
    db.commit()
    assert rsp.load_regular_session_evidence(db, "005930", DAY)["prices"]["close"] == 110


def test_zero_volume_1530_requires_and_uses_verified_cross_source_close():
    rows = minute_rows()
    rows[-1]["volume"] = 0
    rows[-1]["trading_value"] = rows[-2]["trading_value"]

    assert evidence(rows)["state"] == "unverified"

    result = rsp.regular_session_evidence(
        "005930",
        DAY,
        rows,
        observed_at=OBSERVED,
        closing_auction_evidence=naver_auction_fixture(),
    )

    assert result["state"] == "ready", result["reason"]
    assert result["prices"] == {
        "open": 100,
        "high": 110,
        "low": 100,
        "close": 110,
        "volume": 3900,
        "trading_value": 391000,
    }
    assert result["raw_rows"][-1]["volume"] == 0
    assert result["regular_rows"][-1]["trade_time"] == "153000"
    assert result["regular_rows"][-1]["volume"] == 100
    assert result["source"].endswith("+naver_krx_closing_auction")


def test_cross_source_auction_never_recovers_wrong_venue_date_or_bad_prefix():
    rows = [row for row in minute_rows() if row["trade_time"] <= "151900"]
    corruptions = []
    for field, value in (("code", "000660"), ("stockExchangeType", "NXT"), ("periodType", "day"), ("priceInfos", {"20261008": []})):
        corruptions.append({**naver_auction_fixture(), field: value})
    for index, field, value in ((0, "highPrice", 120), (1, "accumulatedTradingVolume", 206), (-1, "highPrice", 120), (-1, "accumulatedTradingVolume", 3805)):
        changed = naver_auction_fixture()
        changed["priceInfos"]["20261012"][index][field] = value
        corruptions.append(changed)
    for naver in corruptions:
        assert rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, closing_auction_evidence=naver)["state"] == "unverified"

    # A 15:40 print is after-market evidence, not a shifted closing auction.
    # When both dated regular sources omit 15:30, preserve the last actual
    # regular trade instead of relabelling the later bucket.
    shifted = naver_auction_fixture()
    shifted["priceInfos"]["20261012"][-1]["localDateTime"] = "20261012154000"
    no_close = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=shifted,
    )
    assert no_close["state"] == "ready"
    assert no_close["regular_rows"][-1]["trade_time"] == "151900"
    assert rsp.regular_session_evidence("005930", DAY, rows[:70] + rows[71:], observed_at=OBSERVED, closing_auction_evidence=naver_auction_fixture())["state"] == "unverified"


def test_november_10_last_continuous_trade_is_verified_and_replayed(db):
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths

    fixture = json.loads((Path(__file__).parent / "fixtures" / "kr_regular_122630_20261110.json").read_text())
    trade_date = date.fromisoformat(fixture["trade_date"])
    observed_at = datetime(2026, 11, 13, 2, 30, tzinfo=rsp.KST)

    def verify(source):
        return rsp.regular_session_evidence(
            fixture["code"], trade_date, source["raw_rows"],
            observed_at=observed_at,
            preopen_baseline=source["preopen_baseline"],
            closing_auction_evidence=source["closing_auction_evidence"],
        )

    result = verify(fixture)
    assert result["state"] == "bounded", result["reason"]
    assert result["prices"]["volume"] == 24_919_754
    assert result["prices"]["close"] == 58_435
    assert [(row["trade_time"], row["price"], row["volume"]) for row in result["regular_rows"][-2:]] == [
        ("152000", 58_525, 20), ("153000", 58_435, 149_796),
    ]
    stored = rsp.store_regular_session_evidence(db, result, observed_at=observed_at)
    db.commit()
    assert stored.state == "bounded"
    loaded = rsp.load_regular_session_evidence(db, fixture["code"], trade_date, allow_bounded=True)
    assert loaded["regular_rows"] == result["regular_rows"]
    envelope = regular_price_envelope(
        db, fixture["code"], [DailyPrice(code=fixture["code"], trade_date=trade_date, close=58_435)],
        completed_through=trade_date,
    )
    assert len(regular_ordered_paths(envelope)[trade_date]) == 380

    bad_naver_volume = deepcopy(fixture)
    bad_naver_volume["closing_auction_evidence"]["priceInfos"]["20261110"][-2]["accumulatedTradingVolume"] += 1
    bad_naver_price = deepcopy(fixture)
    bad_naver_price["closing_auction_evidence"]["priceInfos"]["20261110"][-2]["currentPrice"] += 5
    bad_kis_money = deepcopy(fixture)
    next(row for row in bad_kis_money["raw_rows"] if row["trade_time"] == "152000")["trading_value"] += 1
    missing_kis_trade = deepcopy(fixture)
    missing_kis_trade["raw_rows"] = [row for row in missing_kis_trade["raw_rows"] if row["trade_time"] != "152000"]
    after_auction_trade = deepcopy(fixture)
    after_auction_trade["raw_rows"].append({**next(row for row in after_auction_trade["raw_rows"] if row["trade_time"] == "152000"), "trade_time": "152100", "volume": 1})
    for changed in (bad_naver_volume, bad_naver_price, bad_kis_money, missing_kis_trade, after_auction_trade):
        assert verify(changed)["state"] == "unverified"


def test_regular_backfill_checks_scheduled_days_missing_from_display_database(db):
    from types import SimpleNamespace
    provider = SimpleNamespace(fetch_regular_session_data=lambda *_args: {"rows": minute_rows()})
    # No DailyPrice rows: absence must not be interpreted as a complete history.
    result = rsp.collect_regular_session_prices(db, provider, codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED)
    assert result["total_pairs"] == 1
    assert result["attempted"] == 1


def test_regular_cli_defaults_to_read_only_and_preserves_alphanumeric_codes(monkeypatch, db):
    from contextlib import nullcontext
    from typer.testing import CliRunner
    from app import cli
    captured = []

    def collect(_db, _provider, **kwargs):
        captured.append(kwargs)
        return {"state": "ready"}

    monkeypatch.setattr(cli, "SessionLocal", lambda: nullcontext(db))
    monkeypatch.setattr(rsp, "collect_regular_session_prices", collect)
    result = CliRunner().invoke(cli.app, ["regular-session-prices", "--codes", "0126Z0,005930", "--to-date", "2026-10-12"])
    assert result.exit_code == 0, result.output
    assert captured[0]["persist"] is False
    assert captured[0]["codes"] == ["005930", "0126Z0"]
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 0


def test_regular_backfill_does_not_hide_conflicting_persisted_evidence(db):
    from types import SimpleNamespace
    record = rsp.store_regular_session_evidence(db, evidence(), observed_at=OBSERVED)
    record.evidence_hash = "0" * 64
    db.commit()

    def forbidden(*_args):
        pytest.fail("corrupt stored evidence cannot be masked by a fresh fetch")

    result = rsp.collect_regular_session_prices(db, SimpleNamespace(fetch_regular_session_data=forbidden), codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED, persist=True)
    assert result["state"] == "incomplete"
    assert result["unverified"][0]["reason"] == "stored_evidence_conflict_or_corruption"


def test_bounded_prices_are_opt_in_only_and_never_supply_a_fake_point_value(db):
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths
    rows = minute_rows()[1:]
    rows[0].update(low=99, high=101)
    baseline = {"kind": "observed_day_boundary", "requested_date": "20261012", "requested_time": "085900", "previous_trade_date": "20261008", "previous_trade_time": "195900", "value": None}
    bounded = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, preopen_baseline=baseline)
    assert bounded["state"] == "bounded"
    assert bounded["prices"]["trading_value"] is None
    rsp.store_regular_session_evidence(db, bounded, observed_at=OBSERVED)
    db.commit()
    with pytest.raises(rsp.UnverifiedRegularSessionPrice):
        rsp.load_regular_session_evidence(db, "005930", DAY)
    assert rsp.load_regular_session_evidence(db, "005930", DAY, allow_bounded=True) == bounded
    display = DailyPrice(code="005930", trade_date=DAY, close=120, trading_value=999999)
    scenarios = regular_price_envelope(db, "005930", [display], completed_through=DAY)
    assert scenarios.lower[0].close == scenarios.upper[0].close == 100
    assert scenarios.lower[0].trading_value == 380990
    assert scenarios.upper[0].trading_value == 381010
    assert display.trading_value == 999999
    assert len(regular_ordered_paths(scenarios)[DAY]) == 381


def test_regular_dry_run_does_not_create_a_missing_sidecar_table():
    from types import SimpleNamespace
    from sqlalchemy import inspect
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        result = rsp.collect_regular_session_prices(
            db, SimpleNamespace(fetch_regular_session_data=lambda *_args: {"rows": minute_rows()}),
            codes=["005930"], start=DAY, end=DAY, observed_at=OBSERVED,
        )
        assert result["ready"] == 1
        assert inspect(engine).get_table_names() == []
    engine.dispose()


def test_regular_integer_evidence_preserves_exact_values_above_float_precision():
    assert rsp._integer("9007199254740993") == 9007199254740993
    with pytest.raises(ValueError):
        rsp._integer("9007199254740993.5")


def sparse_regular_fixture(missing="094000"):
    rows = [row for row in minute_rows() if row["trade_time"] != missing]
    for row in rows:
        if row["trade_time"] > missing:
            row["trading_value"] -= 1000
    naver = naver_auction_fixture()
    for bucket in naver["priceInfos"]["20261012"][:-1]:
        if bucket["localDateTime"][-6:-2] >= missing[:3] + "0":
            bucket["accumulatedTradingVolume"] -= 10
    naver["priceInfos"]["20261012"][-1].update(
        openPrice=100, highPrice=100, lowPrice=100, currentPrice=100,
        accumulatedTradingVolume=3805,
    )
    return rows, naver


def delayed_open_minute_fixture(rows, naver):
    prefix = [row for row in rows if "090000" <= row["trade_time"] < "091000" and row["volume"] > 0]
    opening = naver["priceInfos"]["20261012"][0]
    offset = opening["accumulatedTradingVolume"] - sum(
        row["volume"] for row in prefix if row["trade_time"] < "091000"
    )
    cumulative = offset
    minutes = []
    for row in prefix:
        cumulative += row["volume"]
        minutes.append({"trade_time": row["trade_time"], "close": row["price"],
                        "accumulated_volume": cumulative})
    return {"code": "005930", "trade_date": "20261012", "timeframe": "minute", "rows": minutes}


def halted_regular_fixture(*, keep_zero_volume_rows=False):
    start, end = "124000", "125900"
    rows = minute_rows()
    removed_volume = sum(
        row["volume"] for row in rows if start <= row["trade_time"] <= end
    )
    removed_value = sum(
        row["volume"] * row["price"]
        for row in rows
        if start <= row["trade_time"] <= end
    )
    if keep_zero_volume_rows:
        baseline = next(
            row["trading_value"]
            for row in rows
            if row["trade_time"] == "123900"
        )
        for row in rows:
            if start <= row["trade_time"] <= end:
                row["volume"] = 0
                row["trading_value"] = baseline
            elif row["trade_time"] > end:
                row["trading_value"] -= removed_value
    else:
        rows = [row for row in rows if not start <= row["trade_time"] <= end]
        for row in rows:
            if row["trade_time"] > end:
                row["trading_value"] -= removed_value
    rows[-1]["volume"] = 0
    rows[-1]["trading_value"] = rows[-2]["trading_value"]

    naver = naver_auction_fixture()
    buckets = []
    for bucket in naver["priceInfos"]["20261012"]:
        stamp = bucket["localDateTime"][-6:]
        if stamp in {"124000", "125000"}:
            continue
        if stamp > end:
            bucket["accumulatedTradingVolume"] -= removed_volume
        buckets.append(bucket)
    naver["priceInfos"]["20261012"] = buckets
    return rows, naver


def test_sparse_regular_minutes_require_independent_volume_coverage_not_interpolation(db):
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths
    rows, naver = sparse_regular_fixture()
    assert evidence(rows)["state"] == "unverified"
    verified = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, closing_auction_evidence=naver)
    assert verified["state"] == "ready", verified["reason"]
    assert verified["prices"]["volume"] == 3800
    assert verified["prices"]["trading_value"] == 380000
    assert len(verified["regular_rows"]) == 380
    assert "094000" not in {row["trade_time"] for row in verified["regular_rows"]}
    rsp.store_regular_session_evidence(db, verified, observed_at=OBSERVED)
    db.commit()
    inputs = regular_price_envelope(db, "005930", [DailyPrice(code="005930", trade_date=DAY, close=120)], completed_through=DAY)
    assert len(regular_ordered_paths(inputs)[DAY]) == 380


def test_sparse_regular_coverage_accepts_opening_bucket_gap_after_cross_source_match():
    rows, naver = sparse_regular_fixture("090500")
    result = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, closing_auction_evidence=naver)
    assert result["state"] == "ready", result["reason"]
    assert result["prices"]["volume"] == 3800


def test_sparse_regular_coverage_still_requires_observed_opening_trade_anchor():
    rows, naver = sparse_regular_fixture("090000")
    result = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )
    assert result["state"] == "unverified"
    assert "zero cross-source volume offset" in result["reason"]


def test_delayed_first_trade_requires_zero_cross_source_volume_offset():
    rows, naver = sparse_regular_fixture("090000")
    for bucket in naver["priceInfos"]["20261012"]:
        bucket["accumulatedTradingVolume"] -= 5

    result = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )

    assert result["state"] == "ready", result["reason"]
    assert result["regular_rows"][0]["trade_time"] == "090100"


def test_delayed_open_accepts_only_exact_independent_minute_path(db):
    rows, naver = sparse_regular_fixture("090000")
    minutes = delayed_open_minute_fixture(rows, naver)
    verified = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=naver, minute_coverage_evidence=minutes,
    )
    assert verified["state"] == "ready", verified["reason"]
    assert verified["coverage_basis"] == rsp.NAVER_MINUTE_OPENING_COVERAGE_BASIS
    assert verified["source"].endswith("+naver_1m_delayed_open")
    rsp.store_regular_session_evidence(db, verified, observed_at=OBSERVED)
    db.commit()
    assert rsp.load_regular_session_evidence(db, "005930", DAY)["prices"] == verified["prices"]
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths
    envelope = regular_price_envelope(
        db, "005930", [DailyPrice(code="005930", trade_date=DAY, close=100)],
        completed_through=DAY, effective_from=DAY,
    )
    assert len(regular_ordered_paths(envelope)[DAY]) == len(verified["regular_rows"])

    for mutation in ("early_print", "missing_print", "close", "volume_delta", "identity"):
        changed = deepcopy(minutes)
        if mutation == "early_print":
            changed["rows"].insert(0, {"trade_time": "090000", "close": 100,
                                         "accumulated_volume": 1})
        elif mutation == "missing_print":
            changed["rows"].pop(2)
        elif mutation == "close":
            changed["rows"][2]["close"] = 101
        elif mutation == "volume_delta":
            changed["rows"][2]["accumulated_volume"] += 1
        else:
            changed["code"] = "000660"
        rejected = rsp.regular_session_evidence(
            "005930", DAY, rows, observed_at=OBSERVED,
            closing_auction_evidence=naver, minute_coverage_evidence=changed,
        )
        assert rejected["state"] == "unverified", mutation


def test_naver_minute_parser_rejects_wrong_identity_and_keeps_regular_minutes():
    from app.collectors.briefing import _parse_naver_minute_coverage
    xml = b'''<?xml version="1.0" encoding="EUC-KR"?>
    <protocol><chartdata symbol="005930" timeframe="minute">
    <item data="202610120901|null|null|null|100|15"/>
    <item data="202610121530|null|null|null|101|25"/>
    <item data="202610121540|null|null|null|102|30"/>
    </chartdata></protocol>'''
    parsed = _parse_naver_minute_coverage("005930", "20261012", xml)
    assert parsed["rows"] == [{"trade_time": "090100", "close": "100", "accumulated_volume": "15"}]
    with pytest.raises(ValueError, match="identity"):
        _parse_naver_minute_coverage("000660", "20261012", xml)


def test_dated_regular_provider_fetches_delayed_open_minute_proof(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings

    rows, naver = sparse_regular_fixture("090000")
    minute = delayed_open_minute_fixture(rows, naver)
    source = [{"stck_bsop_date": row["trade_date"], "stck_cntg_hour": row["trade_time"],
               "stck_oprc": row["open"], "stck_hgpr": row["high"],
               "stck_lwpr": row["low"], "stck_prpr": row["price"],
               "cntg_vol": row["volume"], "acml_tr_pbmn": row["trading_value"]}
              for row in rows]
    provider = KisRestBriefingProvider(Settings(kis_app_key="fixture", kis_app_secret="fixture"))
    monkeypatch.setattr(provider, "_get", lambda _path, _tr, params: {
        "output2": [row for row in reversed(source)
                    if row["stck_cntg_hour"] <= params["FID_INPUT_HOUR_1"]][:120]
    })
    minute_xml = ('<protocol><chartdata symbol="005930" timeframe="minute">'
                  + "".join('<item data="20261012' + row["trade_time"][:4]
                            + '|null|null|null|' + str(row["close"]) + '|'
                            + str(row["accumulated_volume"]) + '"/>'
                            for row in minute["rows"])
                  + '</chartdata></protocol>').encode("euc-kr")
    urls = []

    class Response:
        def __init__(self, content):
            self.content = content

        def raise_for_status(self):
            pass

        def json(self):
            return naver

    def request(url, **_kwargs):
        urls.append(url)
        return Response(minute_xml if "fchart.stock.naver.com" in url else b"")

    monkeypatch.setattr("app.collectors.briefing.requests.get", request)
    fetched = provider.fetch_regular_session_data("005930", DAY)
    assert len(urls) == 2
    assert [row["trade_time"] for row in fetched["minute_coverage_evidence"]["rows"]] == [
        row["trade_time"] for row in minute["rows"]
    ]
    verified = rsp.regular_session_evidence(
        "005930", DAY, fetched["rows"], observed_at=OBSERVED,
        preopen_baseline=fetched["preopen_baseline"],
        closing_auction_evidence=fetched["closing_auction_evidence"],
        minute_coverage_evidence=fetched["minute_coverage_evidence"],
    )
    assert verified["state"] == "ready", verified["reason"]


def test_november_6_halt_bucket_open_requires_third_price_source(db):
    from app.collectors.briefing import _halt_bucket_open_candidate

    fixture = json.loads((Path(__file__).parent / "fixtures" / "kr_2026-11-06_396500_halt_open.json").read_text())
    source = fixture["source"]
    day = date(2026, 11, 6)
    observed = datetime(2026, 11, 7, 0, tzinfo=rsp.KST)
    assert _halt_bucket_open_candidate(
        {row["trade_time"]: row for row in source["rows"]},
        source["closing_auction_evidence"]["priceInfos"]["20261106"], "20261106",
    ) == "093000"

    def replay(proof):
        return rsp.regular_session_evidence(
            "396500", day, source["rows"], observed_at=observed,
            preopen_baseline=source["preopen_baseline"],
            closing_auction_evidence=source["closing_auction_evidence"],
            minute_coverage_evidence=fixture["minute_coverage_evidence"],
            bucket_open_proof=proof,
        )

    assert replay(None)["state"] == "unverified"
    verified = replay(fixture["bucket_open_proof"])
    assert verified["state"] == "bounded", verified["reason"]
    assert verified["regular_rows"][0]["trade_time"] == "090200"
    assert "+yahoo_1m_halt_bucket_open" in verified["source"]
    rsp.store_regular_session_evidence(db, verified, observed_at=observed)
    db.commit()
    assert rsp.load_regular_session_evidence(db, "396500", day, allow_bounded=True)["prices"] == verified["prices"]
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths
    envelope = regular_price_envelope(
        db, "396500", [DailyPrice(code="396500", trade_date=day, close=verified["prices"]["close"])],
        completed_through=day, effective_from=day,
    )
    path = regular_ordered_paths(envelope)[day]
    assert len(path) == 349 and path[0].open == 23720

    for mutation in ("yahoo_open", "yahoo_time", "yahoo_ticker", "naver_close", "naver_volume"):
        changed = deepcopy(fixture["bucket_open_proof"])
        if mutation == "yahoo_open":
            changed["yahoo"]["rows"][0]["open"] = 24620
        elif mutation == "yahoo_time":
            changed["yahoo"]["rows"][0]["trade_time"] = "093300"
        elif mutation == "yahoo_ticker":
            changed["yahoo"]["ticker"] = "000660.KS"
        elif mutation == "naver_close":
            changed["naver_minutes"][0]["close"] = 25230
        else:
            changed["naver_minutes"][0]["accumulated_volume"] = int(changed["naver_minutes"][0]["accumulated_volume"]) + 1
        assert replay(changed)["state"] == "unverified", mutation


def test_yahoo_halt_bucket_fetch_checks_identity_and_filters_outside_rows(monkeypatch):
    from app.collectors.briefing import _fetch_yahoo_bucket_open

    start = datetime(2026, 11, 6, 9, 34, tzinfo=rsp.KST)
    outside = datetime(2026, 11, 6, 15, 0, tzinfo=rsp.KST)
    calls = []

    class Response:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"chart": {"result": [{
                "meta": {"symbol": "396500.KS", "exchangeTimezoneName": "Asia/Seoul", "dataGranularity": "1m"},
                "timestamp": [int(start.timestamp()), int(outside.timestamp())],
                "indicators": {"quote": [{"open": [24625, 28130], "close": [25235, 28130]}]},
            }]}}

    def request(url, **kwargs):
        calls.append((url, kwargs["params"]))
        return Response()

    monkeypatch.setattr("app.collectors.briefing.requests.get", request)
    result = _fetch_yahoo_bucket_open("396500", date(2026, 11, 6), "093000")
    assert result["ticker"] == "396500.KS"
    assert result["rows"] == [{"trade_time": "093400", "open": 24625, "close": 25235}]
    assert calls[0][1]["interval"] == "1m"


def test_dated_provider_attaches_halt_bucket_open_proof(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings

    fixture = json.loads((Path(__file__).parent / "fixtures" / "kr_2026-11-06_396500_halt_open.json").read_text())
    source = fixture["source"]
    raw = [{"stck_bsop_date": row["trade_date"], "stck_cntg_hour": row["trade_time"],
            "stck_oprc": row["open"], "stck_hgpr": row["high"], "stck_lwpr": row["low"],
            "stck_prpr": row["price"], "cntg_vol": row["volume"],
            "acml_tr_pbmn": row["trading_value"]} for row in source["rows"]]
    provider = KisRestBriefingProvider(Settings(kis_app_key="fixture", kis_app_secret="fixture"))

    def kis(_path, _tr, params):
        cursor = params["FID_INPUT_HOUR_1"]
        dated = [row for row in reversed(raw) if row["stck_cntg_hour"] <= cursor][:120]
        if not dated:
            return {"output2": [{"stck_bsop_date": "20261105", "stck_cntg_hour": "195900"}]}
        return {"output2": dated}

    monkeypatch.setattr(provider, "_get", kis)
    minute_rows = fixture["minute_coverage_evidence"]["rows"] + fixture["bucket_open_proof"]["naver_minutes"]
    xml = ('<protocol><chartdata symbol="396500" timeframe="minute">'
           + "".join('<item data="20261106' + row["trade_time"][:4]
                     + '|null|null|null|' + str(row["close"]) + '|'
                     + str(row["accumulated_volume"]) + '"/>' for row in minute_rows)
           + '</chartdata></protocol>').encode("euc-kr")
    yahoo = fixture["bucket_open_proof"]["yahoo"]
    stamps = [int(datetime(2026, 11, 6, int(row["trade_time"][:2]), int(row["trade_time"][2:4]), tzinfo=rsp.KST).timestamp())
              for row in yahoo["rows"]]
    yahoo_json = {"chart": {"result": [{
        "meta": {"symbol": yahoo["ticker"], "exchangeTimezoneName": "Asia/Seoul", "dataGranularity": "1m"},
        "timestamp": stamps,
        "indicators": {"quote": [{"open": [row["open"] for row in yahoo["rows"]],
                                  "close": [row["close"] for row in yahoo["rows"]]}]},
    }]}}
    calls = []

    class Response:
        status_code = 200

        def __init__(self, body=None, content=b""):
            self.body, self.content = body, content

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    def request(url, **_kwargs):
        calls.append(url)
        if "fchart.stock.naver.com" in url:
            return Response(content=xml)
        if "query1.finance.yahoo.com" in url:
            return Response(body=yahoo_json)
        return Response(body=source["closing_auction_evidence"])

    monkeypatch.setattr("app.collectors.briefing.requests.get", request)
    fetched = provider.fetch_regular_session_data("396500", date(2026, 11, 6))
    assert len(calls) == 3
    assert fetched["bucket_open_proof"] == fixture["bucket_open_proof"]
    result = rsp.regular_session_evidence(
        "396500", date(2026, 11, 6), fetched["rows"],
        observed_at=datetime(2026, 11, 7, 0, tzinfo=rsp.KST),
        preopen_baseline=fetched["preopen_baseline"],
        closing_auction_evidence=fetched["closing_auction_evidence"],
        minute_coverage_evidence=fetched["minute_coverage_evidence"],
        bucket_open_proof=fetched["bucket_open_proof"],
    )
    assert result["state"] == "bounded", result["reason"]


def test_sparse_regular_coverage_accepts_missing_last_preauction_minute():
    rows, naver = sparse_regular_fixture("151900")
    result = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )
    assert result["state"] == "ready", result["reason"]
    assert result["regular_rows"][-1]["trade_time"] == "153000"


def test_cross_source_absent_closing_auction_uses_last_actual_regular_trade(db):
    rows = [row for row in minute_rows() if row["trade_time"] != "153000"]
    naver = naver_auction_fixture()
    naver["priceInfos"]["20261012"] = [
        bucket
        for bucket in naver["priceInfos"]["20261012"]
        if bucket["localDateTime"][-6:] != "153000"
    ]

    result = rsp.regular_session_evidence(
        "005930", DAY, rows, observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )

    assert result["state"] == "ready", result["reason"]
    assert result["prices"] == {
        "open": 100,
        "high": 100,
        "low": 100,
        "close": 100,
        "volume": 3800,
        "trading_value": 380000,
    }
    assert result["regular_rows"][-1]["trade_time"] == "151900"
    assert result["source"].endswith("+naver_krx_no_closing_trade")
    rsp.store_regular_session_evidence(db, result, observed_at=OBSERVED)
    db.commit()
    loaded = rsp.load_regular_session_evidence(db, "005930", DAY)
    assert loaded["prices"] == result["prices"]


def test_sparse_regular_coverage_rejects_conflicting_price_volume_or_closing_print():
    for bucket_index, field, value in ((5, "lowPrice", 99), (5, "accumulatedTradingVolume", 606), (-1, "currentPrice", 101)):
        rows, naver = sparse_regular_fixture()
        naver["priceInfos"]["20261012"][bucket_index][field] = value
        result = rsp.regular_session_evidence("005930", DAY, rows, observed_at=OBSERVED, closing_auction_evidence=naver)
        assert result["state"] == "unverified"


@pytest.mark.parametrize("keep_zero_volume_rows", [False, True])
def test_cross_source_regular_coverage_accepts_independently_confirmed_halt_buckets(
    keep_zero_volume_rows,
):
    rows, naver = halted_regular_fixture(
        keep_zero_volume_rows=keep_zero_volume_rows
    )

    result = rsp.regular_session_evidence(
        "005930",
        DAY,
        rows,
        observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )

    assert result["state"] == "ready", result["reason"]
    assert result["prices"]["close"] == 110
    assert result["prices"]["volume"] == 3700
    assert not {
        row["trade_time"] for row in result["regular_rows"]
    }.intersection({f"12{minute:02d}00" for minute in range(40, 60)})
    assert "+naver_krx_regular_coverage" in result["source"]


def test_cross_source_coverage_labels_remain_append_only_replay_compatible(db):
    rows, naver = halted_regular_fixture()
    canonical = rsp.regular_session_evidence(
        "005930",
        DAY,
        rows,
        observed_at=OBSERVED,
        closing_auction_evidence=naver,
    )
    assert canonical["state"] == "ready", canonical["reason"]

    for coverage_basis in (
        rsp.NAVER_REGULAR_COVERAGE_BASIS,
        (
            "naver_regular_buckets_with_complete_opening_volume_anchor_"
            "and_confirmed_empty_intervals"
        ),
    ):
        stored = deepcopy(canonical)
        stored["coverage_basis"] = coverage_basis
        rsp.store_regular_session_evidence(db, stored, observed_at=OBSERVED)
        db.commit()

    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 2
    loaded = rsp.load_regular_session_evidence(db, "005930", DAY)
    assert loaded["prices"] == canonical["prices"]
    assert loaded["coverage_basis"] in rsp.NAVER_REGULAR_COVERAGE_BASIS_ALIASES


def test_empty_regular_bucket_requires_matching_cross_source_absence_and_later_proof():
    rows, _naver = halted_regular_fixture()
    conflicting = rsp.regular_session_evidence(
        "005930",
        DAY,
        rows,
        observed_at=OBSERVED,
        closing_auction_evidence=naver_auction_fixture(),
    )
    assert conflicting["state"] == "unverified"
    assert "conflicts with Naver trades" in conflicting["reason"]

    trailing_rows = [
        row
        for row in minute_rows()
        if not "151000" <= row["trade_time"] <= "151900"
    ]
    trailing_naver = naver_auction_fixture()
    trailing_naver["priceInfos"]["20261012"] = [
        bucket
        for bucket in trailing_naver["priceInfos"]["20261012"]
        if bucket["localDateTime"][-6:] != "151000"
    ]
    trailing = rsp.regular_session_evidence(
        "005930",
        DAY,
        trailing_rows,
        observed_at=OBSERVED,
        closing_auction_evidence=trailing_naver,
    )
    assert trailing["state"] == "unverified"


def test_delayed_first_trade_still_requests_explicit_preopen_boundary(monkeypatch):
    from app.collectors.briefing import KisRestBriefingProvider
    from app.config import Settings
    import requests
    def unavailable(*_a, **_kw):
        raise requests.RequestException('No independent auction fixture')
    monkeypatch.setattr('app.collectors.briefing.requests.get',unavailable)
    for first, before in (('090100','090000'),('090700','090600')):
        provider=KisRestBriefingProvider(Settings())
        calls=[]
        def get(_path,_tr,params):
            cursor=params['FID_INPUT_HOUR_1'];calls.append(cursor)
            if cursor=='153100':
                return {'output2':[{'stck_bsop_date':'20261012','stck_cntg_hour':first,
                    'stck_prpr':'100','stck_oprc':'100','stck_hgpr':'100','stck_lwpr':'100',
                    'cntg_vol':'10','acml_tr_pbmn':'1000'}]}
            return {'output2':[{'stck_bsop_date':'20261008','stck_cntg_hour':'153000','acml_tr_pbmn':'9000'}]}
        monkeypatch.setattr(provider,'_get',get)
        result=provider.fetch_regular_session_data('005930',DAY)
        assert calls==['153100',before,'085900']
        assert result['preopen_baseline']=={'kind':'observed_day_boundary','requested_date':'20261012',
            'requested_time':'085900','previous_trade_date':'20261008','previous_trade_time':'153000','value':None}
        assert len(result['rows'])==1 and result['rows'][0]['trade_time']==first


def _november_11_path_fixture():
    return json.loads(
        (Path(__file__).parent / "fixtures" / "kr_2026-11-11_path_corroboration.json").read_text()
    )


def _seed_november_11_unsealed_path(db, code, fixture, *, cancelled_at="2026-11-11T09:36:53+09:00"):
    from app.models import QuantSignalIntradayPathSnapshot, QuantSignalObservedEntry
    from app.services import observed_entry, quant_signals as qs

    day = date(2026, 11, 11)
    observed = datetime(2026, 11, 12, 1, 30, tzinfo=rsp.KST)
    source = fixture["source"]
    original = rsp.regular_session_evidence(
        code, day, source["raw_rows"], observed_at=observed,
        preopen_baseline=source["preopen_baseline"],
        closing_auction_evidence=source["closing_auction_evidence"],
    )
    assert original["state"] == "bounded", original["reason"]
    rsp.store_regular_session_evidence(db, original, observed_at=observed)
    db.add(QuantSignalIntradayPathSnapshot(
        stock_code=code, trade_date=day, strategy_version=qs.STRATEGY_VERSION,
        source="kis_rest" if code == "068270" else "kis_rest+ccnl_auction",
        payload=json.dumps(fixture["prior_path"], ensure_ascii=False),
        is_final=False, observed_at=datetime(2026, 11, 11, 6, 31),
    ))
    if code == "068270":
        db.add(QuantSignalObservedEntry(
            stock_code=code, trade_date=day, policy_version=observed_entry.POLICY_VERSION,
            status="cancelled", payload=json.dumps({
                "status": "cancelled", "cancelled_at": cancelled_at,
            }), updated_at=datetime(2026, 11, 11, 0, 36),
        ))
    db.commit()
    return original, observed


@pytest.mark.parametrize("code", ["068270", "458730"])
def test_full_day_independent_minute_proof_seals_only_the_recorded_path(db, code):
    from app.models import QuantSignalIntradayPathSnapshot
    from app.services.regular_path_repair import corroborate_unfinalized_regular_path

    fixture = _november_11_path_fixture()[code]
    original, observed = _seed_november_11_unsealed_path(db, code, fixture)
    proof = {"naver": fixture["naver"]}
    if code == "458730":
        proof["yahoo"] = fixture["yahoo"]
    packaged = json.loads(Path("app/evidence/kr_2026-11-11_full_minute_paths.json").read_text())
    assert packaged[code] == proof
    day = date(2026, 11, 11)
    dry = corroborate_unfinalized_regular_path(
        db, code, day, observed_at=observed, source_proof=proof,
    )
    assert dry["state"] == "verified" and dry["persisted"] is False
    assert db.get(QuantSignalIntradayPathSnapshot, (code, day)).is_final is False
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 1

    report = corroborate_unfinalized_regular_path(
        db, code, day, observed_at=observed, persist=True, source_proof=proof,
    )
    assert report["persisted"] is True and report["notifications_sent"] == 0
    assert report["history_overwrite"] is False
    assert db.get(QuantSignalIntradayPathSnapshot, (code, day)).is_final is True
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 2
    selected = rsp.load_regular_session_evidence(db, code, day, allow_bounded=True)
    assert selected["prices"] == original["prices"]
    assert selected["turnover_bounds"] == original["turnover_bounds"]
    assert selected["full_minute_path_proof"]["prior_path"] == fixture["prior_path"]
    assert len(selected["regular_rows"]) == 381
    from app.services.regular_price_replay import regular_price_envelope, regular_ordered_paths
    envelope = regular_price_envelope(
        db, code, [DailyPrice(code=code, trade_date=day, close=selected["prices"]["close"])],
        completed_through=day, effective_from=day,
    )
    assert len(regular_ordered_paths(envelope)[day]) == 381
    if code == "458730":
        assert next(row for row in selected["regular_rows"] if row["trade_time"] == "131300")["open"] == 15145
    else:
        assert next(row for row in selected["regular_rows"] if row["trade_time"] == "151900")["volume"] == 867


@pytest.mark.parametrize("mutation", [
    "yahoo_open", "missing_yahoo", "naver_high", "naver_volume", "naver_time", "second_open", "prior_hash",
])
def test_disputed_minute_open_rejects_mutated_independent_proof(mutation):
    from hashlib import sha256

    fixture = _november_11_path_fixture()["458730"]
    source = fixture["source"]
    proof = {
        "naver": deepcopy(fixture["naver"]), "yahoo": deepcopy(fixture["yahoo"]),
        "prior_path": fixture["prior_path"],
        "prior_path_hash": sha256(rsp._json(fixture["prior_path"]).encode()).hexdigest(),
    }
    naver_row = next(row for row in proof["naver"]["rows"] if row["localDateTime"] == "20261111131300")
    if mutation == "yahoo_open":
        next(row for row in proof["yahoo"]["rows"] if row["trade_time"] == "131300")["open"] = 15140
    elif mutation == "missing_yahoo":
        proof.pop("yahoo")
    elif mutation == "naver_high":
        naver_row["highPrice"] = 15150
    elif mutation == "naver_volume":
        naver_row["accumulatedTradingVolume"] += 1
    elif mutation == "naver_time":
        naver_row["localDateTime"] = "20261111131400"
    elif mutation == "second_open":
        next(row for row in proof["naver"]["rows"] if row["localDateTime"] == "20261111131200")["openPrice"] = 15145
    else:
        proof["prior_path_hash"] = "0" * 64
    result = rsp.regular_session_evidence(
        "458730", date(2026, 11, 11), source["raw_rows"],
        observed_at=datetime(2026, 11, 12, 1, 30, tzinfo=rsp.KST),
        preopen_baseline=source["preopen_baseline"],
        closing_auction_evidence=source["closing_auction_evidence"],
        full_minute_path_proof=proof,
    )
    assert result["state"] == "unverified"


def test_full_day_source_fetches_only_dated_regular_minutes_and_one_disputed_bucket(monkeypatch):
    from app.collectors import briefing

    fixture = _november_11_path_fixture()["458730"]
    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {
                "code": "458730", "periodType": "day", "stockExchangeType": "KRX",
                "priceInfos": fixture["naver"]["rows"] + [{
                    "localDateTime": "20261111160000", "openPrice": 15140,
                }],
            }
    requests_seen = []
    yahoo_seen = []
    def fetch(url, **kwargs):
        requests_seen.append((url, kwargs["params"]))
        return Response()
    def yahoo(code, day, bucket_start):
        yahoo_seen.append((code, day, bucket_start))
        return fixture["yahoo"]
    monkeypatch.setattr(briefing.requests, "get", fetch)
    monkeypatch.setattr(briefing, "_fetch_yahoo_bucket_open", yahoo)
    source = fixture["source"]
    original = rsp.regular_session_evidence(
        "458730", date(2026, 11, 11), source["raw_rows"],
        observed_at=datetime(2026, 11, 12, 1, 30, tzinfo=rsp.KST),
        preopen_baseline=source["preopen_baseline"],
        closing_auction_evidence=source["closing_auction_evidence"],
    )
    proof = briefing.fetch_regular_path_corroboration(
        "458730", date(2026, 11, 11), original["regular_rows"],
    )
    assert len(proof["naver"]["rows"]) == 381
    assert proof["yahoo"] == fixture["yahoo"]
    assert requests_seen == [
        ("https://api.stock.naver.com/chart/domestic/item/458730", {"periodType": "day"}),
    ]
    assert yahoo_seen == [("458730", date(2026, 11, 11), "131000")]


@pytest.mark.parametrize("cancelled_at", ["2026-11-11T15:19:00+09:00", "invalid"])
def test_cancelled_watcher_never_allows_prior_or_undated_minute_revision(db, cancelled_at):
    from app.models import QuantSignalIntradayPathSnapshot
    from app.services.regular_path_repair import corroborate_unfinalized_regular_path
    from app.services.quant_signals import UnverifiedIntradayPathError

    code = "068270"
    fixture = _november_11_path_fixture()[code]
    _original, observed = _seed_november_11_unsealed_path(
        db, code, fixture, cancelled_at=cancelled_at,
    )
    with pytest.raises(UnverifiedIntradayPathError):
        corroborate_unfinalized_regular_path(
            db, code, date(2026, 11, 11), observed_at=observed,
            persist=True, source_proof={"naver": fixture["naver"]},
        )
    assert db.get(QuantSignalIntradayPathSnapshot, (code, date(2026, 11, 11))).is_final is False
    assert db.scalar(select(func.count()).select_from(SignalSessionPrice)) == 1
