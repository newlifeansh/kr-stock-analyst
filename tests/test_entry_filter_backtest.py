import json
from datetime import date

from app.models import MarketQuantSignalSnapshot
from app.services import entry_filter_backtest as shadow
from app.services import quant_signals as qs


class _FakeDb:
    def __init__(self) -> None:
        self.snapshot = None
        self.added = []

    def scalar(self, _statement):
        return date(2026, 9, 4)

    def get(self, _model, _key):
        return self.snapshot

    def add(self, value):
        self.added.append(value)
        self.snapshot = value

    def commit(self) -> None:
        return None


class _HistoryCountDb:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _statement):
        return self

    def all(self):
        return self.rows


def test_shadow_history_backfill_repairs_short_staging_history(monkeypatch) -> None:
    db = _HistoryCountDb([("000001", 38), ("000002", qs.MIN_BACKTEST_HISTORY_ROWS)])
    calls = []

    def fake_collect(_db, codes, **kwargs):
        calls.append((codes, kwargs))
        return 31700

    monkeypatch.setattr("app.collectors.krx.collect_prices_for_codes", fake_collect)

    result = shadow._ensure_shadow_history(
        db,
        ["000001", "000002"],
        latest_price_date=date(2026, 10, 7),
    )

    assert result == {"requested_codes": 1, "rows_loaded": 31700}
    assert calls == [
        (
            ["000001"],
            {
                "from_yyyymmdd": "20250214",
                "to_yyyymmdd": "20261007",
                "max_workers": shadow.SHADOW_HISTORY_MAX_WORKERS,
            },
        )
    ]


def test_codes_needing_shadow_history_are_deterministic() -> None:
    assert shadow._codes_needing_shadow_history(
        {"000002": 317, "000001": 0, "000003": 316}
    ) == ["000001", "000003"]


def test_shadow_backtest_refreshes_once_per_latest_price_date(monkeypatch) -> None:
    db = _FakeDb()
    calls = []

    def fake_build(_db, **_kwargs):
        calls.append(True)
        return {
            "latest_price_date": date(2026, 9, 4),
            "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
            "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
            "symbols_evaluated": 99,
            "forward_comparison": {
                "version": "entry-filter-fixed-cohort-forward-v1",
                "filters": {version: {} for version in shadow.FILTER_VERSIONS},
                "rolling_last_trades": {version: {} for version in shadow.FILTER_VERSIONS},
            },
            "aggregate": {
                version: {"symbols": 99}
                for version in shadow.FILTER_VERSIONS
            },
        }

    monkeypatch.setattr(shadow, "build_entry_filter_shadow_report", fake_build)

    first = shadow.refresh_entry_filter_shadow_snapshot(db)
    second = shadow.refresh_entry_filter_shadow_snapshot(db)
    forced = shadow.refresh_entry_filter_shadow_snapshot(db, force=True)

    assert first["status"] == "refreshed"
    assert second["status"] == "unchanged"
    assert forced["status"] == "refreshed"
    assert len(calls) == 2
    assert db.snapshot.cache_key == shadow.ENTRY_FILTER_SHADOW_CACHE_KEY
    assert db.snapshot.cache_key.endswith(qs.CANDIDATE_STRATEGY_VERSION)
    assert json.loads(db.snapshot.payload)["symbols_evaluated"] == 99


def test_shadow_refresh_rebuilds_legacy_report_with_same_price_date(monkeypatch) -> None:
    db = _FakeDb()
    db.snapshot = MarketQuantSignalSnapshot(
        cache_key=shadow.ENTRY_FILTER_SHADOW_CACHE_KEY,
        payload=json.dumps(
            {
                "latest_price_date": "2026-09-04",
                "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
                "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
                "symbols_evaluated": 99,
            }
        ),
    )
    calls = []

    def fake_build(_db, **_kwargs):
        calls.append(True)
        return {
            "latest_price_date": date(2026, 9, 4),
            "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
            "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
            "symbols_evaluated": 99,
            "forward_comparison": {
                "version": "entry-filter-fixed-cohort-forward-v1",
                "filters": {version: {} for version in shadow.FILTER_VERSIONS},
                "rolling_last_trades": {version: {} for version in shadow.FILTER_VERSIONS},
            },
        }

    monkeypatch.setattr(shadow, "build_entry_filter_shadow_report", fake_build)

    result = shadow.refresh_entry_filter_shadow_snapshot(db)

    assert result["status"] == "refreshed"
    assert len(calls) == 1


def test_zero_symbol_shadow_report_is_not_current() -> None:
    report = {
        "candidate_strategy_version": qs.CANDIDATE_STRATEGY_VERSION,
        "active_entry_filter_version": qs.ENTRY_FILTER_VERSION,
        "symbols_evaluated": 0,
        "forward_comparison": {
            "version": "entry-filter-fixed-cohort-forward-v1",
            "filters": {version: {} for version in shadow.FILTER_VERSIONS},
            "rolling_last_trades": {version: {} for version in shadow.FILTER_VERSIONS},
        },
    }

    assert shadow._shadow_report_is_current(report) is False


def test_shadow_refresh_is_separate_from_user_signal_snapshot() -> None:
    assert shadow.ENTRY_FILTER_SHADOW_CACHE_KEY != qs.market_quant_signal_snapshot_key(
        qs.MARKET_SIGNAL_UNIVERSE_LIMIT,
        qs.MARKET_SIGNAL_FEED_LIMIT,
        qs.MARKET_SIGNAL_RECENT_DAYS,
    )
    assert MarketQuantSignalSnapshot.__tablename__ == "market_quant_signal_snapshot"
    assert shadow.FILTER_VERSIONS == (
        qs.ENTRY_FILTER_BASELINE_VERSION,
        qs.ENTRY_FILTER_H1_VERSION,
        qs.ENTRY_FILTER_H2_VERSION,
        qs.ENTRY_FILTER_H3_VERSION,
    )


def _promotion_fixture(h3_completed: int, h3_recent: int) -> tuple[dict, dict]:
    aggregate = {
        version: {
            "completed_trades": 50,
            "average_trade_return": 1.0,
            "average_max_drawdown": -1.0,
        }
        for version in shadow.FILTER_VERSIONS
    }
    aggregate[qs.ENTRY_FILTER_H3_VERSION].update(
        {
            "completed_trades": h3_completed,
            "average_trade_return": 1.2,
            "average_max_drawdown": -0.8,
        }
    )
    rolling = {
        version: {
            "completed_trades": 20,
            "average_trade_return": 0.8,
        }
        for version in shadow.FILTER_VERSIONS
    }
    rolling[qs.ENTRY_FILTER_H3_VERSION].update(
        {
            "completed_trades": h3_recent,
            "average_trade_return": 1.1,
        }
    )
    return aggregate, rolling


def test_h3_promotion_stays_shadow_until_fixed_cohort_samples_are_sufficient() -> None:
    aggregate, rolling = _promotion_fixture(h3_completed=39, h3_recent=19)

    assessment = shadow._h3_promotion_assessment(aggregate, rolling)

    assert assessment["status"] == "shadow_collecting"
    assert assessment["eligible_for_operator_review"] is False
    assert assessment["automatic_promotion"] is False
    assert assessment["operator_approval_required"] is True


def test_h3_promotion_can_only_become_eligible_for_operator_review() -> None:
    aggregate, rolling = _promotion_fixture(h3_completed=40, h3_recent=20)

    assessment = shadow._h3_promotion_assessment(aggregate, rolling)

    assert assessment["status"] == "eligible_for_operator_review"
    assert assessment["eligible_for_operator_review"] is True
    assert assessment["automatic_promotion"] is False
    assert all(assessment["checks"].values())


def test_h3_promotion_with_enough_samples_stays_ineligible_when_quality_fails() -> None:
    aggregate, rolling = _promotion_fixture(h3_completed=40, h3_recent=20)
    rolling[qs.ENTRY_FILTER_H3_VERSION]["average_trade_return"] = -0.1

    assessment = shadow._h3_promotion_assessment(aggregate, rolling)

    assert assessment["status"] == "shadow_not_eligible"
    assert assessment["eligible_for_operator_review"] is False
    assert assessment["checks"]["minimum_forward_trades"] is True
    assert assessment["checks"]["minimum_recent_trades"] is True
    assert assessment["checks"]["positive_recent_expectancy"] is False
    assert assessment["automatic_promotion"] is False
