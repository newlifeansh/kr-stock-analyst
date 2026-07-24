from datetime import datetime, timedelta

from app.config import Settings
from app.services import briefing


def test_research_backfill_runs_daily_not_every_poll():
    runtime = briefing.BriefingRuntime(Settings(research_backfill_poll_seconds=86400))

    assert runtime._research_backfill_due() is True


def test_briefing_snapshot_uses_separate_storage_cadence():
    runtime = briefing.BriefingRuntime(
        Settings(briefing_poll_seconds=30, briefing_snapshot_seconds=300)
    )

    assert runtime._briefing_snapshot_due() is True

    runtime.last_briefing_at = datetime.utcnow()
    assert runtime._briefing_snapshot_due() is False

    runtime.last_briefing_at = datetime.utcnow() - timedelta(seconds=301)
    assert runtime._briefing_snapshot_due() is True

    runtime.last_research_backfill_at = datetime.utcnow()
    assert runtime._research_backfill_due() is False

    runtime.last_research_backfill_at = datetime.utcnow() - timedelta(days=2)
    assert runtime._research_backfill_due() is True


def test_collect_prices_uses_krx_market_before_fallback(monkeypatch):
    calls = []
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=3))
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 0, "coverage_ratio": 0.0})

    def fake_market(db, yyyymmdd, market):
        calls.append(("krx", yyyymmdd, market))
        return 10 if market == "KOSPI" else 20

    monkeypatch.setattr(briefing, "collect_market_prices", fake_market)
    monkeypatch.setattr(briefing, "collect_naver_quotes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Naver should not be called")))
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(object())

    assert result["source"] == "krx_market"
    assert result["rows_loaded"] == 30
    assert [call[2] for call in calls] == ["KOSPI", "KOSDAQ"]


def test_collect_prices_falls_back_to_naver_full_quotes(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    calls = []
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 0, "coverage_ratio": 0.0})

    def fake_market(db, yyyymmdd, market):
        calls.append(("krx", market))
        raise RuntimeError(f"{market} unavailable")

    def fake_naver(db, yyyymmdd, markets, limit, max_workers):
        calls.append(("naver", markets, limit, max_workers))
        return 2710

    monkeypatch.setattr(briefing, "collect_market_prices", fake_market)
    monkeypatch.setattr(briefing, "collect_naver_quotes", fake_naver)
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(object())

    assert result["source"] == "naver_full_quotes"
    assert result["rows_loaded"] == 2710
    assert calls[:2] == [("krx", "KOSPI"), ("krx", "KOSDAQ")]
    assert calls[2] == ("naver", "KOSPI,KOSDAQ", None, 5)


def test_collect_prices_skips_when_latest_coverage_is_already_high(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 98, "coverage_ratio": 0.98})
    monkeypatch.setattr(briefing, "collect_market_prices", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("KRX should not be called")))
    monkeypatch.setattr(briefing, "collect_naver_quotes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Naver should not be called")))
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(object())

    assert result["source"] == "existing_prices"
    assert result["rows_loaded"] == 0
    assert "fresh=98/100" in result["message"]


def test_collect_investor_flows_skips_when_latest_coverage_is_already_high(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(investor_flow_max_workers=5))
    monkeypatch.setattr(
        runtime,
        "_latest_investor_flow_coverage",
        lambda db: {"target_date": "2026-06-24", "total": 100, "fresh": 99, "coverage_ratio": 0.99},
    )
    monkeypatch.setattr(
        briefing,
        "collect_naver_investor_flows",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Naver should not be called")),
    )

    result = runtime._collect_investor_flows(object())

    assert result["source"] == "existing_investor_flows"
    assert result["rows_loaded"] == 0
    assert "fresh=99/100" in result["message"]


def test_collect_investor_flows_uses_naver_when_coverage_is_low(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(investor_flow_pages=2, investor_flow_max_workers=3))
    calls = []
    monkeypatch.setattr(
        runtime,
        "_latest_investor_flow_coverage",
        lambda db: {"target_date": "2026-06-24", "total": 100, "fresh": 10, "coverage_ratio": 0.10},
    )

    def fake_collect(db, markets, pages, limit, max_workers):
        calls.append((markets, pages, limit, max_workers))
        return 200

    monkeypatch.setattr(briefing, "collect_naver_investor_flows", fake_collect)

    result = runtime._collect_investor_flows(object())

    assert result["source"] == "naver_investor_flow"
    assert result["rows_loaded"] == 200
    assert calls == [("KOSPI,KOSDAQ", 2, None, 3)]


def test_collect_macro_skips_when_default_series_are_fresh(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(macro_range="1y"))
    monkeypatch.setattr(
        runtime,
        "_latest_macro_coverage",
        lambda db: {"total": 6, "fresh": 6, "fresh_since": "2026-06-18", "coverage_ratio": 1.0},
    )
    monkeypatch.setattr(
        briefing,
        "collect_yahoo_macro_observations",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Yahoo macro should not be called")),
    )

    result = runtime._collect_macro(object())

    assert result["source"] == "existing_macro"
    assert result["rows_loaded"] == 0
    assert "fresh=6/6" in result["message"]


def test_collect_macro_uses_yahoo_when_series_are_missing(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(macro_range="6mo"))
    calls = []
    monkeypatch.setattr(
        runtime,
        "_latest_macro_coverage",
        lambda db: {"total": 6, "fresh": 2, "fresh_since": "2026-06-18", "coverage_ratio": 0.33},
    )

    def fake_collect(db, range_):
        calls.append(range_)
        return 300

    monkeypatch.setattr(briefing, "collect_yahoo_macro_observations", fake_collect)

    result = runtime._collect_macro(object())

    assert result["source"] == "yahoo_macro"
    assert result["rows_loaded"] == 300
    assert calls == ["6mo"]
