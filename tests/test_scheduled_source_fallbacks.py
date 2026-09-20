"""Regression evidence for DATA-KRX-NAVER-001/005."""
from datetime import date
from types import SimpleNamespace
import sys
import pandas as pd
import pytest
import requests
from app.collectors import krx, naver_flows


@pytest.mark.qa_gate
def test_kosdaq_global_normalized_before_filter(monkeypatch):
    frame = pd.DataFrame([
        {"Code": "000001", "Name": "Global", "Market": "KOSDAQ GLOBAL"},
        {"Code": "000002", "Name": "Segment", "Market": "KOSDAQ GLOBAL SEGMENT"},
        {"Code": "000003", "Name": "Regular", "Market": "KOSDAQ"},
        {"Code": "000004", "Name": "Other", "Market": "KOSPI"},
    ])
    monkeypatch.setitem(sys.modules, "FinanceDataReader", SimpleNamespace(StockListing=lambda market: frame))
    rows = krx._stock_rows_from_fdr(["KOSDAQ"], date(2026, 9, 15))
    assert [row["code"] for row in rows] == ["000001", "000002", "000003"]
    assert all(row["market"] == "KOSDAQ" and row["is_active"] for row in rows)
    assert frame.iloc[0]["Market"] == "KOSDAQ GLOBAL"


@pytest.mark.qa_gate
@pytest.mark.parametrize("failure", [None, requests.Timeout("fixture timeout"), ValueError("fixture JSON")])
def test_trend_failure_or_empty_falls_back_to_html(monkeypatch, failure):
    def trend(*args):
        if failure is not None:
            raise failure
        return []
    calls = []
    html = '<table class="type2"><tr><th>기관</th><th>외국인</th></tr><tr><td>2026.09.15</td><td>100</td><td>0</td><td>0%</td><td>1000</td><td>+20</td><td>-10</td><td>100</td><td>1%</td></tr></table>'
    def get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        return SimpleNamespace(text=html, raise_for_status=lambda: None)
    monkeypatch.setattr(naver_flows, "_fetch_trend_rows_for_code", trend)
    monkeypatch.setattr(naver_flows.requests, "get", get)
    rows = naver_flows._fetch_rows_for_code("005930", 1)
    assert calls == [(naver_flows.NAVER_FLOW_URL, {"code": "005930", "page": 1})]
    assert [(row["investor_type"], row["net_buy_value"]) for row in rows] == [("기관합계", 2000), ("외국인", -1000)]
    assert all(row["trade_date"] == date(2026, 9, 15) for row in rows)
