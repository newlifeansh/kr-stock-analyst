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


def test_shadow_backtest_refreshes_once_per_latest_price_date(monkeypatch) -> None:
    db = _FakeDb()
    calls = []

    def fake_build(_db, **_kwargs):
        calls.append(True)
        return {
            "latest_price_date": date(2026, 9, 4),
            "symbols_evaluated": 99,
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
