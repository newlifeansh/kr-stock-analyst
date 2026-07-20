from datetime import datetime
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
                "label": "위험자산",
                "percent": Decimal("18.0"),
                "direction": "호재",
                "confidence": Decimal("80.0"),
                "interpretation": "나스닥 상승은 위험자산 선호를 지지합니다.",
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
                "label": "채권",
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
    assert all(factor["direction"] in {"호재", "악재"} for factor in factors)
    assert all(factor["evidence"] for factor in factors)
    assert abs(sum(float(factor["percent"]) for factor in factors) - 100) <= 0.5


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

    payload = market_impact.build_market_impact()
    factors = payload["factors"]

    assert len(factors) == 5
    assert {factor["key"] for factor in factors} == {"rate", "dollar", "bond", "commodity", "risk"}
    assert all(factor["confidence"] == Decimal("20") for factor in factors)
    assert all(factor["evidence"][0]["source"] == "시스템" for factor in factors)
