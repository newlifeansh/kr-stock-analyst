from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from app.services.position_lifecycle_core import (
    calculate_indicators,
    chase_entry_veto_reason,
)
from app.services import us_position_lifecycle as lifecycle
from app.services.us_position_lifecycle import (
    US_CHASE_POLICY,
    US_LIFECYCLE_REPLAY_VERSION,
    US_REENTRY_RUNTIME_ENABLED,
    US_ROLLOUT_MODE,
    US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
    US_STRATEGY_VERSION,
    USLifecycleBar,
    _aligned_recent_sessions,
    _load_histories,
    build_us_member_public_evidence,
    build_us_position_lifecycle_feed,
    evaluate_us_entry_candidate,
    evaluate_us_momentum_watch_baseline,
    replay_us_position_lifecycle,
    us_entry_execution_allowed,
    us_price_bars,
    us_reentry_allowed,
)
from app.services.us_market_calendar import recent_us_market_session_dates


UTC = timezone.utc


def test_us_history_loader_retries_only_transient_failures_with_lower_concurrency():
    attempts: dict[str, int] = {}

    def loader(symbol: str) -> list[str]:
        attempts[symbol] = attempts.get(symbol, 0) + 1
        if symbol == "NVDA" and attempts[symbol] < 3:
            raise RuntimeError("temporary throttle")
        if symbol == "BROKEN":
            raise RuntimeError("permanent failure")
        return [symbol]

    histories, errors = _load_histories(["SPY", "NVDA", "BROKEN"], loader)

    assert histories == {"SPY": ["SPY"], "NVDA": ["NVDA"]}
    assert errors == {"BROKEN": "permanent failure"}
    assert attempts == {"SPY": 1, "NVDA": 3, "BROKEN": 3}


def test_us_feed_retries_a_symbol_missing_the_completed_session():
    complete = _bars(daily_return=0.001)
    members = [
        {
            "code": f"A{index:03d}",
            "name": f"Stock {index}",
            "market": "NASDAQ",
            "sector": "Technology",
            "cik": "0001045810",
            "market_cap_rank": index + 1,
            "market_cap": 1_000_000_000 - index,
        }
        for index in range(100)
    ]
    attempts: dict[str, int] = {}

    def loader(symbol: str) -> list[USLifecycleBar]:
        attempts[symbol] = attempts.get(symbol, 0) + 1
        if symbol == "A000" and attempts[symbol] == 1:
            return complete[:-1]
        return complete

    payload = build_us_position_lifecycle_feed(
        limit=20,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload={
            "status": "ready",
            "data_state": "ready",
            "universe_as_of": date(2026, 9, 8),
            "universe_count": 100,
            "checksum": "fixture",
            "items": members,
        },
        history_loader=loader,
    )

    assert attempts["A000"] == 2
    assert attempts["A001"] == 1
    assert payload["data_state"] == "ready"
    assert payload["data_coverage_count"] == 100
    assert len(payload["public_member_signals"]) == 100


def _bars(
    *,
    daily_return: float,
    count: int = 150,
    recent_volume_multiplier: float = 1.15,
) -> list[USLifecycleBar]:
    rows: list[USLifecycleBar] = []
    trading_dates = list(recent_us_market_session_dates(date(2026, 9, 8), count))
    price = 100.0
    for trading_date in trading_dates:
        price *= 1.0 + daily_return
        volume = 1_000_000.0 * (
            recent_volume_multiplier if len(rows) >= count - 5 else 1.0
        )
        rows.append(
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
    return rows


def test_us_member_public_evidence_recovers_three_completed_session_reasons():
    evidence = build_us_member_public_evidence(
        "NVDA",
        universe_date=date(2026, 9, 8),
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        history_loader=lambda symbol: _bars(
            daily_return=0.0015,
            recent_volume_multiplier=1.25,
        ),
    )

    assert evidence["code"] == "NVDA"
    assert evidence["signal_date"] == date(2026, 9, 8)
    assert evidence["data_state"] == "ready"
    assert evidence["current"]["action"] == "no_signal"
    assert [reason["key"] for reason in evidence["public_reasons"]] == [
        "trend_20d",
        "trend_60d",
        "flow",
    ]
    assert [reason["label"] for reason in evidence["public_reasons"]] == [
        "20일 가격",
        "60일 가격",
        "거래대금 참여도",
    ]
    assert all(
        reason["available"] is True for reason in evidence["public_reasons"]
    )


def test_us_member_public_evidence_rejects_a_completed_session_gap():
    rows = _bars(daily_return=0.0015)

    try:
        build_us_member_public_evidence(
            "NVDA",
            universe_date=date(2026, 9, 8),
            now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
            history_loader=lambda symbol: rows[:-20] + rows[-19:],
        )
    except ValueError as exc:
        assert "session gap" in str(exc)
    else:
        raise AssertionError("a completed-session gap must fail closed")


def test_us_entry_requires_market_relative_strength_and_dollar_volume_evidence():
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)

    decision = evaluate_us_entry_candidate(stock, spy, qqq, sector)

    assert decision["data_state"] == "ready"
    assert decision["action"] == "entry_pending"
    assert decision["confirmation"]["quality_state"] == "ready"
    assert decision["confirmation"]["allowed"] is True
    assert "순매수" in decision["confirmation"]["proxy_notice"]


def test_legacy_us_momentum_baseline_reproduces_rounded_entry_boundary():
    def legacy_inputs(return_percent: Decimal) -> dict[str, Decimal]:
        return {
            "legacy_regular_market_change_percent": return_percent,
            "legacy_regular_market_volume": Decimal("1000000"),
            "legacy_fifty_day_average_change_percent": return_percent / Decimal("100"),
            "legacy_two_hundred_day_average_change_percent": return_percent
            / Decimal("100"),
        }

    bars = _bars(daily_return=0.0, count=64)
    below = evaluate_us_momentum_watch_baseline(
        bars,
        legacy_inputs(Decimal("8.15")),
    )
    at_rounded_threshold = evaluate_us_momentum_watch_baseline(
        bars,
        legacy_inputs(Decimal("8.16")),
    )

    assert below["score"] == Decimal("59.99")
    assert below["action"] == "entry_watch"
    assert at_rounded_threshold["score"] == Decimal("60.00")
    assert at_rounded_threshold["action"] == "entry_pending"


def test_legacy_us_momentum_baseline_uses_point_in_time_quote_valuation():
    bars = _bars(daily_return=0.0, count=64)
    cheap = evaluate_us_momentum_watch_baseline(
        bars,
        {
            "legacy_regular_market_volume": 1,
            "legacy_trailing_pe": Decimal("1"),
            "legacy_price_to_book": Decimal("1"),
        },
    )
    expensive = evaluate_us_momentum_watch_baseline(
        bars,
        {
            "legacy_regular_market_volume": 1,
            "legacy_trailing_pe": Decimal("100"),
            "legacy_price_to_book": Decimal("20"),
        },
    )

    assert cheap["value_score"] == Decimal("95.00")
    assert expensive["value_score"] == Decimal("20.00")
    assert cheap["score"] > expensive["score"]


def test_legacy_us_momentum_baseline_preserves_rounding_and_quote_volume_semantics():
    bars = _bars(daily_return=0.0, count=64)
    inputs = {
        "legacy_regular_market_change_percent": Decimal("8.1549"),
        "legacy_fifty_day_average_change_percent": Decimal("0.081549"),
        "legacy_two_hundred_day_average_change_percent": Decimal("0.081549"),
    }
    without_quote_volume = evaluate_us_momentum_watch_baseline(bars, inputs)
    with_quote_volume = evaluate_us_momentum_watch_baseline(
        bars,
        {**inputs, "legacy_regular_market_volume": 1},
    )

    assert without_quote_volume["one_month_return"] == Decimal("8.15")
    assert without_quote_volume["three_month_return"] == Decimal("8.15")
    assert with_quote_volume["score"] - without_quote_volume["score"] == Decimal("1.80")


def test_us_entry_is_not_pending_when_evidence_dates_are_misaligned():
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)[:-1]

    decision = evaluate_us_entry_candidate(stock, spy, qqq, sector)

    assert decision["action"] != "entry_pending"
    assert decision["confirmation"]["quality_state"] == "unavailable"


def test_us_entry_fails_closed_when_a_recent_session_is_missing_mid_series():
    stock = _bars(daily_return=0.0017)
    stock.pop(-10)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)

    decision = evaluate_us_entry_candidate(stock, spy, qqq, sector)

    assert decision["action"] != "entry_pending"
    assert decision["confirmation"]["quality_state"] == "unavailable"


def test_common_non_session_date_cannot_pass_alignment():
    bars = _bars(daily_return=0.0010)
    with_holiday = [
        replace(bar, trade_date=date(2026, 7, 3))
        if bar.trade_date == date(2026, 7, 2)
        else bar
        for bar in bars
    ]

    assert _aligned_recent_sessions(
        with_holiday,
        with_holiday,
        with_holiday,
        with_holiday,
    ) is False


def test_us_entry_requires_stock_strength_relative_to_its_sector():
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0045)

    decision = evaluate_us_entry_candidate(stock, spy, qqq, sector)

    assert decision["confirmation"]["stock_sector_relative_strength_20d"] < -0.03
    assert decision["action"] != "entry_pending"


def test_us_price_bars_drop_forming_and_explicitly_unadjusted_rows():
    completed = SimpleNamespace(
        trade_date=date(2026, 9, 7),
        open=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
        volume=1_000,
        trading_value=100_000,
        adjusted_ohlc_complete=True,
    )
    unadjusted = SimpleNamespace(
        trade_date=date(2026, 9, 7),
        open=99.0,
        high=101.0,
        low=98.0,
        close=100.0,
        volume=1_000,
        trading_value=100_000,
        adjusted_ohlc_complete=False,
    )
    forming = SimpleNamespace(
        trade_date=date(2026, 9, 8),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000,
        trading_value=101_000,
        adjusted_ohlc_complete=True,
    )

    bars = us_price_bars(
        [unadjusted, completed, forming],
        now=datetime(2026, 9, 8, 19, 0, tzinfo=UTC),
        market_session="regular",
    )

    assert [bar.trade_date for bar in bars] == [date(2026, 9, 7)]


def test_us_chase_guard_blocks_high_score_entry_independently():
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)
    # A five-session surge greater than 10% must remain a veto even when the
    # slower trend and market evidence are strongly supportive.
    for index in range(-5, 0):
        prior = stock[index - 1].close
        close = prior * 1.025
        original = stock[index]
        stock[index] = USLifecycleBar(
            trade_date=original.trade_date,
            open=prior,
            high=close * 1.005,
            low=prior * 0.995,
            close=close,
            volume=original.volume,
            trading_value=close * original.volume,
        )

    decision = evaluate_us_entry_candidate(stock, spy, qqq, sector)

    assert US_CHASE_POLICY.momentum5_max == 0.10
    assert decision["action"] != "entry_pending"
    assert decision["chase_veto"] in {
        "momentum5_cooldown",
        "ema20_extension_atr",
        "ema20_extension_percent",
    }


def test_us_chase_guard_boundaries_and_three_bar_lookback_are_exact():
    bar = _bars(daily_return=0.0, count=1)[0]
    at_atr_boundary = {
        "ema20": 100.0,
        "ema20_extension_atr": 1.5,
        "momentum5": 0.0,
    }
    assert (
        chase_entry_veto_reason(
            bar,
            at_atr_boundary,
            [at_atr_boundary],
            US_CHASE_POLICY,
        )
        == "ema20_extension_atr"
    )

    percent_bar = USLifecycleBar(
        trade_date=bar.trade_date,
        open=107.0,
        high=107.0,
        low=107.0,
        close=107.0,
        volume=bar.volume,
        trading_value=107.0 * bar.volume,
    )
    at_percent_boundary = {
        "ema20": 100.0,
        "ema20_extension_atr": 1.499,
        "momentum5": 0.0,
    }
    assert (
        chase_entry_veto_reason(
            percent_bar,
            at_percent_boundary,
            [at_percent_boundary],
            US_CHASE_POLICY,
        )
        == "ema20_extension_percent"
    )

    safe = {"ema20": 100.0, "ema20_extension_atr": 0.0, "momentum5": 0.10}
    hot = {**safe, "momentum5": 0.100001}
    assert chase_entry_veto_reason(bar, safe, [hot, safe, safe, safe], US_CHASE_POLICY) is None
    assert (
        chase_entry_veto_reason(bar, safe, [safe, hot, safe], US_CHASE_POLICY)
        == "momentum5_cooldown"
    )


def test_us_reentry_has_no_fixed_wait_but_requires_new_price_event():
    bars = _bars(daily_return=0.0005, count=80)
    indicators = calculate_indicators(bars)
    last_exit = len(bars) - 2
    latest = bars[-1]
    bars[-1] = USLifecycleBar(
        trade_date=latest.trade_date,
        open=latest.close,
        high=latest.close * 1.001,
        low=latest.close,
        close=latest.close,
        volume=latest.volume,
        trading_value=latest.trading_value,
    )
    indicators[-1] = {
        **indicators[-1],
        "ema20": latest.close / 1.03,
        "prior_high": latest.close * 1.10,
        "momentum5": 0.01,
    }
    indicators[-2] = {**indicators[-2], "prior_high": latest.close * 1.10}

    assert us_reentry_allowed(bars, indicators, len(bars) - 1, last_exit) is False

    prior_high = latest.close * 0.99
    bars[-1] = USLifecycleBar(
        trade_date=latest.trade_date,
        open=latest.open,
        high=prior_high * 1.02,
        low=latest.low,
        close=prior_high * 1.01,
        volume=latest.volume,
        trading_value=prior_high * 1.01 * latest.volume,
    )
    indicators[-1] = {**indicators[-1], "prior_high": prior_high}
    indicators[-2] = {**indicators[-2], "prior_high": prior_high}
    assert us_reentry_allowed(bars, indicators, len(bars) - 1, last_exit) is True


def test_us_reentry_allows_ema20_retest_recovery_without_fixed_wait():
    bars = _bars(daily_return=0.0005, count=80)
    indicators = calculate_indicators(bars)
    index = len(bars) - 1
    last_exit = index - 2
    prior = bars[index - 1]
    current = bars[index]
    ema20 = current.close * 0.995
    bars[index - 1] = USLifecycleBar(
        trade_date=prior.trade_date,
        open=prior.open,
        high=prior.high,
        low=ema20 * 1.01,
        close=prior.close,
        volume=prior.volume,
        trading_value=prior.trading_value,
    )
    indicators[index - 1] = {
        **indicators[index - 1],
        "ema20": ema20,
        "prior_high": current.close * 1.10,
    }
    indicators[index] = {
        **indicators[index],
        "ema20": ema20,
        "prior_high": current.close * 1.10,
        "momentum5": 0.01,
    }

    assert us_reentry_allowed(bars, indicators, index, last_exit) is True


def test_us_next_open_gap_guard_uses_atr_and_percent_cap():
    assert us_entry_execution_allowed(103.0, 100.0, 2.0) is True
    assert us_entry_execution_allowed(103.0001, 100.0, 2.0) is False
    assert us_entry_execution_allowed(105.0, 100.0, 10.0) is True
    assert us_entry_execution_allowed(105.0001, 100.0, 10.0) is False
    assert us_entry_execution_allowed(100.15, 100.0, 0.1) is True
    assert us_entry_execution_allowed(100.1501, 100.0, 0.1) is False
    assert us_entry_execution_allowed(105.0, 100.0, 0.0) is False
    assert us_entry_execution_allowed(105.0, 100.0, -1.0) is False
    assert us_entry_execution_allowed(0.0, 100.0, 2.0) is False


def test_us_model_replay_confirms_only_the_next_open_inside_gap(monkeypatch):
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)
    signal_index = 125
    signal_date = stock[signal_index].trade_date

    def decision_for_session(stock_rows, *_args, **_kwargs):
        latest = stock_rows[-1]
        if latest.trade_date == signal_date:
            return {
                "data_state": "ready",
                "action": "entry_pending",
                "price": latest.close,
                "score": 70.0,
                "technical": {"atr": 2.0},
            }
        return {
            "data_state": "ready",
            "action": "entry_watch",
            "price": latest.close,
            "score": 60.0,
            "technical": {"atr": 2.0},
        }

    monkeypatch.setattr(lifecycle, "evaluate_us_entry_candidate", decision_for_session)
    monkeypatch.setattr(lifecycle, "us_reentry_allowed", lambda *_args: True)

    replay = replay_us_position_lifecycle(stock, spy, qqq, sector)

    assert replay["complete"] is True
    assert replay["action"] == "holding"
    assert replay["position"]["entry_date"] == stock[signal_index + 1].trade_date
    assert replay["position"]["entry_price"] == stock[signal_index + 1].open
    assert replay["events"][-1]["side"] == "buy"
    assert replay["events"][-1]["execution_date"] == stock[signal_index + 1].trade_date

    gap_rejected = list(stock)
    next_bar = gap_rejected[signal_index + 1]
    gap_rejected[signal_index + 1] = replace(
        next_bar,
        open=stock[signal_index].close * 1.06,
    )
    rejected = replay_us_position_lifecycle(gap_rejected, spy, qqq, sector)

    assert rejected["action"] == "entry_watch"
    assert rejected["position"] is None
    assert rejected["events"] == []


def test_us_feed_replays_top100_model_lifecycle_without_orders():
    stock = _bars(daily_return=0.0017)
    spy = _bars(daily_return=0.0007)
    qqq = _bars(daily_return=0.0009)
    sector = _bars(daily_return=0.0010)
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
    histories = {"SPY": spy, "QQQ": qqq, "XLK": sector}
    histories.update({item["code"]: stock for item in members})
    # One member crosses the legacy baseline's 60-point threshold while the
    # other 99 remain watch-only, proving the aggregate is computed per symbol.
    histories["A000"] = _bars(daily_return=0.003)
    members[0].update(
        {
            "legacy_regular_market_change_percent": Decimal("8.16"),
            "legacy_regular_market_volume": 1_000_000,
            "legacy_fifty_day_average_change_percent": Decimal("0.0816"),
            "legacy_two_hundred_day_average_change_percent": Decimal("0.0816"),
        }
    )

    payload = build_us_position_lifecycle_feed(
        limit=20,
        now=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        universe_payload={
            "status": "ready",
            "data_state": "ready",
            "universe_as_of": date(2026, 9, 8),
            "universe_count": 100,
            "checksum": "fixture",
            "items": members,
        },
        history_loader=lambda symbol: histories[symbol],
    )

    assert payload["strategy_version"] == US_STRATEGY_VERSION
    assert payload["baseline_strategy_version"] == "us-momentum-watch-v1"
    assert payload["rollout_mode"] == US_ROLLOUT_MODE
    assert payload["execution_enabled"] is False
    assert payload["stateful_lifecycle_replay_enabled"] is US_STATEFUL_LIFECYCLE_REPLAY_ENABLED
    assert payload["reentry_runtime_enabled"] is US_REENTRY_RUNTIME_ENABLED
    assert payload["lifecycle_replay_version"] == US_LIFECYCLE_REPLAY_VERSION
    assert payload["universe_count"] == 100
    assert payload["confirmed_count"] == 20
    assert payload["preliminary_count"] == 0
    assert payload["stateful_lifecycle_replay_complete"] is True
    assert payload["stateful_lifecycle_replay_eligible_count"] == 100
    assert payload["stateful_lifecycle_replay_completed_count"] == 100
    assert len(payload["public_member_signals"]) == 100
    assert {
        item["code"] for item in payload["public_member_signals"]
    } == {item["code"] for item in members}
    assert all(
        [reason["label"] for reason in item["public_reasons"]]
        == ["20일 가격", "60일 가격", "거래대금 참여도"]
        for item in payload["public_member_signals"]
    )
    assert all(
        reason["available"] is True
        for item in payload["public_member_signals"]
        for reason in item["public_reasons"]
    )
    assert all(item["status"] == "confirmed" for item in payload["items"])
    assert all(item["current"]["action"] == "holding" for item in payload["items"])
    assert all(item["current"]["position_open"] is True for item in payload["items"])
    assert all(item["current"]["model_exposure_percent"] == 100 for item in payload["items"])
    assert all(item["events"] for item in payload["items"])
    assert all(item["market_cap_rank"] <= 100 for item in payload["items"])
    comparison = payload["shadow_comparison"]
    assert comparison["universe_checksum"] == "fixture"
    assert comparison["same_snapshot_evaluated_count"] == 100
    assert comparison["comparison_complete"] is True
    assert comparison["candidate_action_counts"] == {"entry_pending": 100}
    assert comparison["baseline_action_counts"] == {
        "entry_pending": 1,
        "entry_watch": 99,
    }
    assert comparison["candidate_entry_pending_count"] == 100
    assert comparison["displayed_entry_pending_count"] == 0
    assert comparison["baseline_entry_pending_count"] == 1
    assert comparison["entry_pending_overlap_count"] == 1
    assert comparison["candidate_only_entry_pending_count"] == 99
    assert comparison["baseline_only_entry_pending_count"] == 0
    assert comparison["action_agreement_count"] == 1
    assert comparison["action_agreement_rate"] == Decimal("1.00")
    assert comparison["candidate_only_entry_pending_codes"] == [
        f"A{index:03d}" for index in range(1, 100)
    ]
    assert comparison["promotion_state"] == "simulation_only"
    assert "실제 주문" in comparison["promotion_reason"]
