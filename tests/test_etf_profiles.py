from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app
from app.services.etf_profiles import (
    _build_etf_profile_uncached,
    build_naver_etf_holdings_snapshot,
    is_likely_etf_name,
    korean_security_isin,
    parse_fnguide_etf_profile,
    parse_naver_etf_holdings,
    parse_naver_etf_distribution_history,
    parse_naver_etf_dividend_summary,
    parse_tiger_distribution_history,
    validate_etf_holdings_snapshot,
)


def test_etf_name_detection_and_korean_isin_check_digit():
    assert is_likely_etf_name("TIGER 200") is True
    assert is_likely_etf_name("KODEX 미국S&P500") is True
    assert is_likely_etf_name("삼성전자") is False
    assert korean_security_isin("102110") == "KR7102110004"
    assert korean_security_isin("069500") == "KR7069500007"


def test_every_current_domestic_etf_brand_is_detected_without_false_stock_prefixes():
    brands = (
        "1Q",
        "ACE",
        "BNK",
        "DAISHIN",
        "DS",
        "FOCUS",
        "HANARO",
        "HK",
        "IBK",
        "KCGI",
        "KIWOOM",
        "KoAct",
        "KODEX",
        "MIDAS",
        "PLUS",
        "RISE",
        "SOL",
        "TIGER",
        "TIME",
        "TREX",
        "TRUSTON",
        "UNICORN",
        "WON",
        "더제이",
        "마이티",
        "아이엠에셋",
        "에셋플러스",
        "파워",
    )

    assert all(is_likely_etf_name(f"{brand} 대표 ETF") for brand in brands)
    assert is_likely_etf_name("DS단석") is False
    assert is_likely_etf_name("IBK기업은행") is False


def test_naver_query_resolver_prefers_exact_etf_name(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "items": [
                    {
                        "code": "139260",
                        "name": "TIGER 200 IT",
                        "nationCode": "KOR",
                    },
                    {
                        "code": "102110",
                        "name": "TIGER 200",
                        "nationCode": "KOR",
                    },
                ]
            }

    monkeypatch.setattr(main_module.requests, "get", lambda *args, **kwargs: Response())

    assert main_module._fetch_naver_stock_code_by_query("TIGER 200") == "102110"


def test_six_character_etf_name_still_uses_name_search(monkeypatch):
    class EmptyDb:
        def get(self, *_args):
            return None

        def scalar(self, *_args):
            return None

        def scalars(self, *_args):
            return []

    attempts = []

    def ensure_after_search(_db, code):
        attempts.append(code)
        if code == "105190":
            return main_module.StockMaster(
                code="105190",
                name="ACE 200",
                market="KOSPI",
                is_active=True,
            )
        return None

    monkeypatch.setattr(main_module, "_ensure_stock_master_from_naver", ensure_after_search)
    monkeypatch.setattr(
        main_module,
        "_fetch_naver_stock_code_by_query",
        lambda query: "105190" if query == "ACE 200" else None,
    )
    monkeypatch.setattr(
        main_module.api_cache,
        "get_or_set",
        lambda _key, _ttl, factory: factory(),
    )

    item = main_module.resolve_stock(
        query="ACE 200",
        response=main_module.Response(),
        db=EmptyDb(),
    )

    assert attempts == ["ACE200", "105190"]
    assert item.code == "105190"
    assert item.name == "ACE 200"


def test_naver_identity_supports_new_alphanumeric_etf_codes(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"itemCode": "0080G0", "itemName": "KODEX 방산TOP10"}

    monkeypatch.setattr(main_module.requests, "get", lambda *args, **kwargs: Response())

    assert main_module._fetch_naver_stock_identity("0080G0") == {
        "code": "0080G0",
        "name": "KODEX 방산TOP10",
        "market": "KOSPI",
    }


def test_fnguide_etf_profile_parser_keeps_top_ten_by_weight():
    rows = [
        {
            "TRD_DT": "2026-08-21",
            "AGMT_STK_CNT": index * 10,
            "STK_NM_KOR": f"구성자산 {index}",
            "ETF_WEIGHT": index,
        }
        for index in range(1, 12)
    ]
    html = f"""
    <script>
      var summary_data = {{"CMP_KOR":"TIGER 200","CMP_CD":"102110","BASE_IDX_NM_KOR":"코스피 200","ISSUE_NM_KOR":"미래에셋자산운용(주)","ETF_TYP_SVC_NM":"국내주식형, 대표지수","TOT_PAY":"0.050","CMP_TYP":"5"}};
      var product_summary_data = {{"BASE_IDX_NM_KOR":"코스피 200","TOT_PAY":"0.050","DIV_BASE_DT":"매 1, 4, 7, 10월의 마지막 영업일","ISSUE_NM_KOR":"미래에셋자산운용(주)"}};
      var CU_data = {{"grid_data":{rows!r}}};
    </script>
    """.replace("'", '"')

    payload = parse_fnguide_etf_profile(html)

    assert payload["is_etf"] is True
    assert payload["as_of"].isoformat() == "2026-08-21"
    assert payload["benchmark"] == "코스피 200"
    assert payload["total_fee"] == Decimal("0.050")
    assert len(payload["holdings"]) == 10
    assert payload["holdings"][0]["name"] == "구성자산 11"
    assert payload["holdings"][0]["weight"] == Decimal("11")


def test_tiger_distribution_history_parser_orders_latest_first():
    html = """
    <tr data-tot-cnt="2"><td>2025-10-31</td><td>2025-11-04</td><td>145</td><td>131</td></tr>
    <tr data-tot-cnt="2"><td>2026-07-31</td><td>2026-08-04</td><td>133</td><td>125</td></tr>
    """

    items = parse_tiger_distribution_history(html)

    assert [item["record_date"].isoformat() for item in items] == [
        "2026-07-31",
        "2025-10-31",
    ]
    assert items[0]["payment_date"].isoformat() == "2026-08-04"
    assert items[0]["amount_per_share"] == Decimal("133")
    assert items[0]["date_type"] == "record_date"


def test_naver_etf_dividend_parsers_keep_ttm_and_ex_dividend_history():
    summary = parse_naver_etf_dividend_summary(
        {
            "itemCode": "069500",
            "referenceDate": "2026-08-21",
            "dividendYieldTtm": "0.77",
            "dividendPerShareTtm": "849",
        }
    )
    history = parse_naver_etf_distribution_history(
        [
            {
                "id": {"itemCode": "069500", "exDividendAt": "2026-07-30"},
                "dividendAmount": "183",
                "dividendYield": "0.17",
            },
            {
                "id": {"itemCode": "069500", "exDividendAt": "2026-04-29"},
                "dividendAmount": "446",
                "dividendYield": "0.47",
            },
        ]
    )

    assert summary["reference_date"].isoformat() == "2026-08-21"
    assert summary["trailing_distribution_yield"] == Decimal("0.77")
    assert summary["trailing_distribution_amount"] == Decimal("849")
    assert [item["record_date"].isoformat() for item in history] == [
        "2026-07-30",
        "2026-04-29",
    ]
    assert history[0]["payment_date"] is None
    assert history[0]["date_type"] == "ex_dividend_date"


def test_naver_etf_holdings_parser_fills_foreign_top_ten():
    rows = [
        {
            "componentName": f"미국 종목 {index}",
            "componentItemCode": None,
            "componentReutersCode": f"US{index}.O",
            "cuUnitQuantity": f"{index}.25",
            "weight": str(index),
            "referenceDate": "2026-08-24",
        }
        for index in range(1, 12)
    ]

    payload = parse_naver_etf_holdings(rows)

    assert payload["as_of"].isoformat() == "2026-08-24"
    assert len(payload["holdings"]) == 10
    assert payload["holdings"][0] == {
        "name": "미국 종목 11",
        "code": "US11.O",
        "weight": Decimal("11"),
        "shares": Decimal("11.25"),
    }


def test_non_tiger_etf_profile_uses_shared_distribution_history():
    fnguide_html = """
    <script>
      var summary_data = {"CMP_KOR":"KODEX 200","CMP_CD":"069500","CMP_TYP":"5"};
      var product_summary_data = {"DIV_BASE_DT":"매 1, 4, 7, 10월의 마지막 영업일"};
      var CU_data = {"grid_data":[{"TRD_DT":"2026-08-21","STK_NM_KOR":"삼성전자","ETF_WEIGHT":"30.0"}]};
    </script>
    """

    class Response:
        def __init__(self, *, text="", payload=None):
            self.text = text
            self._payload = payload
            self.encoding = None

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **_kwargs):
        if "wisereport" in url:
            return Response(text=fnguide_html)
        if url.endswith("/ETFComponent"):
            return Response(
                payload=[
                    {
                        "componentName": "삼성전자",
                        "componentItemCode": "005930",
                        "cuUnitQuantity": "100",
                        "weight": "31.5",
                        "referenceDate": "2026-08-24",
                    }
                ]
            )
        if url.endswith("/ETFDividend"):
            return Response(
                payload={
                    "itemCode": "069500",
                    "referenceDate": "2026-08-21",
                    "dividendYieldTtm": "0.77",
                    "dividendPerShareTtm": "849",
                }
            )
        if url.endswith("/ETFDividendHist"):
            return Response(
                payload=[
                    {
                        "id": {"itemCode": "069500", "exDividendAt": "2026-07-30"},
                        "dividendAmount": "183",
                    }
                ]
            )
        raise AssertionError(f"unexpected URL: {url}")

    payload = _build_etf_profile_uncached(
        "069500",
        "KODEX 200",
        "KR7069500007",
        get=fake_get,
    )

    assert payload["is_etf"] is True
    assert payload["trailing_distribution_amount"] == Decimal("849")
    assert payload["distributions"][0]["date_type"] == "ex_dividend_date"
    assert payload["distribution_source_label"] == "네이버페이 증권 ETF"
    assert payload["as_of"].isoformat() == "2026-08-24"
    assert payload["holdings"][0]["weight"] == Decimal("31.5")
    assert payload["source_label"] == "네이버페이 증권 ETF"


def test_full_etf_holdings_snapshot_detects_component_changes():
    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, **_kwargs):
        if url.endswith("/etfs/v2/domestic"):
            return Response(
                {
                    "hasNext": False,
                    "items": [
                        {"itemCode": "133690", "itemName": "TIGER 미국나스닥100"},
                        {"itemCode": "069500", "itemName": "KODEX 200"},
                    ],
                }
            )
        code = url.split("/detail/", 1)[1].split("/", 1)[0]
        name = "엔비디아" if code == "133690" else "삼성전자"
        return Response(
            [
                {
                    "componentName": name,
                    "componentItemCode": "005930" if code == "069500" else None,
                    "componentReutersCode": "NVDA.O" if code == "133690" else None,
                    "cuUnitQuantity": "100",
                    "weight": "10",
                    "referenceDate": "2026-08-24",
                }
            ]
        )

    previous = {
        "items": {
            "133690": {
                "code": "133690",
                "name": "TIGER 미국나스닥100",
                "holdings": [{"name": "애플", "code": "AAPL.O", "weight": "10"}],
            }
        }
    }
    payload = build_naver_etf_holdings_snapshot(
        previous,
        get=fake_get,
        max_workers=2,
        now=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )

    assert payload["total_count"] == 2
    assert payload["fresh_count"] == 2
    assert payload["changed_codes"] == ["133690"]
    assert payload["added_codes"] == ["069500"]
    assert payload["items"]["133690"]["holdings"][0]["name"] == "엔비디아"
    assert validate_etf_holdings_snapshot(payload) is payload


def test_full_etf_holdings_snapshot_keeps_last_complete_item_on_empty_refresh():
    class Response:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, **_kwargs):
        if url.endswith("/etfs/v2/domestic"):
            return Response(
                {
                    "hasNext": False,
                    "items": [
                        {"itemCode": "133690", "itemName": "TIGER 미국나스닥100"},
                    ],
                }
            )
        return Response([])

    previous_item = {
        "code": "133690",
        "name": "TIGER 미국나스닥100",
        "as_of": "2026-08-24",
        "holdings": [{"name": "엔비디아", "code": "NVDA.O", "weight": "8.43"}],
        "stale": False,
    }
    payload = build_naver_etf_holdings_snapshot(
        {"items": {"133690": previous_item}},
        get=fake_get,
        max_workers=1,
    )

    assert payload["fresh_count"] == 0
    assert payload["loaded_count"] == 1
    assert payload["failed_codes"] == ["133690"]
    assert payload["items"]["133690"]["holdings"] == previous_item["holdings"]
    assert payload["items"]["133690"]["stale"] is True


def test_etf_holdings_refresh_is_due_at_midnight_and_noon_kst():
    class Complete:
        def __init__(self, captured_at):
            self.captured_at = captured_at

    before_noon_utc = datetime(2026, 8, 25, 2, 59)
    after_noon_utc = datetime(2026, 8, 25, 3, 1)
    noon_kst = datetime(2026, 8, 25, 12, 0, tzinfo=main_module.KST)
    next_midnight_kst = datetime(2026, 8, 26, 0, 0, tzinfo=main_module.KST)

    assert main_module._etf_holdings_snapshot_due(Complete(before_noon_utc), noon_kst)
    assert not main_module._etf_holdings_snapshot_due(Complete(after_noon_utc), noon_kst)
    assert main_module._etf_holdings_snapshot_due(
        Complete(after_noon_utc),
        next_midnight_kst,
    )


def test_etf_profile_endpoint_and_stock_home_shell(monkeypatch):
    monkeypatch.setattr(main_module, "get_complete_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main_module,
        "request_complete_snapshot_refresh",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.main.build_etf_profile",
        lambda code, name, isin, **_kwargs: {
            "code": code,
            "name": name,
            "is_etf": False,
            "holdings": [],
            "distributions": [],
            "source_label": "FnGuide ETF",
            "source_url": None,
        },
    )
    client = TestClient(app)
    response = client.get("/stocks/005930/etf-profile")

    assert response.status_code == 200
    assert response.json()["code"] == "005930"
    assert response.json()["is_etf"] is False
    assert "max-age=900" in response.headers["cache-control"]

    shell = client.get("/dashboard/TIGER%20200")
    assert shell.status_code == 200
    for expected in (
        'id="stock-company-tab"',
        'id="stock-etf-holdings-section"',
        "보유 비중 Top10",
        'id="stock-etf-dividend-section"',
        "배당 소식",
        'id="stock-etf-dividend-page"',
        "지난 분배금 보기",
        "분배 내역",
        "분배금 기준일",
    ):
        assert expected in shell.text

    source = client.get("/assets/dashboard/app.js").text
    assert "function currentStockIsEtf()" in source
    assert "elements.stockCompanyTab.disabled = etf;" in source
    assert 'requestedTab === "company" && currentStockIsEtf()' in source
    assert "/etf-profile" in source


def test_etf_profile_endpoint_uses_the_persisted_universe_item(monkeypatch):
    stock = main_module.StockMaster(
        code="133690",
        name="TIGER 미국나스닥100",
        market="KOSPI",
        is_active=True,
    )
    snapshot_item = {
        "code": "133690",
        "name": stock.name,
        "as_of": "2026-08-24",
        "holdings": [{"name": "엔비디아", "code": "NVDA.O", "weight": "8.43"}],
    }
    complete = SimpleNamespace(
        payload={"items": {stock.code: snapshot_item}},
        captured_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    received = {}

    class Db:
        def get(self, _model, code):
            return stock if code == stock.code else None

    def fake_profile(code, name, isin, *, holdings_snapshot=None):
        received["holdings_snapshot"] = holdings_snapshot
        return {
            "code": code,
            "name": name,
            "is_etf": True,
            "holdings": holdings_snapshot["holdings"],
            "distributions": [],
            "source_label": "네이버페이 증권 ETF",
            "source_url": None,
        }

    monkeypatch.setattr(main_module, "get_complete_snapshot", lambda *_args, **_kwargs: complete)
    monkeypatch.setattr(main_module, "build_etf_profile", fake_profile)
    response = main_module.Response()

    payload = main_module.stock_etf_profile(stock.code, response, db=Db())

    assert received["holdings_snapshot"] == snapshot_item
    assert payload["holdings"][0]["name"] == "엔비디아"
    assert response.headers["X-ETF-Holdings-Source"] == "scheduled-snapshot"
