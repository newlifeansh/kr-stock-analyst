from decimal import Decimal

from app.services import us_market


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

    monkeypatch.setattr(us_market, "_dashboard_cached", fake_dashboard)

    payload = us_market.build_us_rankings("surge", limit=100, market="ALL")
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
    monkeypatch.setattr(us_market, "_dashboard_cached", fake_dashboard)

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

    research = us_market._research_from_quote_summary(payload)

    assert research["report_count_90d"] == 2
    assert research["target_up_count"] == 1
    assert research["target_down_count"] == 1
    assert research["target_up_ratio"] == Decimal("61.7")
    assert research["latest_target_price"] == Decimal("314.42")
    assert research["latest_opinion"] == "매수"
    assert research["analyst_opinion_count"] == 42
