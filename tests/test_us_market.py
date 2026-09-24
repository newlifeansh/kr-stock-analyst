from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.services import us_market


ROOT = Path(__file__).resolve().parents[1]


def test_sec_request_identity_contains_configured_contact(monkeypatch):
    headers = us_market._sec_request_headers()

    assert "@" in headers["User-Agent"]
    assert headers["Accept"] == "application/json"

    class InvalidSettings:
        sec_user_agent = "anonymous-client"

    monkeypatch.setattr(us_market, "get_settings", lambda: InvalidSettings())

    with pytest.raises(ValueError, match="contact email"):
        us_market._sec_request_headers()


class _FakeNewsResponse:
    content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
    <rss><channel><item><title>엔비디아 실적 전망</title><link>https://example.test/nvda</link>
    <pubDate>Fri, 04 Sep 2026 12:00:00 GMT</pubDate><source>테스트뉴스</source></item></channel></rss>""".encode("utf-8")

    def raise_for_status(self):
        return None


def test_chart_price_rows_use_adjusted_ohlc_but_raw_dollar_notional():
    timestamp = 1788888600
    result = {
        "meta": {},
        "timestamp": [timestamp],
        "indicators": {
            "quote": [{
                "open": [100.0],
                "high": [110.0],
                "low": [90.0],
                "close": [100.0],
                "volume": [1_000],
            }],
            "adjclose": [{"adjclose": [50.0]}],
        },
    }

    _meta, rows = us_market._chart_price_rows("TEST", result, limit=10)

    assert rows[0].open == Decimal("50.0")
    assert rows[0].high == Decimal("55.0")
    assert rows[0].low == Decimal("45.0")
    assert rows[0].close == Decimal("50.0")
    assert rows[0].trading_value == Decimal("100000.0")
    assert rows[0].adjusted_ohlc_complete is True


@pytest.mark.parametrize(
    ("market_session", "price_key", "time_key", "quote_price", "observed_at"),
    [
        (
            "closed",
            "regularMarketPrice",
            "regularMarketTime",
            339.75,
            datetime(2026, 9, 22, 20, 0, tzinfo=UTC),
        ),
        (
            "premarket",
            "preMarketPrice",
            "preMarketTime",
            341.5,
            datetime(2026, 9, 23, 12, 0, tzinfo=UTC),
        ),
        (
            "afterhours",
            "postMarketPrice",
            "postMarketTime",
            340.25,
            datetime(2026, 9, 22, 22, 0, tzinfo=UTC),
        ),
    ],
)
def test_us_dashboard_quote_date_follows_selected_market_timestamp_when_daily_bar_lags(
    market_session,
    price_key,
    time_key,
    quote_price,
    observed_at,
):
    latest = us_market.USPrice(
        code="AAPL",
        trade_date=date(2026, 9, 21),
        open=Decimal("336"),
        high=Decimal("340"),
        low=Decimal("335"),
        close=Decimal("336.13"),
        volume=1_000,
        trading_value=Decimal("336130"),
    )

    price, trade_date = us_market._us_quote_price_and_trade_date(
        {
            price_key: quote_price,
            time_key: int(observed_at.timestamp()),
            "regularMarketPrice": 339.75,
            "regularMarketTime": int(
                datetime(2026, 9, 22, 20, 0, tzinfo=UTC).timestamp()
            ),
        },
        latest,
        market_session,
    )

    assert price == Decimal(str(quote_price))
    assert trade_date == observed_at.astimezone(us_market.NEW_YORK_TZ).date()


def test_us_dashboard_quote_date_falls_back_with_the_same_daily_price():
    latest = us_market.USPrice(
        code="AAPL",
        trade_date=date(2026, 9, 21),
        open=Decimal("336"),
        high=Decimal("340"),
        low=Decimal("335"),
        close=Decimal("336.13"),
        volume=1_000,
        trading_value=Decimal("336130"),
    )

    price, trade_date = us_market._us_quote_price_and_trade_date({}, latest, "closed")

    assert price == Decimal("336.13")
    assert trade_date == date(2026, 9, 21)


def test_signal_chart_rows_fail_closed_without_adjusted_complete_ohlcv():
    result = {
        "meta": {},
        "timestamp": [1788888600, 1788975000],
        "indicators": {
            "quote": [{
                "open": [None, 100.0],
                "high": [None, 110.0],
                "low": [None, 90.0],
                "close": [100.0, 100.0],
                "volume": [1_000, 1_000],
            }],
            "adjclose": [{"adjclose": [None, 50.0]}],
        },
    }

    _meta, strict_rows = us_market._chart_price_rows(
        "TEST",
        result,
        limit=10,
        require_adjusted_ohlc=True,
    )
    _meta, display_rows = us_market._chart_price_rows("TEST", result, limit=10)

    assert len(strict_rows) == 1
    assert strict_rows[0].adjusted_ohlc_complete is True
    assert strict_rows[0].close == Decimal("50.0")
    assert len(display_rows) == 2
    assert display_rows[0].adjusted_ohlc_complete is False


@pytest.mark.parametrize(
    ("open_price", "high", "low", "close"),
    [
        (416.010009765625, 424.45001220703125, 416.0199890136719, 418.010009765625),
        (119.62999725341797, 121.2249984741211, 119.75, 120.93000030517578),
        (107.08999633789062, 109.41999816894531, 107.20500183105469, 108.58999633789062),
        (254.27999877929688, 258.45001220703125, 254.64500427246094, 257.489990234375),
    ],
)
def test_signal_chart_rows_accept_bounded_yahoo_open_range_drift(
    open_price,
    high,
    low,
    close,
):
    result = {
        "meta": {},
        "timestamp": [1789401600],
        "indicators": {
            "quote": [{
                "open": [open_price],
                "high": [high],
                "low": [low],
                "close": [close],
                "volume": [1_000],
            }],
            "adjclose": [{"adjclose": [close]}],
        },
    }

    _meta, rows = us_market._chart_price_rows(
        "TEST",
        result,
        limit=10,
        require_adjusted_ohlc=True,
    )

    assert len(rows) == 1
    assert rows[0].adjusted_ohlc_complete is True
    assert rows[0].high >= max(rows[0].open, rows[0].close)
    assert rows[0].low <= min(rows[0].open, rows[0].close)


def _provider_lagged_daily_chart():
    completed_at = int(datetime(2026, 9, 14, 20, 0, tzinfo=UTC).timestamp())
    return {
        "meta": {
            "symbol": "AAPL",
            "currency": "USD",
            "instrumentType": "EQUITY",
        },
        "timestamp": [completed_at],
        "indicators": {
            "quote": [{
                "open": [100.0],
                "high": [110.0],
                "low": [90.0],
                "close": [None],
                "volume": [1_234_567],
            }],
            "adjclose": [{"adjclose": [None]}],
        },
    }


def _completed_regular_intraday_chart(*, final_hour: int = 20):
    return {
        "meta": {
            "symbol": "AAPL",
            "currency": "USD",
            "instrumentType": "EQUITY",
        },
        "timestamp": [
            int(datetime(2026, 9, 14, 13, 30, tzinfo=UTC).timestamp()),
            int(datetime(2026, 9, 14, final_hour, 0, tzinfo=UTC).timestamp()),
        ],
        "indicators": {
            "quote": [{
                "open": [101.0, 104.0],
                "high": [102.0, 106.0],
                "low": [100.0, 103.0],
                "close": [101.0, 105.0],
                "volume": [10_000, 20_000],
            }],
        },
    }


def _gap_free_regular_intraday_chart(
    session_date=date(2026, 9, 14),
):
    timestamps = [
        int(
            (
                datetime(
                    session_date.year,
                    session_date.month,
                    session_date.day,
                    13,
                    30,
                    tzinfo=UTC,
                )
                + timedelta(minutes=5 * index)
            ).timestamp()
        )
        for index in range(78)
    ]
    return {
        "meta": {
            "symbol": "AAPL",
            "currency": "USD",
            "instrumentType": "EQUITY",
        },
        "timestamp": timestamps,
        "indicators": {
            "quote": [{
                "open": [100.0 + index / 100 for index in range(78)],
                "high": [101.0 + index / 100 for index in range(78)],
                "low": [99.0 + index / 100 for index in range(78)],
                "close": [100.5 + index / 100 for index in range(78)],
                "volume": [1_000 + index for index in range(78)],
            }],
        },
    }


def test_signal_daily_close_repairs_only_null_fields_from_completed_regular_intraday(
    monkeypatch,
):
    daily = _provider_lagged_daily_chart()
    monkeypatch.setattr(
        us_market,
        "_fetch_chart",
        lambda symbol, **kwargs: _completed_regular_intraday_chart(),
    )

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 16, tzinfo=UTC),
    )

    assert daily["indicators"]["quote"][0]["close"] == [None]
    assert daily["indicators"]["adjclose"][0]["adjclose"] == [None]
    assert repaired["indicators"]["quote"][0]["close"] == [105.0]
    assert repaired["indicators"]["adjclose"][0]["adjclose"] == [105.0]
    assert repaired["indicators"]["quote"][0]["volume"] == [1_234_567]


def test_signal_daily_row_repairs_fully_null_completed_day_before_forming_row(
    monkeypatch,
):
    daily = _provider_lagged_daily_chart()
    daily["timestamp"].append(
        int(datetime(2026, 9, 15, 13, 30, tzinfo=UTC).timestamp())
    )
    quote = daily["indicators"]["quote"][0]
    for key, value in {
        "open": 102.0,
        "high": 104.0,
        "low": 101.0,
        "close": 103.0,
        "volume": 55_000,
    }.items():
        quote[key] = [None, value]
    daily["indicators"]["adjclose"][0]["adjclose"] = [None, 103.0]
    intraday = _gap_free_regular_intraday_chart()
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 15, 16, 0, tzinfo=UTC),
    )

    repaired_quote = repaired["indicators"]["quote"][0]
    assert daily["indicators"]["quote"][0]["open"] == [None, 102.0]
    assert repaired_quote["open"][0] == 100.0
    assert repaired_quote["high"][0] == max(
        intraday["indicators"]["quote"][0]["high"]
    )
    assert repaired_quote["low"][0] == min(
        intraday["indicators"]["quote"][0]["low"]
    )
    assert repaired_quote["close"][0] == 101.27
    assert repaired_quote["volume"][0] == sum(
        intraday["indicators"]["quote"][0]["volume"]
    )
    assert repaired["indicators"]["adjclose"][0]["adjclose"][0] == 101.27
    assert repaired_quote["close"][1] == 103.0


def test_signal_daily_row_repairs_recent_completed_gap_after_newer_daily_close(
    monkeypatch,
):
    daily = _provider_lagged_daily_chart()
    daily["timestamp"] = [
        int(datetime(2026, 9, 22, 13, 30, tzinfo=UTC).timestamp()),
        int(datetime(2026, 9, 23, 13, 30, tzinfo=UTC).timestamp()),
    ]
    quote = daily["indicators"]["quote"][0]
    for key, value in {
        "open": 1174.0,
        "high": 1188.0,
        "low": 1145.0,
        "close": 1150.0,
        "volume": 2_100_000,
    }.items():
        quote[key] = [None, value]
    daily["indicators"]["adjclose"][0]["adjclose"] = [None, 1150.0]
    intraday = _gap_free_regular_intraday_chart(date(2026, 9, 22))
    for interval_index in (20, 40, 50):
        for values in intraday["indicators"]["quote"][0].values():
            values[interval_index] = None
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 23, 20, 16, tzinfo=UTC),
    )

    repaired_quote = repaired["indicators"]["quote"][0]
    assert daily["indicators"]["quote"][0]["open"] == [None, 1174.0]
    assert repaired_quote["open"][0] == 100.0
    assert repaired_quote["high"][0] == max(
        value
        for value in intraday["indicators"]["quote"][0]["high"]
        if value is not None
    )
    assert repaired_quote["low"][0] == min(
        value
        for value in intraday["indicators"]["quote"][0]["low"]
        if value is not None
    )
    assert repaired_quote["close"] == [101.27, 1150.0]
    assert repaired["indicators"]["adjclose"][0]["adjclose"] == [
        101.27,
        1150.0,
    ]
    assert repaired_quote["volume"][0] == sum(
        value or 0
        for value in intraday["indicators"]["quote"][0]["volume"]
    )


def test_signal_daily_row_keeps_recent_completed_gap_without_exact_intraday_vector(
    monkeypatch,
):
    daily = _provider_lagged_daily_chart()
    daily["timestamp"] = [
        int(datetime(2026, 9, 22, 13, 30, tzinfo=UTC).timestamp()),
        int(datetime(2026, 9, 23, 13, 30, tzinfo=UTC).timestamp()),
    ]
    quote = daily["indicators"]["quote"][0]
    for key, value in {
        "open": 1174.0,
        "high": 1188.0,
        "low": 1145.0,
        "close": 1150.0,
        "volume": 2_100_000,
    }.items():
        quote[key] = [None, value]
    daily["indicators"]["adjclose"][0]["adjclose"] = [None, 1150.0]
    intraday = _gap_free_regular_intraday_chart(date(2026, 9, 22))
    for values in [
        intraday["timestamp"],
        *intraday["indicators"]["quote"][0].values(),
    ]:
        values.pop(20)
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 23, 20, 16, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None, 1150.0]


def test_signal_daily_row_repair_rejects_intraday_session_gap(monkeypatch):
    daily = _provider_lagged_daily_chart()
    quote = daily["indicators"]["quote"][0]
    for key in ("open", "high", "low", "volume"):
        quote[key] = [None]
    intraday = _gap_free_regular_intraday_chart()
    for values in [
        intraday["timestamp"],
        *intraday["indicators"]["quote"][0].values(),
    ]:
        values.pop(20)
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 16, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None]


def test_signal_daily_close_repair_stays_closed_before_publication_grace(monkeypatch):
    daily = _provider_lagged_daily_chart()
    monkeypatch.setattr(
        us_market,
        "_fetch_chart",
        lambda *_args, **_kwargs: pytest.fail("forming session must not fetch fallback"),
    )

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 14, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None]


def test_signal_daily_close_repair_requires_intraday_through_official_close(monkeypatch):
    daily = _provider_lagged_daily_chart()
    intraday = _completed_regular_intraday_chart(final_hour=19)
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 16, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None]


@pytest.mark.parametrize(
    ("meta_field", "meta_value"),
    [("symbol", "MSFT"), ("currency", "KRW")],
)
def test_signal_daily_close_repair_rejects_mismatched_intraday_metadata(
    monkeypatch,
    meta_field,
    meta_value,
):
    daily = _provider_lagged_daily_chart()
    intraday = _completed_regular_intraday_chart()
    intraday["meta"][meta_field] = meta_value
    monkeypatch.setattr(us_market, "_fetch_chart", lambda *_args, **_kwargs: intraday)

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 16, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None]


def test_signal_daily_close_repair_rejects_partial_close_pair(monkeypatch):
    daily = _provider_lagged_daily_chart()
    daily["indicators"]["adjclose"][0]["adjclose"] = [105.0]
    monkeypatch.setattr(
        us_market,
        "_fetch_chart",
        lambda *_args, **_kwargs: pytest.fail("partial close pair must not fetch fallback"),
    )

    repaired = us_market._repair_completed_daily_close_from_intraday(
        "AAPL",
        daily,
        now=datetime(2026, 9, 14, 20, 16, tzinfo=UTC),
    )

    assert repaired is daily
    assert repaired["indicators"]["quote"][0]["close"] == [None]
    assert repaired["indicators"]["adjclose"][0]["adjclose"] == [105.0]


def test_signal_chart_range_invokes_completed_daily_close_repair(monkeypatch):
    daily = _provider_lagged_daily_chart()
    completed = _provider_lagged_daily_chart()
    completed["indicators"]["quote"][0]["close"] = [105.0]
    completed["indicators"]["adjclose"][0]["adjclose"] = [105.0]
    calls = []
    monkeypatch.setattr(us_market, "fetch_chart_range", lambda *_args, **_kwargs: daily)
    monkeypatch.setattr(
        us_market,
        "_repair_completed_daily_close_from_intraday",
        lambda symbol, result: calls.append((symbol, result)) or completed,
    )

    _meta, rows = us_market.chart_prices_range(
        "AAPL",
        range_="2y",
        interval="1d",
        require_adjusted_ohlc=True,
    )

    assert calls == [("AAPL", daily)]
    assert len(rows) == 1
    assert rows[0].trade_date == date(2026, 9, 14)
    assert rows[0].close == Decimal("105.0")


@pytest.mark.parametrize(
    ("open_price", "high", "low", "close", "adjusted_close"),
    [
        (100.0, 99.0, 90.0, 100.0, 50.0),
        (100.0, 110.0, 101.0, 100.0, 50.0),
        (0.0, 110.0, 90.0, 100.0, 50.0),
        (100.0, 110.0, 90.0, 100.0, 0.0),
    ],
)
def test_signal_chart_rows_reject_invalid_adjusted_ohlc_geometry(
    open_price,
    high,
    low,
    close,
    adjusted_close,
):
    result = {
        "meta": {},
        "timestamp": [1788888600],
        "indicators": {
            "quote": [{
                "open": [open_price],
                "high": [high],
                "low": [low],
                "close": [close],
                "volume": [1_000],
            }],
            "adjclose": [{"adjclose": [adjusted_close]}],
        },
    }

    _meta, rows = us_market._chart_price_rows(
        "TEST",
        result,
        limit=10,
        require_adjusted_ohlc=True,
    )

    assert rows == []


@pytest.mark.parametrize(
    ("meta", "symbol"),
    [
        ({"symbol": "AAPL", "currency": "CAD", "instrumentType": "EQUITY"}, "AAPL"),
        ({"symbol": "MSFT", "currency": "USD", "instrumentType": "EQUITY"}, "AAPL"),
        ({"symbol": "AAPL", "currency": "USD", "instrumentType": "CRYPTOCURRENCY"}, "AAPL"),
    ],
)
def test_signal_chart_range_rejects_non_usd_or_mismatched_instrument(
    monkeypatch,
    meta,
    symbol,
):
    result = {
        "meta": meta,
        "timestamp": [1788888600],
        "indicators": {
            "quote": [
                {
                    "open": [100.0],
                    "high": [110.0],
                    "low": [90.0],
                    "close": [100.0],
                    "volume": [1_000],
                }
            ],
            "adjclose": [{"adjclose": [100.0]}],
        },
    }
    monkeypatch.setattr(us_market, "fetch_chart_range", lambda *_args, **_kwargs: result)

    with pytest.raises(ValueError, match="matching USD equity"):
        us_market.chart_prices_range(
            symbol,
            range_="2y",
            require_adjusted_ohlc=True,
        )


def test_sector_snapshot_pairs_last_valid_close_with_its_new_york_date(monkeypatch):
    valid_timestamp = int(datetime(2026, 9, 8, 20, 0, tzinfo=UTC).timestamp())
    null_timestamp = int(datetime(2026, 9, 9, 20, 0, tzinfo=UTC).timestamp())
    monkeypatch.setattr(
        us_market,
        "_fetch_chart",
        lambda *_args, **_kwargs: {
            "meta": {},
            "timestamp": [valid_timestamp, null_timestamp],
            "indicators": {"quote": [{"close": [100.0, None]}]},
        },
    )

    payload = us_market._sector_etf_snapshot(
        {"symbol": "XLK", "label": "Technology", "sector": "Technology"},
        live=True,
    )

    assert payload["price"] == Decimal("100.0")
    assert payload["trade_date"] == date(2026, 9, 8)


def test_us_liquidity_proxy_uses_explicit_dollar_volume_names(monkeypatch):
    monkeypatch.setattr(us_market, "chart_prices", lambda *args, **kwargs: ({}, []))
    monkeypatch.setattr(
        us_market,
        "_momentum",
        lambda rows: {
            "latest_trading_value": Decimal("120"),
            "baseline_trading_value": Decimal("100"),
            "trading_value_change": Decimal("20"),
        },
    )

    flows = us_market._us_liquidity_proxy(
        {"sector": "Technology", "market": "NASDAQ"},
        {
            "latest_trading_value": Decimal("150"),
            "baseline_trading_value": Decimal("100"),
            "trading_value_change": Decimal("50"),
        },
    )

    assert flows["stock_dollar_volume_delta"] == Decimal("50.0")
    assert flows["sector_etf_dollar_volume_change"] == Decimal("20")
    assert flows["flow_type"] == "price_volume_participation_proxy"
    assert flows["flow_semantics"] == "dollar_volume_participation_proxy"
    assert "순매수" in flows["proxy_notice"]
    assert "foreign_net_buy_20d" not in flows
    assert "institution_net_buy_20d" not in flows


def test_us_dashboard_clients_render_explicit_dollar_volume_proxy_fields():
    nasdaq_source = (ROOT / "app/static/nasdaq/app.js").read_text()
    dashboard_source = (ROOT / "app/static/dashboard/app.js").read_text()

    for field in (
        "stock_dollar_volume_delta",
        "sector_etf_dollar_volume_delta",
        "stock_dollar_volume_change",
        "sector_etf_dollar_volume_change",
    ):
        assert f"data.flows.{field}" in nasdaq_source
        assert f"data.flows.{field}" in dashboard_source


def test_resolve_compact_apple_company_name_without_koreanizing(monkeypatch):
    monkeypatch.setattr(us_market, "_search_yahoo", lambda *args, **kwargs: {"quotes": []})

    stock = us_market.resolve_us_stock("APPLEINC.")

    assert stock["code"] == "AAPL"
    assert stock["name"] == "Apple"


def test_resolve_korean_alias_keeps_original_us_name(monkeypatch):
    monkeypatch.setattr(us_market, "_search_yahoo", lambda *args, **kwargs: {"quotes": []})

    stock = us_market.resolve_us_stock("애플")

    assert stock["code"] == "AAPL"
    assert stock["name"] == "Apple"


def test_us_market_cap_uses_quote_fallback_for_class_share_mismatch(monkeypatch):
    monkeypatch.setattr(
        us_market,
        "fetch_us_quote_batch",
        lambda symbols, refresh=False: {
            "BRK.B": {"marketCap": Decimal("1085339860992")}
        },
    )

    market_cap = us_market._market_cap_with_quote_fallback(
        "BRK.B",
        {"market_cap": None},
    )

    assert market_cap == Decimal("1085339860992")


def test_us_market_cap_keeps_valid_financial_value_without_quote_request(monkeypatch):
    def fail_quote_request(*args, **kwargs):
        raise AssertionError("valid financial market cap must not fetch a fallback")

    monkeypatch.setattr(us_market, "fetch_us_quote_batch", fail_quote_request)

    market_cap = us_market._market_cap_with_quote_fallback(
        "AAPL",
        {"market_cap": Decimal("4000000000000")},
    )

    assert market_cap == Decimal("4000000000000")


def test_us_rankings_scan_full_universe(monkeypatch):
    calls = []

    def fake_dashboard(code):
        calls.append(code)
        rank_seed = len(calls)
        return {
            "code": code,
            "name": code,
            "market": "NASDAQ",
            "quote": {
                "trade_date": None,
                "price": Decimal("100"),
                "change_rate": Decimal(rank_seed),
                "trading_value": Decimal(rank_seed * 1000),
            },
            "momentum": {
                "one_month_return": Decimal(rank_seed),
                "three_month_return": Decimal(rank_seed),
                "trading_value_change": Decimal(rank_seed),
            },
            "sentiment": {
                "score": Decimal(rank_seed),
                "positive_count": 1,
                "negative_count": 0,
                "neutral_count": 0,
            },
            "chart_analysis": {"score": Decimal(rank_seed)},
            "valuation": {
                "per": Decimal("20"),
                "pbr": Decimal("3"),
                "industry_per": Decimal("25"),
            },
        }

    monkeypatch.setattr(
        us_market,
        "_quote_batch_dashboards",
        lambda universe: [fake_dashboard(str(item["code"])) for item in universe],
    )

    payload = us_market.build_us_rankings("surge", limit=1000, market="ALL")
    universe_codes = {item["code"] for item in us_market.US_EQUITY_UNIVERSE}

    assert {item["code"] for item in payload["items"]} == universe_codes
    assert set(calls) == universe_codes


def test_us_rankings_support_current_dashboard_volume_market_cap_and_low_per(monkeypatch):
    universe = [
        {"code": "AAA", "name": "Alpha", "market": "NASDAQ", "sector": "기술"},
        {"code": "BBB", "name": "Beta", "market": "NASDAQ", "sector": "기술"},
    ]
    values = {
        "AAA": {"volume": 100, "market_cap": Decimal("500"), "per": Decimal("30")},
        "BBB": {"volume": 300, "market_cap": Decimal("900"), "per": Decimal("12")},
    }

    def fake_dashboard(code):
        value = values[code]
        return {
            "code": code,
            "name": code,
            "market": "NASDAQ",
            "quote": {
                "trade_date": None,
                "price": Decimal("100"),
                "change_rate": Decimal("1"),
                "volume": value["volume"],
                "trading_value": Decimal(value["volume"] * 100),
                "market_cap": value["market_cap"],
            },
            "momentum": {
                "one_week_return": Decimal("2"),
                "one_month_return": Decimal("3"),
                "three_month_return": Decimal("4"),
                "trading_value_change": Decimal("5"),
            },
            "sentiment": {"score": Decimal("0"), "positive_count": 0, "negative_count": 0, "neutral_count": 0},
            "valuation": {"per": value["per"], "pbr": Decimal("2"), "dividend_yield": Decimal("1")},
        }

    monkeypatch.setattr(us_market, "_us_universe_for_market", lambda market: universe)
    monkeypatch.setattr(
        us_market,
        "_quote_batch_dashboards",
        lambda current: [fake_dashboard(str(item["code"])) for item in current],
    )

    volume = us_market.build_us_rankings("volume", limit=5, market="NASDAQ")
    market_cap = us_market.build_us_rankings("market_cap", limit=5, market="NASDAQ")
    low_per = us_market.build_us_rankings("per", limit=5, market="NASDAQ")

    assert [item["code"] for item in volume["items"]] == ["BBB", "AAA"]
    assert [item["code"] for item in market_cap["items"]] == ["BBB", "AAA"]
    assert [item["code"] for item in low_per["items"]] == ["BBB", "AAA"]
    assert volume["source"] == "yahoo_finance"
    assert volume["items"][0]["currency"] == "USD"
    assert volume["items"][0]["volume"] == 300


def test_us_surge_ranking_honors_week_and_month_modes(monkeypatch):
    universe = [
        {"code": "AAA", "name": "Alpha", "market": "NASDAQ", "sector": "기술"},
        {"code": "BBB", "name": "Beta", "market": "NASDAQ", "sector": "기술"},
    ]

    def fake_dashboard(code):
        is_alpha = code == "AAA"
        return {
            "code": code,
            "name": code,
            "market": "NASDAQ",
            "quote": {"trade_date": None, "price": Decimal("100"), "change_rate": Decimal("1"), "volume": 10, "trading_value": Decimal("1000"), "market_cap": Decimal("10000")},
            "momentum": {
                "one_week_return": Decimal("9" if is_alpha else "2"),
                "one_month_return": Decimal("1" if is_alpha else "8"),
                "three_month_return": Decimal("3"),
                "trading_value_change": Decimal("0"),
            },
            "sentiment": {"score": Decimal("0"), "positive_count": 0, "negative_count": 0, "neutral_count": 0},
            "valuation": {"per": Decimal("20"), "pbr": Decimal("2")},
        }

    monkeypatch.setattr(us_market, "_us_universe_for_market", lambda market: universe)
    monkeypatch.setattr(us_market, "_dashboard_cached", fake_dashboard)

    week = us_market.build_us_rankings("surge", limit=5, market="NASDAQ", mode="week")
    month = us_market.build_us_rankings("surge", limit=5, market="NASDAQ", mode="month")

    assert [item["code"] for item in week["items"]] == ["AAA", "BBB"]
    assert [item["code"] for item in month["items"]] == ["BBB", "AAA"]
    assert week["items"][0]["one_week_return"] == Decimal("9")


def test_us_recommendations_use_the_same_rc1_snapshot_as_the_signal_feed():
    as_of = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    universe_member = {
        "code": "NVDA",
        "name": "NVIDIA",
        "market": "NASDAQ",
        "currency": "USD",
        "sector": "Technology",
        "market_cap_rank": 2,
        "market_cap": Decimal("4200000000000"),
        "price": Decimal("168.25"),
        "average_daily_dollar_volume_3m": Decimal("25000000000"),
        "legacy_regular_market_change_percent": Decimal("1.5"),
        "legacy_fifty_day_average_change_percent": Decimal("0.12"),
        "legacy_two_hundred_day_average_change_percent": Decimal("0.35"),
        "legacy_trailing_pe": Decimal("28"),
        "legacy_price_to_book": Decimal("12"),
    }
    canonical_feed = {
            "status": "ready",
            "data_state": "ready",
            "as_of": as_of,
            "snapshot_id": "us-rc1-snapshot",
            "snapshot_checksum": "feed-checksum",
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "baseline_strategy_version": "us-momentum-watch-v1",
            "sector_classification_version": "us-sector-etf-cik-v4",
            "rollout_mode": "shadow",
            "execution_enabled": False,
            "stateful_lifecycle_replay_enabled": False,
            "reentry_runtime_enabled": False,
            "universe_as_of": date(2026, 9, 6),
            "universe_count": 100,
            "evaluated_count": 100,
            "data_coverage_count": 100,
            "signal_eligible_count": 98,
            "insufficient_history_count": 2,
            "methodology": ["완료 정규장 시총 상위 100종목"],
            "universe_members": [universe_member],
            "items": [
                {
                    "code": "NVDA",
                    "name": "NVIDIA",
                    "market": "NASDAQ",
                    "currency": "USD",
                    "sector": "Technology",
                    "market_cap_rank": 2,
                    "score": Decimal("68"),
                    "price": Decimal("168.25"),
                    "public_reasons": [{"summary": "상대강도 확인"}],
                    "current": {
                        "action": "entry_pending",
                        "position_open": False,
                        "next_confirmation": "다음 정규장 확인",
                    },
                    "status": "preliminary",
                }
            ],
        }

    payload = us_market.build_us_recommendations(
        limit=1,
        candidate_limit=5,
        feed=canonical_feed,
    )

    assert payload["candidate_count"] == 1
    assert payload["snapshot_id"] == "us-rc1-snapshot"
    assert payload["snapshot_checksum"] == "feed-checksum"
    assert payload["universe_count"] == 100
    assert payload["evaluated_count"] == 100
    assert payload["data_coverage_count"] == 100
    assert payload["signal_eligible_count"] == 98
    assert payload["insufficient_history_count"] == 2
    assert payload["strategy_version"] == "position-lifecycle-us-v1-rc1"
    assert payload["baseline_strategy_version"] == "us-momentum-watch-v1"
    assert payload["sector_classification_version"] == "us-sector-etf-cik-v4"
    assert payload["stateful_lifecycle_replay_enabled"] is False
    assert payload["reentry_runtime_enabled"] is False
    assert payload["items"][0]["code"] == "NVDA"
    assert payload["items"][0]["currency"] == "USD"
    assert payload["items"][0]["recommendation_score"] == Decimal("100.00")
    assert payload["items"][0]["recommendation_model_version"] == "us-independent-recommendation-v1"
    assert payload["items"][0]["recommendation_selection_rule"] == (
        "recommendation_score_ranked_independent_of_trade_signal"
    )
    assert payload["items"][0]["ai_trade_signal"]["status"] == "preliminary"
    assert payload["items"][0]["ai_trade_signal"]["current"]["position_open"] is False
    assert "상위 100" in payload["methodology"][0]


def test_us_quant_signals_expose_only_usd_preliminary_candidates():
    as_of = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    canonical_feed = {
            "status": "ready",
            "data_state": "ready",
            "as_of": as_of,
            "snapshot_id": "us-rc1-snapshot",
            "snapshot_checksum": "feed-checksum",
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "rollout_mode": "shadow",
            "execution_enabled": False,
            "universe_count": 100,
            "confirmed_count": 0,
            "preliminary_count": 1,
            "items": [
                {
                    "code": "NVDA",
                    "name": "NVIDIA",
                    "market": "NASDAQ",
                    "sector": "Technology",
                    "currency": "USD",
                    "data_state": "ready",
                    "side": "buy",
                    "status": "preliminary",
                    "is_preliminary": True,
                    "signal_date": date(2026, 9, 7),
                    "current": {
                        "action": "entry_watch",
                        "position_open": False,
                        "model_exposure_percent": Decimal("0"),
                    },
                },
            ],
        }

    payload = us_market.build_us_quant_signals(
        limit=20,
        recent_days=30,
        feed=canonical_feed,
    )

    assert payload["status"] == "ready"
    assert payload["snapshot_id"] == "us-rc1-snapshot"
    assert payload["strategy_version"] == "position-lifecycle-us-v1-rc1"
    assert payload["confirmed_count"] == 0
    assert payload["preliminary_count"] == 1
    assert payload["items"][0]["code"] == "NVDA"
    assert payload["items"][0]["currency"] == "USD"
    assert payload["items"][0]["current"]["position_open"] is False
    assert payload["items"][0]["current"]["model_exposure_percent"] == Decimal("0")


def test_us_recommendation_and_quant_projections_share_one_member_result():
    signal = {
        "code": "NVDA",
        "name": "NVIDIA",
        "market": "NASDAQ",
        "currency": "USD",
        "status": "preliminary",
        "score": Decimal("68"),
        "current": {
            "action": "entry_watch",
            "position_open": False,
            "next_confirmation": "next close",
        },
    }
    feed = {
        "status": "ready",
        "data_state": "ready",
        "strategy_version": "position-lifecycle-us-v1-rc1",
        "rollout_mode": "shadow",
        "snapshot_id": "shared-snapshot",
        "snapshot_checksum": "shared-checksum",
        "universe_members": [
            {
                "code": "NVDA",
                "name": "NVIDIA",
                "market": "NASDAQ",
                "currency": "USD",
                "sector": "Technology",
                "market_cap_rank": 1,
                "market_cap": Decimal("4200000000000"),
                "price": Decimal("168.25"),
                "average_daily_dollar_volume_3m": Decimal("25000000000"),
                "legacy_fifty_day_average_change_percent": Decimal("0.12"),
                "legacy_two_hundred_day_average_change_percent": Decimal("0.35"),
                "legacy_trailing_pe": Decimal("28"),
                "legacy_price_to_book": Decimal("12"),
            }
        ],
        "items": [signal],
    }

    recommendations = us_market.build_us_recommendations(feed=feed, limit=1)
    quant = us_market.build_us_quant_signals(feed=feed, limit=1)

    assert recommendations["snapshot_id"] == quant["snapshot_id"] == "shared-snapshot"
    assert recommendations["snapshot_checksum"] == quant["snapshot_checksum"] == "shared-checksum"
    assert recommendations["items"][0]["ai_trade_signal"] == quant["items"][0]


def test_us_recommendations_rank_top100_independently_of_trade_signal_action():
    members = [
        {
            "code": "AAA",
            "name": "Alpha",
            "market": "NYSE",
            "currency": "USD",
            "sector": "Industrials",
            "market_cap_rank": 3,
            "market_cap": Decimal("300"),
            "price": Decimal("30"),
            "average_daily_dollar_volume_3m": Decimal("900"),
            "legacy_regular_market_change_percent": Decimal("2"),
            "legacy_fifty_day_average_change_percent": Decimal("0.30"),
            "legacy_two_hundred_day_average_change_percent": Decimal("0.50"),
            "legacy_trailing_pe": Decimal("10"),
            "legacy_price_to_book": Decimal("1"),
        },
        {
            "code": "BBB",
            "name": "Beta",
            "market": "NASDAQ",
            "currency": "USD",
            "sector": "Technology",
            "market_cap_rank": 1,
            "market_cap": Decimal("900"),
            "price": Decimal("90"),
            "average_daily_dollar_volume_3m": Decimal("500"),
            "legacy_regular_market_change_percent": Decimal("1"),
            "legacy_fifty_day_average_change_percent": Decimal("0.10"),
            "legacy_two_hundred_day_average_change_percent": Decimal("0.20"),
            "legacy_trailing_pe": Decimal("30"),
            "legacy_price_to_book": Decimal("8"),
        },
        {
            "code": "CCC",
            "name": "Gamma",
            "market": "NASDAQ",
            "currency": "USD",
            "sector": "Technology",
            "market_cap_rank": 2,
            "market_cap": Decimal("600"),
            "price": Decimal("60"),
            "average_daily_dollar_volume_3m": Decimal("100"),
            "legacy_regular_market_change_percent": Decimal("-1"),
            "legacy_fifty_day_average_change_percent": Decimal("-0.10"),
            "legacy_two_hundred_day_average_change_percent": Decimal("-0.20"),
            "legacy_trailing_pe": Decimal("50"),
            "legacy_price_to_book": Decimal("12"),
        },
    ]

    def feed(action: str) -> dict[str, object]:
        return {
            "status": "ready",
            "data_state": "ready",
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "snapshot_id": "us-independent-rank",
            "snapshot_checksum": "checksum",
            "new_entries_allowed": True,
            "universe_members": members,
            "items": [
                {
                    "code": "BBB",
                    "name": "Beta",
                    "market": "NASDAQ",
                    "current": {"action": action, "position_open": False},
                }
            ],
        }

    pending = us_market.build_us_recommendations(feed=feed("entry_pending"), limit=3)
    watching = us_market.build_us_recommendations(feed=feed("entry_watch"), limit=3)

    assert [item["code"] for item in pending["items"]] == ["AAA", "BBB", "CCC"]
    assert [item["code"] for item in watching["items"]] == ["AAA", "BBB", "CCC"]
    assert pending["items"][0]["ai_trade_signal"]["current"]["action"] == "no_signal"
    assert pending["items"][1]["ai_trade_signal"]["current"]["action"] == "entry_pending"
    assert watching["items"][1]["ai_trade_signal"]["current"]["action"] == "entry_watch"
    assert pending["items"][0]["recommendation_score"] > pending["items"][1]["recommendation_score"]


def test_us_recommendation_missing_valuation_reweights_only_observed_components():
    members = [
        {
            "code": "FULL",
            "name": "Full Data",
            "market": "NYSE",
            "sector": "Industrials",
            "market_cap_rank": 1,
            "market_cap": Decimal("200"),
            "price": Decimal("20"),
            "average_daily_dollar_volume_3m": Decimal("200"),
            "legacy_fifty_day_average_change_percent": Decimal("0.20"),
            "legacy_two_hundred_day_average_change_percent": Decimal("0.30"),
            "legacy_trailing_pe": Decimal("20"),
            "legacy_price_to_book": Decimal("2"),
        },
        {
            "code": "MISS",
            "name": "Missing Valuation",
            "market": "NASDAQ",
            "sector": "Technology",
            "market_cap_rank": 2,
            "market_cap": Decimal("100"),
            "price": Decimal("10"),
            "average_daily_dollar_volume_3m": Decimal("100"),
            "legacy_fifty_day_average_change_percent": Decimal("0.10"),
            "legacy_two_hundred_day_average_change_percent": Decimal("0.20"),
            "legacy_trailing_pe": None,
            "legacy_price_to_book": None,
        },
    ]
    payload = us_market.build_us_recommendations(
        feed={
            "status": "ready",
            "data_state": "ready",
            "strategy_version": "position-lifecycle-us-v1-rc1",
            "snapshot_id": "valuation-missing",
            "snapshot_checksum": "checksum",
            "universe_members": members,
            "items": [],
        },
        limit=2,
    )

    missing = next(item for item in payload["items"] if item["code"] == "MISS")
    assert "valuation" not in missing["recommendation_components"]
    assert missing["recommendation_observed_weight"] == Decimal("80")
    assert missing["recommendation_score"] == Decimal("0.00")


def test_research_from_quote_summary_fills_analyst_fields():
    payload = {
        "financialData": {
            "targetMeanPrice": {"raw": 314.42},
            "targetHighPrice": {"raw": 400.0},
            "targetLowPrice": {"raw": 215.0},
            "recommendationMean": {"raw": 1.98},
            "recommendationKey": "buy",
            "numberOfAnalystOpinions": {"raw": 42},
        },
        "recommendationTrend": {
            "trend": [
                {"period": "0m", "strongBuy": 6, "buy": 23, "hold": 15, "sell": 1, "strongSell": 2},
            ]
        },
        "upgradeDowngradeHistory": {
            "history": [
                {
                    "epochGradeDate": 1781014385,
                    "firm": "TD Cowen",
                    "toGrade": "Buy",
                    "fromGrade": "Buy",
                    "action": "main",
                    "priceTargetAction": "Raises",
                    "currentPriceTarget": 350.0,
                    "priorPriceTarget": 335.0,
                },
                {
                    "epochGradeDate": 1782138875,
                    "firm": "KGI Securities",
                    "toGrade": "Hold",
                    "fromGrade": "Outperform",
                    "action": "down",
                    "priceTargetAction": "Announces",
                    "currentPriceTarget": 315.0,
                    "priorPriceTarget": 0.0,
                },
            ]
        },
    }

    research = us_market._research_from_quote_summary(
        payload,
        now=datetime(2026, 7, 1, tzinfo=UTC),
    )

    assert research["report_count_90d"] == 2
    assert research["target_up_count"] == 1
    assert research["target_down_count"] == 1
    assert research["target_up_ratio"] == Decimal("61.7")
    assert research["latest_target_price"] == Decimal("314.42")
    assert research["latest_opinion"] == "매수"
    assert research["analyst_opinion_count"] == 42


def test_us_financial_series_keeps_raw_usd_and_calculates_percent_margins():
    fundamentals = {
        "annualTotalRevenue": [{"asOfDate": "2024-12-31", "reportedValue": {"raw": 100_000_000_000}}],
        "annualOperatingIncome": [{"asOfDate": "2024-12-31", "reportedValue": {"raw": 20_000_000_000}}],
        "annualNetIncome": [{"asOfDate": "2024-12-31", "reportedValue": {"raw": 15_000_000_000}}],
        "annualDilutedEPS": [{"asOfDate": "2024-12-31", "reportedValue": {"raw": 2.5}}],
    }

    rows = us_market._financial_series_rows(fundamentals, "annual")

    assert rows == [{
        "period": "2024",
        "reported_at": "2024-12-31",
        "estimated": False,
        "revenue": Decimal("100000000000"),
        "operating_profit": Decimal("20000000000"),
        "net_income": Decimal("15000000000"),
        "eps": Decimal("2.5"),
        "operating_margin": Decimal("20.00"),
        "net_margin": Decimal("15.00"),
    }]


def test_google_news_defaults_to_korean_service_locale(monkeypatch):
    request = {}

    def fake_get(url, **kwargs):
        request.update({"url": url, **kwargs})
        return _FakeNewsResponse()

    monkeypatch.setattr(us_market.requests, "get", fake_get)

    rows = us_market._google_news_items("NVIDIA stock")

    assert request["params"] == {"q": "NVIDIA stock", "hl": "ko", "gl": "KR", "ceid": "KR:ko"}
    assert rows[0]["title"] == "엔비디아 실적 전망"
    assert rows[0]["source"] == "테스트뉴스"


def test_us_news_does_not_fallback_to_non_naver_sources(monkeypatch):
    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "NVDA", "name": "NVIDIA"},
    )
    monkeypatch.setattr(
        us_market,
        "_naver_news_items",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        us_market,
        "_naver_world_local_news_items",
        lambda *args, **kwargs: [],
    )
    rows = us_market._news("NVDA")

    assert rows == []


def test_us_news_prefers_korean_naver_news_results(monkeypatch):
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    monkeypatch.setattr(
        us_market,
        "_naver_world_local_news_items",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        us_market,
        "_naver_news_items",
        lambda *args, **kwargs: [{
            "title": "엔비디아, AI 투자 확대",
            "source": "한국경제",
            "url": "https://news.example/nvda",
            "published_at": datetime(2026, 9, 23, 9),
        }],
    )
    monkeypatch.setattr(
        us_market,
        "_google_news_items",
        lambda *args, **kwargs: [{
            "title": "구글 뉴스 대체 기사",
            "source": "Google News",
            "url": "https://news.example/google",
        }],
    )

    rows = us_market._news("NVDA", now=now)

    assert rows == [{
        "title": "엔비디아, AI 투자 확대",
        "source": "한국경제",
        "url": "https://news.example/nvda",
        "published_at": datetime(2026, 9, 23, 9),
    }]


def test_parse_naver_world_local_news_payload_builds_korean_article_links():
    rows = us_market._parse_naver_world_local_news_payload({
        "result": [{
            "articleId": "0005410226",
            "datetime": "202609071026",
            "officeId": "008",
            "officeName": "머니투데이",
            "title": "&quot;AGI가 왔다&quot; 젠슨 황도 선언",
        }],
    })

    assert rows == [{
        "title": '"AGI가 왔다" 젠슨 황도 선언',
        "source": "머니투데이",
        "url": "https://n.news.naver.com/mnews/article/008/0005410226",
        "published_at": datetime(2026, 9, 7, 10, 26),
    }]


def test_us_news_prefers_naver_world_local_news_api(monkeypatch):
    local_rows = [{
        "title": "엔비디아 국내 언론 기사",
        "source": "한국경제",
        "url": "https://n.news.naver.com/mnews/article/999/0000000001",
        "published_at": datetime(2026, 9, 23, 9),
    }]
    monkeypatch.setattr(us_market, "_naver_world_local_news_items", lambda *args, **kwargs: local_rows)
    monkeypatch.setattr(us_market, "_naver_news_items", lambda *args, **kwargs: pytest.fail("search fallback should not run"))

    assert us_market._news(
        "NVDA",
        now=datetime(2026, 9, 24, 12, tzinfo=UTC),
    ) == local_rows


def test_us_news_filters_unrelated_naver_headlines_for_the_selected_stock(monkeypatch):
    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "ASML", "name": "ASML Holding"},
    )
    monkeypatch.setattr(
        us_market,
        "_naver_world_local_news_items",
        lambda *args, **kwargs: [
            {
                "title": "에코프로, 로봇 정조준",
                "source": "딜사이트",
                "url": "https://news.example/ecopro",
                "published_at": datetime(2026, 9, 23, 9),
            },
            {
                "title": "ASML 장비 수요 확대",
                "source": "한국경제",
                "url": "https://news.example/asml",
                "published_at": datetime(2026, 9, 23, 10),
            },
        ],
    )

    rows = us_market._news(
        "ASML",
        now=datetime(2026, 9, 24, 12, tzinfo=UTC),
    )

    assert [row["title"] for row in rows] == ["ASML 장비 수요 확대"]


def test_naver_news_queries_exact_company_before_aliases_and_ticker():
    candidates = us_market._naver_news_query_candidates({
        "code": "ASML",
        "name": "ASML Holding",
    })

    assert candidates == ["ASML Holding", "에이에스엠엘", "ASML"]
    assert "ASML ASML" not in candidates


def test_naver_news_search_skips_full_unrelated_page_and_uses_next_query(monkeypatch):
    calls = []

    class FakeSearchResponse:
        def __init__(self, query):
            self.text = query

        def raise_for_status(self):
            return None

    def fake_get(url, **kwargs):
        query = kwargs["params"]["query"]
        calls.append(kwargs["params"])
        return FakeSearchResponse(query)

    def fake_parse(html, limit=10):
        if html == "ASML Holding":
            return [
                {
                    "title": f"에코프로 배터리 뉴스 {index}",
                    "source": "테스트뉴스",
                    "url": f"https://news.example/ecopro-{index}",
                    "published_at": datetime(2026, 9, 23, 8),
                }
                for index in range(10)
            ]
        if html == "에이에스엠엘":
            return [{
                "title": "에이에스엠엘, 차세대 노광장비 투자 확대",
                "source": "테스트뉴스",
                "url": "https://news.example/asml",
                "published_at": datetime(2026, 9, 23, 9),
            }]
        return []

    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "ASML", "name": "ASML Holding"},
    )
    monkeypatch.setattr(us_market.requests, "get", fake_get)
    monkeypatch.setattr(us_market, "_parse_naver_news_search_html", fake_parse)

    rows = us_market._naver_news_items(
        "ASML",
        limit=10,
        now=datetime(2026, 9, 24, 12, tzinfo=UTC),
    )

    assert [row["title"] for row in rows] == ["에이에스엠엘, 차세대 노광장비 투자 확대"]
    assert [call["query"] for call in calls] == ["ASML Holding", "에이에스엠엘", "ASML"]
    assert all(call["sort"] == "0" for call in calls)


def test_wmb_naver_news_rejects_short_ticker_collisions_stale_and_duplicates():
    now = datetime(2026, 9, 24, 12, tzinfo=UTC)
    stock = {
        "code": "WMB",
        "name": "Williams Companies Inc. (The)",
        "market": "SP500",
    }
    rows = us_market._filter_us_news_for_stock(
        [
            {
                "title": "언오피셜보이X윤병호, '보이스3' OST WMB 공개",
                "source": "연예뉴스",
                "url": "https://news.example/voice-ost",
                "published_at": datetime(2026, 9, 23, 11),
            },
            {
                "title": "HBM4 웨이퍼 제조공정 WMB 기술 공개",
                "source": "반도체뉴스",
                "url": "https://news.example/wafer",
                "published_at": datetime(2026, 9, 23, 10),
            },
            {
                "title": "윌리엄스 타운, VFLW 결승 진출",
                "source": "스포츠뉴스",
                "url": "https://news.example/williams-town",
                "published_at": datetime(2026, 9, 23, 9, 30),
            },
            {
                "title": "윌리엄스 컴퍼니즈, 천연가스 인프라 투자 확대",
                "source": "에너지경제",
                "url": "https://news.example/williams-new",
                "published_at": datetime(2026, 9, 23, 9),
            },
            {
                "title": "윌리엄스 컴퍼니즈 - 천연가스 인프라 투자 확대",
                "source": "에너지경제",
                "url": "https://news.example/williams-duplicate",
                "published_at": datetime(2026, 9, 23, 8),
            },
            {
                "title": "윌리엄스, 파이프라인 투자 계획 발표",
                "source": "과거뉴스",
                "url": "https://news.example/williams-stale",
                "published_at": datetime(2019, 6, 8, 9),
            },
        ],
        stock,
        now=now,
    )

    assert [row["title"] for row in rows] == [
        "윌리엄스 컴퍼니즈, 천연가스 인프라 투자 확대",
    ]
    assert not us_market._us_news_title_matches_stock(
        "WMB 모니터 신제품 출시",
        stock,
    )
    assert not us_market._us_news_title_matches_stock(
        "윌리엄스 타운, VFLW 결승 진출",
        stock,
    )
    assert "companies" not in us_market._us_news_identity_terms(stock)


def test_wmb_yahoo_news_accepts_trusted_related_ticker_for_short_symbol():
    timestamp = int(datetime(2026, 9, 23, 15, tzinfo=UTC).timestamp())

    rows = us_market._parse_yahoo_news_payload(
        {
            "news": [{
                "uuid": "wmb-yahoo-1",
                "title": "WMB Gains as Natural Gas Demand Improves",
                "publisher": "Reuters",
                "link": "https://finance.yahoo.com/news/wmb-gains",
                "providerPublishTime": timestamp,
                "relatedTickers": ["WMB"],
            }],
        },
        "WMB",
        stock={"code": "WMB", "name": "Williams Companies Inc. (The)"},
        now=datetime(2026, 9, 24, 12, tzinfo=UTC),
    )

    assert [row["title"] for row in rows] == [
        "WMB Gains as Natural Gas Demand Improves",
    ]


def test_naver_world_news_uses_verified_yahoo_exchange_code_only():
    stock = {
        "code": "WMB",
        "name": "Williams Companies Inc. (The)",
        "market": "SP500",
        "markets": ["SP500"],
        "exchange_name": "NYQ",
        "full_exchange_name": "NYSE",
    }

    assert us_market._naver_world_news_code_candidates(stock) == ["WMB.N"]


def test_parse_yahoo_news_payload_keeps_ticker_related_overseas_fields():
    timestamp = 1788562282
    rows = us_market._parse_yahoo_news_payload(
        {
            "news": [
                {
                    "uuid": "y-1",
                    "title": "Why ASML Holding Stock Bumped 4% Higher Today",
                    "publisher": "Motley Fool",
                    "link": "https://finance.yahoo.com/news/asml",
                    "providerPublishTime": timestamp,
                    "relatedTickers": ["ASML", "NVDA"],
                    "thumbnail": {"resolutions": [{"tag": "140x140", "url": "https://img.example/asml.jpg"}]},
                },
                {
                    "uuid": "y-2",
                    "title": "Ecopro outlook",
                    "publisher": "Other",
                    "link": "https://finance.yahoo.com/news/ecopro",
                    "relatedTickers": ["ECOR"],
                },
            ],
        },
        "ASML",
        stock={"code": "ASML", "name": "ASML Holding"},
        now=datetime(2026, 9, 24, 12, tzinfo=UTC),
    )

    assert rows == [{
        "title": "Why ASML Holding Stock Bumped 4% Higher Today",
        "source": "Yahoo Finance",
        "source_category": "overseas",
        "press_name": "Motley Fool",
        "url": "https://finance.yahoo.com/news/asml",
        "detail_url": "https://finance.yahoo.com/news/asml",
        "external_id": "y-1",
        "published_at": datetime.fromtimestamp(timestamp, UTC),
        "image_url": "https://img.example/asml.jpg",
    }]


def test_parse_naver_news_search_html_extracts_domestic_article_fields():
    html = """
    <div class="hCxR_uNoqfEahHu_">
      <div class="sds-comps-profile-info-title-text">테스트경제 <span>새 창 열림</span></div>
      <div class="sds-comps-profile-info-subtext">2026.09.07. 08:10</div>
      <a data-heatmap-target=".tit" href="https://news.example/nvda">
        <span class="sds-comps-text-type-headline1">엔비디아 실적 전망</span>
      </a>
    </div>
    """

    rows = us_market._parse_naver_news_search_html(html)

    assert rows == [{
        "title": "엔비디아 실적 전망",
        "source": "테스트경제",
        "url": "https://news.example/nvda",
        "published_at": datetime(2026, 9, 7, 8, 10),
    }]


def test_us_prices_requests_long_history_for_five_year_and_all_charts(monkeypatch):
    calls = []
    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "NVDA", "name": "NVIDIA"},
    )

    def fake_chart_prices_range(symbol, range_, interval, refresh, limit):
        calls.append((symbol, range_, interval, refresh, limit))
        return {}, []

    monkeypatch.setattr(us_market, "chart_prices_range", fake_chart_prices_range)

    assert us_market.us_prices("NVDA", limit=2000) == []
    assert calls == [("NVDA", "10y", "1d", False, 2000)]


def test_us_intraday_prices_normalizes_new_york_market_points(monkeypatch):
    timestamp = int(datetime(2026, 9, 4, 13, 31, tzinfo=UTC).timestamp())
    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "NVDA", "name": "NVIDIA"},
    )
    monkeypatch.setattr(
        us_market,
        "fetch_chart_range",
        lambda *args, **kwargs: {
            "meta": {"chartPreviousClose": 170.25},
            "timestamp": [timestamp],
            "indicators": {
                "quote": [{
                    "open": [171.0],
                    "high": [172.5],
                    "low": [170.75],
                    "close": [172.0],
                    "volume": [12345],
                }]
            },
        },
    )
    monkeypatch.setattr(
        us_market,
        "_us_market_session",
        lambda: {
            "session": "regular",
            "label": "미국 정규장 진행 중",
            "is_live": True,
            "local_time": datetime(2026, 9, 4, 9, 31, tzinfo=us_market.NEW_YORK_TZ),
        },
    )

    payload = us_market.us_intraday_prices("NVDA", range_="1d", interval="1m")

    assert payload["market_timezone"] == "America/New_York"
    assert payload["market_session"] == "regular"
    assert payload["reference_price"] == Decimal("170.25")
    assert payload["points"] == [{
        "trade_date": date(2026, 9, 4),
        "trade_time": "093100",
        "open": Decimal("171.0"),
        "high": Decimal("172.5"),
        "low": Decimal("170.75"),
        "close": Decimal("172.0"),
        "price": Decimal("172.0"),
        "volume": 12345,
    }]


def test_us_previous_close_prefers_current_daily_reference_over_stale_chart_metadata():
    meta = {
        "chartPreviousClose": 171.66,
        "previousClose": None,
    }

    assert us_market._us_previous_close(meta, Decimal("228.45")) == Decimal("228.45")
    reference = us_market._us_intraday_reference_price({
        "regularMarketPrice": 230.36,
        "regularMarketChangePercent": 0.836,
        "chartPreviousClose": 171.66,
    })
    assert round(float(reference), 2) == 228.45


def test_us_market_trends_uses_real_recent_articles_and_rejects_synthetic_freshness():
    now = datetime(2026, 9, 23, 12, 30, tzinfo=UTC)
    payload = us_market.build_us_trends(
        days=7,
        now=now,
        news_items=[
            {
                "title": "엔비디아 반도체 랠리에 나스닥 사상 최고 - 뉴스1",
                "source": "뉴스1",
                "url": "https://news.example/us-market-rally",
                "published_at": now - timedelta(hours=1),
            },
            {
                "title": "엔비디아 반도체 랠리에 나스닥 사상 최고 - 뉴스1",
                "source": "뉴스1",
                "url": "https://news.example/duplicate-title",
                "published_at": now - timedelta(hours=2),
            },
            {
                "title": "오래된 미국 증시 뉴스",
                "source": "테스트",
                "url": "https://news.example/old",
                "published_at": now - timedelta(days=8),
            },
            {
                "title": "URL이 없는 뉴스",
                "source": "테스트",
                "url": None,
                "published_at": now,
            },
        ],
    )

    assert payload["status"] == "ready"
    assert payload["data_state"] == "live"
    assert payload["events"] == []
    assert payload["window_start"] == datetime(2026, 9, 16, 12, 30, tzinfo=UTC)
    assert len(payload["timeline"]) == 1
    article = payload["timeline"][0]
    assert article["title"] == "엔비디아 반도체 랠리에 나스닥 사상 최고"
    assert article["url"] == "https://news.example/us-market-rally"
    assert article["published_at"] == datetime(2026, 9, 23, 11, 30, tzinfo=UTC)
    assert article["category"] == "반도체"
    assert article["impact"] == "호재"
    assert article["leader_stocks"] == ["NVDA"]
    assert article["source"] not in {"NASDAQ Brief", "Macro Brief"}


def test_us_market_trends_fails_closed_when_all_live_sources_fail(monkeypatch):
    def unavailable_source(*args, **kwargs):
        raise RuntimeError("upstream unavailable")

    monkeypatch.setattr(us_market, "_google_news_items", unavailable_source)

    payload = us_market.build_us_trends(
        days=7,
        now=datetime(2026, 9, 23, 12, 30, tzinfo=UTC),
    )

    assert payload["status"] == "unavailable"
    assert payload["data_state"] == "unavailable"
    assert payload["timeline"] == []
    assert payload["events"] == []
