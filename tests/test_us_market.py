from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from app.services import us_market


class _FakeNewsResponse:
    content = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
    <rss><channel><item><title>엔비디아 실적 전망</title><link>https://example.test/nvda</link>
    <pubDate>Fri, 04 Sep 2026 12:00:00 GMT</pubDate><source>테스트뉴스</source></item></channel></rss>""".encode("utf-8")

    def raise_for_status(self):
        return None


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


def test_us_recommendations_use_the_batch_ranking_snapshot_without_per_stock_fetches(monkeypatch):
    as_of = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        us_market,
        "build_us_rankings",
        lambda *args, **kwargs: {
            "as_of": as_of,
            "items": [
                {
                    "code": "NVDA",
                    "name": "NVIDIA",
                    "market": "NASDAQ",
                    "currency": "USD",
                    "price": Decimal("168.25"),
                    "change_rate": Decimal("2.4"),
                    "one_month_return": Decimal("12.5"),
                    "three_month_return": Decimal("24.0"),
                    "trading_value": Decimal("12000000000"),
                    "per": Decimal("36"),
                    "pbr": Decimal("20"),
                    "sentiment_score": Decimal("0"),
                }
            ],
        },
    )
    monkeypatch.setattr(
        us_market,
        "_dashboard_cached",
        lambda symbol: (_ for _ in ()).throw(AssertionError(f"unexpected detail fetch: {symbol}")),
    )

    payload = us_market.build_us_recommendations(limit=1, candidate_limit=5)

    assert payload["candidate_count"] == 1
    assert payload["items"][0]["code"] == "NVDA"
    assert payload["items"][0]["currency"] == "USD"
    assert payload["items"][0]["ai_trade_signal"]["status"] == "preliminary"
    assert payload["items"][0]["ai_trade_signal"]["current"]["position_open"] is False
    assert "배치 시세" in payload["methodology"][0]


def test_us_quant_signals_expose_only_usd_preliminary_candidates(monkeypatch):
    as_of = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        us_market,
        "build_us_recommendations",
        lambda **kwargs: {
            "as_of": as_of,
            "universe_count": 2,
            "items": [
                {
                    "code": "NVDA",
                    "name": "NVIDIA",
                    "market": "NASDAQ",
                    "sector": "Technology",
                    "ai_trade_signal": {
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
                },
            ],
        },
    )

    payload = us_market.build_us_quant_signals(limit=20, recent_days=30)

    assert payload["status"] == "ready"
    assert payload["confirmed_count"] == 0
    assert payload["preliminary_count"] == 1
    assert payload["items"][0]["code"] == "NVDA"
    assert payload["items"][0]["currency"] == "USD"
    assert payload["items"][0]["current"]["position_open"] is False
    assert payload["items"][0]["current"]["model_exposure_percent"] == Decimal("0")


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

    rows = us_market._news("NVDA")

    assert rows == [{
        "title": "엔비디아, AI 투자 확대",
        "source": "한국경제",
        "url": "https://news.example/nvda",
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
    }]
    monkeypatch.setattr(us_market, "_naver_world_local_news_items", lambda *args, **kwargs: local_rows)
    monkeypatch.setattr(us_market, "_naver_news_items", lambda *args, **kwargs: pytest.fail("search fallback should not run"))

    assert us_market._news("NVDA") == local_rows


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
            {"title": "에코프로, 로봇 정조준", "source": "딜사이트", "url": "https://news.example/ecopro"},
            {"title": "ASML 장비 수요 확대", "source": "한국경제", "url": "https://news.example/asml"},
        ],
    )

    rows = us_market._news("ASML")

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
                }
                for index in range(10)
            ]
        if html == "에이에스엠엘":
            return [{
                "title": "에이에스엠엘, 차세대 노광장비 투자 확대",
                "source": "테스트뉴스",
                "url": "https://news.example/asml",
            }]
        return []

    monkeypatch.setattr(
        us_market,
        "resolve_us_stock",
        lambda symbol: {"code": "ASML", "name": "ASML Holding"},
    )
    monkeypatch.setattr(us_market.requests, "get", fake_get)
    monkeypatch.setattr(us_market, "_parse_naver_news_search_html", fake_parse)

    rows = us_market._naver_news_items("ASML", limit=10)

    assert [row["title"] for row in rows] == ["에이에스엠엘, 차세대 노광장비 투자 확대"]
    assert [call["query"] for call in calls] == ["ASML Holding", "에이에스엠엘", "ASML"]
    assert all(call["sort"] == "0" for call in calls)


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
