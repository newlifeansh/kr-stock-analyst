from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.services import market_impact
from app.services.market_impact import SeriesPoint


def _sample_payload():
    return {
        "as_of": datetime(2026, 6, 25, 9, 0, 0),
        "market_status": "리스크 우위",
        "summary": "원자재 영향이 가장 크고, 현재는 리스크 관리가 더 우선입니다.",
        "good_weight": Decimal("37.5"),
        "bad_weight": Decimal("62.5"),
        "factors": [
            {
                "key": "commodity",
                "label": "원자재",
                "percent": Decimal("37.5"),
                "direction": "악재",
                "confidence": Decimal("82.0"),
                "interpretation": "원유 가격 상승은 물가와 비용 부담을 키웁니다.",
                "evidence": [
                    {
                        "source": "FRED",
                        "metric": "WTI 원유",
                        "value_text": "82.00$",
                        "change_1d_text": "+1.00%",
                        "change_5d_text": "+4.00%",
                        "as_of": "2026-06-24",
                        "url": "https://fred.stlouisfed.org/series/DCOILWTICO",
                    }
                ],
                "affected_sectors": ["정유", "화학"],
                "leader_stocks": ["S-Oil", "LG화학"],
            },
            {
                "key": "rate",
                "label": "금리",
                "percent": Decimal("25.0"),
                "direction": "악재",
                "confidence": Decimal("80.0"),
                "interpretation": "금리 상승은 성장주 밸류에이션 부담입니다.",
                "evidence": [],
                "affected_sectors": ["인터넷"],
                "leader_stocks": ["NAVER"],
            },
            {
                "key": "risk",
                "label": "투자심리",
                "percent": Decimal("18.0"),
                "direction": "호재",
                "confidence": Decimal("80.0"),
                "interpretation": "나스닥 상승은 투자심리를 지지합니다.",
                "evidence": [],
                "affected_sectors": ["반도체"],
                "leader_stocks": ["SK하이닉스"],
            },
            {
                "key": "dollar",
                "label": "달러",
                "percent": Decimal("12.0"),
                "direction": "악재",
                "confidence": Decimal("75.0"),
                "interpretation": "원화 약세는 외국인 수급 부담입니다.",
                "evidence": [],
                "affected_sectors": ["자동차"],
                "leader_stocks": ["현대차"],
            },
            {
                "key": "bond",
                "label": "채권금리",
                "percent": Decimal("7.5"),
                "direction": "호재",
                "confidence": Decimal("75.0"),
                "interpretation": "채권금리 안정은 주식 상대 매력을 높입니다.",
                "evidence": [],
                "affected_sectors": ["금융"],
                "leader_stocks": ["KB금융"],
            },
        ],
    }


def test_market_impact_model_has_five_official_factor_axes(monkeypatch):
    samples = {
        "DGS10": [4.40, 4.44, 4.48, 4.51, 4.56, 4.62],
        "DFII10": [2.00, 2.02, 2.04, 2.06, 2.07, 2.08],
        "DEXKOUS": [1370, 1375, 1380, 1382, 1384, 1388],
        "DTWEXBGS": [124, 124.5, 124.8, 125.0, 125.3, 125.7],
        "T10Y2Y": [-0.44, -0.43, -0.42, -0.41, -0.40, -0.38],
        "VIXCLS": [17.1, 17.4, 17.0, 17.9, 18.3, 19.0],
        "DCOILWTICO": [78, 79, 80, 81, 82, 83],
        "PCOPPUSDM": [9300, 9310, 9280, 9260, 9240, 9230],
        "NASDAQCOM": [18000, 18100, 18040, 17920, 17800, 17720],
        "CBBTCUSD": [104000, 103000, 102500, 101000, 100500, 99000],
    }

    def fake_fetch(series_id, *, limit=260):
        return [
            SeriesPoint(date=f"2026-06-{19 + index:02d}", value=value)
            for index, value in enumerate(samples[series_id])
        ]

    monkeypatch.setattr(market_impact, "_fetch_fred_series", fake_fetch)

    payload = market_impact.build_market_impact()
    factors = payload["factors"]

    assert {factor["key"] for factor in factors} == {"rate", "dollar", "bond", "commodity", "risk"}
    assert len(factors) == 5
    labels = {factor["key"]: factor["label"] for factor in factors}
    assert labels["bond"] == "채권금리"
    assert labels["risk"] == "투자심리"
    risk = next(factor for factor in factors if factor["key"] == "risk")
    assert risk["interpretation"] == (
        "미국 기술주와 가상자산은 약세이고, 시장 불안 지표는 높아 투자심리가 위축된 상태입니다."
    )
    assert any(item["metric"] == "미국 증시 불안지수(VIX)" for item in risk["evidence"])
    assert all(factor["direction"] in {"호재", "악재", "혼조", "자료 부족"} for factor in factors)
    assert all(factor["evidence"] for factor in factors)
    assert abs(sum(float(factor["percent"]) for factor in factors) - 100) <= 0.5
    assert abs(
        float(payload["good_weight"])
        + float(payload["bad_weight"])
        + float(payload["neutral_weight"])
        - 100
    ) <= 0.1


def test_market_impact_endpoint_returns_cached_shape(monkeypatch):
    monkeypatch.setattr("app.main.build_market_impact", _sample_payload)

    client = TestClient(app)
    response = client.get("/market/impact?refresh=true")

    assert response.status_code == 200
    body = response.json()
    assert body["market_status"] == "리스크 우위"
    assert len(body["factors"]) == 5
    assert body["factors"][0]["key"] == "commodity"


def test_market_impact_uses_low_confidence_fallback_when_source_fails(monkeypatch):
    def failing_fetch(series_id, *, limit=260):
        raise RuntimeError(f"{series_id} unavailable")

    monkeypatch.setattr(market_impact, "_fetch_fred_series", failing_fetch)
    monkeypatch.setattr(market_impact, "_fetch_yahoo_series", failing_fetch)

    payload = market_impact.build_market_impact()
    factors = payload["factors"]

    assert len(factors) == 5
    assert {factor["key"] for factor in factors} == {"rate", "dollar", "bond", "commodity", "risk"}
    assert all(factor["confidence"] == Decimal("20") for factor in factors)
    assert all(factor["direction"] == "자료 부족" for factor in factors)
    assert all(factor["data_quality"] == "자료 부족" for factor in factors)
    assert payload["market_status"] == "자료 부족"


def test_market_impact_uses_yahoo_when_fred_times_out(monkeypatch):
    samples = {
        "^TNX": [4.40, 4.44, 4.48, 4.51, 4.56, 4.62],
        "USDKRW=X": [1370, 1375, 1380, 1382, 1384, 1388],
        "DX-Y.NYB": [124, 124.5, 124.8, 125.0, 125.3, 125.7],
        "^VIX": [17.1, 17.4, 17.0, 17.9, 18.3, 19.0],
        "CL=F": [78, 79, 80, 81, 82, 83],
        "HG=F": [9.3, 9.31, 9.28, 9.26, 9.24, 9.23],
        "^IXIC": [18000, 18100, 18040, 17920, 17800, 17720],
        "BTC-USD": [104000, 103000, 102500, 101000, 100500, 99000],
    }

    def failing_fred(series_id, *, limit=260):
        raise RuntimeError(f"{series_id} unavailable")

    def fake_yahoo(symbol, *, limit=260):
        return [
            SeriesPoint(date=f"2026-06-{19 + index:02d}", value=value)
            for index, value in enumerate(samples[symbol])
        ]

    monkeypatch.setattr(market_impact, "_fetch_fred_series", failing_fred)
    monkeypatch.setattr(market_impact, "_fetch_yahoo_series", fake_yahoo)

    payload = market_impact.build_market_impact()
    factors = payload["factors"]

    assert len(factors) == 5
    assert any(item["evidence"][0]["source"] == "Yahoo Finance" for item in factors if item["evidence"])
    assert all(factor["data_quality"] in {"확인", "주의", "자료 부족"} for factor in factors)


def test_investor_sentiment_marks_nasdaq_up_and_bitcoin_down_as_mixed(monkeypatch):
    samples = {
        "NASDAQCOM": [100, 100, 100, 100, 100, 102],
        "CBBTCUSD": [100, 100, 100, 100, 100, 98],
        "VIXCLS": [20, 20, 20, 20, 20, 20],
    }
    latest_date = datetime.now(market_impact.KST).date()
    dates = [
        (latest_date - timedelta(days=5 - index)).isoformat()
        for index in range(6)
    ]

    def fake_fetch(series_id, *, limit=260):
        return [SeriesPoint(date=day, value=value) for day, value in zip(dates, samples[series_id])]

    monkeypatch.setattr(market_impact, "_fetch_fred_series", fake_fetch)

    factor = market_impact._build_risk_factor()

    assert factor["direction"] == "혼조"
    assert "나스닥은 강세지만 비트코인은 약세" in factor["interpretation"]
    assert factor["data_quality"] == "확인"


def test_monthly_copper_is_not_presented_as_daily_or_five_day_change(monkeypatch):
    monthly = ["2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31"]

    monkeypatch.setattr(
        market_impact,
        "_fetch_fred_series",
        lambda series_id, *, limit=260: [
            SeriesPoint(date=day, value=9300 + index)
            for index, day in enumerate(monthly)
        ],
    )

    evidence, points = market_impact._series_snapshot("PCOPPUSDM", "구리 월간 가격")

    assert points and evidence
    assert evidence["change_1d"] is None
    assert evidence["change_5d"] is None
    assert evidence["data_quality"] == "주의"
    assert "주기" in evidence["quality_note"]
