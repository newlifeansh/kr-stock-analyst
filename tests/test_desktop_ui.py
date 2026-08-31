from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import SessionLocal, init_db
from app.main import app
from app.models import DesktopUserPreference


client = TestClient(app)
STATIC_DIR = Path(__file__).resolve().parents[1] / "app" / "static"


def test_desktop_shell_is_isolated_and_not_cached():
    response = client.get("/desktop")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert "/assets/desktop/styles.css" in response.text
    assert "/assets/desktop/app.js" in response.text
    assert "/assets/desktop/styles.css?v=20260810h12" in response.text
    assert "/assets/desktop/app.js?v=20260829h4" in response.text
    assert "/assets/dashboard/styles.css" not in response.text
    assert "/dashboard-app-v170.js" not in response.text


def test_desktop_assets_expose_spreadsheet_shell_and_four_fixed_sheets():
    html = (STATIC_DIR / "desktop" / "index.html").read_text(encoding="utf-8")
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    for menu in ("파일", "수정", "보기", "삽입", "서식", "데이터", "도구", "확장 프로그램", "도움말"):
        assert f">{menu}</button>" in html
    for sheet_id, label in (("home", "홈"), ("search", "검색"), ("portfolio", "내 종목"), ("notifications", "알림")):
        assert f'id: "{sheet_id}", label: "{label}"' in script
    assert '{ id: "chart", label: "차트분석" }' not in script
    assert '{ id: "notifications", label: "알림", utility: true }' in script
    assert "desk-tab-utility" in script
    for portfolio_tab in ("관심종목", "핀 종목", "AI 전략", "종목 뉴스"):
        assert f'"{portfolio_tab}"' in script
    assert "portfolioSheetTab" in script
    assert 'section(root, "차트분석 · 5일·10일 전망"' in script
    assert 'state.details.set(code' in script
    assert 'history[options.replaceHistory ? "replaceState" : "pushState"]' in script
    assert 'renderNotifications(token)' in script
    assert '"이 PC에서 알림 받기"' in script
    assert '`/push/subscriptions/${encodeURIComponent(state.watchlistId)}`' in script
    assert "sendDesktopPushTest" in script
    assert "disableDesktopPush" in script
    assert 'navigator.serviceWorker.register(' in script
    assert '{ scope: "/desktop" }' in script
    assert "PUSH_LAST_SEEN" not in script
    assert "pushLastSeen" not in script
    assert 'options.href' in script
    assert 'target.pathname.match(/^\\/(?:dashboard|stocks)\\/([^/?#]+)/)' in script
    assert "decodeURIComponent(pathMatch[1])" in script
    assert '["watchlist", "portfolio"]' in script
    assert 'NOTIFICATION_VIEW_MAP.get(view) || "notifications"' in script
    assert 'morning_briefing: "돈이 되는 소식"' in script
    assert '{ id: "morning_briefing", label: "돈이 되는 소식", required: true }' in script
    assert 'if (view === "morning-briefing")' in script
    assert 'openUtilitySheet("briefing")' in script
    assert 'ariaLabel: item.url ? `${item.title} 열기`' in script
    assert 'event.key === "Enter" || event.key === " "' in script
    assert 'financialBarChart(quarterly' in script
    assert "financialSeriesAmount(point.revenue, financialUnit)" in script
    assert "financialPeriodLabel(point.period, point.estimated)" in script
    assert "shortMoney(point.revenue)" not in script
    assert '`분기 실적 · 단위: ${financialUnit}`' in script
    assert 'marginLineChart(quarterly)' in script
    assert "sectorMarginLineChart" in script
    assert "동종 업계 영업이익률" in script
    assert "/sector-operating-margins?limit=5" in script
    assert "판관비 심층분석" in script
    for detail_tab in ("종목홈", "기업분석", "AI 시그널"):
        assert f'\"{detail_tab}\"' in script
    assert '`/stocks/${code}/quant-signals`' in script
    assert "AI 지금 이렇게 판단해요" in script
    assert "최근 1년 AI 시그널" in script
    assert "목표 매도가" in script
    assert "turnover_percent" in script
    assert "execution_count" in script
    assert "/sga-analysis" in script
    assert "sgaDetailText" in script
    assert 'section(root, "커뮤니티"' in script
    assert 'id="desk-document-title"' in html
    assert 'id="desk-save-state"' in html
    assert "readonly" not in html
    assert 'fetch("/desktop/session"' in script
    assert 'fetch("/desktop/preferences"' in script
    assert "saveDocumentTitle" in script
    assert "DOCUMENT_TITLE_KEY_PREFIX" in script
    assert "DOCUMENT_TITLE_PENDING_PREFIX" in script
    assert "persistDocumentTitlePending" in script
    assert 'class="desk-share"' in html
    assert 'id="desk-side-panel"' in html
    assert 'id="desk-side-toggle"' in html
    for side_app in ("캘린더", "메모", "할 일 목록", "주소록", "지도", "부가기능 추가"):
        assert f'title="{side_app}"' in html
    assert "SIDE_PANEL_COLLAPSED_KEY" in script
    assert "setSidePanelCollapsed" in script
    assert "computeDesktopChartAnalysis" in script
    assert "desktopForecastChartSvg" in script
    assert "실제 가격, 5일선, 10일선과 5일·10일 예상 범위" in script
    assert "5일·10일 전망 비교" in script
    assert 'api(`/stocks/${encodeURIComponent(stock.code)}/prices?limit=260`)' in script
    assert "connectLiveQuoteStream" in script
    assert "registerLiveQuote" in script
    assert '`${protocol}//${location.host}/ws/quotes`' in script
    assert "/stocks/quotes?codes=" in script
    assert "/ws/stocks/" not in script
    assert "rebasePeriodReturn" in script
    assert "animateLiveCellValue" in script
    assert "startedAt = performance.now(), duration = 620" in script
    assert 'node.dataset.liveCode = String(code)' in script
    assert 'startHomeMarketRefresh()' in script
    assert 'resetLiveUpdates(); state.active = id' in script
    assert "desk-live-updated-up" in (STATIC_DIR / "desktop" / "styles.css").read_text(encoding="utf-8")
    assert "desk-sector-chart" in (STATIC_DIR / "desktop" / "styles.css").read_text(encoding="utf-8")
    assert "chartTooltipEvents" in script
    assert "chartPointAttributes" in script
    assert 'role=\"img\" aria-label=' in script
    assert "data-chart-tooltip" in script
    assert "desk-chart-hit" in script
    assert "desk-chart-tooltip" in (STATIC_DIR / "desktop" / "styles.css").read_text(encoding="utf-8")
    assert "function loadDesktopMarketSignals30d()" in script
    assert 'const path = "/market/quant-signals?universe_limit=150&limit=0&recent_days=30";' in script
    assert '/market/quant-signals?limit=20' not in script
    assert 'AI 시그널 · 최근 30일 전체 ${marketSignals.length}개' in script
    for signal_header in ("신호일", "체결일", "체결가(원)", "목표 매도가(원)", "현재 상태"):
        assert signal_header in script
    assert "marketSignals.slice(0, 100)" in script
    assert "desktopMarketSignalLabel(item)" in script
    assert "desktopMarketSignalState(item)" in script


def test_desktop_numeric_table_headers_show_units_and_notifications_stay_separate():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    for label in (
        "현재가(원)",
        "전일대비(원)",
        "등락률(%)",
        "점수(점)",
        "수익률(%)",
        "순매수량(주)",
        "순매수금액(원)",
        "영업이익률(%)",
        "매출 대비(%)",
        "금액(억원)",
        "목표가(원)",
        "공감(건)",
        "댓글(건)",
        "체결 횟수(회)",
        "현재(포인트/USD)",
    ):
        assert label in script

    assert '{ id: "notifications", label: "알림", utility: true }' in script
    assert 'sheetTitle(root, "알림"' in script
    assert 'section(root, "이 PC 알림"' in script
    assert 'section(root, "받을 알림"' in script
    assert 'section(root, "알림 내역"' in script
    assert 'headers(root, ["수신일", "시간", "유형", "제목", "내용", "연결"]' in script
    assert 'sparkline(item.points, Number(item.change_rate) < 0 ? "#1967d2" : "#d93025", "포인트")' in script
    assert 'sparkline(prices.slice().reverse(), Number(quote.change_rate) < 0 ? "#1967d2" : "#d93025", "원")' in script
    assert "globalAssetValue(current, unit)" in script


def test_desktop_charts_hide_bottom_date_axes_and_keep_tooltip_dates():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    for removed_axis_markup in (
        'class="desk-fin-period"',
        "const periodLabels = periods.map",
        "const startLabel = period ===",
        "const endLabel = period ===",
        "const dates = rows.map",
        'row.month.slice(2).replace("-", ".")',
        "dateLabel(rows[0].date).slice(5)",
        "dateLabel(rows.at(-1).date).slice(5)",
        'y="252" text-anchor="middle">${year}',
    ):
        assert removed_axis_markup not in script

    for tooltip_date_source in (
        "financialPeriodLabel(row.period, row.estimated)",
        'dateLabel(row.date)} · ${labels[key]}',
        'row.month.replace("-", ".")} · 리포트',
        "dateLabel(date)} · ${item.impact",
        "dateLabel(row.date)} · 실제",
    ):
        assert tooltip_date_source in script
    assert "chartPointAttributes" in script
    assert "data-chart-tooltip" in script


def test_desktop_sheet_buttons_have_raised_pressed_and_focus_states():
    styles = (STATIC_DIR / "desktop" / "styles.css").read_text(encoding="utf-8")

    for selector in (
        ".desk-cell-button button {",
        ".desk-cell-button button:hover {",
        ".desk-cell-button button:active {",
        ".desk-cell-button button:focus-visible {",
        ".desk-cell-button button:disabled {",
        ".desk-cell-detail-tab button {",
        ".desk-cell-detail-tab.is-active button {",
        ".desk-cell-option button {",
        ".desk-cell-option.is-active button {",
    ):
        assert selector in styles

    assert "--desk-control-border:" in styles
    assert "--desk-control-shadow:" in styles
    assert "linear-gradient(180deg" in styles
    assert "transform: translateY(-1px)" in styles
    assert "box-shadow: inset 0 2px 4px" in styles


def test_desktop_login_dialog_owns_focus_until_login_completes():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    assert 'app: document.querySelector(".desk-app")' in script
    assert "function setLoginDialogOpen(open)" in script
    assert 'elements.app.toggleAttribute("inert", open)' in script
    assert "if (!elements.login.hidden) elements.loginId.focus()" in script
    assert "if (elements.login.hidden) input.focus()" in script
    assert "!elements.login.contains(event.target)" in script
    assert "function trapLoginDialogFocus(event)" in script
    assert 'elements.login.addEventListener("keydown", trapLoginDialogFocus)' in script
    assert "setLoginDialogOpen(true)" in script
    assert "setLoginDialogOpen(false)" in script


def test_desktop_stock_detail_preserves_the_mobile_information_contract():
    mobile = (STATIC_DIR / "dashboard" / "index.html").read_text(encoding="utf-8")
    desktop = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_DIR / "desktop" / "styles.css").read_text(encoding="utf-8")

    for label in (
        "오늘의 요약",
        "최근 1개월 공시",
        "최근 7일 수급",
        "핵심 키워드",
        "종목 이슈",
        "투자자별 매매동향",
        "리포트 분석",
        "종목뉴스",
        "뉴스 온도",
        "기업 체력 한눈에 보기",
        "이 회사는",
        "실적 분석",
        "매출 심층 분석",
        "동종 업계 영업이익률 추이",
        "판관비 심층분석",
        "현금 흐름 심층 분석",
        "현금 사용 추적",
        "현금·안정성·효율",
        "밸류에이션 비교",
        "투자 체크포인트",
        "AI 지금 이렇게 판단해요",
        "최근 1년 AI 시그널",
        "최근 1년 전략 결과",
        "모든 매매내역 보기",
    ):
        assert label in mobile
        assert label in desktop

    assert "renderDesktopDetailHeader(root, code, dashboard, prices, intraday)" in desktop
    assert "renderDesktopStockHome(root, code, dashboard, prices, viewData || {})" in desktop
    assert "renderDesktopCompany(root, code, dashboard, prices, financials, sectorMargins, sgaAnalysis)" in desktop
    assert "renderDesktopAISignal(root, code, dashboard, prices, viewData)" in desktop
    for endpoint in (
        "prices?limit=1000",
        "intraday?limit=390",
        "home-context?flow_limit=1500&research_limit=100&disclosure_limit=100&news_limit=60&community_limit=12",
        "financials?limit=500",
        "sector-operating-margins?limit=5&per_pair=1",
        "sga-analysis",
        "quant-signals",
    ):
        assert endpoint in desktop

    for chart_class in (
        "desk-price-chart",
        "desk-flow-chart",
        "desk-report-chart",
        "desk-news-chart",
        "desk-revenue-chart",
        "desk-balance-chart",
        "desk-cashflow-chart",
        "desk-per-chart",
        "desk-quant-chart",
    ):
        assert chart_class in desktop
        assert f".{chart_class}" in styles
    assert "마우스 또는 키보드 포커스로 상세값 확인" in desktop
    assert "detailNewsModes" not in desktop
    assert "AI 속보" not in desktop
    assert 'section(root,"최근 기사 · 종목뉴스"' in desktop
    assert 'news.filter((item)=>item.source_category!=="breaking")' in desktop
    assert "최근 종목뉴스가 없습니다." in desktop


def test_desktop_service_worker_handles_push_without_reusing_mobile_worker():
    response = client.get("/desktop-sw.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["service-worker-allowed"] == "/desktop"
    assert 'self.addEventListener("push"' in response.text
    assert 'self.addEventListener("notificationclick"' in response.text
    assert "/desktop?view=notifications&notification_url=" in response.text
    assert 'payload.kind === "morning_briefing"' not in response.text
    assert 'data: { url: targetUrl, kind: payload.kind || "general" }' in response.text
    assert 'const DESKTOP_SW_VERSION = "20260829h4";' in response.text
    assert "dashboard-sw.js" not in response.text


def test_mobile_dashboard_still_uses_original_bundle():
    response = client.get("/dashboard")

    assert response.status_code == 200
    assert "/assets/dashboard/styles.css" in response.text
    assert "/dashboard-app-v170.js" in response.text
    assert "/assets/desktop/" not in response.text


def test_custom_domain_desktop_session_persists_document_title():
    init_db()
    share_id = "codex-desktop-custom-domain"
    browser = TestClient(app)
    with SessionLocal() as db:
        db.execute(delete(DesktopUserPreference).where(DesktopUserPreference.share_id == share_id))
        db.commit()

    try:
        assert browser.get("/desktop/preferences").status_code == 401
        session = browser.post("/desktop/session", json={"share_id": share_id})
        assert session.status_code == 200
        assert session.cookies.get("sn_desktop_session")

        initial = browser.get("/desktop/preferences")
        assert initial.status_code == 200
        assert initial.json()["document_title"] == "한국증시 비밀노트"

        saved = browser.put("/desktop/preferences", json={"document_title": "나의 PC 투자노트"})
        assert saved.status_code == 200
        assert saved.json()["document_title"] == "나의 PC 투자노트"
        assert browser.get("/desktop/preferences").json()["document_title"] == "나의 PC 투자노트"
    finally:
        with SessionLocal() as db:
            db.execute(delete(DesktopUserPreference).where(DesktopUserPreference.share_id == share_id))
            db.commit()


def test_desktop_home_includes_the_latest_mobile_briefing_and_ai_response_contract():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    for expected in (
        'briefing: { id: "briefing", label: "돈이 되는 소식"',
        'signals: { id: "signals", label: "AI 시그널"',
        'movers: { id: "movers", label: "급등주"',
        'cached("/briefings/morning-money"',
        "renderDesktopMorningMoneyBriefing",
        "renderDesktopMorningMoneyPreview",
        "morningMoneyEditionPresentation",
        '"오전판 · 06:00 발행"',
        '"점심판 · 12:00 발행"',
        '"오후판 · 16:00 발행"',
        'section(root, "오늘의 돈이 되는 소식"',
        'cached("/market/us-sector-moves"',
        "renderDesktopHomeAiResponse",
        'section(root, "AI 관심종목 대응"',
        '"관심종목 맞춤 대응"',
        '"관심종목 전체보기"',
        '`/watchlists/${encodeURIComponent(state.watchlistId)}/quant-signals`',
        'openUtilitySheet("briefing")',
        'openUtilitySheet("signals")',
        'openUtilitySheet("movers")',
    ):
        assert expected in script

    # The three desktop home columns must start in disjoint column bands.
    assert 'section(root, "시장 지수", 0, 3, 8)' in script
    assert 'section(root, "급등주", 10, 3, 6)' in script
    assert 'section(root, "AI 관심종목 대응", col, row, 8)' in script
    assert 'renderDesktopHomeAiResponse(root, { trends, impact: impact || {}, usSectors, identity }, 16, 3)' in script


def test_desktop_search_preserves_mobile_watch_pin_and_recommendation_detail_actions():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    for expected in (
        'const RECOMMENDATION_TRACK_KEY = "analyst.recommendationTracks";',
        "function readRecommendationTracks",
        "function saveRecommendationTracks",
        "function toggleRecommendationTrack",
        'method: "PUT"',
        '`/watchlists/${encodeURIComponent(state.watchlistId)}/recommendation-tracks`',
        '"관심 추가"',
        '"핀 설정"',
        '"AI 시그널 상세"',
        "renderDesktopRecommendationDetail",
        'section(root, "AI 대응 · 지금 할 일"',
        'section(root, "판단에 쓴 핵심 수치"',
        'section(root, "세부 근거"',
    ):
        assert expected in script


def test_dynamic_sheet_close_controls_support_keyboard_activation():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    assert "close.tabIndex = 0" in script
    assert 'event.key !== "Enter" && event.key !== " "' in script
    assert "closeDynamicSheet(sheet)" in script


def test_direct_recommendation_route_falls_back_to_stock_dashboard_data():
    script = (STATIC_DIR / "desktop" / "app.js").read_text(encoding="utf-8")

    assert "function desktopRecommendationFallback" in script
    assert '`/stocks/${encodeURIComponent(code)}/dashboard?include_profile=0`' in script
    assert "item = desktopRecommendationFallback(dashboard, code)" in script
    assert 'item.action || current.label || current.action || "관찰"' in script
