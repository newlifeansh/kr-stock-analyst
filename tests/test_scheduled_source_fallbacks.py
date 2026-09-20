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


def _price_runtime(monkeypatch):
    from app.services import briefing

    runtime = object.__new__(briefing.BriefingRuntime)
    runtime.settings = SimpleNamespace(price_max_workers=1, price_days_back=30)
    runtime.last_post_close_price_repair_date = date(2026, 9, 18)
    monkeypatch.setattr(runtime, '_repair_signal_price_ohlc', lambda *a, **k: 0)
    monkeypatch.setattr(runtime, '_post_close_price_repair_due', lambda *a: False)
    monkeypatch.setattr(runtime, '_recent_price_codes', lambda *a: [])
    monkeypatch.setattr(briefing, 'collect_market_prices', lambda *a, **k: 0)
    return briefing, runtime


@pytest.mark.qa_gate
def test_html_price_fallback_retries_market_cap_backfill(monkeypatch):
    """DATA-KRX-NAVER-002: HTML recovery must still call market-cap backfill."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    briefing, runtime = _price_runtime(monkeypatch)
    calls = []
    coverage = iter([
        {'total': 100, 'fresh': 0, 'coverage_ratio': 0.0},
        {'total': 100, 'fresh': 100, 'coverage_ratio': 1.0},
    ])
    monkeypatch.setattr(runtime, '_latest_price_coverage', lambda *a: next(coverage))
    monkeypatch.setattr(briefing, 'collect_naver_realtime_market_caps',
                        lambda *a, **k: calls.append(a[1]) or 0)
    monkeypatch.setattr(briefing, 'collect_naver_quotes', lambda *a, **k: 100)
    result = runtime._collect_prices(None, datetime(2026, 9, 18, 14, tzinfo=ZoneInfo('Asia/Seoul')))
    assert result['source'] == 'naver_html_quotes'
    assert calls == ['20260918', '20260918'], 'HTML recovery skipped its market-cap backfill'


@pytest.mark.qa_gate
@pytest.mark.parametrize('ratio,expected_source', [(0.94, 'degraded'), (0.95, 'naver_realtime_market_caps+naver_krx_chart')])
def test_completed_session_fallback_rechecks_coverage(monkeypatch, ratio, expected_source):
    """DATA-KRX-NAVER-002: nonzero repair counts alone do not establish readiness."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    briefing, runtime = _price_runtime(monkeypatch)
    coverage_calls = []
    def coverage(*args):
        coverage_calls.append(args)
        value = 0.0 if len(coverage_calls) == 1 else ratio
        return {'total': 100, 'fresh': int(value * 100), 'coverage_ratio': value}
    monkeypatch.setattr(runtime, '_latest_price_coverage', coverage)
    monkeypatch.setattr(briefing, 'collect_naver_realtime_market_caps', lambda *a, **k: 0)
    monkeypatch.setattr(briefing, 'collect_naver_quotes', lambda *a, **k: 0)
    monkeypatch.setattr(runtime, '_repair_completed_session_from_naver', lambda *a: 95)
    result = runtime._collect_prices(None, datetime(2026, 9, 19, 12, tzinfo=ZoneInfo('Asia/Seoul')))
    assert result['source'] == expected_source
    assert result['rows_loaded'] == 95
    assert len(coverage_calls) >= 2


@pytest.mark.qa_gate
@pytest.mark.parametrize('item,fallback,expected', [
    ({'price': 100, 'volume': 3}, None, 300),
    ({}, {'price': 100, 'volume': 3}, 300),
    ({'price': 100, 'volume': 0}, None, 0),
    ({'trading_value': 0}, {'price': 100, 'volume': 3}, 0),
    ({'trading_value': 123}, {'price': 100, 'volume': 3}, 123),
    ({'price': 100}, None, None),
    ({'price': 'bad', 'volume': 3}, None, None),
])
def test_recommendation_trading_value_fallback_preserves_observed_values(item, fallback, expected):
    """SIG-CONTRACT-002: preserve real zero and missing-input uncertainty."""
    from app.services.recommendations import _ensure_trading_value

    _ensure_trading_value(item, fallback=fallback)
    assert item.get('trading_value') == expected
