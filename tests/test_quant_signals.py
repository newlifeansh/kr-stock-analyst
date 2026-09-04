from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.db import Base, get_db
from app.main import app
from app.models import (
    DailyPrice,
    DisclosureItem,
    InvestorFlow,
    NewsItem,
    ResearchReport,
    StockCompanySnapshot,
    StockMaster,
    WatchlistItem,
)
from app.services.quant_signals import (
    MIN_HISTORY_ROWS,
    STRATEGY_VERSION,
    build_quant_signal_payload,
    enrich_market_quant_signal_sectors,
    enrich_quant_signal_payload_sector,
    load_external_market_quant_signal_feed,
    load_external_stock_quant_signal_payload,
    load_market_quant_signal_feed,
    load_reference_quant_signal_payload,
    load_quant_signal_payload,
    quant_signal_current_summary_fields,
    synchronize_quant_payload_live_quote,
)
from app.services import quant_signals
from app.services.signal_reconciliations import (
    apply_market_signal_reconciliations,
    apply_stock_signal_reconciliations,
)


def _price_rows(code: str, count: int = 340) -> list[DailyPrice]:
    rows: list[DailyPrice] = []
    value = 10_000.0
    trade_date = date(2025, 1, 2)
    for index in range(count):
        while trade_date.weekday() >= 5:
            trade_date += timedelta(days=1)
        if index < 80:
            daily_return = 0.0004
        elif index < 155:
            daily_return = 0.009
        elif index < 190:
            daily_return = -0.014
        elif index < 275:
            daily_return = 0.008
        else:
            daily_return = -0.009
        previous = value
        value *= 1.0 + daily_return
        open_price = previous * (1.0 + (daily_return * 0.25))
        rows.append(
            DailyPrice(
                code=code,
                trade_date=trade_date,
                open=round(open_price),
                high=round(max(open_price, value) * 1.012),
                low=round(min(open_price, value) * 0.988),
                close=round(value),
                volume=1_000_000 + (index % 23) * 50_000,
                trading_value=50_000_000_000 + (index % 7) * 1_000_000_000,
            )
        )
        trade_date += timedelta(days=1)
    return rows


def _stock(code: str = "005930", name: str = "삼성전자") -> StockMaster:
    return StockMaster(code=code, name=name, market="KOSPI", is_active=True)


def _session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def test_oci_legacy_buy_is_closed_by_current_strategy_reconciliation():
    payload = {
        "code": "010060",
        "name": "OCI홀딩스",
        "strategy_version": STRATEGY_VERSION,
        "as_of": datetime(2026, 8, 20, 12, 40),
        "data_message": "신호 계산 완료",
        "current": {
            "action": "exited",
            "score": Decimal("92.25"),
            "price": 293_500,
            "as_of": datetime(2026, 8, 20, 12, 40),
            "lifecycle": {
                "stages": ["관망", "예비 포착", "매수 대기", "보유", "수익확정", "전량 매도"]
            },
        },
        "events": [],
    }

    result = apply_stock_signal_reconciliations(
        payload,
        now=datetime(2026, 8, 20, 12, 40),
    )

    assert result is not None
    assert result["current"]["action"] == "exited"
    assert result["current"]["position_open"] is False
    assert result["current"]["signal_origin"] == "legacy_reconciliation"
    assert result["current"]["lifecycle"]["latest_transition"]["transition_date"] == date(2026, 8, 20)
    assert result["events"][-1]["label"] == "확정 매도 · 전략 버전 통일"
    assert result["events"][-1]["entry_price"] == 273_500
    assert result["events"][-1]["price"] == 293_500
    assert result["events"][-1]["reconciliation_id"] == "legacy-v2-oci-010060-close-20260820"
    assert result["display_return_rate"] == Decimal("6.83")
    assert result["signal_reconciliations"][0]["source_strategy_version"] == "position-lifecycle-v2.0"


def test_oci_reconciliation_is_not_applied_before_effective_date():
    payload = {
        "code": "010060",
        "strategy_version": STRATEGY_VERSION,
        "events": [],
    }

    result = apply_stock_signal_reconciliations(
        payload,
        now=datetime(2026, 8, 19, 16, 0),
    )

    assert result == payload


def test_market_feed_includes_oci_confirmed_sell_reconciliation():
    payload = {
        "status": "ready",
        "strategy_version": STRATEGY_VERSION,
        "as_of": datetime(2026, 8, 20, 16, 0),
        "recent_days": 30,
        "preliminary_count": 0,
        "confirmed_count": 0,
        "items": [],
    }

    result = apply_market_signal_reconciliations(
        payload,
        now=datetime(2026, 8, 20, 16, 0),
    )

    assert result is not None
    assert result["confirmed_count"] == 1
    assert result["preliminary_count"] == 0
    assert result["items"][0]["code"] == "010060"
    assert result["items"][0]["side"] == "sell"
    assert result["items"][0]["event_side"] == "sell"
    assert result["items"][0]["signal"] == "확정 매도 · 전략 버전 통일"
    assert result["items"][0]["status"] == "confirmed"
    assert result["items"][0]["execution_date"] == date(2026, 8, 20)
    assert result["items"][0]["signal_origin"] == "legacy_reconciliation"
    assert result["items"][0]["reconciliation_id"] == "legacy-v2-oci-010060-close-20260820"
    reapplied = apply_market_signal_reconciliations(
        result,
        now=datetime(2026, 8, 20, 16, 0),
    )
    assert reapplied is not None
    assert len([item for item in reapplied["items"] if item["code"] == "010060"]) == 1


def test_quant_signals_execute_on_the_next_bar_and_include_costs():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930"),
        now=datetime(2026, 7, 25, 12, 0),
    )

    assert payload["data_state"] == "ready"
    assert payload["strategy_version"] == STRATEGY_VERSION
    assert payload["profit_preservation_effective_date"] == date(2026, 8, 24)
    assert payload["tactical_exit_effective_date"] == date(2026, 8, 25)
    assert payload["events"]
    assert {event["side"] for event in payload["events"]} == {"buy", "partial_sell", "sell"}
    assert all(event["execution_date"] > event["signal_date"] for event in payload["events"])
    partial_events = [event for event in payload["events"] if event["side"] == "partial_sell"]
    assert partial_events
    assert {
        (event["profit_stage"], event["sold_percent"], event["position_percent"])
        for event in partial_events
    } == {
        (1, Decimal("10.00"), Decimal("90.00")),
        (2, Decimal("15.00"), Decimal("75.00")),
        (3, Decimal("15.00"), Decimal("60.00")),
    }
    assert all(event["label"] == f"{event['profit_stage']}차 수익확정" for event in partial_events)
    assert all(event["signal_at"].hour == 15 and event["signal_at"].minute == 40 for event in payload["events"])
    assert all(event["entry_price"] is not None for event in payload["events"])
    assert all(
        event["entry_price"] == event["price"]
        for event in payload["events"]
        if event["side"] == "buy"
    )
    for event in (item for item in payload["events"] if item["side"] == "sell"):
        trade = next(item for item in payload["trades"] if item["exit_date"] == event["execution_date"])
        assert event["entry_price"] == trade["entry_price"]
    for event in (item for item in payload["events"] if item["side"] == "partial_sell"):
        trade = next(
            item
            for item in payload["trades"]
            if any(
                partial["execution_date"] == event["execution_date"]
                for partial in item["partial_exits"]
            )
        )
        assert event["entry_price"] == trade["entry_price"]
    assert all(event["target_sell_price"] is not None for event in payload["events"])
    assert all(
        event["target_sell_status"] == "planned"
        for event in payload["events"]
        if event["side"] == "buy"
    )
    for trade in (item for item in payload["trades"] if item["status"] == "closed"):
        assert trade["net_return"] <= trade["gross_return"]
        assert trade["holding_days"] >= 1
        assert trade["profit_stage"] == len(trade["partial_exits"])
        assert trade["remaining_percent"] == Decimal("0.00")
    assert Decimal("0.12") <= payload["performance"]["transaction_cost_per_side"] <= Decimal("0.50")
    assert payload["performance"]["max_drawdown"] <= 0
    assert payload["performance"]["annualized_volatility"] >= 0
    assert Decimal("0.00") <= payload["performance"]["average_model_exposure_percent"] <= Decimal("100.00")
    assert "average_account_exposure_percent" not in payload["performance"]
    assert "risk_budget_percent" not in payload["performance"]
    assert "account_allocation_percent" not in payload["events"][0]
    assert payload["performance"]["turnover_percent"] > 0
    assert payload["performance"]["execution_count"] == len(payload["events"])
    assert "hypothetical_start" not in payload["performance"]
    assert any("최대 낙폭" in item for item in payload["applied_principles"])
    assert any("생존편향" in item for item in payload["excluded_principles"])


def _strategy_test_inputs(count: int = 90):
    bars = []
    indicators = []
    start = date(2026, 1, 2)
    for index in range(count):
        close = 100.0
        bars.append(
            quant_signals.PriceBar(
                trade_date=start + timedelta(days=index),
                open=100.0,
                high=max(101.0, close),
                low=min(99.0, close),
                close=close,
                volume=1_000_000,
                trading_value=50_000_000_000,
            )
        )
        indicators.append(
            {
                "score": 50.0,
                "ema10": 100.0,
                "ema10_slope": 0.0,
                "ema20": 100.0,
                "ema60": 99.0,
                "ema20_slope": 0.0,
                "momentum5": 0.0,
                "momentum10": 0.0,
                "momentum20": 0.0,
                "prior_high": 101.0,
                "high_distance": -0.01,
                "volume_ratio": 1.0,
                "atr": 1.0,
                "atr_percent": 0.01,
                "ema20_extension_atr": 0.0,
                "trend_score": 0.0,
                "momentum_score": 0.0,
                "breakout_score": 0.0,
                "volume_score": 0.0,
                "average_trading_value": 50_000_000_000,
            }
        )
    return bars, indicators


def _set_entry_indicator(indicator):
    indicator.update(
        score=70.0,
        ema10=100.0,
        ema10_slope=0.01,
        ema20=99.0,
        ema60=98.0,
        ema20_slope=0.01,
        momentum5=0.03,
        momentum10=0.03,
        momentum20=0.03,
    )


def _daily_rows_from_bars(code: str, bars):
    return [
        DailyPrice(
            code=code,
            trade_date=bar.trade_date,
            open=round(bar.open),
            high=round(bar.high),
            low=round(bar.low),
            close=round(bar.close),
            volume=round(bar.volume),
            trading_value=round(bar.trading_value),
        )
        for bar in bars
    ]


def test_verified_live_krx_bar_executes_previous_close_buy_during_session(monkeypatch):
    bars, indicators = _strategy_test_inputs(66)
    _set_entry_indicator(indicators[-1])
    rows = _daily_rows_from_bars("005930", bars)
    live_date = bars[-1].trade_date + timedelta(days=1)
    now = datetime.combine(live_date, datetime.min.time()).replace(hour=9, minute=1)
    live_quote = {
        "trade_date": live_date,
        "trade_date_verified": True,
        "market_venue": "KRX",
        "market_division": "J",
        "price": 101,
        "open": 100,
        "high": 102,
        "low": 99,
        "volume": 1_000_000,
        "trading_value": 100_000_000_000,
    }

    monkeypatch.setattr(quant_signals, "MIN_HISTORY_ROWS", len(bars))
    monkeypatch.setattr(quant_signals, "_normalize_prices", lambda _rows: list(bars))
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: bars[-1].trade_date,
    )
    monkeypatch.setattr(
        quant_signals,
        "is_korea_market_session_date",
        lambda *_args, **_kwargs: True,
    )

    def indicator_rows(candidate_bars):
        result = [dict(item) for item in indicators]
        if len(candidate_bars) == len(bars) + 1:
            result.append(dict(indicators[-1]))
        return result

    monkeypatch.setattr(quant_signals, "_indicator_rows", indicator_rows)

    payload = build_quant_signal_payload(
        _stock(),
        rows,
        live_quote=live_quote,
        now=now,
    )

    assert payload["current"]["action"] == "entered"
    assert payload["current"]["entry_date"] == live_date
    assert payload["current"]["entry_price"] == 100
    assert payload["current"]["model_exposure_percent"] == Decimal("100.00")
    buy = payload["events"][-1]
    assert (buy["side"], buy["signal_date"], buy["execution_date"], buy["price"]) == (
        "buy",
        bars[-1].trade_date,
        live_date,
        100,
    )
    assert payload["performance"]["period_end"] == bars[-1].trade_date


@pytest.mark.parametrize(
    ("decision_close", "live_open", "expected_side", "expected_action", "expected_exposure"),
    [
        (90.0, 89.0, "sell", "exited", Decimal("0.00")),
        (102.0, 102.0, "partial_sell", "partially_exited", Decimal("70.00")),
    ],
)
def test_verified_live_krx_bar_executes_previous_sell_once(
    monkeypatch,
    decision_close,
    live_open,
    expected_side,
    expected_action,
    expected_exposure,
):
    bars, indicators = _strategy_test_inputs(69)
    monkeypatch.setattr(quant_signals, "STABLE_PROFIT_EFFECTIVE_DATE", date(9999, 12, 31))
    monkeypatch.setattr(quant_signals, "PROFIT_PRESERVATION_EFFECTIVE_DATE", bars[0].trade_date)
    monkeypatch.setattr(quant_signals, "TACTICAL_EXIT_EFFECTIVE_DATE", bars[0].trade_date)
    _set_entry_indicator(indicators[65])
    bars[-1] = quant_signals.PriceBar(
        trade_date=bars[-1].trade_date,
        open=decision_close,
        high=max(decision_close + 0.5, 90.5),
        low=decision_close - 0.5,
        close=decision_close,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    live_date = bars[-1].trade_date + timedelta(days=1)
    now = datetime.combine(live_date, datetime.min.time()).replace(hour=10)
    live_quote = {
        "trade_date": live_date,
        "trade_date_verified": True,
        "market_venue": "KRX",
        "market_division": "J",
        "price": live_open,
        "open": live_open,
        "high": live_open + 1,
        "low": live_open - 1,
        "volume": 1_000_000,
        "trading_value": 100_000_000_000,
    }

    monkeypatch.setattr(
        quant_signals,
        "is_korea_market_session_date",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: bars[-1].trade_date,
    )

    simulation_bars, projected = quant_signals._live_execution_bars(bars, live_quote, now)
    assert projected is True
    live_indicators = [*indicators, dict(indicators[-1])]
    simulation = quant_signals._simulate(simulation_bars, live_indicators)
    current, _factors = quant_signals._current_signal(
        simulation_bars,
        simulation,
        live_quote,
        now,
    )
    today_events = [event for event in simulation["events"] if event["execution_date"] == live_date]

    assert len(today_events) == 1
    assert today_events[0]["side"] == expected_side
    assert today_events[0]["price"] == round(live_open)
    assert current["action"] == expected_action
    assert current["model_exposure_percent"] == expected_exposure
    if expected_side == "partial_sell":
        assert today_events[0]["sold_percent"] == Decimal("30.00")


def test_live_execution_bar_fails_closed_for_unverified_or_non_krx_quotes(monkeypatch):
    confirmed = [
        quant_signals.PriceBar(
            trade_date=date(2026, 8, 26),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1_000_000,
            trading_value=50_000_000_000,
        )
    ]
    valid = {
        "trade_date": date(2026, 8, 27),
        "trade_date_verified": True,
        "market_venue": "KRX",
        "market_division": "J",
        "price": 101,
        "open": 100,
        "high": 102,
        "low": 99,
        "volume": 1_000,
    }
    regular_now = datetime(2026, 8, 27, 9, 1)

    monkeypatch.setattr(quant_signals, "is_korea_market_session_date", lambda *_args: True)
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: confirmed[-1].trade_date,
    )

    bars, projected = quant_signals._live_execution_bars(confirmed, valid, regular_now)
    assert projected is True
    assert len(bars) == 2

    fresh_kis_quote = {
        **valid,
        "trade_date_verified": False,
        "quote_source": "kis_rest",
        "observed_at": regular_now,
    }
    bars, projected = quant_signals._live_execution_bars(
        confirmed,
        fresh_kis_quote,
        regular_now,
    )
    assert projected is True
    assert len(bars) == 2

    rejected = [
        ({**valid, "trade_date_verified": False}, regular_now),
        ({**valid, "volume": 0}, regular_now),
        ({**valid, "open": None}, regular_now),
        ({**valid, "market_session": "nxt_pre_market", "market_venue": "NXT"}, regular_now),
        ({**valid, "market_session": "integrated_regular", "market_venue": "INTEGRATED", "market_division": "UN"}, regular_now),
        ({key: value for key, value in valid.items() if key != "trade_date_verified"}, regular_now),
        ({key: value for key, value in valid.items() if key != "market_venue"}, regular_now),
        ({key: value for key, value in valid.items() if key != "trade_date"}, regular_now),
        (valid, datetime(2026, 8, 27, 8, 59)),
    ]
    for quote, now in rejected:
        bars, projected = quant_signals._live_execution_bars(confirmed, quote, now)
        assert projected is False
        assert bars == confirmed

    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: date(2026, 8, 25),
    )
    bars, projected = quant_signals._live_execution_bars(confirmed, valid, regular_now)
    assert projected is False
    assert bars == confirmed

    monkeypatch.setattr(quant_signals, "is_korea_market_session_date", lambda *_args: False)
    bars, projected = quant_signals._live_execution_bars(
        confirmed,
        fresh_kis_quote,
        regular_now,
    )
    assert projected is False
    assert bars == confirmed


def test_weekend_synthetic_kis_quote_does_not_change_completed_signal(monkeypatch):
    rows = _price_rows("004370")
    latest_trade_date = rows[-1].trade_date
    weekend_date = latest_trade_date
    while weekend_date.weekday() != 5:
        weekend_date += timedelta(days=1)
    weekend = datetime.combine(weekend_date, time(0, 2), tzinfo=quant_signals.KST)
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: latest_trade_date,
    )
    baseline = build_quant_signal_payload(
        _stock("004370", "농심"),
        rows,
        now=weekend,
    )
    synthetic_quote = {
        "trade_date": weekend_date,
        "trade_date_verified": False,
        "quote_source": "kis_rest",
        "observed_at": weekend,
        "price": rows[-1].close + 23_000,
        "open": rows[-1].open,
        "high": rows[-1].high + 23_000,
        "low": rows[-1].low,
        "volume": rows[-1].volume,
        "trading_value": rows[-1].trading_value,
        "market_session": "closed",
        "market_venue": "KRX",
        "market_division": "J",
    }
    observed = build_quant_signal_payload(
        _stock("004370", "농심"),
        rows,
        live_quote=synthetic_quote,
        now=weekend,
    )

    assert observed["current"]["live_observation"] is False
    assert observed["current"]["price"] == baseline["current"]["price"]
    assert observed["current"]["score"] == baseline["current"]["score"]
    assert observed["price_through"] == latest_trade_date


def test_current_buy_signal_respects_the_same_reentry_cooldown_as_simulation(monkeypatch):
    bars, indicators = _strategy_test_inputs(80)
    _set_entry_indicator(indicators[65])
    bars[67] = quant_signals.PriceBar(
        trade_date=bars[67].trade_date,
        open=90,
        high=91,
        low=89,
        close=90,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    _set_entry_indicator(indicators[68])
    monkeypatch.setattr(
        quant_signals,
        "_indicator_rows",
        lambda candidate_bars: [dict(item) for item in indicators[: len(candidate_bars)]],
    )
    early_bars = bars[:69]
    early_indicators = indicators[:69]
    early_simulation = quant_signals._simulate(early_bars, early_indicators)
    early_current, _factors = quant_signals._current_signal(
        early_bars,
        early_simulation,
        None,
        datetime.combine(early_bars[-1].trade_date, datetime.min.time()).replace(hour=16),
    )

    assert early_current["action"] == "exited"
    assert early_current["label"] == "전량 매도 후 재진입 유예"

    _set_entry_indicator(indicators[-1])
    late_simulation = quant_signals._simulate(bars, indicators)
    late_current, _factors = quant_signals._current_signal(
        bars,
        late_simulation,
        None,
        datetime.combine(bars[-1].trade_date, datetime.min.time()).replace(hour=16),
    )

    assert late_current["action"] == "entry_pending"


def test_entry_rejects_atr_over_six_percent():
    bars, indicators = _strategy_test_inputs(1)
    _set_entry_indicator(indicators[0])
    indicators[0]["atr_percent"] = 0.061

    assert quant_signals._entry_signal(bars[0], indicators[0]) is False

    indicators[0]["atr_percent"] = 0.06
    assert quant_signals._entry_signal(bars[0], indicators[0]) is True


def test_initial_risk_is_capped_at_six_percent_of_entry():
    old_date = date(2026, 1, 2)
    assert quant_signals._initial_risk(100.0, 20.0, strategy_date=old_date) == 6.0
    assert quant_signals._initial_risk(100.0, 2.0, strategy_date=old_date) == 3.5
    assert quant_signals._initial_risk(100.0, 0.1, strategy_date=old_date) == 1.0


def test_v74_entry_filter_and_initial_risk_cap():
    bar = quant_signals.PriceBar(
        trade_date=date(2026, 9, 4),
        open=100.0,
        high=103.0,
        low=99.0,
        close=102.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    indicator = {
        "score": 64.0,
        "ema10": 101.0,
        "ema20": 100.0,
        "ema60": 99.0,
        "ema10_slope": 0.01,
        "ema20_slope": 0.01,
        "momentum5": 0.0,
        "momentum20": 0.01,
        "volume_ratio": 0.8,
        "atr": 5.0,
        "atr_percent": 0.045,
        "ema20_extension_atr": 1.0,
        "average_trading_value": 5_000_000_000.0,
    }

    assert quant_signals._entry_setup_kind(
        bar,
        indicator,
        entry_filter_version=quant_signals.ENTRY_FILTER_BASELINE_VERSION,
    ) == "trend_continuation"
    for field, value in (("score", 63.99), ("atr_percent", 0.0451), ("momentum5", -0.0001), ("volume_ratio", 0.799)):
        assert quant_signals._entry_setup_kind(
            bar,
            {**indicator, field: value},
            entry_filter_version=quant_signals.ENTRY_FILTER_BASELINE_VERSION,
        ) is None
    assert quant_signals._initial_risk(100.0, 20.0, strategy_date=bar.trade_date) == 4.0


def test_v75_rc1_activates_h1_and_keeps_h2_h3_shadow_only():
    bar = quant_signals.PriceBar(
        trade_date=date(2026, 9, 4),
        open=100.0,
        high=103.0,
        low=99.0,
        close=102.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    indicator = {
        "score": 70.0,
        "ema10": 101.0,
        "ema20": 100.0,
        "ema60": 99.0,
        "ema10_slope": 0.01,
        "ema20_slope": 0.01,
        "momentum5": 0.007,
        "momentum20": 0.01,
        "volume_ratio": 1.05,
        "atr": 2.0,
        "atr_percent": 0.035,
        "ema20_extension_atr": 1.5,
        "average_trading_value": 5_000_000_000.0,
    }

    assert quant_signals.STRATEGY_VERSION == "position-lifecycle-v7.4"
    assert quant_signals.CANDIDATE_STRATEGY_VERSION == "position-lifecycle-v7.5-rc1"
    assert [item["version"] for item in quant_signals.STRATEGY_VERSION_HISTORY] == [
        "position-lifecycle-legacy",
        "position-lifecycle-v7.1",
        "position-lifecycle-v7.3",
        "position-lifecycle-v7.4",
        "position-lifecycle-v7.5-rc1",
    ]
    assert quant_signals.active_entry_filter_version(bar.trade_date) == "buy-filter-h1"
    assert quant_signals._entry_signal(bar, indicator) is True
    assert quant_signals._entry_signal(
        bar,
        indicator,
        entry_filter_version=quant_signals.ENTRY_FILTER_H2_VERSION,
    ) is False
    assert quant_signals._entry_signal(
        bar,
        indicator,
        entry_filter_version=quant_signals.ENTRY_FILTER_H3_VERSION,
    ) is True

    comparison = quant_signals.compare_entry_filter_candidates(bar, indicator)
    assert comparison[quant_signals.ENTRY_FILTER_BASELINE_VERSION]["allowed"] is True
    assert comparison[quant_signals.ENTRY_FILTER_H1_VERSION]["allowed"] is True
    assert comparison[quant_signals.ENTRY_FILTER_H2_VERSION]["allowed"] is False
    assert comparison[quant_signals.ENTRY_FILTER_H3_VERSION]["allowed"] is True


def test_strategy_version_for_date_preserves_previous_releases():
    assert quant_signals.strategy_version_for_date(date(2026, 8, 23)) == "position-lifecycle-legacy"
    assert quant_signals.strategy_version_for_date(date(2026, 8, 24)) == "position-lifecycle-v7.1"
    assert quant_signals.strategy_version_for_date(date(2026, 8, 25)) == "position-lifecycle-v7.3"
    assert quant_signals.strategy_version_for_date(date(2026, 9, 3)) == "position-lifecycle-v7.3"
    assert quant_signals.strategy_version_for_date(date(2026, 9, 4)) == "position-lifecycle-v7.4"


def test_v74_fixed_targets_protect_at_two_percent_and_sell_remaining_half_at_five_percent():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_date": date(2026, 9, 4),
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 1,
        "remaining_fraction": 0.50,
    }

    levels = quant_signals._position_levels(position, indicators[0], peak_price=102.0)
    assert levels["profit_ladder_mode"] == "fixed_percent"
    assert levels["profit_protection_active"] is True
    assert levels["next_partial_target"] == pytest.approx(105.0)

    bar = quant_signals.PriceBar(
        trade_date=date(2026, 9, 5),
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    should_partial, reason, target_levels = quant_signals._partial_exit_signal(
        bar,
        indicators[0],
        position,
        peak_price=105.0,
    )
    assert should_partial is True
    assert "5% 수익" in reason
    assert target_levels["target_stage"] == 2
    assert target_levels["target_price"] == pytest.approx(105.0)
    assert target_levels["sell_fraction"] == pytest.approx(0.50)
    assert target_levels["remaining_after_fraction"] == pytest.approx(0.0)


def test_v74_second_target_closes_the_trade_without_a_runner(monkeypatch):
    bars, indicators = _strategy_test_inputs(72)
    monkeypatch.setattr(quant_signals, "STABLE_PROFIT_EFFECTIVE_DATE", bars[65].trade_date)
    monkeypatch.setattr(quant_signals, "PROFIT_PRESERVATION_EFFECTIVE_DATE", bars[0].trade_date)
    monkeypatch.setattr(quant_signals, "TACTICAL_EXIT_EFFECTIVE_DATE", bars[0].trade_date)
    for index in range(65, 70):
        _set_entry_indicator(indicators[index])
    bars[67] = quant_signals.PriceBar(
        trade_date=bars[67].trade_date,
        open=100.0,
        high=104.0,
        low=99.0,
        close=103.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    bars[68] = quant_signals.PriceBar(
        trade_date=bars[68].trade_date,
        open=103.0,
        high=106.0,
        low=102.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    bars[69] = quant_signals.PriceBar(
        trade_date=bars[69].trade_date,
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    result = quant_signals._simulate(bars, indicators)
    assert [event["side"] for event in result["events"]] == ["buy", "partial_sell", "sell"]
    assert result["events"][-1]["profit_stage"] == 2
    assert result["trades"][-1]["status"] == "closed"
    assert result["position"] is None


def test_strict_early_turn_can_confirm_before_the_medium_trend_crosses():
    bars, indicators = _strategy_test_inputs(1)
    bars[0] = quant_signals.PriceBar(
        trade_date=bars[0].trade_date,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_200_000,
        trading_value=50_000_000_000,
    )
    indicators[0].update(
        score=quant_signals.EARLY_ENTRY_SCORE,
        ema10=100.0,
        ema10_slope=0.01,
        ema20=99.5,
        ema60=100.0,
        ema20_slope=0.0,
        momentum5=quant_signals.EARLY_ENTRY_MOMENTUM_5_MIN + 0.001,
        momentum20=0.0,
        volume_ratio=quant_signals.EARLY_ENTRY_VOLUME_MIN,
    )

    assert indicators[0]["ema20"] < indicators[0]["ema60"]
    assert quant_signals._entry_setup_kind(bars[0], indicators[0]) == "early_turn"

    indicators[0]["volume_ratio"] = quant_signals.EARLY_ENTRY_VOLUME_MIN - 0.01
    assert quant_signals._entry_signal(bars[0], indicators[0]) is False

    indicators[0]["volume_ratio"] = quant_signals.EARLY_ENTRY_VOLUME_MIN
    indicators[0]["ema20"] = 99.4
    assert quant_signals._entry_signal(bars[0], indicators[0]) is False


def test_near_ready_setup_is_exposed_as_entry_watch_without_trade_metrics(monkeypatch):
    bars, indicators = _strategy_test_inputs(1)
    indicators[0].update(
        score=quant_signals.PRE_ENTRY_SCORE,
        ema10=100.0,
        ema10_slope=0.01,
        ema20=99.5,
        ema60=99.0,
        momentum5=0.01,
        momentum20=0.0,
        volume_ratio=0.9,
    )
    bars[0] = quant_signals.PriceBar(
        trade_date=bars[0].trade_date,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    monkeypatch.setattr(quant_signals, "_indicator_rows", lambda _bars: indicators)

    current, _factors = quant_signals._current_signal(
        bars,
        {"position": None, "events": [], "lifecycle_events": []},
        None,
        datetime(2026, 7, 25, 16, 0),
    )

    assert quant_signals._entry_signal(bars[0], indicators[0]) is False
    assert quant_signals._pre_entry_signal(bars[0], indicators[0]) is True
    assert current["action"] == "entry_watch"
    assert current["label"] == "예비 매수 포착"
    assert current["position_open"] is False
    assert current["entry_price"] is None
    assert current["unrealized_return"] is None


def test_single_stock_simulation_uses_full_model_position_without_account_sizing():
    bars, indicators = _strategy_test_inputs(70)
    _set_entry_indicator(indicators[65])

    result = quant_signals._simulate(bars, indicators)

    assert result["position"]["entry_equity"] == 1.0
    assert "account_allocation_fraction" not in result["position"]
    assert result["lifecycle_events"][0]["position_percent"] == Decimal("100.00")
    assert "account_allocation_percent" not in result["lifecycle_events"][0]


def test_entry_rejects_illiquid_or_overextended_setup():
    bars, indicators = _strategy_test_inputs(1)
    _set_entry_indicator(indicators[0])

    indicators[0]["average_trading_value"] = quant_signals.MIN_AVERAGE_TRADING_VALUE - 1
    assert quant_signals._entry_signal(bars[0], indicators[0]) is False

    indicators[0]["average_trading_value"] = quant_signals.MIN_AVERAGE_TRADING_VALUE
    indicators[0]["ema20_extension_atr"] = quant_signals.MAX_ENTRY_EXTENSION_ATR + 0.01
    assert quant_signals._entry_signal(bars[0], indicators[0]) is False

    indicators[0]["ema20_extension_atr"] = quant_signals.MAX_ENTRY_EXTENSION_ATR
    assert quant_signals._entry_signal(bars[0], indicators[0]) is True


def test_next_open_gap_cancels_stale_entry_signal():
    bars, indicators = _strategy_test_inputs(72)
    _set_entry_indicator(indicators[65])
    bars[66] = quant_signals.PriceBar(
        trade_date=bars[66].trade_date,
        open=110.0,
        high=111.0,
        low=99.0,
        close=100.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    result = quant_signals._simulate(bars, indicators)

    assert not any(event["side"] == "buy" for event in result["events"])
    assert result["position"] is None
    assert result["performance"]["rejected_gap_entries"] == 1


def test_normal_exit_waits_for_minimum_holding_and_two_closes():
    bars, indicators = _strategy_test_inputs(76)
    _set_entry_indicator(indicators[65])
    for index in range(66, len(indicators)):
        indicators[index]["score"] = 40.0

    result = quant_signals._simulate(bars, indicators)
    buy, sell = [event for event in result["events"] if event["side"] in {"buy", "sell"}]

    assert buy["execution_date"] == bars[66].trade_date
    assert sell["signal_date"] == bars[72].trade_date
    assert sell["execution_date"] == bars[73].trade_date
    assert "2일 연속 확인" in sell["reason"]


def test_exit_confirmation_requires_the_same_reason_on_consecutive_closes():
    bars, indicators = _strategy_test_inputs(78)
    _set_entry_indicator(indicators[65])
    indicators[71]["score"] = 40.0
    indicators[72].update(score=50.0, ema10=99.0, ema20=101.0)
    indicators[73].update(score=50.0, ema10=99.0, ema20=101.0)

    result = quant_signals._simulate(bars, indicators)
    sell = next(event for event in result["events"] if event["side"] == "sell")

    assert sell["signal_date"] == bars[73].trade_date
    assert sell["execution_date"] == bars[74].trade_date
    assert "20일선" in sell["reason"]


def test_hard_stop_exits_without_waiting_for_minimum_holding():
    bars, indicators = _strategy_test_inputs(72)
    _set_entry_indicator(indicators[65])
    bars[66] = quant_signals.PriceBar(
        trade_date=bars[66].trade_date,
        open=100.0,
        high=100.0,
        low=94.0,
        close=95.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    result = quant_signals._simulate(bars, indicators)
    sell = next(event for event in result["events"] if event["side"] == "sell")

    assert sell["signal_date"] == bars[66].trade_date
    assert sell["execution_date"] == bars[67].trade_date
    assert sell["reason"] == "초기 급락 위험선 이탈"


def test_reentry_is_delayed_for_ten_trading_bars_after_exit():
    bars, indicators = _strategy_test_inputs(90)
    _set_entry_indicator(indicators[65])
    bars[66] = quant_signals.PriceBar(
        trade_date=bars[66].trade_date,
        open=100.0,
        high=100.0,
        low=94.0,
        close=95.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    for index in range(67, len(indicators)):
        _set_entry_indicator(indicators[index])

    result = quant_signals._simulate(bars, indicators)
    buys = [event for event in result["events"] if event["side"] == "buy"]

    assert [event["execution_date"] for event in buys[:2]] == [
        bars[66].trade_date,
        bars[79].trade_date,
    ]


def test_lifecycle_preroll_preserves_position_opened_before_performance_window():
    bars, indicators = _strategy_test_inputs(400)
    _set_entry_indicator(indicators[65])

    result = quant_signals._simulate(bars, indicators)

    assert result["start_index"] == 148
    assert result["position"]["entry_date"] == bars[66].trade_date
    assert result["events"] == []
    assert result["lifecycle_events"][0]["side"] == "buy"
    assert result["performance"]["trading_days"] == 252
    assert result["performance"]["history_complete"] is True
    assert Decimal("0.00") <= result["performance"]["average_model_exposure_percent"] <= Decimal("100.00")


def test_profit_protection_floor_covers_estimated_round_trip_costs():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "partial_exit_done": False,
    }

    levels = quant_signals._position_levels(position, indicators[0], peak_price=105.0)

    assert levels["profit_protection_active"] is True
    assert levels["break_even_floor"] > 100.0
    assert levels["trailing_stop"] >= levels["break_even_floor"]


def test_tactical_profit_ladder_raises_the_locked_floor_and_keeps_a_thirty_percent_runner():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 0,
        "remaining_fraction": 1.0,
    }

    stage_one = quant_signals._position_levels(
        position, indicators[0], peak_price=102.0, strategy_date=quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE
    )
    stage_two = quant_signals._position_levels(
        position, indicators[0], peak_price=103.2, strategy_date=quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE
    )
    stage_three = quant_signals._position_levels(
        position, indicators[0], peak_price=105.0, strategy_date=quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE
    )
    assert [
        stage_one["locked_profit_floor"],
        stage_two["locked_profit_floor"],
        stage_three["locked_profit_floor"],
    ] == pytest.approx([100.5, 102.0, 103.6])

    should_partial, _reason, levels = quant_signals._partial_exit_signal(
        quant_signals.PriceBar(
            trade_date=quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE,
            open=105.0,
            high=106.0,
            low=104.0,
            close=105.0,
            volume=1_000_000,
            trading_value=50_000_000_000,
        ),
        indicators[0],
        position,
        peak_price=105.0,
    )
    assert should_partial is True
    assert levels["target_stage"] == 3
    assert levels["sell_fraction"] == 1.0 - quant_signals.V7_3_MIN_RUNNER_FRACTION


def test_profit_preservation_ladder_starts_on_effective_date_without_rewriting_history():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 0,
        "remaining_fraction": 1.0,
    }

    def signal_bar(trade_date: date, close: float):
        return quant_signals.PriceBar(
            trade_date=trade_date,
            open=close,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=1_000_000,
            trading_value=50_000_000_000,
        )

    old_partial, old_reason, old_levels = quant_signals._partial_exit_signal(
        signal_bar(date(2026, 8, 21), 104.0),
        indicators[0],
        position,
        peak_price=104.0,
    )
    preservation_partial, preservation_reason, preservation_levels = (
        quant_signals._partial_exit_signal(
            signal_bar(quant_signals.PROFIT_PRESERVATION_EFFECTIVE_DATE, 104.0),
            indicators[0],
            position,
            peak_price=104.0,
        )
    )
    tactical_partial, tactical_reason, tactical_levels = quant_signals._partial_exit_signal(
        signal_bar(quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE, 102.0),
        indicators[0],
        position,
        peak_price=102.0,
    )

    assert old_partial is False
    assert old_reason == "다음 3.0R 수익확정 기준 미도달"
    assert old_levels["next_partial_target"] == 106.0
    assert preservation_partial is True
    assert "2.0배 수익" in preservation_reason
    assert preservation_levels["target_stage"] == 1
    assert preservation_levels["sell_fraction"] == pytest.approx(0.15)
    assert preservation_levels["target_remaining_fraction"] == pytest.approx(0.85)
    assert preservation_levels["locked_profit_floor"] == 102.0
    assert tactical_partial is True
    assert "1.0배 수익" in tactical_reason
    assert tactical_levels["target_stage"] == 1
    assert tactical_levels["sell_fraction"] == pytest.approx(0.30)
    assert tactical_levels["target_remaining_fraction"] == pytest.approx(0.70)
    assert tactical_levels["locked_profit_floor"] == pytest.approx(100.5)


def test_existing_position_transitions_to_tactical_ladder_at_no_more_than_thirty_percent_per_day():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_date": date(2026, 8, 24),
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 0,
        "remaining_fraction": 1.0,
    }
    bar = quant_signals.PriceBar(
        trade_date=quant_signals.TACTICAL_EXIT_EFFECTIVE_DATE,
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    should_partial, reason, first = quant_signals._partial_exit_signal(
        bar,
        indicators[0],
        position,
        peak_price=105.0,
    )
    assert should_partial is True
    assert "단기 전술형 전환" in reason
    assert first["target_stage"] == 3
    assert first["target_remaining_fraction"] == pytest.approx(0.30)
    assert first["sell_fraction"] == pytest.approx(0.30)
    assert first["remaining_after_fraction"] == pytest.approx(0.70)

    position.update(profit_stage=3, remaining_fraction=0.70)
    _partial, _reason, second = quant_signals._partial_exit_signal(
        bar,
        indicators[0],
        position,
        peak_price=105.0,
    )
    assert second["sell_fraction"] == pytest.approx(0.30)
    assert second["remaining_after_fraction"] == pytest.approx(0.40)

    position["remaining_fraction"] = 0.40
    _partial, _reason, third = quant_signals._partial_exit_signal(
        bar,
        indicators[0],
        position,
        peak_price=105.0,
    )
    assert third["sell_fraction"] == pytest.approx(0.10)
    assert third["remaining_after_fraction"] == pytest.approx(0.30)


def test_current_tactical_transition_exposes_one_consistent_pending_stage(monkeypatch):
    bars, indicators = _strategy_test_inputs(69)
    monkeypatch.setattr(
        quant_signals,
        "PROFIT_PRESERVATION_EFFECTIVE_DATE",
        bars[60].trade_date,
    )
    monkeypatch.setattr(
        quant_signals,
        "TACTICAL_EXIT_EFFECTIVE_DATE",
        bars[68].trade_date,
    )
    _set_entry_indicator(indicators[65])
    bars[68] = quant_signals.PriceBar(
        trade_date=bars[68].trade_date,
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    simulation = quant_signals._simulate(bars, indicators)

    current, _factors = quant_signals._current_signal(
        bars,
        simulation,
        None,
        datetime.combine(bars[-1].trade_date, datetime.min.time()).replace(hour=16),
    )

    assert current["action"] == "partial_exit_pending"
    assert current["pending_profit_stage"] == 3
    assert current["pending_sell_percent"] == Decimal("30.00")
    assert current["expected_remaining_percent"] == Decimal("70.00")
    assert current["label"] == "3차 수익확정 대기"
    assert current["levels"][0]["label"] == "3차 수익확정"
    assert current["target_sell_price"] == current["levels"][0]["price"]
    assert "1차 수익확정" not in current["levels"][0]["label"]


def test_tactical_transition_never_lowers_a_profit_floor_earned_under_v71():
    _bars, indicators = _strategy_test_inputs(1)
    existing_position = {
        "entry_date": date(2026, 8, 24),
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 2,
        "remaining_fraction": 0.70,
    }
    new_position = {**existing_position, "entry_date": date(2026, 8, 25)}

    inherited = quant_signals._position_levels(
        existing_position,
        indicators[0],
        peak_price=108.0,
        strategy_date=date(2026, 8, 25),
    )
    tactical_only = quant_signals._position_levels(
        new_position,
        indicators[0],
        peak_price=108.0,
        strategy_date=date(2026, 8, 25),
    )

    assert inherited["locked_profit_floor"] == pytest.approx(106.0)
    assert tactical_only["locked_profit_floor"] == pytest.approx(103.6)
    assert inherited["hard_floor"] >= tactical_only["hard_floor"]


def test_tactical_exit_uses_shorter_holding_and_single_close_confirmation_prospectively():
    assert quant_signals._minimum_holding_bars(date(2026, 8, 24)) == 5
    assert quant_signals._exit_confirmation_bars(date(2026, 8, 24)) == 2
    assert quant_signals._minimum_holding_bars(date(2026, 8, 25)) == 3
    assert quant_signals._exit_confirmation_bars(date(2026, 8, 25)) == 1


def test_existing_position_tactical_transition_executes_only_thirty_percent(monkeypatch):
    bars, indicators = _strategy_test_inputs(72)
    monkeypatch.setattr(
        quant_signals,
        "PROFIT_PRESERVATION_EFFECTIVE_DATE",
        bars[60].trade_date,
    )
    monkeypatch.setattr(
        quant_signals,
        "TACTICAL_EXIT_EFFECTIVE_DATE",
        bars[68].trade_date,
    )
    _set_entry_indicator(indicators[65])
    bars[68] = quant_signals.PriceBar(
        trade_date=bars[68].trade_date,
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    bars[69] = quant_signals.PriceBar(
        trade_date=bars[69].trade_date,
        open=105.0,
        high=106.0,
        low=104.0,
        close=105.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    result = quant_signals._simulate(bars, indicators)
    partial = next(event for event in result["events"] if event["side"] == "partial_sell")

    assert partial["execution_date"] == bars[69].trade_date
    assert partial["profit_stage"] == 3
    assert partial["sold_percent"] == Decimal("30.00")
    assert partial["position_percent"] == Decimal("70.00")


def test_partial_profit_gap_below_protection_exits_the_remaining_position(monkeypatch):
    bars, indicators = _strategy_test_inputs(72)
    monkeypatch.setattr(
        quant_signals,
        "PROFIT_PRESERVATION_EFFECTIVE_DATE",
        bars[65].trade_date,
    )
    _set_entry_indicator(indicators[65])
    bars[67] = quant_signals.PriceBar(
        trade_date=bars[67].trade_date,
        open=100.0,
        high=104.5,
        low=99.0,
        close=104.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )
    bars[68] = quant_signals.PriceBar(
        trade_date=bars[68].trade_date,
        open=101.0,
        high=102.0,
        low=100.0,
        close=101.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    result = quant_signals._simulate(bars, indicators)
    event_sides = [event["side"] for event in result["events"]]
    sell = next(event for event in result["events"] if event["side"] == "sell")

    assert event_sides == ["buy", "sell"]
    assert sell["execution_date"] == bars[68].trade_date
    assert sell["price"] == 101
    assert sell["position_percent"] == Decimal("0.00")
    assert "시가가 수익 보호선을 하회" in sell["reason"]


def test_locked_profit_floor_is_a_hard_exit_without_two_close_confirmation():
    _bars, indicators = _strategy_test_inputs(1)
    position = {
        "entry_price": 100.0,
        "entry_cost": 0.002,
        "initial_risk": 2.0,
        "initial_stop": 96.0,
        "profit_stage": 1,
        "remaining_fraction": 0.9,
    }
    bar = quant_signals.PriceBar(
        trade_date=date(2026, 1, 2),
        open=101.0,
        high=102.0,
        low=100.0,
        close=101.0,
        volume=1_000_000,
        trading_value=50_000_000_000,
    )

    should_exit, reason, _levels, is_hard_exit = quant_signals._full_exit_signal(
        bar,
        indicators[0],
        position,
        peak_price=106.0,
    )

    assert should_exit is True
    assert is_hard_exit is True
    assert reason == "1단계 수익 보호선 이탈"


def test_quant_lifecycle_keeps_sixty_percent_runner_after_three_profit_steps():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930", 150),
        now=datetime(2026, 7, 25, 12, 0),
    )

    current = payload["current"]
    assert current["lifecycle"]["state"] == "partially_exited"
    assert current["model_exposure_percent"] == Decimal("60.00")
    assert not {
        "risk_budget_percent",
        "max_account_allocation_percent",
        "initial_account_allocation_percent",
        "suggested_account_allocation_percent",
        "estimated_loss_to_stop_percent",
        "position_sizing_note",
    }.intersection(current)
    assert current["partial_exit_date"] is not None
    assert current["partial_exit_price"] is not None
    assert current["profit_stage"] == 3
    assert current["profit_steps_total"] == 3
    assert [item["remaining_percent"] for item in current["partial_exits"]] == [
        Decimal("90.00"),
        Decimal("75.00"),
        Decimal("60.00"),
    ]
    assert current["lifecycle"]["latest_transition"]["entry_price"] == current["entry_price"]
    assert [level["key"] for level in current["levels"]] == ["full_exit"]
    assert payload["events"][-1]["label"] == "3차 수익확정"


def test_open_position_exposes_cost_adjusted_live_return_basis():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930", 150),
        now=datetime(2026, 7, 25, 12, 0),
    )

    current = payload["current"]
    basis = current["return_basis"]

    assert current["position_open"] is True
    assert basis["price"] == current["price"]
    assert basis["return_rate"].quantize(Decimal("0.01")) == current["unrealized_return"]
    assert basis["return_rate_per_price"] > 0
    assert payload["display_return_kind"] == "open_position"
    assert payload["display_return_rate"] == current["unrealized_return"]


def test_canonical_open_position_is_repriced_with_latest_live_quote(monkeypatch):
    monkeypatch.setattr(
        quant_signals,
        "is_korea_market_session_date",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda *_args, **_kwargs: date(2026, 8, 11),
    )
    payload = {
        "code": "000660",
        "as_of": datetime(2026, 8, 12, 9, 20),
        "price_through": date(2026, 8, 11),
        "current": {
            "position_open": True,
            "price": 124_000,
            "entry_price": 128_700,
            "model_exposure_percent": Decimal("100.00"),
            "unrealized_return": Decimal("-3.90"),
            "return_basis": {
                "price": 124_000,
                "return_rate": Decimal("-3.90000000"),
                "return_rate_per_price": Decimal("0.00077000"),
            },
        },
    }

    synchronized = synchronize_quant_payload_live_quote(
        payload,
        {
            "trade_date": date(2026, 8, 12),
            "trade_date_verified": True,
            "price": 125_000,
            "market_venue": "KRX",
            "market_division": "J",
        },
        now=datetime(2026, 8, 12, 9, 27),
    )

    assert synchronized["current"]["price"] == 125_000
    assert synchronized["current"]["unrealized_return"] == Decimal("-3.13")
    assert synchronized["current"]["as_of"] == datetime(2026, 8, 12, 9, 27)
    assert synchronized["display_return_rate"] == Decimal("-3.13")
    assert synchronized["display_return_kind"] == "open_position"
    assert payload["current"]["price"] == 124_000


def test_pending_entry_sync_clears_previous_trade_metrics_without_deleting_history():
    payload = {
        "code": "088350",
        "current": {
            "action": "entry_pending",
            "position_open": False,
            "price": 5_450,
            "entry_date": None,
            "entry_price": None,
            "target_sell_price": 5_593,
            "target_sell_status": "missed",
            "target_sell_delta": -603,
            "unrealized_return": None,
            "return_basis": None,
            "lifecycle": {
                "latest_transition": {
                    "side": "sell",
                    "transition_date": date(2026, 5, 29),
                    "price": 4_990,
                    "entry_price": 4_830,
                    "target_sell_price": 5_593,
                }
            },
        },
        "display_return_rate": Decimal("10.21"),
        "display_return_kind": "closed_trade",
        "display_return_event_date": date(2026, 5, 29),
        "display_return_event_side": "sell",
        "events": [
            {
                "side": "sell",
                "execution_date": date(2026, 5, 29),
                "entry_price": 4_830,
                "target_sell_price": 5_593,
                "return_rate": Decimal("10.21"),
            }
        ],
        "trades": [
            {
                "entry_date": date(2026, 4, 24),
                "entry_price": 4_830,
                "target_sell_price": 5_593,
                "exit_date": date(2026, 5, 29),
                "net_return": Decimal("10.21"),
            }
        ],
    }

    synchronized = synchronize_quant_payload_live_quote(payload, None)

    assert synchronized["current"]["price"] == 5_450
    assert synchronized["current"]["entry_price"] is None
    assert synchronized["current"]["target_sell_price"] is None
    assert synchronized["current"]["target_sell_status"] is None
    assert synchronized["current"]["target_sell_delta"] is None
    assert synchronized["display_return_rate"] is None
    assert synchronized["display_return_kind"] is None
    assert synchronized["display_return_event_date"] is None
    assert synchronized["display_return_event_side"] is None
    assert synchronized["current"]["lifecycle"]["latest_transition"]["entry_price"] == 4_830
    assert synchronized["events"][0]["return_rate"] == Decimal("10.21")
    assert synchronized["trades"][0]["net_return"] == Decimal("10.21")
    assert payload["current"]["target_sell_price"] == 5_593
    assert payload["display_return_rate"] == Decimal("10.21")


def test_market_pending_entry_sanitizer_cleans_cached_and_history_items():
    stale_fields = {
        "entry_price": 4_830,
        "target_sell_price": 5_593,
        "target_sell_status": "missed",
        "target_sell_delta": -603,
        "return_rate": Decimal("10.21"),
        "display_return_rate": Decimal("10.21"),
        "display_return_kind": "closed_trade",
        "display_return_event_date": date(2026, 5, 29),
        "display_return_event_side": "sell",
    }
    payload = {
        "items": [
            {
                **stale_fields,
                "action": "entry_pending",
                "status": "preliminary",
                "is_current_holding": False,
                "current": {
                    "action": "entry_pending",
                    "position_open": False,
                    "target_sell_price": 5_593,
                    "target_sell_status": "missed",
                    "target_sell_delta": -603,
                },
            }
        ],
        "preliminary_history": [
            {
                **stale_fields,
                "action": "entry_pending",
                "status": "preliminary",
                "is_current_holding": False,
            }
        ],
    }

    sanitized = quant_signals.sanitize_pending_entry_signal_items(payload)

    for item in (sanitized["items"][0], sanitized["preliminary_history"][0]):
        assert item["entry_price"] is None
        assert item["target_sell_price"] is None
        assert item["target_sell_status"] is None
        assert item["target_sell_delta"] is None
        assert item["return_rate"] is None
        assert item["display_return_rate"] is None
        assert item["display_return_kind"] is None
        assert item["display_return_event_date"] is None
        assert item["display_return_event_side"] is None
    assert payload["items"][0]["entry_price"] == 4_830
    assert payload["preliminary_history"][0]["display_return_rate"] == Decimal("10.21")


def test_future_price_changes_do_not_rewrite_past_signals():
    rows = _price_rows("005930")
    changed_rows = _price_rows("005930")
    cutoff_index = 285
    for index in range(cutoff_index + 1, len(changed_rows)):
        changed_rows[index].open = max(1, changed_rows[index].open // 4)
        changed_rows[index].high = max(1, changed_rows[index].high // 4)
        changed_rows[index].low = max(1, changed_rows[index].low // 4)
        changed_rows[index].close = max(1, changed_rows[index].close // 4)

    original = build_quant_signal_payload(_stock(), rows, now=datetime(2026, 7, 25, 12, 0))
    changed = build_quant_signal_payload(_stock(), changed_rows, now=datetime(2026, 7, 25, 12, 0))
    cutoff = rows[cutoff_index].trade_date

    def past_events(payload):
        return [
            (event["signal_date"], event["execution_date"], event["side"], event["price"])
            for event in payload["events"]
            if event["execution_date"] <= cutoff
        ]

    assert past_events(original) == past_events(changed)


def test_quant_signals_report_insufficient_history_without_fake_result():
    payload = build_quant_signal_payload(
        _stock(),
        _price_rows("005930", MIN_HISTORY_ROWS - 1),
        now=datetime(2026, 7, 25, 12, 0),
    )

    assert payload["data_state"] == "insufficient"
    assert payload["current"] is None
    assert payload["performance"] is None
    assert payload["events"] == []


def test_quant_signals_ignore_weekend_price_rows():
    rows = [
        DailyPrice(code="005930", trade_date=date(2026, 7, 31), close=100, volume=100),
        DailyPrice(code="005930", trade_date=date(2026, 8, 1), close=120, volume=100),
        DailyPrice(code="005930", trade_date=date(2026, 8, 2), close=130, volume=100),
    ]

    bars = quant_signals._normalize_prices(rows)

    assert [bar.trade_date for bar in bars] == [date(2026, 7, 31)]


def test_quant_signals_estimate_missing_trading_value_from_close_and_volume():
    rows = [
        DailyPrice(
            code="005930",
            trade_date=date(2026, 7, 31),
            close=80_000,
            volume=1_000_000,
            trading_value=None,
        )
    ]

    bars = quant_signals._normalize_prices(rows)

    assert bars[0].trading_value == 80_000_000_000


def test_quant_signals_ignore_non_trading_weekday_placeholders():
    rows = [
        DailyPrice(
            code="000880",
            trade_date=date(2026, 7, 29),
            open=87_100,
            high=90_100,
            low=79_400,
            close=83_800,
            volume=399_375,
            trading_value=33_467_625_000,
        ),
        DailyPrice(
            code="000880",
            trade_date=date(2026, 7, 30),
            open=0,
            high=0,
            low=0,
            close=83_800,
            volume=0,
            trading_value=0,
        ),
    ]

    bars = quant_signals._normalize_prices(rows)

    assert [bar.trade_date for bar in bars] == [date(2026, 7, 29)]


def test_quant_signal_payload_labels_completed_non_trading_placeholder(monkeypatch):
    rows = _price_rows("000880")
    placeholder_date = rows[-1].trade_date + timedelta(days=1)
    while placeholder_date.weekday() >= 5:
        placeholder_date += timedelta(days=1)
    rows.append(
        DailyPrice(
            code="000880",
            trade_date=placeholder_date,
            open=0,
            high=0,
            low=0,
            close=rows[-1].close,
            volume=0,
            trading_value=0,
        )
    )
    monkeypatch.setattr(
        quant_signals,
        "latest_completed_korea_market_session_date",
        lambda _now: placeholder_date,
    )

    payload = build_quant_signal_payload(
        _stock("000880", "한화"),
        rows,
        now=datetime(
            placeholder_date.year,
            placeholder_date.month,
            placeholder_date.day,
            18,
        ),
    )

    assert payload["data_state"] == "ready"
    assert payload["trading_state"] == "non_trading"
    assert payload["trading_state_label"] == "거래정지·무거래 확인"
    assert payload["price_through"] == rows[-2].trade_date
    assert "종가 반복 행은 신호 산출에서 제외" in payload["data_message"]


def test_stock_signal_response_preserves_non_trading_state(monkeypatch):
    db = _session()
    db.add(_stock("000880", "한화"))
    db.commit()
    payload = build_quant_signal_payload(
        _stock("000880", "한화"),
        _price_rows("000880"),
        now=datetime(2026, 8, 21, 18, 0),
    )
    payload["trading_state"] = "non_trading"
    payload["trading_state_label"] = "거래정지·무거래 확인"

    def override_db():
        yield db

    monkeypatch.setattr(main, "ensure_stock_price_history", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(main, "_fetch_uncached_current_quote", lambda *_args, **_kwargs: ({}, "test"))
    monkeypatch.setattr(main, "load_reference_quant_signal_payload", lambda *_args, **_kwargs: payload)
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/stocks/000880/quant-signals")

        assert response.status_code == 200
        assert response.json()["trading_state"] == "non_trading"
        assert response.json()["trading_state_label"] == "거래정지·무거래 확인"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_quant_signals_stop_when_a_weekday_candle_has_no_confirmed_open():
    rows = _price_rows("096770")
    rows[-2].open = None
    rows[-2].high = None
    rows[-2].low = None

    payload = build_quant_signal_payload(
        _stock("096770", "SK이노베이션"),
        rows,
        now=datetime(2026, 8, 12, 18, 0),
    )

    assert payload["data_state"] == "incomplete"
    assert "가격 이력을 보강한 뒤 다시 계산" in payload["data_message"]
    assert payload["current"] is None
    assert payload["performance"] is None
    assert payload["events"] == []
    assert payload["trades"] == []


def test_quant_signals_use_complete_history_after_an_old_incomplete_candle():
    rows = _price_rows("096770", MIN_HISTORY_ROWS + 40)
    rows[10].open = None
    rows[10].high = None
    rows[10].low = None

    payload = build_quant_signal_payload(
        _stock("096770", "SK이노베이션"),
        rows,
        now=datetime(2026, 8, 12, 18, 0),
    )

    assert payload["data_state"] == "ready"
    assert payload["data_rows"] == len(rows) - 11
    assert "오래된 불완전 일봉 1건은 제외" in payload["data_message"]
    assert payload["current"] is not None


def test_close_only_row_is_not_treated_as_a_real_open_price():
    row = DailyPrice(
        code="096770",
        trade_date=date(2026, 8, 11),
        close=128_700,
        volume=190_638,
    )

    bar = quant_signals._normalize_prices([row])[0]
    _bars, indicators = _strategy_test_inputs(1)
    _set_entry_indicator(indicators[0])

    assert bar.open == 128_700
    assert bar.ohlc_complete is False
    assert quant_signals._entry_signal(bar, indicators[0]) is False


def test_quant_signal_endpoint_uses_same_engine_for_multiple_stocks(monkeypatch):
    db = _session()
    db.add_all([_stock(), _stock("000660", "SK하이닉스")])
    db.add_all(_price_rows("005930") + _price_rows("000660"))
    db.commit()

    def override_db():
        yield db

    monkeypatch.setattr(main, "ensure_stock_price_history", lambda *_args, **_kwargs: 340)
    monkeypatch.setattr(
        main,
        "_fetch_kis_current_quote",
        lambda code: {
            "trade_date": date(2026, 7, 25),
            "price": 25_000 if code == "005930" else 30_000,
            "volume": 2_000_000,
        },
    )
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        samsung = client.get("/stocks/005930/quant-signals")
        hynix = client.get("/stocks/000660/quant-signals")
        assert samsung.status_code == 200
        assert hynix.status_code == 200
        assert samsung.headers["cache-control"].startswith("no-store")
        assert samsung.json()["strategy_version"] == hynix.json()["strategy_version"]
        assert samsung.json()["entry_score_threshold"] == "64.00"
        assert samsung.json()["performance"]["turnover_percent"] is not None
        assert samsung.json()["performance"]["execution_count"] > 0
        assert all(event["entry_price"] is not None for event in samsung.json()["events"])
        assert samsung.json()["current"]["lifecycle"]["latest_transition"]["entry_price"] is not None
        assert samsung.json()["code"] == "005930"
        assert hynix.json()["code"] == "000660"
        assert samsung.json()["signal_source"] == "local"
        assert samsung.json()["current"]["live_observation"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_quant_signal_endpoint_returns_canonical_state_before_local_refresh(monkeypatch):
    db = _session()
    canonical = build_quant_signal_payload(
        _stock("175330", "JB금융지주"),
        _price_rows("175330"),
        now=datetime(2026, 8, 4, 16, 0),
    )
    canonical["signal_source"] = "canonical"

    def override_db():
        yield db

    monkeypatch.setattr(main, "load_external_stock_quant_signal_payload", lambda *_args, **_kwargs: canonical)
    monkeypatch.setattr(main, "_fetch_uncached_current_quote", lambda _code: ({}, "test"))
    monkeypatch.setattr(
        main,
        "ensure_stock_price_history",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("local history refreshed")),
    )
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/stocks/175330/quant-signals")

        assert response.status_code == 200
        assert response.json()["code"] == "175330"
        assert response.json()["signal_source"] == "canonical"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_watchlist_quant_signal_endpoint_aggregates_the_same_strategy_without_cache(monkeypatch):
    db = _session()
    samsung = _stock()
    samsung.sector = "전기·전자"
    samsung.industry = "반도체와반도체장비"
    hynix = _stock("000660", "SK하이닉스")
    hynix.sector = "전기·전자"
    hynix.industry = "반도체와반도체장비"
    db.add_all([samsung, hynix])
    db.add_all(_price_rows("005930") + _price_rows("000660"))
    db.add_all(
        [
            WatchlistItem(share_id="tester", code="005930", name="삼성전자", market="KOSPI", sort_order=0),
            WatchlistItem(share_id="tester", code="000660", name="SK하이닉스", market="KOSPI", sort_order=1),
        ]
    )
    db.commit()

    def override_db():
        yield db

    monkeypatch.setattr(main, "_watchlist_quant_signal_live_quotes", lambda *_args, **_kwargs: {})
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/watchlists/tester/quant-signals")
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        payload = response.json()
        assert payload["share_id"] == "tester"
        assert [item["code"] for item in payload["items"]] == ["005930", "000660"]
        assert all(item["current"] for item in payload["items"])
        assert all(item["entry_price"] is not None for item in payload["items"])
        assert all(
            not item["current"]["position_open"]
            or item["entry_price"] == item["current"]["entry_price"]
            for item in payload["items"]
        )
        assert all(item["data_state"] == "ready" for item in payload["items"])
        assert all(item["signal_source"] == "local" for item in payload["items"])
        assert all(item["investment_sector"] == "semiconductor" for item in payload["items"])
        assert all(item["investment_sector_label"] == "반도체" for item in payload["items"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


@pytest.mark.parametrize("pending_action", ["entry_watch", "entry_pending"])
def test_watchlist_pending_entry_does_not_reuse_previous_trade_metrics(monkeypatch, pending_action):
    db = _session()
    db.add(_stock("088350", "한화생명"))
    db.add(
        WatchlistItem(
            share_id="pending-entry-tester",
            code="088350",
            name="한화생명",
            market="KOSPI",
            sort_order=0,
        )
    )
    db.commit()

    previous_transition = {
        "side": "sell",
        "execution_date": date(2026, 5, 29),
        "transition_date": date(2026, 5, 29),
        "price": 4_990,
        "entry_price": 4_830,
        "target_sell_price": 5_593,
        "target_sell_status": "missed",
        "target_sell_delta": -603,
        "return_rate": Decimal("10.21"),
    }

    def signal_payload(_db, _code, **kwargs):
        return {
            "data_state": "ready",
            "data_message": "ready",
            "as_of": kwargs["now"],
            "price_through": date(2026, 8, 20),
            "signal_source": "canonical",
            "events": [previous_transition],
            "trades": [
                {
                    "entry_price": 4_830,
                    "target_sell_price": 5_593,
                    "net_return": Decimal("10.21"),
                }
            ],
            "display_return_rate": Decimal("10.21"),
            "display_return_kind": "closed_trade",
            "display_return_event_date": date(2026, 5, 29),
            "display_return_event_side": "sell",
            "current": {
                "action": pending_action,
                "live_observation": True,
                "position_open": False,
                "price": 5_450,
                "entry_price": None,
                "target_sell_price": 5_593,
                "target_sell_status": "missed",
                "target_sell_delta": -603,
                "unrealized_return": None,
                "lifecycle": {"latest_transition": previous_transition},
            },
        }

    def override_db():
        yield db

    monkeypatch.setattr(main, "_watchlist_quant_signal_live_quotes", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(main, "load_reference_quant_signal_payload", signal_payload)
    main.watchlist_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/watchlists/pending-entry-tester/quant-signals")

        assert response.status_code == 200
        body = response.json()
        item = body["items"][0]
        assert body["strategy_version"] == STRATEGY_VERSION
        assert item["strategy_version"] == STRATEGY_VERSION
        assert item["status"] == "preliminary"
        assert item["is_preliminary"] is True
        assert item["side"] == "buy"
        assert item["signal_date"] == body["as_of"][:10]
        assert item["execution_date"] is None
        assert item["entry_price"] is None
        assert item["return_rate"] is None
        assert item["display_return_rate"] is None
        assert item["display_return_kind"] is None
        assert item["display_return_event_date"] is None
        assert item["display_return_event_side"] is None
        assert item["current"]["entry_price"] is None
        assert item["current"]["target_sell_price"] is None
        assert item["current"]["target_sell_status"] is None
        assert item["current"]["target_sell_delta"] is None
        assert item["current"]["lifecycle"]["latest_transition"]["entry_price"] == 4_830
        assert item["current"]["lifecycle"]["latest_transition"]["target_sell_price"] == 5_593
    finally:
        main.watchlist_quant_signal_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_quant_signal_list_summary_copies_stock_detail_identity_and_live_return():
    signal_date = date(2026, 8, 20)
    execution_date = date(2026, 8, 21)
    payload = {
        "strategy_version": STRATEGY_VERSION,
        "data_state": "ready",
        "as_of": datetime(2026, 8, 21, 12, 20),
        "price_through": execution_date,
        "display_return_rate": Decimal("-3.60"),
        "display_return_kind": "open_position",
        "display_return_event_date": execution_date,
        "display_return_event_side": "buy",
        "events": [
            {
                "label": "확정 매수",
                "side": "buy",
                "signal_at": datetime(2026, 8, 20, 15, 40),
                "signal_date": signal_date,
                "execution_date": execution_date,
                "price": 130_000,
                "entry_price": 130_000,
            }
        ],
        "current": {
            "action": "holding",
            "position_open": True,
            "live_observation": True,
            "as_of": datetime(2026, 8, 21, 12, 20),
            "price": 125_000,
            "entry_price": 130_000,
            "lifecycle": {
                "latest_transition": {
                    "label": "확정 매수",
                    "side": "buy",
                    "signal_at": datetime(2026, 8, 20, 15, 40),
                    "signal_date": signal_date,
                    "transition_date": execution_date,
                    "price": 130_000,
                    "entry_price": 130_000,
                }
            },
        },
    }

    summary = quant_signal_current_summary_fields(payload)

    assert summary["strategy_version"] == payload["strategy_version"]
    assert summary["signal_date"] == signal_date
    assert summary["execution_date"] == execution_date
    assert summary["entry_price"] == payload["current"]["entry_price"]
    assert summary["display_return_rate"] == payload["display_return_rate"]
    assert summary["return_rate"] == payload["display_return_rate"]
    assert summary["display_return_kind"] == payload["display_return_kind"]
    assert summary["current"] == payload["current"]


def test_quant_signal_list_summary_keeps_weekend_pending_signal_on_last_close():
    signal_date = date(2026, 8, 28)
    weekend_refresh = datetime(2026, 8, 30, 12, 38, tzinfo=quant_signals.KST)
    payload = {
        "strategy_version": STRATEGY_VERSION,
        "data_state": "ready",
        "as_of": weekend_refresh,
        "price_through": signal_date,
        "events": [],
        "current": {
            "action": "entry_watch",
            "position_open": False,
            "live_observation": False,
            "as_of": weekend_refresh,
            "price": 370_000,
            "score": Decimal("81.83"),
            "lifecycle": {"latest_transition": None},
        },
    }

    summary = quant_signal_current_summary_fields(payload)

    assert summary["status"] == "preliminary"
    assert summary["signal_date"] == signal_date
    assert summary["signal_at"] == datetime(
        2026,
        8,
        28,
        15,
        40,
        tzinfo=quant_signals.KST,
    )
    assert summary["execution_date"] is None


def test_watchlist_signal_row_matches_the_same_stock_detail_payload(monkeypatch):
    db = _session()
    db.add(_stock("005930", "삼성전자"))
    db.add_all(_price_rows("005930"))
    db.add(
        WatchlistItem(
            share_id="detail-parity-tester",
            code="005930",
            name="삼성전자",
            market="KOSPI",
            sort_order=0,
        )
    )
    db.commit()

    def override_db():
        yield db

    monkeypatch.setattr(main, "_watchlist_quant_signal_live_quotes", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(main, "_fetch_uncached_current_quote", lambda *_args, **_kwargs: ({}, "test"))
    monkeypatch.setattr(main, "ensure_stock_price_history", lambda *_args, **_kwargs: 0)
    main.watchlist_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        watch_response = client.get("/watchlists/detail-parity-tester/quant-signals")
        detail_response = client.get("/stocks/005930/quant-signals")

        assert watch_response.status_code == 200
        assert detail_response.status_code == 200
        row = watch_response.json()["items"][0]
        detail = detail_response.json()
        transition = detail["current"]["lifecycle"]["latest_transition"]
        assert row["strategy_version"] == detail["strategy_version"] == STRATEGY_VERSION
        assert row["current"]["action"] == detail["current"]["action"]
        assert row["current"]["position_open"] == detail["current"]["position_open"]
        assert row["entry_price"] == (
            detail["current"]["entry_price"] or transition["entry_price"]
        )
        assert Decimal(str(row["display_return_rate"])) == Decimal(
            str(detail["display_return_rate"])
        )
        assert row["display_return_kind"] == detail["display_return_kind"]
        assert row["signal_date"] == transition["signal_date"]
        assert row["execution_date"] == transition["transition_date"]
    finally:
        main.watchlist_quant_signal_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_watchlist_quant_signal_endpoint_reprices_after_close_instead_of_using_stale_cache(monkeypatch):
    db = _session()
    db.add(
        WatchlistItem(
            share_id="live-tester",
            code="096770",
            name="SK이노베이션",
            market="KOSPI",
            sort_order=0,
        )
    )
    db.commit()
    quote_prices = iter((125_000, 122_500))
    received_prices = []

    def override_db():
        yield db

    def live_quotes(_codes, _now=None):
        return {"096770": {"trade_date": date(2026, 8, 12), "price": next(quote_prices)}}

    def signal_payload(_db, code, **kwargs):
        received_prices.append(kwargs["live_quote"]["price"])
        live_display_return = Decimal("-3.60") if kwargs["live_quote"]["price"] == 125_000 else Decimal("-5.52")
        return {
            "data_state": "ready",
            "data_message": "ready",
            "as_of": kwargs["now"],
            "price_through": date(2026, 8, 12),
            "signal_source": "local",
            "events": [{"side": "sell", "return_rate": Decimal("99.99")}],
            "display_return_rate": live_display_return,
            "display_return_kind": "open_position",
            "display_return_event_date": date(2026, 8, 11),
            "display_return_event_side": "buy",
            "current": {
                "action": "holding",
                "position_open": True,
                "price": kwargs["live_quote"]["price"],
                "entry_price": 130_000,
            },
        }

    monkeypatch.setattr(main, "is_korea_regular_market_session", lambda _now=None: False)
    monkeypatch.setattr(main, "_quant_signal_quote_refresh_active", lambda _now=None: True)
    monkeypatch.setattr(main, "_watchlist_quant_signal_live_quotes", live_quotes)
    monkeypatch.setattr(main, "load_reference_quant_signal_payload", signal_payload)
    main.watchlist_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        first = client.get("/watchlists/live-tester/quant-signals")
        second = client.get("/watchlists/live-tester/quant-signals")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["items"][0]["current"]["price"] == 125_000
        assert second.json()["items"][0]["current"]["price"] == 122_500
        assert first.json()["items"][0]["return_rate"] == -3.6
        assert second.json()["items"][0]["return_rate"] == -5.52
        assert second.json()["items"][0]["display_return_kind"] == "open_position"
        assert second.json()["items"][0]["entry_price"] == 130_000
        assert second.json()["live_quotes"] is True
        assert received_prices == [125_000, 122_500]
    finally:
        main.watchlist_quant_signal_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_watchlist_quote_loader_fetches_a_fresh_close_mark_outside_regular_session(monkeypatch):
    received_codes = []

    def current_quote(code):
        received_codes.append(code)
        return {"trade_date": date(2026, 8, 12), "price": 122_500}, "kis_rest"

    monkeypatch.setattr(main, "_fetch_uncached_current_quote", current_quote)

    quotes = main._watchlist_quant_signal_live_quotes(
        ["096770", "096770"],
        datetime(2026, 8, 12, 20, 0),
    )

    assert quotes == {"096770": {"trade_date": date(2026, 8, 12), "price": 122_500}}
    assert received_codes == ["096770"]


def test_quant_signal_quote_refresh_stays_active_through_post_close_window(monkeypatch):
    monkeypatch.setattr(main, "is_korea_regular_market_session", lambda _now=None: False)
    monkeypatch.setattr(main, "is_korea_market_session_date", lambda *_args: True)

    assert main._quant_signal_quote_refresh_active(datetime(2026, 8, 12, 16, 27)) is True
    assert main._quant_signal_quote_refresh_active(datetime(2026, 8, 12, 18, 1)) is False


def test_market_quant_signal_feed_returns_all_recent_transitions_and_normalizes_sell(monkeypatch):
    db = _session()
    stocks = [_stock("000001", "대형주"), _stock("000002", "중형주"), _stock("000003", "소형주")]
    stocks[0].sector = "전기·전자"
    stocks[0].industry = "반도체와반도체장비"
    stocks[1].sector = "음식료·담배"
    stocks[1].industry = "식품"
    trade_date = date(2026, 7, 25)
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=trade_date, close=100_000, market_cap=300_000_000),
            DailyPrice(code="000002", trade_date=trade_date, close=50_000, market_cap=200_000_000),
            DailyPrice(code="000003", trade_date=trade_date, close=10_000, market_cap=100_000_000),
        ]
    )
    db.commit()

    def signal_payload(stock, _rows, **_kwargs):
        events = [
            {
                "signal_date": trade_date - timedelta(days=1),
                "execution_date": trade_date,
                "side": "buy" if stock.code == "000001" else "partial_sell",
                "price": 100_000,
                "entry_price": 100_000 if stock.code == "000001" else 95_000,
                "score": 77.5,
                "reason": "거래대금과 추세 조건 충족",
                "holding_days": 6,
                "position_percent": 50,
                "state_after": "holding" if stock.code == "000001" else "partially_exited",
            }
        ]
        if stock.code == "000001":
            events.insert(
                0,
                {
                    "signal_date": trade_date - timedelta(days=6),
                    "execution_date": trade_date - timedelta(days=5),
                    "side": "sell",
                    "price": 90_000,
                    "entry_price": 88_000,
                    "score": 68.0,
                    "reason": "청산 기준 충족",
                    "holding_days": 12,
                    "position_percent": 0,
                    "state_after": "exited",
                },
            )
        return {
            "events": events,
            "current": (
                {
                    "action": "holding",
                    "position_open": True,
                    "unrealized_return": Decimal("4.25"),
                    "entry_date": trade_date,
                }
                if stock.code == "000001"
                else None
            ),
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", signal_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 7, 26, 9, 0),
    )

    assert payload["universe_count"] == 2
    assert [item["code"] for item in payload["items"]] == ["000001", "000002", "000001"]
    assert [item["signal"] for item in payload["items"]] == ["매수", "수익확정", "전량 매도"]
    assert [item["event_side"] for item in payload["items"]] == ["buy", "partial_sell", "sell"]
    assert [item["market_cap_rank"] for item in payload["items"]] == [1, 2, 1]
    assert [item["score"] for item in payload["items"]] == [77.5, 77.5, 68.0]
    assert [item["reason"] for item in payload["items"]] == [
        "거래대금과 추세 조건 충족",
        "거래대금과 추세 조건 충족",
        "청산 기준 충족",
    ]
    assert [item["holding_days"] for item in payload["items"]] == [6, 6, 12]
    assert [item["position_percent"] for item in payload["items"]] == [50, 50, 0]
    assert [item["state_after"] for item in payload["items"]] == ["holding", "partially_exited", "exited"]
    assert [item["entry_price"] for item in payload["items"]] == [100_000, 95_000, 88_000]
    assert payload["items"][0]["display_return_rate"] == Decimal("4.25")
    assert payload["items"][0]["display_return_kind"] == "open_position"
    assert payload["items"][0]["is_current_holding"] is True
    assert payload["items"][0]["current"]["unrealized_return"] == Decimal("4.25")
    assert [item["investment_sector_label"] for item in payload["items"]] == ["반도체", "소비재", "반도체"]
    db.close()


def test_signal_sector_enrichment_falls_back_to_company_snapshot():
    db = _session()
    db.add(_stock("003230", "삼양식품"))
    db.add(
        StockCompanySnapshot(
            stock_code="003230",
            source="naver_wisereport",
            summary="식품 기업",
            sector="음식료·담배",
            industry="식품",
            source_url="https://example.test/003230",
            fetched_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
    )
    db.commit()

    stock_payload = enrich_quant_signal_payload_sector(
        db,
        {"code": "003230", "sector": None, "industry": None},
    )
    market_payload = enrich_market_quant_signal_sectors(
        db,
        {"items": [{"code": "003230", "sector": None, "industry": None}]},
    )

    assert stock_payload["investment_sector_label"] == "소비재"
    assert market_payload["items"][0]["investment_sector_label"] == "소비재"
    db.close()


def test_market_signal_ohlc_repair_selects_only_traded_incomplete_universe_rows():
    db = _session()
    trade_date = date(2026, 8, 12)
    db.add_all(
        [
            _stock("000001", "보강대상"),
            _stock("000002", "거래정지"),
            _stock("000003", "순위밖"),
        ]
    )
    db.add_all(
        [
            DailyPrice(
                code="000001",
                trade_date=trade_date,
                close=100,
                volume=1_000,
                trading_value=100_000,
                market_cap=300,
            ),
            DailyPrice(
                code="000002",
                trade_date=trade_date,
                close=100,
                volume=0,
                trading_value=0,
                market_cap=200,
            ),
            DailyPrice(
                code="000003",
                trade_date=trade_date,
                close=100,
                volume=1_000,
                trading_value=100_000,
                market_cap=100,
            ),
        ]
    )
    db.commit()

    codes = main._market_quant_signal_ohlc_repair_codes(
        db,
        universe_limit=2,
        recent_days=30,
    )

    assert codes == ["000001"]
    db.close()


def test_market_quant_signal_feed_keeps_recent_event_after_latest_rank_exit(monkeypatch):
    db = _session()
    previous_date = date(2026, 8, 10)
    current_date = date(2026, 8, 11)
    stocks = [
        _stock("000001", "상위주"),
        _stock("000002", "신규상위주"),
        _stock("271560", "오리온"),
    ]
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=previous_date, close=100, market_cap=300),
            DailyPrice(code="271560", trade_date=previous_date, close=100, market_cap=200),
            DailyPrice(code="000002", trade_date=previous_date, close=100, market_cap=100),
            DailyPrice(code="000001", trade_date=current_date, close=100, market_cap=300),
            DailyPrice(code="000002", trade_date=current_date, close=100, market_cap=250),
            DailyPrice(code="271560", trade_date=current_date, close=100, market_cap=200),
        ]
    )
    db.commit()

    def signal_payload(stock, _rows, **_kwargs):
        if stock.code != "271560":
            return {"events": [], "current": None}
        return {
            "events": [
                {
                    "signal_date": previous_date - timedelta(days=3),
                    "execution_date": previous_date,
                    "side": "buy",
                    "price": 136_200,
                    "score": 73.24,
                    "reason": "상승 추세와 모멘텀 확인",
                }
            ],
            "current": {
                "action": "entry_pending",
                "live_observation": True,
                "price": 136_000,
                "score": Decimal("71.00"),
                "as_of": datetime(2026, 8, 11, 13, 20),
                "reasons": ["장중 조건 충족"],
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", signal_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 11, 13, 20),
        live_quotes={"271560": {"trade_date": current_date, "price": 136_000}},
    )

    assert payload["current_universe_count"] == 2
    assert payload["universe_count"] == 3
    assert [item["code"] for item in payload["items"]] == ["271560"]
    assert payload["items"][0]["signal"] == "매수"
    assert payload["items"][0]["status"] == "confirmed"
    assert payload["items"][0]["market_cap_rank"] == 2
    db.close()


def test_market_quant_signal_feed_admits_only_qualified_extended_candidate(monkeypatch):
    db = _session()
    current_date = date(2026, 8, 27)
    current_time = datetime(2026, 8, 27, 16, 0)
    core_stocks = [
        _stock(f"{index:06d}", f"핵심{index}")
        for index in range(1, 101)
    ]
    liquid = _stock("900101", "확장고유동성")
    illiquid = _stock("900102", "확장저유동성")
    db.add_all([*core_stocks, liquid, illiquid])
    db.add_all(
        [
            DailyPrice(
                code=stock.code,
                trade_date=current_date,
                open=100,
                high=103,
                low=99,
                close=102,
                volume=1_000_000,
                trading_value=102_000_000_000,
                market_cap=2_000_000_000_000 - index,
            )
            for index, stock in enumerate(core_stocks)
        ]
    )
    history_dates = []
    cursor = current_date
    while len(history_dates) < 20:
        if cursor.weekday() < 5:
            history_dates.append(cursor)
        cursor -= timedelta(days=1)
    history_dates.reverse()
    for stock, trading_value, market_cap in (
        (liquid, 25_000_000_000, 900_000_000_000),
        (illiquid, 10_000_000_000, 800_000_000_000),
    ):
        db.add_all(
            [
                DailyPrice(
                    code=stock.code,
                    trade_date=trade_date,
                    open=100,
                    high=104,
                    low=99,
                    close=103,
                    volume=1_000_000,
                    trading_value=trading_value,
                    market_cap=market_cap if trade_date == current_date else None,
                )
                for trade_date in history_dates
            ]
        )
    db.commit()

    monkeypatch.setattr(
        quant_signals,
        "load_entry_evidence_timeline",
        lambda *_args, **_kwargs: {current_date: {}},
    )

    def signal_payload(stock, _rows, **_kwargs):
        if stock.code not in {liquid.code, illiquid.code}:
            return {"price_through": current_date, "events": [], "current": None}
        return {
            "price_through": current_date,
            "events": [],
            "current": {
                "action": "entry_pending",
                "position_open": False,
                "live_observation": False,
                "price": 103,
                "score": Decimal("72.00"),
                "as_of": current_time,
                "reasons": ["가격·근거 승인 완료"],
                "entry_confirmation": {
                    "allowed": True,
                    "state": "approved",
                },
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", signal_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=150,
        limit=0,
        recent_days=30,
        now=current_time,
    )

    assert payload["core_universe_count"] == 100
    assert payload["extended_universe_count"] == 2
    assert payload["extended_qualified_count"] == 1
    assert any(item["code"] == liquid.code for item in payload["items"])
    assert all(item["code"] != illiquid.code for item in payload["items"])
    item = next(item for item in payload["items"] if item["code"] == liquid.code)
    assert item["market_cap_rank"] == 101
    assert item["universe_tier"] == "extended"
    assert item["extended_universe_qualified"] is True
    assert item["average_trading_value_20"] == 25_000_000_000
    db.close()


def test_market_quant_signal_feed_retains_pending_entry_after_rank_exit(monkeypatch):
    db = _session()
    first_date = date(2026, 8, 26)
    second_date = date(2026, 8, 27)
    stocks = [
        _stock("000001", "1위주"),
        _stock("000002", "진행신호"),
        _stock("000003", "신규2위주"),
    ]
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=first_date, close=100, market_cap=300),
            DailyPrice(code="000002", trade_date=first_date, close=100, market_cap=200),
            DailyPrice(code="000003", trade_date=first_date, close=100, market_cap=100),
        ]
    )
    db.commit()

    signal_date = first_date

    def signal_payload(stock, _rows, **_kwargs):
        if stock.code != "000002":
            return {"price_through": signal_date, "events": [], "current": None}
        return {
            "price_through": signal_date,
            "events": [],
            "current": {
                "action": "entry_pending",
                "position_open": False,
                "live_observation": False,
                "price": 100,
                "score": Decimal("70.00"),
                "as_of": datetime.combine(signal_date, datetime.min.time()).replace(hour=16),
                "reasons": ["다음 거래일 시가 체결 대기"],
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", signal_payload)
    first_payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 26, 16, 0),
    )
    quant_signals.save_market_quant_signal_snapshot(
        db,
        first_payload,
        universe_limit=2,
        limit=0,
        recent_days=30,
    )

    db.add_all(
        [
            DailyPrice(code="000001", trade_date=second_date, close=100, market_cap=300),
            DailyPrice(code="000003", trade_date=second_date, close=100, market_cap=250),
            DailyPrice(code="000002", trade_date=second_date, close=100, market_cap=200),
        ]
    )
    db.commit()
    signal_date = second_date

    retained = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 27, 16, 0),
    )

    pending = next(item for item in retained["items"] if item["code"] == "000002")
    assert pending["is_preliminary"] is True
    assert pending["universe_tier"] == "core"
    assert pending["universe_tracking_state"] == "retained"
    assert pending["universe_tracking_label"] == "진행 시그널 유지"
    assert retained["retained_signal_count"] == 1
    db.close()


def test_market_quant_signal_feed_keeps_pending_exit_after_latest_rank_exit(monkeypatch):
    db = _session()
    previous_date = date(2026, 8, 10)
    current_date = date(2026, 8, 11)
    stocks = [
        _stock("000001", "상위주"),
        _stock("000002", "신규상위주"),
        _stock("271560", "오리온"),
    ]
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=previous_date, close=100, market_cap=300),
            DailyPrice(code="271560", trade_date=previous_date, close=100, market_cap=200),
            DailyPrice(code="000002", trade_date=previous_date, close=100, market_cap=100),
            DailyPrice(code="000001", trade_date=current_date, close=100, market_cap=300),
            DailyPrice(code="000002", trade_date=current_date, close=100, market_cap=250),
            DailyPrice(code="271560", trade_date=current_date, close=95, market_cap=200),
        ]
    )
    db.commit()
    buy_event = {
        "label": "확정 매수",
        "signal_date": previous_date - timedelta(days=3),
        "execution_date": previous_date,
        "side": "buy",
        "price": 100,
        "entry_price": 100,
        "score": Decimal("73.24"),
        "reason": "상승 추세와 모멘텀 확인",
    }

    def signal_payload(stock, _rows, **_kwargs):
        if stock.code != "271560":
            return {"events": [], "current": None}
        return {
            "events": [buy_event],
            "current": {
                "action": "full_exit_pending",
                "live_observation": True,
                "position_open": True,
                "price": 95,
                "entry_price": 100,
                "unrealized_return": Decimal("-5.00"),
                "score": Decimal("39.00"),
                "as_of": datetime(2026, 8, 11, 13, 20),
                "reasons": ["손절 기준 이탈"],
                "lifecycle": {"latest_transition": buy_event},
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", signal_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 11, 13, 20),
        live_quotes={"271560": {"trade_date": current_date, "price": 95}},
    )

    assert payload["current_universe_count"] == 2
    assert payload["universe_count"] == 3
    assert payload["preliminary_count"] == 1
    assert payload["confirmed_count"] == 1
    preliminary = next(item for item in payload["items"] if item["is_preliminary"])
    confirmed = next(item for item in payload["items"] if not item["is_preliminary"])
    assert preliminary["code"] == "271560"
    assert preliminary["signal"] == "예비 매도"
    assert preliminary["side"] == "sell"
    assert preliminary["event_side"] == "sell"
    assert preliminary["return_rate"] == Decimal("-5.00")
    assert preliminary["display_return_rate"] == Decimal("-5.00")
    assert confirmed.get("current") is None
    assert confirmed["holding_context"]["entry_price"] == 100
    db.close()


def test_market_and_stock_signal_paths_use_the_same_900_price_rows(monkeypatch):
    db = _session()
    stock = _stock("000001", "동일원천주")
    first_date = date(2022, 1, 1)
    rows = [
        DailyPrice(
            code=stock.code,
            trade_date=first_date + timedelta(days=index),
            close=100 + index,
            market_cap=1_000_000_000 if index == 904 else None,
        )
        for index in range(905)
    ]
    db.add(stock)
    db.add_all(rows)
    db.commit()
    captured = []

    def capture_payload(_stock, price_rows, **_kwargs):
        captured.append([row.trade_date for row in price_rows])
        return {"events": [], "current": None}

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", capture_payload)
    load_market_quant_signal_feed(
        db,
        universe_limit=1,
        limit=0,
        recent_days=30,
        now=datetime(2024, 7, 1, 16, 0),
    )
    market_dates = captured.pop()
    load_quant_signal_payload(
        db,
        stock.code,
        now=datetime(2024, 7, 1, 16, 0),
        include_context=False,
    )
    stock_dates = captured.pop()

    assert len(market_dates) == quant_signals.SIGNAL_HISTORY_ROWS
    assert market_dates == stock_dates
    assert market_dates[0] == rows[5].trade_date
    assert market_dates[-1] == rows[-1].trade_date
    db.close()


def test_market_quant_signal_feed_adds_intraday_preliminary_buy_and_sell(monkeypatch):
    db = _session()
    current_date = date(2026, 8, 3)
    stocks = [_stock("000001", "예비매수주"), _stock("000002", "예비매도주")]
    db.add_all(stocks)
    db.add_all(
        [
            DailyPrice(
                code="000001",
                trade_date=current_date,
                open=100,
                high=113,
                low=98,
                close=111,
                volume=1_500_000,
                trading_value=166_500_000,
                market_cap=300_000_000,
            ),
            DailyPrice(
                code="000002",
                trade_date=current_date,
                open=200,
                high=201,
                low=178,
                close=180,
                volume=2_000_000,
                trading_value=360_000_000,
                market_cap=200_000_000,
            ),
        ]
    )
    db.commit()

    def preliminary_payload(stock, _rows, **kwargs):
        live_quote = kwargs.get("live_quote")
        assert live_quote is not None
        assert live_quote["trade_date"] == current_date
        action = "entry_pending" if stock.code == "000001" else "full_exit_pending"
        previous_trade = {
            "signal_date": date(2026, 4, 23),
            "execution_date": date(2026, 5, 29),
            "side": "sell",
            "price": 4_990,
            "entry_price": 4_830,
            "target_sell_price": 5_593,
            "target_sell_status": "missed",
            "target_sell_delta": -603,
            "return_rate": Decimal("10.21"),
        }
        return {
            "events": [previous_trade] if stock.code == "000001" else [],
            "current": {
                "action": action,
                "live_observation": True,
                "position_open": stock.code == "000002",
                "price": live_quote["price"],
                "entry_price": None if stock.code == "000001" else 200,
                "target_sell_price": 5_593 if stock.code == "000001" else 230,
                "target_sell_status": "missed" if stock.code == "000001" else "planned",
                "target_sell_delta": -603 if stock.code == "000001" else None,
                "unrealized_return": None if stock.code == "000001" else Decimal("-12.00"),
                "score": Decimal("71.20") if stock.code == "000001" else Decimal("39.80"),
                "as_of": datetime(2026, 8, 3, 13, 20),
                "reasons": ["장중 조건 충족"],
                "lifecycle": {"latest_transition": previous_trade},
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", preliminary_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=2,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 3, 13, 20),
        live_quotes={
            "000001": {"trade_date": current_date, "price": 115, "volume": 1_800_000},
            "000002": {"trade_date": current_date, "price": 176, "volume": 2_200_000},
        },
    )

    assert payload["preliminary_count"] == 2
    assert payload["confirmed_count"] == 0
    assert [item["signal"] for item in payload["items"]] == ["예비 매수", "예비 매도"]
    assert all(item["is_preliminary"] is True for item in payload["items"])
    assert all(item["signal_date"] == current_date for item in payload["items"])
    assert all(item["execution_date"] is None for item in payload["items"])
    assert payload["items"][0]["price"] == 115
    assert payload["items"][1]["price"] == 176
    assert payload["items"][0]["entry_price"] is None
    assert payload["items"][1]["entry_price"] == 200
    assert payload["items"][0]["target_sell_price"] is None
    assert payload["items"][0]["target_sell_status"] is None
    assert payload["items"][0]["target_sell_delta"] is None
    assert payload["items"][0]["display_return_rate"] is None
    assert payload["items"][0]["display_return_kind"] is None
    assert payload["items"][0]["current"]["target_sell_price"] is None
    assert payload["items"][0]["current"]["lifecycle"]["latest_transition"]["entry_price"] == 4_830
    assert payload["items"][1]["target_sell_price"] == 230
    assert payload["items"][1]["display_return_rate"] == Decimal("-12.00")
    assert payload["items"][1]["display_return_kind"] == "open_position"
    db.close()


@pytest.mark.parametrize(
    ("action", "side", "event_side", "label", "position_open"),
    (
        ("entry_pending", "buy", "buy", "예비 매수", False),
        ("full_exit_pending", "sell", "sell", "예비 매도", True),
    ),
)
def test_market_pending_execution_remains_current_after_close(
    action,
    side,
    event_side,
    label,
    position_open,
):
    stock = _stock("035420", "NAVER")
    signal_date = date(2026, 8, 21)
    as_of = datetime(2026, 8, 21, 15, 40, tzinfo=quant_signals.KST)
    item = quant_signals._market_preliminary_signal_item(
        stock,
        10,
        {
            "price_through": signal_date,
            "current": {
                "action": action,
                "live_observation": False,
                "position_open": position_open,
                "price": 222_000,
                "entry_price": 225_500 if position_open else None,
                "unrealized_return": Decimal("-1.55") if position_open else None,
                "score": Decimal("68.24"),
                "as_of": as_of,
                "reasons": ["종가 확정 후 다음 거래일 시가 체결 대기"],
            },
        },
        as_of,
    )

    assert item is not None
    assert item["side"] == side
    assert item["event_side"] == event_side
    assert item["signal"] == label
    assert item["signal_date"] == signal_date
    assert item["signal_at"] == as_of
    assert item["execution_date"] is None
    assert item["is_preliminary"] is True
    assert item["current"]["live_observation"] is False
    assert item["return_rate"] == (Decimal("-1.55") if position_open else None)


def test_market_pending_signal_weekend_refresh_keeps_close_basis_timestamp():
    stock = _stock("373220", "LG에너지솔루션")
    signal_date = date(2026, 8, 28)
    weekend_refresh = datetime(2026, 8, 30, 12, 38, tzinfo=quant_signals.KST)
    item = quant_signals._market_preliminary_signal_item(
        stock,
        3,
        {
            "price_through": signal_date,
            "current": {
                "action": "entry_watch",
                "live_observation": False,
                "position_open": False,
                "price": 370_000,
                "score": Decimal("81.83"),
                "as_of": weekend_refresh,
                "reasons": ["금요일 종가 기준"],
            },
        },
        weekend_refresh,
    )

    assert item is not None
    assert item["signal_date"] == signal_date
    assert item["signal_at"] == datetime(
        2026,
        8,
        28,
        15,
        40,
        tzinfo=quant_signals.KST,
    )
    assert item["updated_at"] == item["signal_at"]
    assert item["current"]["as_of"] == weekend_refresh


def test_market_confirmed_holding_keeps_return_basis_beside_preliminary_exit(monkeypatch):
    db = _session()
    current_date = date(2026, 8, 21)
    stock = _stock("010950", "S-Oil")
    db.add(stock)
    db.add(
        DailyPrice(
            code=stock.code,
            trade_date=current_date,
            open=80_000,
            high=81_000,
            low=79_000,
            close=80_500,
            volume=1_000_000,
            trading_value=80_500_000_000,
            market_cap=1_000_000_000_000,
        )
    )
    db.commit()
    buy_event = {
        "label": "확정 매수",
        "side": "buy",
        "signal_date": date(2026, 8, 18),
        "signal_at": datetime(2026, 8, 18, 15, 40),
        "execution_date": date(2026, 8, 19),
        "price": 80_500,
        "entry_price": 80_500,
        "target_sell_price": 93_380,
    }

    def preliminary_exit_payload(_stock, _rows, **kwargs):
        return {
            "events": [buy_event],
            "current": {
                "action": "full_exit_pending",
                "position_open": True,
                "live_observation": True,
                "price": kwargs["live_quote"]["price"],
                "entry_price": 80_500,
                "target_sell_price": 93_380,
                "unrealized_return": Decimal("-7.03"),
                "return_basis": {
                    "price": 80_000,
                    "return_rate": Decimal("-7.03"),
                    "return_rate_per_price": Decimal("0.001"),
                },
                "model_exposure_percent": Decimal("100.00"),
                "score": Decimal("41.00"),
                "as_of": datetime(2026, 8, 21, 13, 20),
                "lifecycle": {"latest_transition": buy_event},
            },
        }

    monkeypatch.setattr(quant_signals, "build_quant_signal_payload", preliminary_exit_payload)
    payload = load_market_quant_signal_feed(
        db,
        universe_limit=20,
        limit=0,
        recent_days=30,
        now=datetime(2026, 8, 21, 13, 20),
        live_quotes={stock.code: {"trade_date": current_date, "price": 80_000}},
    )

    preliminary = next(
        item for item in payload["items"]
        if item["code"] == stock.code and item["is_preliminary"]
    )
    confirmed = next(
        item for item in payload["items"]
        if item["code"] == stock.code and not item["is_preliminary"]
    )
    assert preliminary["current"]["action"] == "full_exit_pending"
    assert confirmed.get("current") is None
    assert confirmed["is_current_holding"] is True
    assert confirmed["display_return_rate"] == Decimal("-7.03")
    assert confirmed["display_return_kind"] == "open_position"
    assert confirmed["holding_context"]["entry_price"] == 80_500
    assert confirmed["holding_context"]["return_basis"]["return_rate"] == Decimal("-7.03")
    db.close()


def test_trade_metadata_requires_entry_price_and_uses_new_snapshot_namespace():
    stock_payload = {
        "strategy_version": STRATEGY_VERSION,
        "events": [
            {
                "signal_at": datetime(2026, 8, 12, 15, 40),
                "entry_price": 1_330_000,
                "target_sell_price": 1_542_800,
            }
        ],
    }
    assert quant_signals.quant_payload_has_trade_metadata(stock_payload) is True
    del stock_payload["events"][0]["entry_price"]
    assert quant_signals.quant_payload_has_trade_metadata(stock_payload) is False

    market_payload = {
        "strategy_version": STRATEGY_VERSION,
        "items": [
            {
                "side": "sell",
                "signal_at": datetime(2026, 8, 12, 15, 40),
                "entry_price": 1_330_000,
                "target_sell_price": 1_542_800,
                "return_rate": Decimal("-9.56"),
            }
        ],
    }
    assert quant_signals.market_payload_has_trade_metadata(market_payload) is True
    del market_payload["items"][0]["entry_price"]
    assert quant_signals.market_payload_has_trade_metadata(market_payload) is False
    assert quant_signals.market_quant_signal_snapshot_key(150, 0, 30) == "v31:150:0:30"


def test_market_preliminary_history_keeps_cleared_signals_for_same_day():
    first_payload = {
        "as_of": datetime(2026, 8, 13, 9, 12),
        "items": [
            {
                "code": "003550",
                "name": "LG",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": date(2026, 8, 13),
                "signal_at": datetime(2026, 8, 13, 9, 12),
                "status": "preliminary",
                "is_preliminary": True,
            },
            {
                "code": "078930",
                "name": "GS",
                "side": "sell",
                "signal": "예비 매도",
                "signal_date": date(2026, 8, 13),
                "signal_at": datetime(2026, 8, 13, 9, 12),
                "status": "preliminary",
                "is_preliminary": True,
            },
        ],
    }
    initial = quant_signals.merge_market_preliminary_history(first_payload)
    assert [(item["code"], item["active"]) for item in initial["preliminary_history"]] == [
        ("003550", True),
        ("078930", True),
    ]

    next_payload = {
        "as_of": datetime(2026, 8, 13, 13, 28),
        "items": [
            {
                "code": "003550",
                "name": "LG",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": date(2026, 8, 13),
                "signal_at": datetime(2026, 8, 13, 13, 28),
                "status": "preliminary",
                "is_preliminary": True,
            }
        ],
    }
    merged = quant_signals.merge_market_preliminary_history(next_payload, initial)
    by_code = {item["code"]: item for item in merged["preliminary_history"]}
    assert by_code["003550"]["active"] is True
    assert by_code["003550"]["first_seen_at"] == datetime(2026, 8, 13, 9, 12)
    assert by_code["003550"]["last_seen_at"] == datetime(2026, 8, 13, 13, 28)
    assert by_code["078930"]["active"] is False

    tomorrow = quant_signals.merge_market_preliminary_history(
        {"as_of": datetime(2026, 8, 14, 9, 5), "items": []},
        merged,
    )
    assert tomorrow["preliminary_history"] == []


def test_market_quant_signal_endpoint_is_no_store(monkeypatch):
    db = _session()

    def override_db():
        yield db

    monkeypatch.setattr(
        main,
        "load_market_quant_signal_feed",
        lambda *_args, **_kwargs: {
            "as_of": datetime(2026, 7, 26, 9, 0),
            "universe_as_of": date(2026, 7, 25),
            "universe_count": 100,
            "recent_days": 30,
            "items": [],
        },
    )
    main.market_quant_signal_cache.clear()
    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/market/quant-signals")
        assert response.status_code == 200
        assert response.headers["cache-control"].startswith("no-store")
        assert response.json()["universe_count"] == 100
    finally:
        main.market_quant_signal_cache.clear()
        app.dependency_overrides.pop(get_db, None)
        db.close()


def test_external_market_quant_signal_feed_uses_canonical_payload():
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "ready",
                "preliminary_count": 0,
                "confirmed_count": 1,
                "items": [{"code": "086790", "side": "sell"}],
            }

    def fetcher(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    payload = load_external_market_quant_signal_feed(
        "https://signals.example",
        universe_limit=100,
        limit=0,
        recent_days=14,
        fetcher=fetcher,
    )

    assert payload is not None
    assert payload["signal_source"] == "canonical"
    assert payload["items"][0]["code"] == "086790"
    assert calls[0][0] == "https://signals.example/market/quant-signals"
    assert calls[0][1]["params"]["recent_days"] == 14


def test_external_stock_quant_signal_payload_uses_canonical_full_state():
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": "175330",
                "data_state": "ready",
                "current": {"action": "entry_pending", "position_open": False},
                "events": [{"side": "sell", "execution_date": "2026-08-03"}],
            }

    def fetcher(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    payload = load_external_stock_quant_signal_payload(
        "https://signals.example/market/quant-signals",
        "175330",
        fetcher=fetcher,
    )

    assert payload is not None
    assert payload["signal_source"] == "canonical"
    assert payload["entry_score_threshold"] == Decimal("64.00")
    assert payload["current"]["action"] == "entry_pending"
    assert calls[0][0] == "https://signals.example/stocks/175330/quant-signals"


def test_reference_quant_signal_payload_falls_back_to_local_state(monkeypatch):
    expected = {"code": "005930", "data_state": "ready"}
    monkeypatch.setattr(quant_signals, "load_external_stock_quant_signal_payload", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(quant_signals, "load_quant_signal_payload", lambda *_args, **_kwargs: expected)

    payload = load_reference_quant_signal_payload(object(), "005930", source_url="https://signals.example")

    assert payload == {**expected, "signal_source": "local"}


def test_market_quant_signal_live_quotes_refresh_ranked_universe(monkeypatch):
    db = _session()
    trade_date = date(2026, 8, 3)
    db.add_all([_stock("000001", "대형주"), _stock("000002", "중형주")])
    db.add_all(
        [
            DailyPrice(code="000001", trade_date=trade_date, close=100, market_cap=300_000_000),
            DailyPrice(code="000002", trade_date=trade_date, close=200, market_cap=200_000_000),
        ]
    )
    db.commit()
    monkeypatch.setattr(main, "is_korea_regular_market_session", lambda _now=None: True)
    monkeypatch.setattr(
        main,
        "_fetch_uncached_current_quote",
        lambda code: ({"trade_date": trade_date, "price": 111 if code == "000001" else 222}, "test"),
    )

    quotes = main._market_quant_signal_live_quotes(
        db,
        universe_limit=2,
        now=datetime(2026, 8, 3, 13, 20),
    )

    assert quotes == {
        "000001": {"trade_date": trade_date, "price": 111},
        "000002": {"trade_date": trade_date, "price": 222},
    }
    db.close()


def test_current_context_uses_connected_sources_without_rewriting_backtest():
    db = _session()
    stock = _stock()
    prices = _price_rows("005930")
    latest_date = prices[-1].trade_date
    db.add(stock)
    db.add_all(prices)
    db.add_all(
        [
            InvestorFlow(
                code="005930",
                trade_date=latest_date,
                investor_type="외국인",
                net_buy_value=12_000_000_000,
            ),
            InvestorFlow(
                code="005930",
                trade_date=latest_date,
                investor_type="기관합계",
                net_buy_value=-3_000_000_000,
            ),
            NewsItem(
                source="test",
                source_category="company",
                external_id="news-1",
                title="삼성전자 실적 개선과 성장 전망",
                published_at=datetime(2026, 7, 24, 9, 0),
            ),
            ResearchReport(
                source="test",
                source_category="company",
                external_id="report-1",
                title="삼성전자 전망",
                stock_code="005930",
                broker_name="테스트증권",
                opinion="매수",
                target_price=Decimal("50000"),
                published_at=datetime(2026, 7, 23, 9, 0),
            ),
            DisclosureItem(
                source="dart",
                external_id="disclosure-1",
                disclosure_category="공시목록",
                company_name="삼성전자",
                stock_code="005930",
                report_name="공급계약 수주 증가",
                published_at=datetime(2026, 7, 22, 9, 0),
            ),
        ]
    )
    db.commit()

    baseline = build_quant_signal_payload(stock, prices, now=datetime(2026, 7, 25, 12, 0))
    enriched = load_quant_signal_payload(db, "005930", now=datetime(2026, 7, 25, 12, 0))

    assert enriched is not None
    assert enriched["confirmation"]["available_count"] == 5
    assert {item["key"] for item in enriched["confirmation"]["evidence"]} == {
        "flow",
        "news",
        "research",
        "disclosure",
        "liquidity",
    }
    assert [
        (event["signal_date"], event["execution_date"], event["side"], event["price"])
        for event in enriched["events"]
    ] == [
        (event["signal_date"], event["execution_date"], event["side"], event["price"])
        for event in baseline["events"]
    ]
    db.close()
