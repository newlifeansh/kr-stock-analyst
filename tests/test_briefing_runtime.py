from datetime import date, datetime, timedelta
from types import SimpleNamespace

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


def test_fundamental_snapshot_collection_refreshes_before_quality_sla_cliff():
    daily_runtime = briefing.BriefingRuntime(
        Settings(
            fundamental_snapshot_poll_seconds=86_400,
            fundamental_snapshot_refresh_days=2,
        )
    )
    two_day_poll_runtime = briefing.BriefingRuntime(
        Settings(
            fundamental_snapshot_poll_seconds=172_800,
            fundamental_snapshot_refresh_days=3,
        )
    )
    always_refresh_runtime = briefing.BriefingRuntime(
        Settings(
            fundamental_snapshot_poll_seconds=86_400,
            fundamental_snapshot_refresh_days=1,
        )
    )

    assert daily_runtime._fundamental_snapshot_collection_refresh_days() == 1
    assert two_day_poll_runtime._fundamental_snapshot_collection_refresh_days() == 1
    assert always_refresh_runtime._fundamental_snapshot_collection_refresh_days() == 0
    assert daily_runtime._fundamental_snapshot_effective_poll_seconds() == 86_400
    assert always_refresh_runtime._fundamental_snapshot_effective_poll_seconds() == 43_200

    unsafe_runtime = briefing.BriefingRuntime(
        Settings(
            fundamental_snapshot_poll_seconds=259_200,
            fundamental_snapshot_refresh_days=2,
        )
    )
    assert unsafe_runtime._fundamental_snapshot_effective_poll_seconds() == 86_400
    assert unsafe_runtime._fundamental_snapshot_collection_refresh_days() == 1


def test_briefing_runtime_passes_fundamental_refresh_headroom_to_collector(monkeypatch):
    runtime = briefing.BriefingRuntime(
        Settings(
            briefing_realtime_enabled=False,
            research_enabled=False,
            disclosure_enabled=False,
            news_enabled=False,
            price_enabled=False,
            stock_universe_enabled=False,
            investor_flow_enabled=False,
            financials_enabled=False,
            fundamental_snapshot_enabled=True,
            fundamental_snapshot_poll_seconds=86_400,
            fundamental_snapshot_refresh_days=2,
            stock_news_snapshot_enabled=False,
            stock_company_snapshot_enabled=False,
            macro_enabled=False,
        )
    )
    calls = []

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(briefing, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        briefing,
        "collect_stock_fundamental_snapshots",
        lambda db, **kwargs: calls.append((db, kwargs))
        or {"rows_loaded": 0, "message": "target=0 refreshed=0"},
    )

    runtime.run_once()

    assert len(calls) == 2
    assert calls[0][1]["limit"] == briefing.FUNDAMENTAL_SIGNAL_UNIVERSE_LIMIT
    assert calls[0][1]["refresh_days"] == 1
    assert calls[1][1].get("limit") is None
    assert calls[1][1]["refresh_days"] == 2
    assert all(
        call[1]["max_workers"] == runtime.settings.fundamental_snapshot_max_workers
        for call in calls
    )


def test_fundamental_snapshot_partial_failure_is_degraded_and_retried(monkeypatch):
    runtime = briefing.BriefingRuntime(
        Settings(
            briefing_realtime_enabled=False,
            research_enabled=False,
            disclosure_enabled=False,
            news_enabled=False,
            price_enabled=False,
            stock_universe_enabled=False,
            investor_flow_enabled=False,
            financials_enabled=False,
            fundamental_snapshot_enabled=True,
            fundamental_snapshot_poll_seconds=86_400,
            fundamental_snapshot_refresh_days=2,
            stock_news_snapshot_enabled=False,
            stock_company_snapshot_enabled=False,
            macro_enabled=False,
        )
    )

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    results = [
        {"rows_loaded": 0, "failed": 1, "message": "unavailable=1"},
        {"rows_loaded": 0, "failed": 0, "message": "unavailable=0"},
        {"rows_loaded": 0, "failed": 0, "message": "unavailable=0"},
        {"rows_loaded": 0, "failed": 0, "message": "unavailable=0"},
    ]
    monkeypatch.setattr(briefing, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        briefing,
        "collect_stock_fundamental_snapshots",
        lambda *_args, **_kwargs: results.pop(0),
    )

    runtime.run_once()

    assert runtime.last_fundamental_snapshot_state == "degraded"
    assert runtime.last_fundamental_snapshot_priority_failed == 1
    assert runtime.last_fundamental_snapshot_full_failed == 0
    assert runtime.next_fundamental_snapshot_retry_at is not None
    assert runtime._fundamental_snapshot_due() is False
    assert "priority_failed=1" in runtime.source_errors["fundamental_snapshot"]

    runtime.next_fundamental_snapshot_retry_at = datetime.utcnow() - timedelta(seconds=1)
    runtime.run_once()

    assert runtime.last_fundamental_snapshot_state == "ready"
    assert runtime.last_fundamental_snapshot_priority_failed == 0
    assert runtime.last_fundamental_snapshot_full_failed == 0
    assert runtime.next_fundamental_snapshot_retry_at is None
    assert "fundamental_snapshot" not in runtime.source_errors


def test_fundamental_snapshot_refresh_zero_avoids_duplicate_priority_fetch(monkeypatch):
    runtime = briefing.BriefingRuntime(
        Settings(
            briefing_realtime_enabled=False,
            research_enabled=False,
            disclosure_enabled=False,
            news_enabled=False,
            price_enabled=False,
            stock_universe_enabled=False,
            investor_flow_enabled=False,
            financials_enabled=False,
            fundamental_snapshot_enabled=True,
            fundamental_snapshot_refresh_days=0,
            stock_news_snapshot_enabled=False,
            stock_company_snapshot_enabled=False,
            macro_enabled=False,
        )
    )
    calls = []

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(briefing, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        briefing,
        "collect_stock_fundamental_snapshots",
        lambda _db, **kwargs: calls.append(kwargs)
        or {"rows_loaded": 0, "failed": 0, "message": "unavailable=0"},
    )

    runtime.run_once()

    assert len(calls) == 1
    assert calls[0].get("limit") is None
    assert calls[0]["refresh_days"] == 0


def test_collect_prices_uses_krx_market_before_fallback(monkeypatch):
    calls = []
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=3))
    monkeypatch.setattr(briefing, "is_korea_market_session_date", lambda *_args: True)
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 0, "coverage_ratio": 0.0})
    monkeypatch.setattr(
        runtime,
        "_repair_signal_price_ohlc",
        lambda db, target, **_kwargs: 0,
    )

    def fake_market(db, yyyymmdd, market):
        calls.append(("krx", yyyymmdd, market))
        return 10 if market == "KOSPI" else 20

    monkeypatch.setattr(briefing, "collect_market_prices", fake_market)
    monkeypatch.setattr(briefing, "collect_naver_quotes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Naver should not be called")))
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(object(), now=datetime(2026, 8, 21, 12, 0))

    assert result["source"] == "krx_market"
    assert result["rows_loaded"] == 30
    assert [call[2] for call in calls] == ["KOSPI", "KOSDAQ"]


def test_collect_prices_falls_back_to_naver_full_quotes(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(briefing, "is_korea_market_session_date", lambda *_args: True)
    calls = []
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 0, "coverage_ratio": 0.0})
    monkeypatch.setattr(
        runtime,
        "_repair_signal_price_ohlc",
        lambda db, target, **_kwargs: 0,
    )

    def fake_market(db, yyyymmdd, market):
        calls.append(("krx", market))
        raise RuntimeError(f"{market} unavailable")

    def fake_naver(db, yyyymmdd, markets, limit, max_workers):
        calls.append(("naver", markets, limit, max_workers))
        return 2710

    monkeypatch.setattr(briefing, "collect_market_prices", fake_market)
    monkeypatch.setattr(briefing, "collect_naver_quotes", fake_naver)
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(
        object(),
        now=datetime(2026, 8, 21, 12, 0),
    )

    assert result["source"] == "naver_full_quotes"
    assert result["rows_loaded"] == 2710
    assert calls[:2] == [("krx", "KOSPI"), ("krx", "KOSDAQ")]
    assert calls[2] == ("naver", "KOSPI,KOSDAQ", None, 5)


def test_collect_prices_force_finalizes_naver_fallback_after_close(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(briefing, "is_korea_market_session_date", lambda *_args: True)
    monkeypatch.setattr(
        runtime,
        "_latest_price_coverage",
        lambda _db, _target: {"total": 100, "fresh": 0, "coverage_ratio": 0.0},
    )
    monkeypatch.setattr(
        briefing,
        "collect_market_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("KRX unavailable")),
    )
    monkeypatch.setattr(briefing, "collect_naver_quotes", lambda *_args, **_kwargs: 2710)
    calls = []

    def finalize(_db, target, *, force=False):
        calls.append((target, force))
        return 99

    monkeypatch.setattr(runtime, "_repair_signal_price_ohlc", finalize)

    result = runtime._collect_prices(
        object(),
        now=datetime(2026, 8, 21, 16, 40),
    )

    assert result["source"] == "naver_quotes+naver_ohlc_repair"
    assert result["rows_loaded"] == 2809
    assert calls == [(date(2026, 8, 21), True)]
    assert runtime.last_post_close_price_repair_date == date(2026, 8, 21)


def test_collect_prices_skips_when_latest_coverage_is_already_high(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(briefing, "is_korea_market_session_date", lambda *_args: True)
    monkeypatch.setattr(runtime, "_latest_price_coverage", lambda db, target: {"total": 100, "fresh": 98, "coverage_ratio": 0.98})
    monkeypatch.setattr(briefing, "collect_market_prices", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("KRX should not be called")))
    monkeypatch.setattr(briefing, "collect_naver_quotes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Naver should not be called")))
    monkeypatch.setattr(briefing, "collect_prices_for_codes", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Code fallback should not be called")))

    result = runtime._collect_prices(
        object(),
        now=datetime(2026, 8, 21, 12, 0),
    )

    assert result["source"] == "existing_prices"
    assert result["rows_loaded"] == 0
    assert "fresh=98/100" in result["message"]


def test_collect_prices_finalizes_top_signal_ohlc_once_after_close(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(briefing, "is_korea_market_session_date", lambda *_args: True)
    monkeypatch.setattr(
        runtime,
        "_latest_price_coverage",
        lambda _db, _target: {"total": 100, "fresh": 99, "coverage_ratio": 0.99},
    )
    calls = []

    def finalize(_db, target, *, force=False):
        calls.append((target, force))
        return 99

    monkeypatch.setattr(runtime, "_repair_signal_price_ohlc", finalize)
    monkeypatch.setattr(
        briefing,
        "collect_market_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("coverage path must not start a full KRX collection")
        ),
    )

    first = runtime._collect_prices(object(), now=datetime(2026, 8, 21, 16, 40))
    second = runtime._collect_prices(object(), now=datetime(2026, 8, 21, 17, 10))

    assert first["source"] == "post_close_price_ohlc_finalize"
    assert first["rows_loaded"] == 99
    assert calls == [(date(2026, 8, 21), True)]
    assert second["source"] == "existing_prices"


def test_post_close_price_repair_waits_for_official_close_publication():
    runtime = briefing.BriefingRuntime(Settings())

    assert runtime._post_close_price_repair_due(
        datetime(2026, 8, 21, 16, 34),
    ) is False
    assert runtime._post_close_price_repair_due(
        datetime(2026, 8, 21, 16, 35),
    ) is True

    runtime.last_post_close_price_repair_date = date(2026, 8, 21)
    assert runtime._post_close_price_repair_due(
        datetime(2026, 8, 21, 17, 0),
    ) is False


def test_signal_ohlc_repair_uses_kis_as_final_writer(monkeypatch):
    runtime = briefing.BriefingRuntime(
        Settings(kis_app_key="key", kis_app_secret="secret", price_max_workers=5)
    )
    daily_row = SimpleNamespace(
        code="010060",
        volume=39_887,
        trading_value=10_769_490_000,
    )

    class Database:
        def __init__(self):
            self.commits = 0

        def execute(self, _statement):
            return [(daily_row.code, daily_row)]

        def commit(self):
            self.commits += 1

    db = Database()
    final_row = {
        "code": "010060",
        "trade_date": date(2026, 8, 21),
        "open": 280_500,
        "high": 283_500,
        "low": 259_500,
        "close": 265_000,
        "volume": 276_693,
        "trading_value": 74_863_818_500,
        "market_cap": None,
        "listed_shares": None,
    }
    runtime.market_provider = SimpleNamespace(
        is_configured=lambda: True,
        fetch_daily_price_rows=lambda codes, target: [
            final_row
        ] if codes == ["010060"] and target == date(2026, 8, 21) else [],
    )
    monkeypatch.setattr(
        briefing,
        "collect_naver_price_history_for_codes",
        lambda *_args, **_kwargs: 10,
    )
    monkeypatch.setattr(
        briefing,
        "collect_naver_krx_price_rows_for_codes",
        lambda *_args, **_kwargs: 1,
    )
    captured = []

    def fake_upsert(_db, model, rows):
        captured.append((model, rows))
        return len(rows)

    monkeypatch.setattr(briefing, "upsert_many", fake_upsert)

    repaired = runtime._repair_signal_price_ohlc(
        db,
        date(2026, 8, 21),
        force=True,
    )

    assert repaired == 12
    assert captured == [(briefing.DailyPrice, [final_row])]
    assert db.commits == 1


def test_collect_prices_does_not_create_weekend_rows(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=5))
    monkeypatch.setattr(
        briefing,
        "is_korea_market_session_date",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        briefing,
        "collect_market_prices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("market collector must not run")),
    )
    monkeypatch.setattr(runtime, "_repair_signal_price_ohlc", lambda *_args: 0)

    result = runtime._collect_prices(object(), now=datetime(2026, 8, 2, 10, 0))

    assert result == {
        "source": "market_closed",
        "rows_loaded": 0,
        "message": "date=20260802 skipped_non_trading_day",
    }


def test_price_ohlc_repair_covers_incomplete_stocks_beyond_top_100(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(price_max_workers=4))
    rows = [
        SimpleNamespace(
            code=f"{index:06d}",
            open=100,
            high=110,
            low=90,
            close=105,
            volume=1_000,
            trading_value=105_000,
        )
        for index in range(1, 102)
    ]
    rows[-1].open = None
    rows[-1].high = None
    rows[-1].low = None

    class Database:
        def execute(self, _statement):
            return [(row.code, row) for row in rows] + [("999999", None)]

    calls = []
    monkeypatch.setattr(
        briefing,
        "collect_naver_price_history_for_codes",
        lambda _db, codes, **_kwargs: calls.append(("history", codes)) or 1,
    )
    monkeypatch.setattr(
        briefing,
        "collect_naver_krx_price_rows_for_codes",
        lambda _db, codes, _target, **_kwargs: calls.append(("chart", codes)) or 1,
    )
    monkeypatch.setattr(runtime, "_finalize_signal_price_ohlc_from_kis", lambda *_args: 0)

    repaired = runtime._repair_signal_price_ohlc(
        Database(),
        date(2026, 8, 28),
    )

    assert repaired == 2
    assert calls == [
        ("history", ["000101", "999999"]),
        ("chart", ["000101", "999999"]),
    ]


def test_collect_prices_repairs_previous_session_ohlc_after_midnight(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings())
    monkeypatch.setattr(
        briefing,
        "is_korea_market_session_date",
        lambda *_args: False,
    )
    monkeypatch.setattr(
        briefing,
        "latest_completed_korea_market_session_date",
        lambda _now=None: date(2026, 8, 20),
    )
    calls = []
    monkeypatch.setattr(
        runtime,
        "_repair_signal_price_ohlc",
        lambda _db, target: calls.append(target) or 870,
    )

    result = runtime._collect_prices(
        object(),
        now=datetime(2026, 8, 21, 1, 10),
    )

    assert result["source"] == "previous_session_price_ohlc_repair"
    assert result["rows_loaded"] == 870
    assert calls == [date(2026, 8, 20)]


def test_price_coverage_requires_a_complete_coherent_daily_candle():
    runtime = briefing.BriefingRuntime(Settings())

    class Rows:
        def all(self):
            return [("005930",), ("096770",)]

    class Database:
        def execute(self, _statement):
            return Rows()

        def scalars(self, _statement):
            return [
                SimpleNamespace(
                    code="005930",
                    open=80_000,
                    high=81_000,
                    low=79_000,
                    close=80_500,
                ),
                SimpleNamespace(
                    code="096770",
                    open=None,
                    high=None,
                    low=None,
                    close=128_700,
                ),
            ]

    coverage = runtime._latest_price_coverage(Database(), "20260811")

    assert coverage == {
        "total": 2,
        "fresh": 1,
        "coverage_ratio": 0.5,
    }


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


def test_collect_investor_flows_fetches_only_stale_codes(monkeypatch):
    runtime = briefing.BriefingRuntime(
        Settings(investor_flow_pages=1, investor_flow_max_workers=3)
    )
    calls = []
    monkeypatch.setattr(
        runtime,
        "_latest_investor_flow_coverage",
        lambda db: {
            "target_date": date(2026, 8, 11),
            "total": 100,
            "fresh": 10,
            "coverage_ratio": 0.10,
            "stale_codes": ["005930"],
        },
    )

    def fake_collect(db, *, codes, pages, max_workers):
        calls.append((codes, pages, max_workers))
        return 2

    monkeypatch.setattr(briefing, "collect_naver_investor_flows", fake_collect)

    result = runtime._collect_investor_flows(object())

    assert result["source"] == "naver_investor_flow"
    assert result["rows_loaded"] == 2
    assert result["message"].endswith("stale=1")
    assert calls == [(["005930"], 1, 3)]


def test_investor_flow_coverage_uses_market_calendar_when_prices_are_stale(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings())

    class Rows:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class Database:
        def __init__(self):
            self.execute_calls = 0

        def scalar(self, _statement):
            return date(2026, 8, 6)

        def execute(self, _statement):
            self.execute_calls += 1
            if self.execute_calls == 1:
                return Rows([("005930",), ("000660",)])
            return Rows([
                ("005930", date(2026, 8, 7)),
                ("000660", date(2026, 8, 11)),
            ])

    monkeypatch.setattr(
        briefing,
        "latest_completed_korea_market_session_date",
        lambda _now=None: date(2026, 8, 11),
    )

    coverage = runtime._latest_investor_flow_coverage(
        Database(),
        now=datetime(2026, 8, 12, 9, 27),
    )

    assert coverage == {
        "target_date": date(2026, 8, 11),
        "total": 2,
        "fresh": 1,
        "coverage_ratio": 0.5,
        "stale_codes": ["005930"],
    }


def test_investor_flow_coverage_applies_configured_signal_universe_limit(monkeypatch):
    runtime = briefing.BriefingRuntime(Settings(investor_flow_code_limit=100))
    observed_limits = []

    class Rows:
        def __init__(self, values):
            self.values = values

        def all(self):
            return self.values

    class Database:
        def __init__(self):
            self.execute_calls = 0

        def scalar(self, _statement):
            return date(2026, 8, 21)

        def execute(self, statement):
            self.execute_calls += 1
            if self.execute_calls == 1:
                observed_limits.append(statement._limit_clause.value)
                return Rows([("005930",), ("000660",)])
            return Rows([])

    monkeypatch.setattr(
        briefing,
        "latest_completed_korea_market_session_date",
        lambda _now=None: date(2026, 8, 21),
    )

    coverage = runtime._latest_investor_flow_coverage(
        Database(),
        now=datetime(2026, 8, 21, 21, 0),
    )

    assert observed_limits == [100]
    assert coverage["total"] == 2
    assert coverage["stale_codes"] == ["005930", "000660"]


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
