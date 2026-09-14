from __future__ import annotations

from datetime import date, datetime, timezone

from app.services.us_position_lifecycle import (
    USLifecycleBar,
    _history_loader,
    _sector_etf,
    build_us_position_lifecycle_feed,
)
from app.services.us_sector_classification import (
    US_SECTOR_ETF_BY_CIK,
    US_SECTOR_ETFS,
)
from app.services.us_market_calendar import recent_us_market_session_dates


UTC = timezone.utc


def test_sector_etf_mapping_uses_only_reviewed_cik_taxonomy():
    cases = [
        ("0001403161", "Consumer Discretionary", "XLF"),  # Visa
        ("0001141391", "Consumer Discretionary", "XLF"),  # Mastercard
        ("0000858877", "Telecommunications", "XLK"),  # Cisco
        ("0000040545", "Technology", "XLI"),  # GE Aerospace
        ("0000080424", "Consumer Discretionary", "XLP"),  # P&G
        ("0001413329", "Health Care", "XLP"),  # Philip Morris
        ("0001996810", "Technology", "XLI"),  # GE Vernova
        ("0001094517", "Industrials", "XLY"),  # Toyota
        ("0001596532", "Telecommunications", "XLK"),  # Arista
        ("0000811809", "Energy", "XLB"),  # BHP
        ("0000097745", "Industrials", "XLV"),  # Thermo Fisher
        ("0000078003", "Technology", "XLV"),  # Pfizer
        ("0001181412", "Technology", "XLC"),  # SpaceX
        ("0000820313", "Industrials", "XLK"),  # Amphenol
        ("0001551182", "Technology", "XLI"),  # Eaton
    ]
    for cik, misleading_display_sector, expected in cases:
        assert (
            _sector_etf({"cik": cik, "sector": misleading_display_sector})
            == expected
        )


def test_sector_etf_taxonomy_is_versioned_complete_data_and_unknown_fails_closed():
    assert len(US_SECTOR_ETF_BY_CIK) >= 100
    assert all(len(cik) == 10 and cik.isdigit() for cik in US_SECTOR_ETF_BY_CIK)
    assert set(US_SECTOR_ETF_BY_CIK.values()) <= US_SECTOR_ETFS
    assert _sector_etf({"cik": "9999999999", "sector": "Technology"}) == ""
    assert _sector_etf({"sector": "Consumer Defensive", "market": "NASDAQ"}) == ""


def test_publication_history_loader_bypasses_any_preclose_chart_cache(monkeypatch):
    from app.services import us_market

    calls: list[dict[str, object]] = []

    def fake_chart_prices_range(symbol, **kwargs):
        calls.append({"symbol": symbol, **kwargs})
        return {}, []

    monkeypatch.setattr(us_market, "chart_prices_range", fake_chart_prices_range)

    assert _history_loader("AAPL") == []
    assert calls == [
        {
            "symbol": "AAPL",
            "range_": "2y",
            "interval": "1d",
            "refresh": True,
            "limit": 520,
            "require_adjusted_ohlc": True,
        }
    ]


def _bars(daily_return: float, *, count: int = 150) -> list[USLifecycleBar]:
    trading_dates = list(recent_us_market_session_dates(date(2026, 9, 8), count))
    price = 100.0
    result: list[USLifecycleBar] = []
    for index, trading_date in enumerate(trading_dates):
        price *= 1.0 + daily_return
        volume = 1_150_000.0 if index >= count - 5 else 1_000_000.0
        result.append(
            USLifecycleBar(
                trade_date=trading_date,
                open=price * 0.998,
                high=price * 1.01,
                low=price * 0.99,
                close=price,
                volume=volume,
                trading_value=price * volume,
            )
        )
    return result


def _universe() -> dict[str, object]:
    members = [
        {
            "code": f"A{index:03d}",
            "name": f"Issuer {index}",
            "market": "NASDAQ",
            "sector": "Technology",
            "cik": "0001045810",
            "market_cap_rank": index + 1,
            "market_cap": 1_000_000_000 - index,
        }
        for index in range(100)
    ]
    return {
        "status": "ready",
        "data_state": "ready",
        "universe_as_of": date(2026, 9, 8),
        "universe_count": 100,
        "checksum": "fixture",
        "items": members,
    }


def test_one_missing_member_history_blocks_every_new_entry():
    universe = _universe()
    stock = _bars(0.0017)
    histories = {
        "SPY": _bars(0.0007),
        "QQQ": _bars(0.0009),
        "XLK": _bars(0.0010),
        **{str(item["code"]): stock for item in universe["items"]},
    }
    histories["A099"] = []

    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=universe,
        history_loader=lambda symbol: histories.get(symbol, []),
    )

    assert payload["status"] == "degraded"
    assert payload["data_state"] == "degraded"
    assert payload["new_entries_allowed"] is False
    assert payload["evaluated_count"] == 100
    assert payload["data_coverage_count"] == 99
    assert payload["entry_pending_count"] == 0
    assert payload["items"]
    assert all(item["current"]["action"] == "entry_watch" for item in payload["items"])


def test_contiguous_short_listing_history_blocks_only_that_member():
    universe = _universe()
    stock = _bars(0.0017)
    histories = {
        "SPY": _bars(0.0007),
        "QQQ": _bars(0.0009),
        "XLK": _bars(0.0010),
        **{str(item["code"]): stock for item in universe["items"]},
    }
    histories["A099"] = stock[-45:]

    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=universe,
        history_loader=lambda symbol: histories.get(symbol, []),
    )

    assert payload["status"] == "ready"
    assert payload["data_state"] == "ready"
    assert payload["new_entries_allowed"] is True
    assert payload["data_coverage_count"] == 100
    assert payload["signal_eligible_count"] == 99
    assert payload["insufficient_history_count"] == 1
    assert payload["insufficient_history_codes"] == ["A099"]
    assert all(item["code"] != "A099" for item in payload["items"])
    assert payload["shadow_comparison"]["comparison_complete"] is True
    assert payload["shadow_comparison"]["candidate_action_counts"]["no_signal"] == 1


def test_gapped_short_history_still_blocks_all_new_entries():
    universe = _universe()
    stock = _bars(0.0017)
    short_gapped = list(stock[-46:])
    short_gapped.pop(-10)
    histories = {
        "SPY": _bars(0.0007),
        "QQQ": _bars(0.0009),
        "XLK": _bars(0.0010),
        **{str(item["code"]): stock for item in universe["items"]},
    }
    histories["A099"] = short_gapped

    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=universe,
        history_loader=lambda symbol: histories.get(symbol, []),
    )

    assert payload["status"] == "degraded"
    assert payload["new_entries_allowed"] is False
    assert payload["data_coverage_count"] == 99
    assert payload["insufficient_history_count"] == 0
    assert payload["entry_pending_count"] == 0


def test_one_unreviewed_issuer_sector_blocks_every_new_entry():
    universe = _universe()
    universe["items"][-1]["cik"] = "9999999999"
    stock = _bars(0.0017)
    histories = {
        "SPY": _bars(0.0007),
        "QQQ": _bars(0.0009),
        "XLK": _bars(0.0010),
        **{str(item["code"]): stock for item in universe["items"]},
    }

    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=universe,
        history_loader=lambda symbol: histories.get(symbol, []),
    )

    assert payload["status"] == "degraded"
    assert payload["new_entries_allowed"] is False
    assert payload["sector_classification_error_count"] == 1
    assert payload["sector_classification_errors"] == {"A099": "9999999999"}
    assert payload["data_coverage_count"] == 99
    assert payload["entry_pending_count"] == 0


def test_one_mid_series_session_gap_blocks_every_new_entry():
    universe = _universe()
    stock = _bars(0.0017)
    gapped = list(stock)
    gapped.pop(-10)
    histories = {
        "SPY": _bars(0.0007),
        "QQQ": _bars(0.0009),
        "XLK": _bars(0.0010),
        **{str(item["code"]): stock for item in universe["items"]},
    }
    histories["A099"] = gapped

    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=universe,
        history_loader=lambda symbol: histories.get(symbol, []),
    )

    assert payload["status"] == "degraded"
    assert payload["new_entries_allowed"] is False
    assert payload["data_coverage_count"] == 99
    assert payload["entry_pending_count"] == 0


def test_empty_history_response_cannot_create_watch_or_pending_candidates():
    payload = build_us_position_lifecycle_feed(
        limit=100,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload=_universe(),
        history_loader=lambda _symbol: [],
    )

    assert payload["status"] == "degraded"
    assert payload["data_state"] == "degraded"
    assert payload["new_entries_allowed"] is False
    assert payload["evaluated_count"] == 100
    assert payload["data_coverage_count"] == 0
    assert payload["preliminary_count"] == 0
    assert payload["entry_pending_count"] == 0
    assert payload["items"] == []
