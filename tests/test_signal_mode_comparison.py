from datetime import date, timedelta

import app.services.signal_mode_comparison as mode_comparison
from app.services import quant_signals as qs
from app.services.signal_mode_comparison import (
    IntradayExitDecision,
    aggregate_mode_comparison,
    compare_entry_filter_backtest,
    intraday_exit_decision,
    simulate_full_intraday_ohlc_proxy,
)


def _indicator() -> dict[str, float]:
    return {
        "atr": 1.0,
        "atr_percent": 0.01,
        "average_trading_value": 30_000_000_000.0,
        "score": 70.0,
        "ema20": 100.0,
    }


def _position(*, stage: int = 0, remaining: float = 1.0) -> dict[str, object]:
    return {
        "entry_date": date(2026, 9, 4),
        "entry_price": 100.0,
        "entry_index": 100,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_shares": 1.0,
        "entry_equity": 100.0,
        "peak_price": 100.0,
        "initial_stop": 98.0,
        "profit_stage": stage,
        "remaining_fraction": remaining,
    }


def _bar(*, high: float, low: float, open_price: float = 100.0) -> qs.PriceBar:
    return qs.PriceBar(
        trade_date=date(2026, 9, 4),
        open=open_price,
        high=high,
        low=low,
        close=(high + low) / 2.0,
        volume=1_000_000.0,
        trading_value=30_000_000_000.0,
    )


def test_hybrid_proxy_confirms_half_at_three_percent_target() -> None:
    decision = intraday_exit_decision(_position(), _bar(high=103.2, low=99.0), _indicator())

    assert decision == IntradayExitDecision(
        side="partial_sell",
        price=103.0,
        reason="장중 1차 수익확정(OHLC 보수적 프록시)",
        target_stage=1,
        sell_fraction=0.5,
    )


def test_hybrid_proxy_confirms_remaining_half_at_five_percent_target() -> None:
    decision = intraday_exit_decision(
        _position(stage=1, remaining=0.5),
        _bar(high=105.2, low=104.0),
        _indicator(),
    )

    assert decision is not None
    assert decision.side == "sell"
    assert decision.price == 105.0
    assert decision.target_stage == 2
    assert decision.sell_fraction == 0.5


def test_hybrid_proxy_is_stop_first_when_low_and_target_share_a_candle() -> None:
    decision = intraday_exit_decision(_position(), _bar(high=105.2, low=97.5), _indicator())

    assert decision is not None
    assert decision.side == "sell"
    assert decision.price == 98.0
    assert "하드 리스크선" in decision.reason


def test_full_intraday_proxy_enters_at_signal_day_close(monkeypatch) -> None:
    bars = [
        qs.PriceBar(
            trade_date=date(2026, 1, 1) + timedelta(days=index),
            open=99.5,
            high=101.0,
            low=99.5,
            close=100.0,
            volume=1_000_000.0,
            trading_value=30_000_000_000.0,
        )
        for index in range(70)
    ]
    indicators = [_indicator() for _ in bars]
    captured_entry_prices: list[float | None] = []
    original_new_position = mode_comparison._new_position

    def capture_entry_price(*args, **kwargs):
        captured_entry_prices.append(kwargs.get("entry_price"))
        return original_new_position(*args, **kwargs)

    monkeypatch.setattr(qs, "_entry_signal", lambda bar, indicator: True)
    monkeypatch.setattr(qs, "_entry_setup_kind", lambda bar, indicator: "trend_continuation")
    monkeypatch.setattr(qs, "_signal_reason", lambda indicator, side: "test entry")
    monkeypatch.setattr(mode_comparison, "_new_position", capture_entry_price)

    simulate_full_intraday_ohlc_proxy(bars, indicators)

    assert captured_entry_prices == [100.0]


def test_entry_filter_shadow_replay_keeps_h2_h3_out_of_active_state():
    bars = [
        qs.PriceBar(
            trade_date=date(2026, 1, 1) + timedelta(days=index),
            open=99.5,
            high=101.0,
            low=99.5,
            close=100.0,
            volume=1_000_000.0,
            trading_value=30_000_000_000.0,
        )
        for index in range(70)
    ]
    indicators = [
        {
            **_indicator(),
            "momentum5": 0.007,
            "volume_ratio": 1.05,
            "ema10": 101.0,
            "ema60": 99.0,
            "ema10_slope": 0.01,
            "ema20_slope": 0.01,
            "momentum20": 0.01,
            "ema20_extension_atr": 1.5,
        }
        for _ in bars
    ]

    comparison = compare_entry_filter_backtest(bars, indicators)

    assert comparison["active_version"] == qs.ENTRY_FILTER_H1_VERSION
    assert comparison["shadow_versions"] == [
        qs.ENTRY_FILTER_H2_VERSION,
        qs.ENTRY_FILTER_H3_VERSION,
    ]
    assert set(comparison["results"]) == {
        qs.ENTRY_FILTER_BASELINE_VERSION,
        qs.ENTRY_FILTER_H1_VERSION,
        qs.ENTRY_FILTER_H2_VERSION,
        qs.ENTRY_FILTER_H3_VERSION,
    }
    assert comparison["results"][qs.ENTRY_FILTER_H2_VERSION]["completed_trades"] == 0


def test_aggregate_reports_hybrid_delta_without_portfolio_compounding() -> None:
    rows = [
        {
            "code": "000001",
            "daily": {
                "strategy_return": 1.0,
                "max_drawdown": -4.0,
                "completed_trades": 1,
                "trades": [{"net_return": 1.0}],
                "turnover_percent": 100.0,
            },
            "hybrid": {
                "strategy_return": 2.0,
                "max_drawdown": -3.0,
                "completed_trades": 1,
                "trades": [{"net_return": 2.0}],
                "turnover_percent": 150.0,
            },
        }
    ]

    comparison = aggregate_mode_comparison(rows)

    assert comparison["daily_open"]["average_symbol_return"] == 1.0
    assert comparison["hybrid_intraday_sell"]["average_symbol_return"] == 2.0
    assert comparison["delta_hybrid_minus_daily"]["average_symbol_return"] == 1.0
    assert comparison["delta_hybrid_minus_daily"]["average_max_drawdown"] == 1.0
