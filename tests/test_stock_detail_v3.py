from decimal import Decimal

from fastapi.testclient import TestClient

from app.main import app
from app.services.company_profiles import _short_company_summary
from app.services import stock_dashboard


def test_stock_detail_v3_shell_and_controls():
    client = TestClient(app)

    shell = client.get("/dashboard/SK하이닉스")
    assert shell.status_code == 200
    for expected in (
        'class="stock-detail-v3"',
        ">종목홈</button>",
        ">AI 매매신호</button>",
        'id="stock-financial-chart"',
        'id="stock-flow-history-chart"',
        'id="stock-report-history-chart"',
        'id="stock-news-temperature-chart"',
        'class="stock-v3-section stock-v3-chart-section stock-v3-news-temperature-section"',
        'id="quant-signal-chart"',
        'id="quant-current-label"',
        'id="quant-signal-refresh"',
        "최근 1년 AI 매매신호",
        "모든 매매내역 보기",
        'class="ollama-ai-badge stock-home-ai-status"',
        "20260725v53",
    ):
        assert expected in shell.text
    assert "1,000만원 모의 운용" not in shell.text
    assert "네이버 종토방과 Threads에서 종목 반응을 함께 확인합니다." not in shell.text

    source = client.get("/assets/dashboard/app.js").text
    assert 'state.stockPricePeriod = button.dataset.pricePeriod || "1D"' in source
    assert 'state.stockFinancialMetric = button.dataset.financialMetric || "revenue"' in source
    assert 'state.stockFlowMode = button.dataset.flowMode || "cumulative"' in source
    assert "renderStockIntradayChart" in source
    assert 'marketOpen ? liveUrl(endpoint) : endpoint' in source
    assert "한국투자증권 장마감 확정 분봉" in source
    assert "renderStockReportHistoryChart" in source
    assert "const height = 178;" in source
    assert 'y="170"' in source
    assert "renderQuantSignalChart" in source
    assert "/quant-signals" in source
    assert "quantSignalMarkers" in source
    assert "ensureStockAIAnalysis();" in source
    assert 'elements.stockSummaryAIBadge.textContent = `${generationLabel} 분석 완료`;' in source
    assert 'badge.textContent = "Ollama AI 분석 중";' in source
    assert 'badge.textContent = "AI 분석 확인 실패";' in source
    assert 'headline: "매도 완료"' in source
    assert "AI 전략 기준 현재 상태" not in shell.text
    assert "AI 모의 전략 ·" not in source
    assert 'id="quant-current-score"' not in shell.text
    assert "원에 모두 팔았어요" not in source
    assert "AI 전략의 모의 매매 결과이며 실제 계좌 주문이 아닙니다." in source
    assert "오늘의 대응" not in shell.text
    assert "판단 근거와 위험 보기" not in shell.text

    styles = client.get("/assets/dashboard/styles.css").text
    assert "aspect-ratio: 19 / 8" in styles
    assert "/* iPhone 16 Pro (402 CSS px)" in styles
    assert "@media (max-width: 430px)" in styles
    assert '"Apple SD Gothic Neo"' in styles
    assert "--stock-v3-type-display: 38px" in styles
    assert "--stock-v3-type-tab: 16px" in styles
    assert ".stock-v3-news-temperature-section .stock-v3-main-chart" in styles
    assert ".stock-v3-news-temperature-section .stock-v3-temperature-gauge" in styles
    assert "min-height: 74px;" in styles


def test_short_company_summary_corrects_korean_topic_particle():
    assert _short_company_summary(
        "신라젠는 항암 신약개발을 목적으로 설립된 기업입니다.",
        "신라젠",
    ) == "신라젠은 항암 신약개발을 목적으로 설립된 기업입니다."
    assert _short_company_summary(
        "기아은 자동차를 제조하는 기업입니다.",
        "기아",
    ) == "기아는 자동차를 제조하는 기업입니다."


def test_naver_snapshot_preserves_annual_and_quarterly_series(monkeypatch):
    html = """
    <html><body>
      <table class="tb_type1 tb_num tb_type1_ifrs">
        <thead>
          <tr><th>주요재무정보</th><th colspan="2">최근 연간 실적</th><th colspan="1">최근 분기 실적</th></tr>
        </thead>
        <tbody>
          <tr><th>2024.12</th><th>2025.12 (E)</th><th>2026.03</th></tr>
          <tr><th>매출액</th><td>100,000</td><td>120,000</td><td>35,000</td></tr>
          <tr><th>영업이익</th><td>20,000</td><td>28,000</td><td>9,000</td></tr>
          <tr><th>당기순이익</th><td>15,000</td><td>22,000</td><td>7,000</td></tr>
          <tr><th>영업이익률</th><td>20.0</td><td>23.3</td><td>25.7</td></tr>
          <tr><th>순이익률</th><td>15.0</td><td>18.3</td><td>20.0</td></tr>
          <tr><th>EPS(원)</th><td>1,500</td><td>2,200</td><td>700</td></tr>
        </tbody>
      </table>
    </body></html>
    """

    class Response:
        text = html
        encoding = "utf-8"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(stock_dashboard.requests, "get", lambda *args, **kwargs: Response())
    snapshot = stock_dashboard._fetch_naver_snapshot("000660")

    series = snapshot["financial_series"]
    assert len(series["annual"]) == 2
    assert len(series["quarterly"]) == 1
    assert series["annual"][1]["estimated"] is True
    assert series["annual"][0]["revenue"] == Decimal("100000")
    assert series["quarterly"][0]["operating_profit"] == Decimal("9000")
