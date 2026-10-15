from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json

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
    assert "opening trade anchor" in result["reason"]


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
