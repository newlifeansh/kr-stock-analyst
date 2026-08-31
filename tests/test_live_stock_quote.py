import json
import subprocess
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

import app.main as main_module
from app.services.kis_realtime import KisRealtimeQuoteProvider, parse_kis_stock_tick


class _FakeKisProvider:
    def __init__(self):
        self.calls = 0

    def is_configured(self):
        return True

    def _request_current_price(self, code, market_division="J"):
        self.calls += 1
        return {
            "stck_bsop_date": "20260827",
            "stck_prpr": str(100_000 + self.calls),
            "stck_oprc": "99,000",
            "stck_hgpr": "101,000",
            "stck_lwpr": "98,500",
            "prdy_vrss": "1200",
            "prdy_ctrt": "1.21",
            "prdy_vrss_sign": "2",
            "acml_vol": "345678",
            "acml_tr_pbmn": "9876543210",
        }


def test_kis_current_quote_is_requested_again_instead_of_cached(monkeypatch):
    provider = _FakeKisProvider()
    monkeypatch.setattr(main_module, "kis_rest_provider", provider)

    first = main_module._fetch_kis_current_quote("005930")
    second = main_module._fetch_kis_current_quote("005930")

    assert provider.calls == 2
    assert first["price"] == 100_001
    assert second["price"] == 100_002
    assert (second["open"], second["high"], second["low"]) == (99_000, 101_000, 98_500)
    assert second["change_rate"] == Decimal("1.21")
    assert second["trade_date"] == date(2026, 8, 27)
    assert second["trade_date_verified"] is True
    assert second["quote_source"] == "kis_rest"
    assert isinstance(second["observed_at"], datetime)
    assert second["market_session"] == "krx_reference"
    assert second["market_venue"] == "KRX"
    assert second["market_division"] == "J"


def test_current_quote_falls_back_to_fresh_naver_snapshot(monkeypatch):
    monkeypatch.setattr(main_module, "_fetch_kis_current_quote", lambda code, **_kwargs: {})
    monkeypatch.setattr(
        main_module,
        "_naver_snapshot",
        lambda code, refresh=False: {
            "price": 4250,
            "change_value": 45,
            "change_rate_abs": Decimal("1.07"),
            "volume": 10_424_306,
            "trading_value": 45_824_035_836,
        },
    )

    quote, source = main_module._fetch_uncached_current_quote("079650")

    assert source == "naver_finance"
    assert quote["price"] == 4250
    assert quote["change_rate"] == Decimal("1.07")


def test_synthetic_weekend_quote_cannot_override_last_completed_close():
    weekend = datetime(2026, 8, 29, 0, 2, tzinfo=main_module.KST)
    synthetic = {
        "trade_date": weekend.date(),
        "trade_date_verified": False,
        "quote_source": "kis_rest",
        "observed_at": weekend,
        "price": 450_500,
        "market_session": "closed",
        "market_venue": "KRX",
        "market_division": "J",
        "is_live": False,
    }

    assert (
        main_module._live_quote_can_override_stored_close(
            synthetic,
            date(2026, 8, 28),
            now=weekend,
        )
        is False
    )
    assert main_module._live_quote_can_override_stored_close(
        {**synthetic, "trade_date": date(2026, 8, 28), "trade_date_verified": True},
        date(2026, 8, 28),
        now=weekend,
    )


def test_live_quote_endpoint_disables_http_caching(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_stock_quote_stream_payload",
        lambda code: {
            "type": "quote",
            "code": code,
            "name": "삼성전자",
            "market": "KOSPI",
            "source": "kis_rest",
            "as_of": "2026-07-23T10:00:00+09:00",
            "quote": {"price": 100_000, "change_rate": 1.2},
        },
    )
    response = TestClient(main_module.app).get("/stocks/005930/quote")

    assert response.status_code == 200
    assert response.json()["source"] == "kis_rest"
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"
    assert response.headers["pragma"] == "no-cache"


def test_invalid_kis_approval_key_is_discarded_before_reconnect():
    provider = KisRealtimeQuoteProvider(settings=None)
    provider._approval_key = "stale-approval"
    provider._approval_expires_at = datetime.utcnow() + timedelta(hours=10)

    assert provider.invalidate_approval_key("different-approval") is False
    assert provider._approval_key == "stale-approval"
    assert provider.invalidate_approval_key("stale-approval") is True
    assert provider._approval_key is None
    assert provider._approval_expires_at is None
    assert main_module._kis_approval_is_invalid("invalid approval : stale-approval") is True
    assert main_module._kis_approval_is_invalid("subscription limit exceeded") is False


def test_kis_realtime_errors_are_sanitized_and_contention_backoff_is_extended(
    monkeypatch,
):
    approval = "invalid approval : 9fdcb22a-secret-token"
    busy = "ALREADY IN USE appkey"
    monkeypatch.setattr(
        main_module.settings,
        "kis_realtime_contention_backoff_seconds",
        45,
    )

    approval_message = main_module._public_kis_status_message("fallback", approval)
    busy_message = main_module._public_kis_status_message("fallback", busy)

    assert approval_message == "KIS realtime approval rejected"
    assert "9fdcb22a" not in approval_message
    assert busy_message == "KIS realtime session busy"
    assert main_module._kis_reconnect_delay_seconds(busy_message, 1) == 45
    assert main_module._kis_reconnect_delay_seconds("network unavailable", 1) == 2


def test_live_quote_fallback_uses_fast_market_polling():
    assert main_module._quote_poll_interval_seconds(time(10, 30)) == 2
    assert main_module._quote_poll_interval_seconds(time(15, 45)) == 2
    assert main_module._quote_poll_interval_seconds(time(16, 0)) == 2
    assert main_module._quote_poll_interval_seconds(time(20, 0)) == 8


def test_korea_quote_session_routes_nxt_pre_market_and_integrated_regular(monkeypatch):
    monkeypatch.setattr(main_module, "is_korea_market_session_date", lambda *_args: True)

    pre_market = main_module._korea_quote_session(
        datetime(2026, 8, 27, 8, 10, tzinfo=main_module.KST)
    )
    regular = main_module._korea_quote_session(
        datetime(2026, 8, 27, 10, 0, tzinfo=main_module.KST)
    )

    assert pre_market == {
        "market_session": "nxt_pre_market",
        "market_session_label": "NXT 프리마켓",
        "market_venue": "NXT",
        "market_division": "NX",
        "is_live": True,
    }
    assert regular["market_session"] == "integrated_regular"
    assert regular["market_division"] == "UN"


def test_extended_quote_uses_nxt_price_as_primary_from_8am(monkeypatch):
    class Provider:
        @staticmethod
        def is_configured():
            return True

        @staticmethod
        def _request_current_price(_code, market_division="J"):
            assert market_division == "NX"
            return {
                "stck_prpr": "268500",
                "stck_oprc": "269000",
                "stck_hgpr": "272000",
                "stck_lwpr": "268000",
                "prdy_vrss": "7000",
                "prdy_ctrt": "2.68",
                "prdy_vrss_sign": "2",
                "acml_vol": "2123738",
                "acml_tr_pbmn": "573137797500",
            }

    monkeypatch.setattr(main_module, "kis_rest_provider", Provider())
    monkeypatch.setattr(main_module, "is_korea_market_session_date", lambda *_args: True)

    quote = main_module._fetch_kis_current_quote(
        "005930",
        extended_hours=True,
        now=datetime(2026, 8, 27, 8, 10, tzinfo=main_module.KST),
    )

    assert quote["price"] == 268_500
    assert quote["market_session"] == "nxt_pre_market"
    assert quote["market_division"] == "NX"
    assert quote["pre_market_price"] == 268_500
    assert quote["pre_market_change_rate"] == Decimal("2.68")
    assert quote["pre_market_status"] == "NXT 프리마켓 실시간"


def test_integrated_realtime_subscription_and_tick_parser_support_nxt():
    message = json.loads(main_module._kis_subscription_message("005930"))
    assert message["body"]["input"]["tr_id"] == "H0UNCNT0"

    fields = [""] * 46
    fields[0] = "005930"
    fields[1] = "081015"
    fields[2] = "268500"
    fields[3] = "2"
    fields[4] = "7000"
    fields[5] = "2.68"
    fields[12] = "15"
    fields[13] = "2123738"
    fields[14] = "573137797500"
    tick = parse_kis_stock_tick(f"0|H0UNCNT0|001|{'^'.join(fields)}")

    assert tick is not None
    assert tick["price"] == 268_500
    assert tick["trade_time"] == "081015"
    assert tick["trade_volume"] == 15
    assert tick["market_venue"] == "INTEGRATED"


def test_stored_close_keeps_its_market_timestamp_and_realtime_ticks_are_shared():
    import inspect

    fallback_source = inspect.getsource(main_module._stock_quote_stream_payload_uncached)
    broadcast_source = inspect.getsource(main_module._broadcast_kis_quote)

    assert "datetime.combine(latest.trade_date, time(15, 30), tzinfo=KST)" in fallback_source
    assert "live_quote_cache.set" in broadcast_source


def test_dashboard_frontend_bypasses_quote_cache_and_shows_provider_badge():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text

    assert "isUncachedKoreaMarketDataUrl" in source
    assert 'parsed.pathname === "/stocks/search"' in source
    assert '/^\\/stocks\\/(?:search|resolve)$/' not in source
    assert "/^\\/stocks\\/[^/]+\\/quote$/" in source
    assert 'parsed.searchParams.get("include_live") !== "0"' in source
    assert "if (!bypassCache)" in source
    assert 'badge.textContent = generationLabel;' in source
    assert 'badge.classList.toggle("is-ollama", isOllamaAnalysis);' in source


def test_public_quote_batch_endpoint_fetches_each_code_once(monkeypatch):
    calls = []

    async def fake_payload(code):
        calls.append(code)
        return {
            "type": "quote",
            "code": code,
            "source": "test",
            "quote": {"price": 100_000},
        }

    monkeypatch.setattr(main_module, "_stock_quote_stream_payload_async", fake_payload)
    monkeypatch.setattr(main_module, "_active_stock_quote_codes", lambda codes: set(codes))
    response = TestClient(main_module.app).get(
        "/stocks/quotes?codes=005930,000660,005930"
    )

    assert response.status_code == 200
    assert calls == ["005930", "000660"]
    body = response.json()
    assert [item["code"] for item in body["items"]] == ["005930", "000660"]
    assert body["rejected_codes"] == []
    assert all(item["sequence"] >= 1 for item in body["items"])
    assert all(item["observed_at"] and item["published_at"] for item in body["items"])
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate"


def test_quote_stream_frontends_use_one_multiplex_socket_and_shared_batch_fallback():
    client = TestClient(main_module.app)
    mobile = client.get("/assets/dashboard/app.js").text
    desktop = client.get("/assets/desktop/app.js").text

    assert 'new WebSocket(socketUrl("/ws/quotes"))' in mobile
    assert 'new WebSocket(liveSocketUrl())' in desktop
    assert '`${protocol}//${location.host}/ws/quotes`' in desktop
    assert "/stocks/quotes?codes=" in mobile
    assert "/stocks/quotes?codes=" in desktop
    assert "quoteStreamScopes: new Map()" in mobile
    assert "liveQuoteModels: new Map()" in desktop
    assert "/ws/stocks/" not in mobile
    assert "/ws/stocks/" not in desktop


def test_dashboard_surfaces_extended_session_status_and_live_intraday_refresh():
    client = TestClient(main_module.app)
    mobile = client.get("/assets/dashboard/app.js").text
    shell = client.get("/dashboard/005930").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert "function koreaMarketStatusLabel(" in mobile
    assert "function koreaMarketStatusDisplayLabel(" in mobile
    assert 'pre_market_reference: "프리장 진행중"' in mobile
    assert 'krx_regular: "정규장 진행중"' in mobile
    assert 'return "정규장 마감";' in mobile
    assert 'return "프리장 대기";' in mobile
    assert "elements.stockPreMarket.hidden = false;" in mobile
    assert 'id="stock-v2-as-of" hidden' in shell
    assert 'class="stock-v3-quote-head" hidden aria-hidden="true"' in shell
    assert 'id="stock-pre-market"' in shell
    assert 'aria-controls="stock-trading-hours-sheet"' in shell
    assert 'id="stock-market-status-label"' in shell
    assert 'id="stock-trading-hours-sheet"' in shell
    assert 'aria-modal="true"' in shell
    assert "08:00–08:50" in shell
    assert "09:00–15:30" in shell
    assert "15:40–20:00" in shell
    assert "formatQuoteTradeTime" not in mobile
    assert "setText(elements.stockMarketStatusLabel, displayStatus);" in mobile
    assert "trapStockTradingHoursFocus" in mobile
    assert 'elements.stockPreMarket?.addEventListener("click", openStockTradingHoursSheet);' in mobile
    assert "KIS 실시간" not in mobile
    assert "const marketOpen = koreaExtendedQuoteLive();" in mobile
    assert "quote?.is_live === true" in mobile
    assert '"session chart"' in styles
    assert '[data-status-tone="live"]' in styles
    assert ".stock-trading-hours-sheet" in styles


def test_dashboard_market_status_labels_follow_korea_trading_windows():
    source = TestClient(main_module.app).get("/assets/dashboard/app.js").text
    status_start = source.index("function koreaMarketStatusByClock(")
    status_end = source.index("function renderKoreaQuoteSession(", status_start)
    clock_start = source.index("function koreaClockParts(")
    clock_end = source.index("function morningMoneyEdition(", clock_start)
    script = f"""
const MORNING_MONEY_BRIEFING_TIMEZONE = "Asia/Seoul";
{source[clock_start:clock_end]}
{source[status_start:status_end]}
const times = [
  "2026-08-27T22:30:00Z",
  "2026-08-27T23:10:00Z",
  "2026-08-27T23:55:00Z",
  "2026-08-28T00:10:00Z",
  "2026-08-28T06:35:00Z",
  "2026-08-28T07:00:00Z",
  "2026-08-28T11:10:00Z",
  "2026-08-29T00:10:00Z",
];
console.log(JSON.stringify(times.map((value) => koreaMarketStatusLabel(null, new Date(value)))));
console.log(koreaMarketStatusDisplayLabel({{
  market_session: "integrated_regular",
  market_session_label: "통합 정규장",
}}, new Date("2026-08-28T00:10:00Z")));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    lines = completed.stdout.strip().splitlines()
    assert json.loads(lines[0]) == [
        "프리장 대기",
        "프리장 진행중",
        "정규장 대기",
        "정규장 진행중",
        "애프터장 대기",
        "애프터장 진행중",
        "정규장 마감",
        "정규장 마감",
    ]
    assert lines[1] == "통합 정규장 · 정규장 진행중"


def test_realtime_status_explicitly_reports_private_watchlists_are_not_shared():
    response = TestClient(main_module.app).get("/realtime/status")

    assert response.status_code == 200
    body = response.json()
    assert body["private_watchlists_shared"] is False
    assert body["public_quote_channels"]["max_codes_per_client"] >= 1
    assert body["public_quote_channels"]["min_broadcast_interval_ms"] >= 0
    assert body["public_quote_channels"]["max_unique_codes"] >= 1
    assert body["public_quote_channels"]["kis_session_codes"] >= 0
    assert isinstance(body["public_quote_channels"]["idle_grace_active"], bool)
    assert body["public_quote_channels"]["idle_grace_seconds"] == 60
    assert body["public_quote_channels"]["contention_backoff_seconds"] == 30
    assert "quotes_published" in body["delivery"]
    assert "oldest_published_quote" in body["ages_seconds"]
    assert isinstance(body["signal_revision"]["revision"], int)
