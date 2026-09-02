import asyncio
from datetime import date, datetime
import json
from pathlib import Path
import re
import subprocess

from fastapi.testclient import TestClient

from app.main import app as production_app
import app.staging_app as staging_module
from app.staging_app import STAGING_IA_VERSION, THEME_VERSION, app as staging_app


ROOT = Path(__file__).resolve().parents[1]


HTML_ROUTES = (
    "/dashboard?view=home",
    "/dashboard?view=news",
    "/dashboard?view=event-detail",
    "/dashboard?view=notifications",
    "/dashboard?view=ai-signals",
    "/dashboard?view=morning-briefing",
    "/dashboard?view=search",
    "/dashboard?view=search&panel=recent-stocks",
    "/dashboard?view=recommend-detail",
    "/dashboard?view=movers",
    "/dashboard?view=portfolio",
    "/dashboard?view=chart",
    "/dashboard?view=chart-history",
    "/dashboard/005930",
    "/nasdaq",
    "/nasdaq/AAPL",
    "/nasdaq?view=watchlist",
    "/nasdaq?view=recommend",
    "/nasdaq?view=recommend-history",
    "/nasdaq?view=trend",
    "/nasdaq?view=trend-past",
    "/nasdaq?view=trend-impact",
    "/nasdaq?view=chart",
    "/nasdaq?view=chart-history",
    "/nasdaq?view=market",
    "/insight",
    "/insight/mobile",
    "/insight/desktop",
    "/desktop",
    "/portfolio",
    "/concepts",
)


def test_staging_serves_bundled_official_stock_logo_before_upstream(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "https://example.test")

    assert staging_module._is_staging_read_proxy_request(
        {"method": "GET", "path": "/stock-logos/278470.png"}
    ) is False
    assert staging_module._is_staging_read_proxy_request(
        {"method": "GET", "path": "/stock-logos/005930.png"}
    ) is True


def test_staging_recommendations_keep_pending_and_same_day_executed_entries():
    recommendation_payload = {
        "as_of": "2026-08-31T16:00:00+09:00",
        "universe_count": 100,
        "candidate_count": 20,
        "items": [
            {"rank": 1, "code": "078930", "name": "GS", "score": 81.38, "action": "우수"},
            {"rank": 12, "code": "003230", "name": "삼양식품", "score": 70.98, "action": "관찰", "price": 1_531_000},
            {"rank": 14, "code": "105560", "name": "KB금융", "score": 69.01, "action": "관찰", "price": 173_300},
            {"rank": 18, "code": "000001", "name": "장중예비", "score": 65.0, "action": "관찰"},
            {"rank": 19, "code": "005930", "name": "과거보유", "score": 64.0, "action": "관찰"},
        ],
    }
    signal_payload = {
        "status": "ready",
        "as_of": "2026-08-31T15:40:00+09:00",
        "strategy_version": "confirmed-entry-test",
        "items": [
            {
                "code": "078930",
                "current": {"action": "exited", "position_open": False, "live_observation": False},
            },
            {
                "code": "003230",
                "signal_at": "2026-08-31T15:40:00+09:00",
                "current": {
                    "action": "entry_pending",
                    "position_open": False,
                    "live_observation": False,
                    "score": 94.98,
                    "price": 1_531_000,
                    "entry_confirmation": {
                        "allowed": True,
                        "required_supports": 1,
                        "supportive_count": 2,
                    },
                    "levels": [{"key": "entry", "price": 1_520_000}],
                    "next_confirmation": "다음 거래일 시가의 갭 범위를 확인",
                },
            },
            {
                "code": "105560",
                "signal_at": "2026-08-31T15:40:00+09:00",
                "current": {
                    "action": "entered",
                    "position_open": True,
                    "live_observation": False,
                    "score": 75.37,
                    "price": 171_600,
                    "entry_date": "2026-09-01",
                    "entry_price": 169_100,
                    "entry_confirmation": {
                        "allowed": True,
                        "required_supports": 1,
                        "supportive_count": 2,
                    },
                    "lifecycle": {
                        "state": "entered",
                        "latest_transition": {
                            "side": "buy",
                            "signal_date": "2026-08-31",
                            "transition_date": "2026-09-01",
                            "price": 169_100,
                        },
                    },
                    "levels": [{"key": "partial_exit", "price": 179_146}],
                    "next_confirmation": "초기 위험선과 첫 수익확정 기준을 매일 확인",
                },
            },
            {
                "code": "000001",
                "current": {"action": "entry_pending", "position_open": False, "live_observation": True},
            },
            {
                "code": "005930",
                "signal_at": "2026-08-30T15:40:00+09:00",
                "current": {
                    "action": "holding",
                    "position_open": True,
                    "live_observation": False,
                    "entry_date": "2026-08-31",
                    "entry_confirmation": {"allowed": True},
                    "lifecycle": {
                        "latest_transition": {
                            "side": "buy",
                            "transition_date": "2026-08-31",
                        }
                    },
                },
            },
        ],
    }

    rewritten = staging_module._rewrite_staging_recommendation_contract(
        json.dumps(recommendation_payload).encode(),
        signal_payload,
        requested_limit=2,
        reference_date=date(2026, 9, 1),
    )
    payload = json.loads(rewritten)

    assert payload["selection_rule"] == "confirmed_entry_pending_or_entered_today"
    assert payload["selection_state"] == "ready"
    assert payload["candidate_count"] == 2
    assert payload["qualified_count"] == 2
    assert payload["pending_count"] == 1
    assert payload["entered_today_count"] == 1
    assert [item["code"] for item in payload["items"]] == ["003230", "105560"]
    pending, entered = payload["items"]
    assert pending["rank"] == 1
    assert pending["action"] == "신규 매수 대기"
    assert pending["recommendation_state"] == "entry_confirmed"
    assert pending["condition_price"] == 1_531_000
    assert pending["ai_trade_signal"]["current"]["levels"][0]["price"] == 1_520_000
    assert entered["rank"] == 2
    assert entered["action"] == "보유 유지"
    assert entered["recommendation_state"] == "entered_today"
    assert entered["buy_condition_met"] is True
    assert entered["recommendation_entry_date"] == "2026-09-01"
    assert entered["strategy_entry_price"] == 169_100
    assert entered["condition_price"] == 173_300
    assert entered["ai_trade_signal"]["current"]["position_open"] is True


def test_staging_rebuilds_a_missing_same_day_card_without_reusing_the_signal_score(
    monkeypatch,
):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "https://example.test")
    staging_module._staging_recommendation_supplement_cache.clear()
    requests = []

    dashboard = {"code": "105560", "name": "KB금융"}
    score_item = {
        "code": "105560",
        "name": "KB금융",
        "market": "KOSPI",
        "score": 69.01,
        "action": "관찰",
        "decision_reason": "추천 점수 기준 설명",
        "price": 171_600,
        "change_rate": -0.98,
        "one_month_return": 1.78,
        "three_month_return": 12.75,
        "trading_value": 62_800_000_000,
        "component_scores": {"price_momentum": 71.0},
        "chart_analysis": {"score": 96.0, "trend": "상승 추세"},
        "reasons": ["추천 근거"],
        "risks": ["추천 주의점"],
        "_quant_live_quote": {"price": 171_600},
    }
    monkeypatch.setattr(staging_module, "_score_dashboard", lambda payload: dict(score_item))

    class Response:
        def __init__(self, payload):
            self._payload = payload

        @staticmethod
        def raise_for_status():
            return None

        def json(self):
            return self._payload

    class Client:
        async def get(self, url, **kwargs):
            requests.append((url, kwargs))
            if url.endswith("/dashboard"):
                return Response(dashboard)
            return Response([{"trade_date": "2026-08-31", "close": 173_300}])

    signal_payload = {
        "status": "ready",
        "as_of": "2026-09-01T09:50:00+09:00",
        "strategy_version": "position-lifecycle-v7.3",
        "items": [
            {
                "code": "105560",
                "name": "KB금융",
                "market": "KOSPI",
                "market_cap_rank": 11,
                "universe_tier": "core",
                "signal_date": "2026-08-31",
                "signal_at": "2026-08-31T15:40:00+09:00",
                "score": 89.19,
                "current": {
                    "action": "entered",
                    "position_open": True,
                    "live_observation": False,
                    "score": 75.37,
                    "price": 171_600,
                    "entry_date": "2026-09-01",
                    "entry_price": 169_100,
                    "entry_confirmation": {
                        "allowed": True,
                        "required_supports": 1,
                        "supportive_count": 2,
                    },
                    "lifecycle": {
                        "latest_transition": {
                            "side": "buy",
                            "signal_date": "2026-08-31",
                            "transition_date": "2026-09-01",
                        }
                    },
                },
            }
        ],
    }

    supplements = asyncio.run(
        staging_module._build_staging_recommendation_supplements(
            Client(),
            signal_payload,
            [],
            reference_date=date(2026, 9, 1),
        )
    )
    payload = json.loads(
        staging_module._rewrite_staging_recommendation_contract(
            json.dumps({"universe_count": 100, "candidate_count": 0, "items": []}).encode(),
            signal_payload,
            requested_limit=8,
            reference_date=date(2026, 9, 1),
            supplemental_items=supplements,
        )
    )

    assert len(requests) == 2
    price_request = next(request for request in requests if request[0].endswith("/prices"))
    assert price_request[1]["params"]["from_date"] == "2026-08-31"
    assert payload["qualified_count"] == 1
    item = payload["items"][0]
    assert item["recommendation_state"] == "entered_today"
    assert item["score"] == 69.01
    assert item["ai_trade_signal"]["current"]["score"] == 75.37
    assert item["price"] == 173_300
    assert item["condition_price"] == 173_300
    assert item["ai_trade_signal"]["current"]["price"] == 171_600
    assert "_quant_live_quote" not in item


def test_staging_recommendations_fail_closed_when_signal_membership_is_unavailable():
    source = json.dumps(
        {"universe_count": 100, "candidate_count": 1, "items": [{"code": "078930"}]}
    ).encode()

    payload = json.loads(staging_module._rewrite_staging_recommendation_contract(source, None))

    assert payload["items"] == []
    assert payload["selection_state"] == "unavailable"
    assert "표시하지 않습니다" in payload["selection_message"]


def test_staging_recommendations_keep_a_bounded_refreshing_snapshot_visible():
    source = {
        "universe_count": 100,
        "candidate_count": 1,
        "items": [{"code": "003230", "name": "삼양식품", "score": 66.24}],
    }
    current = {
        "action": "entry_pending",
        "position_open": False,
        "live_observation": False,
        "entry_confirmation": {
            "allowed": True,
            "required_supports": 1,
            "supportive_count": 2,
        },
    }
    refreshing = {
        "status": "refreshing",
        "snapshot_age_seconds": 650,
        "items": [{"code": "003230", "current": current}],
    }

    payload = json.loads(
        staging_module._rewrite_staging_recommendation_contract(
            json.dumps(source).encode(),
            refreshing,
        )
    )

    assert [item["code"] for item in payload["items"]] == ["003230"]
    assert payload["selection_state"] == "ready"
    assert payload["selection_refreshing"] is True
    assert "최신 시장 데이터를 확인 중" in payload["selection_message"]

    refreshing["snapshot_age_seconds"] = 1_801
    stale_payload = json.loads(
        staging_module._rewrite_staging_recommendation_contract(
            json.dumps(source).encode(),
            refreshing,
        )
    )
    assert stale_payload["items"] == []
    assert stale_payload["selection_state"] == "unavailable"


def test_staging_entry_point_injects_adaptive_tds_assets_into_every_html_shell():
    # Avoid entering the production lifespan: these shell checks do not need
    # collectors, quote polling, or any other background runtime.
    client = TestClient(staging_app)
    for route in HTML_ROUTES:
        response = client.get(route)
        assert response.status_code == 200, route
        assert '<meta name="color-scheme" content="light dark" />' in response.text, route
        assert 'id="staging-theme-color"' in response.text, route
        assert '/assets/staging/adaptive-theme.js' in response.text, route
        assert '/assets/staging/dark-theme.css' in response.text, route
        assert 'media="(prefers-color-scheme: dark)"' in response.text, route
        assert '/assets/staging/toss-fidelity.css' in response.text, route
        assert '/assets/staging/toss-ia.js' in response.text, route
        assert f'/assets/staging/toss-ia.js?v={STAGING_IA_VERSION}' in response.text, route
        assert response.headers["x-staging-theme"] == THEME_VERSION
        assert response.headers["x-robots-tag"] == "noindex, nofollow, noarchive"


def test_production_dashboard_loads_promoted_tds_assets_once_without_staging_headers():
    client = TestClient(production_app)
    response = client.get("/dashboard?view=home")
    assert response.status_code == 200
    assert response.text.count("/assets/staging/dark-theme.css") == 1
    assert response.text.count("/assets/staging/adaptive-theme.js") == 1
    assert response.text.count("/assets/staging/toss-fidelity.css") == 1
    assert response.text.count("/assets/staging/toss-ia.js") == 1
    assert "x-staging-theme" not in response.headers
    assert "x-robots-tag" not in response.headers
    assert "noindex" not in response.text
    assert 'name="secret-note-quote-stream-url"' not in response.text


def test_staging_dashboard_routes_quotes_to_canonical_websocket(monkeypatch):
    monkeypatch.setattr(
        staging_module,
        "STAGING_DATA_UPSTREAM",
        "https://secretnote.cloud/canonical",
    )

    response = TestClient(staging_app).get("/dashboard/005930")

    assert response.status_code == 200
    assert (
        '<meta name="secret-note-quote-stream-url" '
        'content="wss://secretnote.cloud/canonical/ws/quotes" />'
    ) in response.text


def test_staging_dashboard_omits_quote_stream_override_without_upstream(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "")

    response = TestClient(staging_app).get("/dashboard/005930")

    assert response.status_code == 200
    assert 'name="secret-note-quote-stream-url"' not in response.text


def test_discovery_and_feed_use_identical_versioned_frontend_assets_in_both_environments():
    staging_client = TestClient(staging_app)
    production_client = TestClient(production_app)

    def frontend_assets(document: str) -> tuple[str, ...]:
        urls = re.findall(r'(?:href|src)="([^"]+)"', document)
        return tuple(
            url
            for url in urls
            if url.startswith("/assets/dashboard/")
            or url.startswith("/assets/staging/")
            or url.startswith("/dashboard-app-v170.js")
        )

    for view in ("search", "news"):
        production_shell = production_client.get(f"/dashboard?view={view}")
        staging_shell = staging_client.get(f"/dashboard?view={view}")

        assert production_shell.status_code == 200
        assert staging_shell.status_code == 200
        assert frontend_assets(staging_shell.text) == frontend_assets(production_shell.text)
        assert "&amp;staging=" not in staging_shell.text
        assert '<meta name="secret-note-service-update" content="20260829-chart-analysis-v1" />' in staging_shell.text
        assert '<meta name="secret-note-service-update" content="20260829-chart-analysis-v1" />' in production_shell.text


def test_page_loading_hidden_state_wins_over_stale_visible_class():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert 'body[data-staging-ia="tds-video"] .page-loading[hidden] {' in css
    assert '.page-loading[hidden]:not(.visible)' not in css


def test_staging_tds_layer_is_adaptive_and_preserves_reference_tokens():
    client = TestClient(staging_app)
    response = client.get("/assets/staging/toss-fidelity.css")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")
    assert "--tds-color-background: light-dark(#ffffff, #17161b)" in response.text
    assert "--tds-color-text-primary: light-dark(#191f28, #e5e7eb)" in response.text
    assert "color-scheme: light dark" in response.text
    assert response.text.count("light-dark(") >= 500
    assert "--tds-space-gutter: 20px" in response.text
    assert "--tds-mobile-canvas: 471px" in response.text
    assert "--tc-tab-height: 50px" in response.text
    assert 'body[data-staging-ia="tds-video"]' in response.text
    assert '[data-tds-text="title"]' in response.text
    assert "overflow-wrap: anywhere !important" in response.text
    assert response.headers["x-staging-theme"] == THEME_VERSION


def test_staging_theme_runtime_follows_system_and_supports_review_override():
    client = TestClient(staging_app)
    response = client.get("/assets/staging/adaptive-theme.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert 'window.matchMedia("(prefers-color-scheme: dark)")' in response.text
    assert 'requestedTheme === "light" || requestedTheme === "dark"' in response.text
    assert "root.dataset.stagingTheme = theme" in response.text
    assert "root.style.colorScheme = theme" in response.text
    assert 'themeColor.content = isDark ? "#17161b" : "#ffffff"' in response.text
    assert 'darkMode.addEventListener("change", handleSystemThemeChange)' in response.text
    assert response.headers["x-staging-theme"] == THEME_VERSION


def test_service_update_dialog_and_intro_are_versioned_for_staging_and_production():
    staging_client = TestClient(staging_app)
    production_client = TestClient(production_app)
    staging_shell = staging_client.get("/dashboard?view=home").text
    production_shell = production_client.get("/dashboard?view=home").text
    staging_js = staging_client.get("/assets/staging/toss-ia.js").text
    css = staging_client.get("/assets/staging/toss-fidelity.css").text

    assert '<meta name="secret-note-environment" content="staging" />' in staging_shell
    assert 'name="secret-note-environment"' not in production_shell
    release_meta = '<meta name="secret-note-service-update" content="20260829-chart-analysis-v1" />'
    assert release_meta in staging_shell
    assert release_meta in production_shell
    assert 'key: "20260829-chart-analysis-v1"' in staging_js
    assert 'meta[name="secret-note-service-update"]' in staging_js
    assert 'secret-note-service-update-dismissed:' in staging_js
    assert 'secret-note-service-update-session:' in staging_js
    assert 'startsAt: "2026-08-29T00:00:00+09:00"' in staging_js
    assert 'endsAt: "2026-09-05T00:00:00+09:00"' in staging_js
    assert "serviceUpdateWithinPublishingWindow()" in staging_js
    assert "window.secretNoteServiceUpdateGate" in staging_js
    assert 'const serviceUpdateEntryGate = document.getElementById("login-gate");' in staging_js
    assert "const openServiceUpdateDialogOnFirstEntry = () =>" in staging_js
    assert "serviceUpdateEntryGateObserver.observe(serviceUpdateEntryGate" in staging_js
    assert 'attributeFilter: ["hidden"]' in staging_js
    assert 'if (serviceUpdateRoute() === "service-update") return;' in staging_js
    assert "window.setTimeout(openServiceUpdateDialog, 700)" not in staging_js
    assert 'new CustomEvent("secret-note:service-update-priority")' in staging_js
    assert 'new CustomEvent("secret-note:service-update-home-reentry")' in staging_js
    assert 'role="dialog" aria-modal="true"' in staging_js
    assert "data-service-update-detail" in staging_js
    assert "업데이트 자세히 보기" in staging_js
    assert "data-service-update-dismiss" in staging_js
    assert "다시 보지 않기" in staging_js
    assert "data-service-update-close" in staging_js
    assert 'url.searchParams.set("view", "service-update")' in staging_js
    for copy in (
        "차트 분석 페이지가 추가됐어요",
        "AI 매매 신호를 더 쉽게 읽을 수 있어요",
        "돈이 되는 소식이 시간대별로 나뉘었어요",
        "종목 상세와 홈의 정보 구조를 다듬었어요",
    ):
        assert copy in staging_js

    rules = css[css.index("/* v121 — campaign-window service-update bottom sheet and notification priority. */"):]
    assert ".staging-service-update-dialog" in rules
    assert "align-items: flex-end !important" in rules
    assert ".staging-service-update-card" in rules
    assert "border-radius: 26px 26px 0 0 !important" in rules
    assert ".staging-service-update-creative" in rules
    assert ".staging-service-update-visual-card" in rules
    assert ".staging-service-update-card-actions" in rules
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 0.64fr) !important" in rules
    assert ".staging-service-update-page" in rules
    assert "position: fixed !important" in rules
    assert ".staging-service-update-page-nav" in rules
    assert "position: sticky !important" in rules
    assert "@media (max-width: 359px)" in rules
    assert "@media (prefers-reduced-motion: reduce)" in rules


def test_staging_tds_palette_has_no_unpaired_theme_colors():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    css_without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    raw_color_lines = {
        line.strip()
        for line in css_without_comments.splitlines()
        if re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", line)
        and "light-dark(" not in line
    }

    assert raw_color_lines == {
        "background: rgba(0, 0, 0, 0.72) !important;",
        'body[data-staging-ia="tds-video"] .staging-empty-shadow { fill: rgba(0, 0, 0, 0.26) !important; }',
        "color: #fff !important;",
        "background: #fff !important;",
    }
    assert '#chart-stock-search-suggestions.discovery-suggestions {' in css
    assert "color-scheme: inherit" in css
    assert "--tc-focus: var(--tc-blue);" in css
    assert "var(--tc-focus, #3182f6)" not in css
    assert css.count("var(--tc-focus)") >= 3


def test_staging_tds_ia_asset_preserves_data_contracts_and_remaps_navigation():
    client = TestClient(staging_app)
    response = client.get("/assets/staging/toss-ia.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert 'label: "증권"' in response.text
    assert 'label: "관심"' in response.text
    assert 'label: "발견"' in response.text
    assert 'label: "피드"' in response.text
    assert 'document.body.dataset.stagingIa = "tds-video"' in response.text
    assert 'document.body.dataset.stagingFidelity = "20260829-v66"' in response.text
    assert 'data-stock-tab="summary"' in response.text
    assert 'createStockTab("stock-news", "news", "소식")' in response.text
    assert 'createStockTab("stock-community", "community", "커뮤니티")' in response.text
    assert 'stockTabs.replaceChildren(summaryTab, strategyTab, newsTab, companyTab, communityTab)' in response.text
    assert 'className = "staging-stock-hero"' in response.text
    assert 'marketStatusButton.classList.add("staging-stock-market-status")' in response.text
    assert "stockHero.appendChild(marketStatusButton)" in response.text
    assert "data-staging-stock-as-of" not in response.text
    assert 'className = "staging-stock-bottom-cta"' not in response.text
    assert 'className = "staging-nav-back"' not in response.text
    assert 'toneTarget.classList.toggle("positive", isPositive)' in response.text
    assert 'toneTarget.classList.toggle("negative", isNegative)' in response.text
    assert 'hint.dataset.stagingVectorHint = "true"' in response.text
    assert 'stock-v3-commandbar.is-scrolled' in client.get("/assets/staging/toss-fidelity.css").text
    assert 'className = "staging-stock-alert"' not in response.text
    assert 'className = "staging-stock-more"' not in response.text
    assert "staging-page-hero" not in response.text
    assert response.text.count("fetch(") == 1
    assert "/stocks/${encodeURIComponent(normalizedCode)}/week-chart" in response.text
    assert ".staging-menu-toggle" not in response.text
    assert "AI 전략 시뮬레이션" not in response.text
    assert "실제 계좌·보유·주문 내역이 아닙니다." not in response.text
    assert 'aiSignalsView.querySelector(".ai-signals-commandbar")?.remove()' not in response.text
    assert 'source.classList.add("staging-proxied-commandbar")' in response.text
    assert 'image.src = `/stock-logos/${encodeURIComponent(normalizedCode)}.png?v=20260828-official-ci-v1`' in response.text
    assert 'className = "staging-pinned-empty"' in response.text
    assert "현재 AI 전략 비중은" in response.text
    for role in (
        "Top", "ListHeader", "ListRow", "Badge", "Tab", "SegmentedControl",
        "SearchField", "Skeleton", "BottomSheet", "BottomCTA", "BottomInfo", "Result",
    ):
        assert f"{role}:" in response.text
    assert response.headers["x-staging-theme"] == THEME_VERSION


def test_staging_theme_has_touch_and_spacing_contract_for_tds_ia():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert '--tds-size-touch: 44px' in css
    assert '--tds-space-gutter: 20px' in css
    assert 'body[data-staging-ia="tds-video"]' in css
    assert 'grid-template-columns: repeat(4, minmax(0, 1fr)) !important' in css
    assert '.staging-market-context' in css
    assert '.staging-shortcut-rail' in css
    assert '.staging-discovery-shortcuts' in css
    assert '.staging-watch-signal' in css
    assert '.staging-feed-modes' in css
    assert '.staging-nav-back' not in css
    assert 'left: 10px !important' in css


def test_staging_v32_centers_stock_header_and_guards_interaction_states():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert "grid-template-columns: 44px minmax(0, 1fr) 44px !important" in css
    assert "--tc-red: light-dark(#d92d4a, #ff637c)" in css
    assert "--tc-blue: light-dark(#2878e5, #6da5ff)" in css
    assert ".stock-investment-snapshot-row > b" in css
    assert ".push-notification-sheet-head h2" in css
    assert ".stock-sector-margin-value" in css
    assert ".service-footer" in css
    assert ".recommend-signal-facts dd" in css
    assert ".stock-v3-command-quote.positive > span" in css
    assert ".stock-v3-command-quote.negative > span" in css
    assert ".staging-stock-hero.positive .staging-stock-hero-price" in css
    assert ".staging-stock-hero.muted .staging-stock-hero-price" in css
    assert ".trend-calendar-event:is(:hover, :active, :focus)" in css
    assert "-webkit-touch-callout: none !important" in css
    assert ".staging-stock-bottom-cta" not in css
    assert ".staging-stock-alert" not in js
    assert ".staging-stock-more" not in js


def test_staging_stock_hero_preserves_simple_market_status_and_adaptive_sheet():
    client = TestClient(staging_app)
    shell = client.get("/dashboard/005930").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'id="stock-market-status-label"' in shell
    assert 'aria-controls="stock-trading-hours-sheet"' in shell
    assert 'id="stock-trading-hours-sheet"' in shell
    assert 'marketStatusButton.classList.add("staging-stock-market-status")' in js
    assert "stockHero.appendChild(marketStatusButton)" in js
    assert 'copyText("[data-staging-stock-as-of]"' not in js
    assert ".staging-stock-market-status:not([hidden])" in css
    assert '[data-status-tone="live"]' in css
    assert '[data-status-tone="waiting"]' in css
    assert 'body[data-staging-ia="tds-video"] .stock-trading-hours-card' in css
    assert 'body[data-staging-ia="tds-video"] .stock-trading-hours-actions button' in css


def test_stock_trading_hours_summary_reserves_ios_font_safety_space():
    styles = TestClient(staging_app).get("/assets/dashboard/styles.css").text
    marker = ".stock-trading-hours-body > p:first-child {"
    rules = styles[styles.index(marker) : styles.index("}", styles.index(marker))]

    assert "margin: 0;" in rules
    assert "padding-block: 2px;" in rules
    assert "line-height: 1.5;" in rules
    assert "margin: -6px" not in rules


def test_staging_theme_keeps_all_known_multi_tab_controls_on_one_row():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert ".notifications-tabs" in css
    assert "grid-template-columns: repeat(5, minmax(0, 1fr)) !important" in css
    assert "#market-view .market-segment" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr)) !important" in css


def test_staging_theme_contains_exhaustive_tds_component_contracts():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    for selector in (
        ".quant-signal-status",
        ".stock-detail-tabs",
        ".staging-market-context",
        ".staging-pinned-empty",
        ".staging-stock-logo-image",
        ".home-ai-signal-row",
        ".market-ranking-row",
        ".morning-money-news-item",
        ".notifications-page .push-history-item",
        ".home-ranking-subfilters",
        ".login-gate[data-phase=\"form\"]",
        "#login-gate .login-card input",
        ".morning-money-popover",
    ):
        assert selector in css

    assert "box-shadow: inset 0 0 0 2px light-dark(#2878e5, #6da5ff) !important" in css
    assert '[data-tds-role="BottomSheet"]' in css
    assert 'word-break: keep-all !important' in css


def test_staging_v32_uses_toss_tab_hierarchy_and_flat_signal_list_rows():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert "#portfolio-view > .portfolio-tabs" in css
    assert "#portfolio-view .watchlist-content-tabs" in css
    assert "#watchlist-view .watch-v3-tabs" in css
    assert "display: none !important" in css
    assert '#ai-signals-view .home-ai-signal-row[data-staging-list-row="true"]' in css
    assert "border-radius: 0 !important" in css
    assert ".home-ai-signal-metric.is-staging-visible" in css
    assert ".home-ai-signal-metric-value.positive" in css
    assert ".home-ai-signal-metric-value.negative" in css
    assert '"buy-holding": "매수 확정"' in js
    assert '"preliminary-buy": "매수 대기"' in js


def test_staging_v32_replaces_duplicate_child_headers_with_one_contextual_topbar():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'className = "staging-contextual-topbar"' in js
    assert 'document.body.dataset.stagingNavigation = contextual ? "contextual"' in js
    assert "initialRequestedContextualView" in js
    assert "contextualOwners.set(view, previousSyncedView)" in js
    assert '["chart-study", "chart-history"].includes(activeContextualView)' in js
    assert js.index('const sourceBack = config ? document.querySelector(config.back) : null;') < js.index(
        "const trackedOwner = contextualOwners.get(activeContextualView);"
    )
    assert "window.history.back()" in js
    assert "ownerButton instanceof HTMLButtonElement" in js
    for view in (
        '"ai-signals"',
        'movers',
        'chart',
        '"chart-history"',
        '"morning-briefing"',
        'notifications',
        '"event-detail"',
        '"recommend-detail"',
    ):
        assert f"{view}: {{" in js
    for selector in (
        "#ai-signals-back",
        "#market-ranking-back",
        "#chart-back",
        "#chart-history-back-button",
        "#morning-money-briefing-back",
        "#push-history-back",
        "#event-detail-back",
        "#recommend-detail-back",
    ):
        assert f'back: "{selector}"' in js
    assert ".app-topbar.is-staging-contextual" in css
    assert ".staging-proxied-commandbar" in css
    assert '[data-view="chart-history"] .bottom-nav' in css
    assert "grid-template-columns: 44px minmax(0, 1fr) 44px !important" in css


def test_staging_v33_bounds_pinned_stock_tabs_and_preserves_chart_visual_contrast():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'stockTabs?.classList.toggle("is-staging-pinned", shouldPinTabs)' in js
    assert 'const tabsWithinStockView = (stockView?.getBoundingClientRect().bottom ?? Infinity)' in js
    assert '&& tabsWithinStockView' in js
    assert 'window.requestAnimationFrame(scheduleStockScrollChrome)' in js
    assert 'const targetTop = window.scrollY + stockTabs.getBoundingClientRect().top' not in js
    assert ".stock-detail-tabs.is-staging-pinned" in css
    assert ".stock-v2-chart-summary" in css
    assert ".stock-cashflow-waterfall-bar.is-outflow" in css
    assert ".stock-per-bar-item.is-current .stock-per-bar" in css
    assert ".stock-per-bar-item.is-forward .stock-per-bar" in css
    assert ".stock-company-valuation-grid dd" in css
    assert '#stock-company-section span {' not in css


def test_staging_v36_restores_home_ai_signal_section_and_removes_response_icon():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'const anchorStockTabToTop = () =>' in js
    assert 'window.scrollTo({ top: Math.round(targetTop), behavior: "auto" })' in js
    assert '}, { capture: true });' in js
    assert 'responseSection.className = "staging-home-response-section"' in js
    assert 'id="staging-home-response-title">AI 종목 대응</h2>' in js
    assert 'aiSignals.insertAdjacentElement("afterend", responseSection)' in js
    assert 'signalTicker.classList.add("staging-home-signal-roller")' not in js
    assert 'market.insertAdjacentElement("afterend", signalTicker)' not in js
    assert 'aiSignals.classList.add("staging-home-ai-source")' not in js
    assert 'class="staging-home-response-icon"' not in js
    assert 'rail.classList.add("staging-home-shortcuts")' not in js
    assert ".home-ai-signals-head" in css
    assert ".staging-home-response-section" in css
    assert ".staging-home-response-icon" not in css
    assert ".morning-money-popover-coin" in css


def test_staging_v35_adds_bottom_navigation_scrim_below_popover_layer():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'bottomNavScrim.className = "staging-bottom-nav-scrim"' in js
    assert 'bottomNav.insertAdjacentElement("beforebegin", bottomNavScrim)' in js
    assert ".staging-bottom-nav-scrim" in css
    assert "z-index: 88 !important" in css
    assert "height: calc(160px + env(safe-area-inset-bottom)) !important" in css
    assert "light-dark(rgba(255, 255, 255, 0.58), rgba(11, 11, 13, 0.58)) 52%" in css
    assert '[data-view="stock"] .staging-bottom-nav-scrim' in css
    assert "pointer-events: none !important" in css


def test_staging_v122_keeps_feed_root_header_and_bottom_navigation_visible():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    rules = css.split(
        "/* v122 — Feed is a primary route: keep the global header and bottom navigation. */",
        1,
    )[1]
    for contract in (
        'body[data-staging-ia="tds-video"][data-view="news"] .app-topbar',
        "position: fixed !important",
        "width: min(100%, var(--tc-content)) !important",
        "display: block !important",
        'body[data-staging-ia="tds-video"][data-view="news"] .shell[data-ui-version="3.0"]',
        "padding-top: var(--tc-header-height) !important",
        'body[data-staging-ia="tds-video"][data-view="news"] .bottom-nav',
        "display: grid !important",
        'body[data-staging-ia="tds-video"][data-view="news"] .staging-bottom-nav-scrim',
    ):
        assert contract in rules
    assert '{ view: "news", label: "피드", icon: icons.feed }' in js
    assert 'home: "증권", portfolio: "관심", search: "발견", news: "피드"' in js


def test_staging_v123_reserves_ios_safe_area_above_every_top_navigation():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert 'viewport-fit=cover' in shell
    assert '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />' in shell
    assert "contextual-safe-area-v128" in shell
    for contract in (
        "--tc-safe-area-top: env(safe-area-inset-top, 0px)",
        "--tc-header-row-height: 78px",
        "--tc-command-row-height: 68px",
        "--tc-header-height: calc(var(--tc-header-row-height) + var(--tc-safe-area-top))",
        "--tc-command-height: calc(var(--tc-command-row-height) + var(--tc-safe-area-top))",
    ):
        assert contract in css

    rules = css.split(
        "/* v123-safe-area — keep every top navigation row below iOS status chrome. */",
        1,
    )[1]
    for contract in (
        ".app-topbar:not(.is-staging-contextual)",
        ":is(.staging-market-context, .staging-top-actions)",
        "top: calc(var(--tc-safe-area-top) + 17px) !important",
        "transform: none !important",
        ".app-topbar.is-staging-contextual",
        "display: block !important",
        ".staging-contextual-topbar",
        "padding: var(--tc-safe-area-top) 12px 0 !important",
        ".secondary-commandbar",
        "padding: calc(8px + var(--tc-safe-area-top)) 12px 8px !important",
    ):
        assert contract in rules


def test_staging_v128_falls_back_for_ios_standalone_chart_headers():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=chart").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert "contextual-safe-area-v128" in shell
    assert "20260902-signal-sell-labels-v91" in shell
    for contract in (
        'const isIosDevice = /iP(?:hone|ad|od)/.test(navigator.userAgent)',
        'navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1',
        'window.matchMedia("(display-mode: standalone)").matches',
        "navigator.standalone === true",
        '"data-staging-ios-standalone"',
    ):
        assert contract in js

    rules = css.split(
        "/* v128-safe-area-fallback — reserve iOS system chrome when standalone WebKit reports a zero env inset. */",
        1,
    )[1]
    for contract in (
        "html[data-staging-ios-standalone]",
        'body[data-staging-ia="tds-video"]',
        "--tc-safe-area-top: max(env(safe-area-inset-top, 0px), 47px) !important",
        '[data-view="chart-study"] #chart-study-view',
        "padding-top: 14px !important",
        ".chart-study-content",
        "margin-top: 0 !important",
    ):
        assert contract in rules


def test_staging_v37_rebuilds_home_top50_with_return_first_and_watch_toggles():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'const homeRankingOrder = ["surge", "volume", "market_cap"' in js
    assert 'homeRankingHead.append(homeRankingTitle, homeRankingMeta);' in js
    assert 'market?.querySelector("#home-index-shared-asof")?.remove();' in js
    assert 'document.getElementById("trend-calendar-window")?.remove();' in js
    assert 'homeRankingMore.textContent = "더 보기"' in js
    assert 'returnTab && !returnTab.classList.contains("active")' in js
    assert 'card.className = `${originalClassName} staging-home-ranking-row`' in js
    assert 'heart.className = "staging-home-ranking-watch"' in js
    assert 'heart.innerHTML = svg(icons.interest)' in js
    assert 'toggleWatchlistItem(item)' in js
    assert 'button.setAttribute("aria-pressed", String(active))' in js
    assert 'homeRankingObserver.observe(homeRankingList, { childList: true, subtree: true })' in js
    assert ".staging-home-ranking-main" in css
    assert ".staging-home-ranking-watch.active svg" in css
    assert "grid-template-columns: minmax(0, 1fr) 44px !important" in css
    assert "width: calc(100% + (var(--tc-gutter) * 2)) !important" in css
    assert "border-top: 1px solid var(--tc-line) !important" in css


def test_staging_rebuilt_navigation_keeps_app_routes_clickable():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'const bindStagingRoute = (button, view) => {' in js
    assert 'if (typeof setView === "function") {' in js
    assert 'window.history.pushState({}, "", `/dashboard?view=${encodeURIComponent(view)}`);' in js
    assert 'window.dispatchEvent(new PopStateEvent("popstate"));' in js
    assert 'bindStagingRoute(button, item.view);' in js
    assert 'bindStagingRoute(proxy, view);' in js


def test_staging_v38_separates_primary_tabs_from_secondary_filter_chips():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'homeRankingTabs.classList.add("staging-primary-tabs")' in js
    assert 'homeRankingFilters.classList.add("staging-filter-chips")' in js
    assert 'homeRankingTabs.dataset.stagingControlLevel = "primary"' in js
    assert 'homeRankingFilters.dataset.stagingControlLevel = "secondary"' in js
    assert 'homeRankingTabs.setAttribute("aria-label", "TOP 50 순위 기준 탭")' in js
    assert 'homeRankingFilters.setAttribute("aria-label", "선택한 순위의 세부 필터")' in js
    assert ".staging-primary-tabs button::after" in css
    assert ".staging-primary-tabs button:is(.active, [aria-selected=\"true\"])::after" in css
    assert ".staging-filter-chips[hidden]" in css
    assert ".staging-filter-chips button:is(.active, [aria-selected=\"true\"])" in css
    assert "border-radius: 0 !important" in css
    assert "border-radius: 11px !important" in css


def test_staging_v39_compacts_home_charts_and_section_rhythm():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'const upgradePreopenMarketCharts = () =>' in js
    assert 'marketIndexChartMarkup(item)' in js
    assert 'chartNode.classList.add("staging-preopen-chart")' in js
    assert 'upgradePreopenMarketCharts();' in js
    assert '.home-index-chart.staging-preopen-chart::after' in css
    assert 'min-height: 36px !important' in css
    assert 'flex-direction: row !important' in css
    assert '#home-view > .staging-home-response-section' in css
    assert '#home-view > #home-surge.staging-home-top50 .home-surge-head' in css
    assert 'min-height: 0 !important' in css
    assert 'margin: 0 0 16px !important' in css


def test_staging_v40_renews_discovery_hierarchy_and_responsive_cards():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'overview.className = "staging-discovery-overview"' in js
    assert 'rail.querySelector(\'[data-staging-view="ai-signals"]\')?.remove()' in js
    assert 'recommendationTitle.textContent = "지금 확인할 추천 종목"' in js
    assert 'description.className = "staging-recommend-description"' in js
    assert "새로 살 차례인지, 보유할 차례인지 먼저 확인해 보세요." in js
    assert '.staging-discovery-shortcuts.staging-shortcut-rail' in css
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr)) !important' in css
    assert '.staging-discovery-signal-copy > small' in css
    assert '#recommend-view .recommend-card:first-child' in css
    assert 'grid-column: 1 / -1 !important' in css
    assert '"score"' in css
    assert 'overflow-wrap: anywhere !important' in css


def test_staging_v41_uses_plump_icons_except_for_the_ai_signal_glyph():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text
    sprite_response = client.get("/assets/staging/streamline-plump-icons.svg")

    assert sprite_response.status_code == 200
    assert sprite_response.headers["content-type"].startswith("image/svg+xml")
    assert 'id="home"' in sprite_response.text
    assert 'id="interest"' in sprite_response.text
    assert 'id="discover"' in sprite_response.text
    assert 'id="feed"' in sprite_response.text
    assert 'data-source="money-graph-bar-increase--Streamline-Plump.svg"' in sprite_response.text
    assert "The AI signal glyph intentionally remains outside this sprite." in sprite_response.text

    assert 'const plump = (symbol) => Object.freeze({ symbol })' in js
    assert 'class="${classes}" viewBox="0 0 36 36"' in js
    assert '/assets/staging/streamline-plump-icons.svg?v=20260828-v64#${icon.symbol}' in js
    assert 'ai: \'<path d="M12 2.8 9.9 8.5' in js
    assert 'ai: plump(' not in js
    assert 'if (searchIcon) searchIcon.outerHTML = svg(icons.search)' in js
    for icon_name in ("search", "home", "interest", "discover", "feed", "back"):
        assert f'{icon_name}: plump("' in js

    assert "svg.staging-plump-icon > use" in css
    assert "fill: currentColor !important" in css
    assert "stroke: none !important" in css


def test_staging_v42_compacts_home_ai_signal_into_a_single_market_card():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'aiSignals.classList.add("staging-home-signal-section")' in js
    assert 'signalTicker.classList.add("staging-home-signal-card")' in js
    assert 'data-staging-home-signal-meta>시총 100위내 매매신호를 확인하세요</small>' in js
    assert 'const signalChevron = document.createElement("a");' in js
    assert 'signalChevron.href = "/dashboard?view=ai-signals";' in js
    assert 'signalChevron.dataset.aiSignalListLink = "true";' in js
    assert 'signalChevron.setAttribute("aria-label", "AI 시그널 전체 목록 보기");' in js
    assert 'signalChevron.setAttribute("aria-hidden", "true");' not in js
    assert 'new MutationObserver(syncHomeSignalMeta)' not in js
    assert 'staging-home-signal-icon' in js
    assert '${svg(icons.ai)}' in js
    assert '#home-view > #home-ai-signals.staging-home-signal-section' in css
    assert 'border-bottom: 12px solid var(--tc-band) !important' in css
    assert '.home-market-signal-ticker.staging-home-signal-card' in css
    assert 'grid-template-areas:' in css
    assert 'linear-gradient(118deg' in css
    assert '.staging-home-signal-chevron' in css
    assert '@media (max-width: 360px)' in css
    v131_rules = css.split(
        "/* v131 — make the home signal chevron actionable and align it with signal content. */",
        1,
    )[1]
    for contract in (
        'grid-template-columns: minmax(0, 1fr) 44px !important',
        '"meta ."',
        '"signal chevron" !important',
        'width: 44px !important',
        'height: 44px !important',
        'touch-action: manipulation !important',
        '.staging-home-signal-chevron:focus-visible',
    ):
        assert contract in v131_rules


def test_staging_v43_adds_ai_signal_page_hierarchy_and_toss_text_tabs():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert 'intro.className = "staging-ai-signals-intro"' in js
    assert '<span>시총 Top 100 에서</span>' in js
    assert '<h2 id="staging-ai-signals-title">AI는 무엇을 사고 팔까?</h2>' in js
    assert 'modeTabs.insertAdjacentElement("beforebegin", intro)' in js
    assert '#ai-signals-view .staging-ai-signals-intro' in css
    assert '#ai-signals-view .ai-signal-mode-tabs' in css
    assert 'border-radius: 0 !important' in css
    assert 'background: transparent !important' in css
    assert '.ai-signal-mode-tabs > button:is(.active, [aria-selected="true"])::after' in css


def test_staging_v45_recreates_toss_stock_chart_sessions_and_scrubbing():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        "STAGING_STOCK_CHART_PERIODS",
        'label: "1일"',
        'label: "1주"',
        'label: "3달"',
        'label: "1년"',
        'label: "5년"',
        'label: "전체"',
        "state.stockIntradayRows",
        "state.stockPriceRows",
        "state.currentDashboard?.quote",
        "stagingStockChartPhase",
        "stagingStockChartLiveSession",
        "STAGING_LIVE_INTRADAY_SESSIONS",
        '"nxt_pre_market"',
        '"nxt_after_market"',
        "stagingLiveIntradayRows",
        "cachedRows.set(liveRow.time",
        "observedIntradayStartMinute",
        "observedIntradayEndMinute",
        "observedIntradaySpan",
        "stagingIntradayMinute(row.endTime || row.time) - observedIntradayStartMinute",
        "staging-toss-chart-live-point",
        'data-chart-live="${liveSession}"',
        'scrubber.addEventListener("pointerdown"',
        'scrubber.addEventListener("pointermove"',
        'scrubber.setAttribute("aria-valuetext"',
        "upgradeStagingStockPriceChart();",
    ):
        assert contract in js


    for contract in (
        ".staging-toss-stock-chart",
        ".staging-toss-chart-line",
        ".staging-toss-chart-tooltip",
        ".staging-toss-chart-scrubber",
        ".staging-toss-chart-live-point",
        "@keyframes staging-chart-pulse-far",
        "@keyframes staging-chart-spark",
        "@media (prefers-reduced-motion: reduce)",
        "grid-template-columns: 32px repeat(6, minmax(0, 1fr)) 44px !important",
    ):
        assert contract in css


def test_staging_v53_adds_interactive_ohlc_candle_chart_toggle():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'let stagingSelectedChartType = "line"',
        "stagingAggregateCandleRows",
        'data-staging-chart-type-toggle',
        'chartTypeIcon.setAttribute("aria-label", "캔들 차트로 보기")',
        'stagingSelectedChartType === "candle" ? "line" : "candle"',
        'staging-toss-chart-candle is-${direction}',
        'data-staging-candle-value="open"',
        'data-staging-candle-value="high"',
        'data-staging-candle-value="low"',
        'data-staging-candle-value="close"',
        'aria-label="${periodConfig.label} ${phaseLabel} ${chartLabel}"',
        "시가 ${stagingChartNumber.format",
        "고가 ${stagingChartNumber.format",
        "저가 ${stagingChartNumber.format",
        "종가 ${priceText}",
    ):
        assert contract in js

    for contract in (
        ".staging-toss-chart-candle.is-rise",
        ".staging-toss-chart-candle.is-fall",
        ".staging-toss-chart-candle .wick",
        ".staging-toss-chart-candle .body",
        ".staging-toss-chart-tooltip-ohlc",
        '.staging-toss-chart-type-toggle[aria-pressed="true"]',
        "width: 174px !important",
        "transition: none !important",
    ):
        assert contract in css


def test_staging_v46_adds_home_hot_community_ranking_and_post_drilldown():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'hotCommunitySection.className = "staging-hot-community"',
        '<h2 id="staging-hot-community-title">핫한 커뮤니티</h2>',
        'data-hot-community-mode="surge">수익률 순</button>',
        'data-hot-community-mode="market_cap">시총 순</button>',
        'data-staging-hot-community-stocks aria-label="상위 15개 종목"',
        '/market/rankings?category=${hotCommunityState.mode}${modeQuery}&limit=15',
        '/community-feed?limit=5',
        '.slice(0, 15)',
        '.slice(0, 3)',
        'renderHotCommunityStocks();',
        'renderHotCommunityPosts(payload);',
        'await navigateToStock(code, `/dashboard/${encodeURIComponent(code)}`)',
        'data-stock-tab="community"',
    ):
        assert contract in js

    assert 'data-staging-hot-community-asof' not in js

    for contract in (
        "#home-view > .staging-hot-community",
        ".staging-hot-community-tabs",
        '.staging-hot-community-tabs > button:is(.active, [aria-selected="true"])::after',
        ".staging-hot-community-stocks",
        ".staging-hot-community-stock.active",
        ".staging-hot-community-post-list",
        ".staging-hot-community-more",
        "@keyframes staging-hot-community-shimmer",
    ):
        assert contract in css

    assert js.count("fetch(") == 1


def test_staging_v48_keeps_staging_stock_lists_on_the_shared_live_quote_stream():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'replaceQuoteStreamScope("staging-hot-community"',
        'replaceQuoteStreamScope("staging-recent-stocks"',
        'clearQuoteStreamScope("staging-hot-community")',
        'clearQuoteStreamScope("staging-recent-stocks")',
        "updateHotCommunityQuote",
        "updateRecentStockQuote",
        'for (const field of ["price", "change_rate", "volume", "trading_value", "market_cap"])',
        'item.rateText = formatPercent(changeRate)',
        'surface.dataset.liveQuoteState = "updating"',
        'window.addEventListener("visibilitychange"',
    ):
        assert contract in js

    assert "[data-hot-community-live-metric]" in css
    assert "[data-recent-stock-rate]" in css
    assert "@keyframes staging-live-quote-flash" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert js.count("fetch(") == 1


def test_staging_v49_renews_recommendation_cards_and_live_detail():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'detailButton.textContent = "자세히 보기"',
        'replaceQuoteStreamScope("staging-recommend-detail"',
        'clearQuoteStreamScope("staging-recommend-detail")',
        "recommendationDetailQuoteText",
        "decorateRecommendationCards",
        "decorateRecommendationDetail",
        "recommendationCustomerState",
        'scoreTrack.className = "staging-recommend-detail-score-track"',
        'quickMetrics.className = "staging-recommend-detail-quick-metrics"',
        'next.className = "staging-recommend-detail-next-check"',
        'content.replaceChildren(loader, ...[hero, action, levels, evidence, decision, source].filter(Boolean))',
        'const enteredToday = Boolean(',
        'item.recommendation_state === "entered_today"',
        'recommendationEntryDate === kstTodayToken()',
        'key: "new-buy-wait"',
        'key: "add-buy-wait"',
        'key: partial ? "partial-hold" : "hold"',
        'label: "신규 매수 대기"',
        'label: "추가 매수 대기"',
        'label: partial ? "일부 수익 확인 후 보유" : "보유 유지"',
        'label.textContent = "지금 어떻게 보면 되나요?"',
        'levels.querySelector(":scope > h2").textContent = "지금 판단에 필요한 가격"',
        'textContent = "추천 점수를 만든 핵심 수치"',
        'textContent = "추천 근거와 꼭 볼 위험"',
        'journeyTitle.textContent = "추천 뒤 AI 판단 변화"',
        'textContent: recommendationStillVisible ? "왜 추천에 들어왔나요?" : "추천 당시 왜 들어왔나요?"',
        'addConditionMetric("추천 기준", recommendationStillVisible ? "통과" : "추천 당시 통과")',
        'addConditionMetric("AI 전략 매수가"',
        'addConditionMetric("현재가"',
        'addConditionMetric("추가 매수", customerState.additionalBuyLabel)',
        'scoreLevelRow?.querySelector("b")',
        'scoreLevel.textContent = "추천 기준 통과"',
        'scoreGuide.textContent = `· ${customerState.guide}`',
        'scoreLevelRow?.classList.add("qualified")',
        "추천 점수는 기준을 통과한 종목끼리 비교한 순위예요.",
        "item.current_price = price",
        "item.ai_trade_signal.current.price = price",
        "item?.ai_trade_signal?.current?.price,",
        "price: initialPrice === undefined ? null : Number(initialPrice)",
        "condition_price: item?.condition_price ?? item?.price",
        "const conditionPrice = Number(item.condition_price ?? item.price)",
        '["초기 위험선과 1차 계단형 수익을 나눠 확인하는 단계 기준", "처음 정한 위험 기준과 첫 수익 확인 기준"]',
        "recommendationDetailFriendlyText(summary.next_check)",
        'journeyStage.textContent = customerState.label',
        '.replaceAll("관찰 후보", "추천 기준 통과")',
        'document.getElementById("recommend-status"),',
        "지금 새로 매수를 검토할 종목이 없어요.",
        'content.dataset.recommendationState = recommendationStillActive',
        'content.dataset.customerState = customerState.key',
        '? "entered-today"',
        "오늘의 신규 추천 목록에는 포함되지 않아요",
        "추천 당시 통과",
        'toggle.dataset.stagingRecommendHistoryToggle = "true"',
        'help.setAttribute("aria-expanded", String(help.classList.contains("open")))',
        'if (event.key !== "Escape") return',
    ):
        assert contract in js
    assert "item.price = price" not in js

    for contract in (
        ".recommend-score-help:not(.open)::after",
        ".staging-contextual-topbar.is-recommend-live",
        ".staging-recommend-detail-score-track",
        ".staging-recommend-detail-quick-metrics",
        ".staging-recommend-detail-next-check",
        ".staging-recommend-detail-journey",
        ".staging-recommend-history-toggle",
        ".recommend-signal-timeline-item[hidden]",
        "overflow-wrap: anywhere !important",
        "word-break: keep-all !important",
        "@media (max-width: 360px)",
    ):
        assert contract in css

    assert js.count("fetch(") == 1


def test_staging_v47_replaces_discovery_signal_with_recent_stock_history():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'const RECENT_STOCKS_KEY = "secret-note-staging-recent-stocks-v1"',
        'recentStocksPreview.className = "staging-recent-stocks-preview"',
        '<h3 id="staging-recent-stocks-preview-title">최근 본 종목</h3>',
        'data-staging-recent-more>더 보기',
        'url.search = "?view=search&panel=recent-stocks"',
        'recentStocksPage.id = "staging-recent-stocks-view"',
        'title: "최근 본 종목"',
        'data-recent-stock-open',
        'data-recent-stock-remove',
        'captureCurrentRecentStock();',
        'window.history.back();',
        'contextualBack?.focus()',
    ):
        assert contract in js

    assert 'signal.className = "staging-discovery-signal"' not in js
    assert "syncSignalMirror" not in js

    for contract in (
        ".staging-recent-stocks-preview",
        ".staging-recent-stocks-rail",
        ".staging-recent-stock-card",
        "#staging-recent-stocks-view",
        ".staging-recent-stock-row",
        ".staging-recent-stock-row-open",
        "grid-template-columns: minmax(0, 1fr) 44px !important",
        "min-width: 44px !important",
        "overflow-wrap: anywhere !important",
        "@media (max-width: 360px)",
    ):
        assert contract in css

    assert js.count("fetch(") == 1


def test_staging_v50_builds_inline_feed_content_calendar_and_editorial_detail():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'data-staging-feed-mode="news"',
        'data-staging-feed-mode="content"',
        'data-staging-feed-mode="calendar"',
        'newsPanel.dataset.stagingFeedPanel = "news"',
        'contentPanel.dataset.stagingFeedPanel = "content"',
        'calendarPanel.dataset.stagingFeedPanel = "calendar"',
        "아침, 점심, 장 마감 후에 꼭 볼 시장 소식",
        'data-staging-editorial-feed',
        'data-staging-content-open',
        'fetchJsonCached("/market/trends?days=14"',
        'Array.from({ length: 18 }',
        'data-staging-calendar-date',
        'data-staging-calendar-today',
        'let stagingKoreaCalendarPayload = null;',
        'fetchJsonCached("/market/calendar?days=14"',
        'Array.isArray(koreaPayload.events)',
        'tag.textContent = "#비밀노트 리서치"',
        'author.className = "staging-article-author"',
        'syncStagingFeed();',
        'decorateStagingBriefingArticle();',
    ):
        assert contract in js

    for contract in (
        ".staging-feed-modes",
        "grid-template-columns: repeat(3, minmax(0, 1fr)) !important",
        ".staging-editorial-post",
        ".staging-editorial-art",
        ".staging-feed-news-panel .thread-item",
        ".staging-calendar-day",
        ".staging-calendar-event.is-holiday",
        ".staging-calendar-today",
        ".staging-editorial-detail .morning-money-overview",
        ".staging-article-author",
        ".staging-article-section-index",
        "word-break: keep-all !important",
        "@media (max-width: 359px)",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in css

    assert js.count("fetch(") == 1


def test_staging_calendar_serves_official_korean_events_without_upstream(monkeypatch):
    release = staging_module.datetime.now(staging_module.KST).replace(tzinfo=None)

    async def fake_calendar(*, days):
        assert days == 14
        return {
            "as_of": release.isoformat(),
            "window_start": release.isoformat(),
            "window_end": release.isoformat(),
            "events": [
                {
                "id": "kr-bsi-esi-test",
                "starts_at": release.isoformat(),
                "category": "한국",
                "title": "한국 BSI·ESI",
                "expected_impact": "국내 경기심리를 점검하는 지표",
                "timeline": [],
                }
            ],
            "past_events": [],
        }

    monkeypatch.setattr(
        staging_module,
        "build_korea_market_calendar",
        fake_calendar,
    )
    response = TestClient(staging_app).get("/staging-data/korea-calendar?days=14")

    assert response.status_code == 200
    rows = [*response.json()["past_events"], *response.json()["events"]]
    assert rows == [
        {
            "id": "kr-bsi-esi-test",
            "starts_at": release.isoformat(),
            "category": "한국",
            "title": "한국 BSI·ESI",
            "expected_impact": "국내 경기심리를 점검하는 지표",
            "timeline": [],
        }
    ]
    assert response.headers["x-staging-data-source"] == "bank-of-korea-statistical-calendar"


def test_staging_v51_keeps_cached_market_route_and_ai_signal_rows_inside_canvas():
    dashboard_js = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")
    css = (ROOT / "app/static/staging/toss-fidelity.css").read_text(encoding="utf-8")

    cached_branch = dashboard_js.split(
        "if (!force && cached?.payload && Date.now() - (cached.savedAt || 0) <= ttlMs) {",
        1,
    )[1].split("closeMarketQuoteStreams();", 1)[0]
    assert "syncMarketRankingSnapshotUrl();" in cached_branch
    assert cached_branch.index("syncMarketRankingSnapshotUrl();") < cached_branch.index(
        "renderRankings(cached.payload);"
    )

    assert (
        'body[data-staging-ia="tds-video"] #ai-signals-view .home-ai-signal-supporting {\n'
        "  width: auto !important;\n"
        "  min-width: 0 !important;"
    ) in css


def test_staging_v52_renews_interest_hub_with_flat_tabs_and_dark_readable_lists():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'let syncStagingWatchlist = () => {};',
        'listHead.className = "staging-watchlist-list-head"',
        '<div><span>실시간 시세</span><h2>내 관심종목</h2></div>',
        'watchlistNewsTitle.textContent = "종목별 최신 소식"',
        'briefingEyebrow.textContent = "오늘의 관심 브리핑"',
        'actionLabel.textContent = "지금 확인할 것"',
        'createStockLogoFrame(button.dataset.code, "staging-watch-news-logo")',
        'createStockLogoFrame(card.dataset.code, "staging-pin-logo")',
        'const resetPortfolioScroll = () => {',
        'window.scrollTo({ top: 0, behavior: "auto" })',
        'syncStagingWatchlist();',
    ):
        assert contract in js

    assert 'signal.className = "staging-watch-signal"' not in js

    for contract in (
        "v52 — Toss-style interest hub",
        "#portfolio-view .watchlist-content-tabs",
        "border-radius: 0 !important",
        "#watchlist-view .watch-v2-briefing",
        "background: light-dark(#ffffff, #1f1e24) !important",
        ".staging-watchlist-list-head",
        "#watchlist-view .watch-v2-stock-row",
        ".staging-watch-news-logo",
        ".trend-watch-news-item > strong",
        "white-space: normal !important",
        ".portfolio-tab-panel[hidden]",
        "#portfolio-tracking-panel .recommend-track-card",
        "#portfolio-tracking-panel .staging-pin-logo",
        "#portfolio-tracking-panel .recommend-track-detail-toggle",
        "@media (max-width: 359px)",
    ):
        assert contract in css

    assert js.count("fetch(") == 1


def test_staging_v53_removes_interest_shortcut_context_and_stock_detail_footer():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'document.querySelector("#watchlist-view .watch-v2-briefing-context")?.remove();' in js
    assert 'watchlistBody?.querySelectorAll(".watch-v2-row-footer")' in js
    assert "footer.remove();" in js
    assert "v53 — interest density cleanup" in css
    for selector in (
        "> .portfolio-tab-panel > .staging-watch-signal",
        "#watchlist-view .watch-v2-briefing-context",
        "#watchlist-view .watch-v2-row-footer",
    ):
        assert selector in css

    assert js.count("fetch(") == 1


def test_staging_v54_removes_light_chart_example_and_search_suggestion_surfaces():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        "v54 — remove the remaining light-theme surfaces from chart analysis",
        "#chart-view .chart-example-future-zone",
        "fill: light-dark(#eef6ff, #1b2634) !important",
        "#chart-stock-search-suggestions.discovery-suggestions",
        "background: light-dark(#ffffff, #1d1c21) !important",
        "#chart-stock-search-suggestions .discovery-suggestion-item",
        "border-bottom: 1px solid var(--tc-line) !important",
        "background: light-dark(#f7f8fa, #29282f) !important",
        'aria-selected="true"',
        "color: var(--tc-text) !important",
    ):
        assert contract in css

    assert (ROOT / "app/static/staging/toss-ia.js").read_text(
        encoding="utf-8"
    ).count("fetch(") == 1


def test_staging_v56_uses_17px_navigation_titles_with_live_detail_exceptions():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert "--tds-size-navigation-title: 17px" in css
    assert "v56 — one 17px navigation-title scale" in css
    assert (
        'body[data-staging-ia="tds-video"] .staging-market-context > strong {'
        in css
    )
    assert "#staging-contextual-topbar:not(.is-recommend-live)" in css
    assert ".stock-etf-dividend-commandbar" in css
    assert "font-size: var(--tds-size-navigation-title) !important" in css
    assert 'contextualTopbar.id = "staging-contextual-topbar"' in client.get(
        "/assets/staging/toss-ia.js"
    ).text

    v56_rules = css.split(
        "/* v56 — one 17px navigation-title scale, except live stock/recommendation headers. */",
        1,
    )[1].split(
        "/* v57 — 20px root-tab titles and one shared stock-detail content gutter. */",
        1,
    )[0]
    assert ".stock-v3-command-title" not in v56_rules
    assert "#staging-contextual-topbar.is-recommend-live" in v56_rules
    assert "font-size: 15px !important" in v56_rules


def test_staging_v57_uses_20px_root_titles_and_one_stock_content_gutter():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert "--tds-size-primary-navigation-title: 20px" in css
    assert "v57 — 20px root-tab titles and one shared stock-detail content gutter" in css

    v57_rules = css.split(
        "/* v57 — 20px root-tab titles and one shared stock-detail content gutter. */",
        1,
    )[1]
    assert ".staging-market-context > strong" in v57_rules
    assert "font-size: var(--tds-size-primary-navigation-title) !important" in v57_rules
    assert "#stock-summary-section" in v57_rules
    assert "> #stock-home-chart-analysis.stock-v3-section" in v57_rules
    assert "padding-right: 0 !important" in v57_rules
    assert "padding-left: 0 !important" in v57_rules
    assert ".chart-pattern-analysis" in v57_rules
    assert ".chart-forecast-reasons" in v57_rules
    assert "padding-right: var(--tc-gutter) !important" in v57_rules
    assert "padding-left: var(--tc-gutter) !important" in v57_rules


def test_staging_v58_replaces_five_daily_closes_with_dense_real_week_chart():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'key: "1W", label: "1주", count: Number.POSITIVE_INFINITY',
        "STAGING_WEEK_CHART_TTL_MS = 30_000",
        "stagingNormalizeWeekChart",
        "ensureStagingWeekChartData",
        "stagingStockWeeklyRows",
        "/stocks/${encodeURIComponent(normalizedCode)}/week-chart",
        'data-chart-source="naver-week-ten-minute"',
        'isDenseWeek ? " is-week" : ""',
        "weekEntry.referencePrice",
        "최근 5거래일 시세를 불러오고 있어요.",
    ):
        assert contract in js

    for contract in (
        ".staging-toss-stock-chart.is-week .staging-toss-chart-line",
        ".staging-toss-week-chart-status",
        "@keyframes staging-week-chart-spin",
    ):
        assert contract in css

    assert staging_module.STAGING_WEEK_CHART_PATTERN.fullmatch(
        "/staging-data/stocks/005930/week-chart"
    )
    assert not staging_module.STAGING_WEEK_CHART_PATTERN.fullmatch(
        "/staging-data/stocks/not-a-code/week-chart"
    )


def test_staging_v58_week_chart_relay_stays_same_origin(monkeypatch):
    payload = b'{"periodType":"week","priceInfos":{"20260827":[]}}'

    async def fake_week_chart(_scope):
        return 200, [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(payload)).encode("ascii")),
            (b"x-staging-theme", THEME_VERSION.encode("ascii")),
            (b"x-staging-data-source", b"naver-finance-public-week-chart"),
        ], payload

    monkeypatch.setattr(staging_module, "_read_staging_week_chart", fake_week_chart)
    response = TestClient(staging_app).get(
        "/staging-data/stocks/005930/week-chart"
    )

    assert response.status_code == 200
    assert response.json()["periodType"] == "week"
    assert response.headers["x-staging-theme"] == THEME_VERSION
    assert response.headers["x-staging-data-source"] == "naver-finance-public-week-chart"


def test_staging_v59_flattens_selected_company_and_moves_simple_search_to_stock_nav():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    sprite = client.get("/assets/staging/streamline-plump-icons.svg").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'document.body.dataset.stagingFidelity = "20260829-v66"' in js
    assert 'stockSearchButton.classList.add("staging-stock-nav-search")' in js
    assert '<button type="button" data-staging-stock-search' not in js

    search_symbol = sprite.split('<symbol id="search"', 1)[1].split("</symbol>", 1)[0]
    assert "magnifier-only" in search_symbol
    assert search_symbol.count("<path") == 1

    v59_rules = css.split(
        "/* v59 — flat community selection, paired header actions, and stock-nav search. */",
        1,
    )[1]
    assert ".staging-hot-community-stock.active" in v59_rules
    assert "border-color: transparent !important" in v59_rules
    assert "background: transparent !important" in v59_rules
    assert ".staging-top-actions > button" in v59_rules
    assert "place-items: center !important" in v59_rules
    assert "grid-template-columns: 44px minmax(0, 1fr) 44px 44px !important" in v59_rules
    assert "#stock-view .stock-v3-search" in v59_rules
    assert "grid-row: 1 !important" in v59_rules
    assert "#stock-view .stock-v3-star" in v59_rules
    assert "grid-column: 4 !important" in v59_rules


def test_staging_v60_uses_watchlist_badges_and_opens_stock_search_in_place():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    for contract in (
        'stockSearchButton.setAttribute("aria-label", "종목 검색 열기")',
        'stockSearchButton.setAttribute("aria-expanded", "false")',
        'leadingIcon.className = "staging-stock-search-leading"',
        'closeSearch.className = "staging-stock-search-close"',
        'stockSearchForm.classList.add("expanded")',
        'stockSearchInput.focus()',
        'new MutationObserver(syncStockSearchState)',
    ):
        assert contract in js
    assert 'stockSearchButton.type = "button"' not in js
    assert 'window.location.assign(url)' not in js

    v60_rules = css.split(
        "/* v60 — compact watchlist badges and an in-place stock search window. */",
        1,
    )[1]
    for contract in (
        "#portfolio-view .watchlist-content-tabs",
        "border-radius: 999px !important",
        "#stock-view .stock-v3-search.expanded .search-box",
        "visibility: visible !important",
        "#stock-view .staging-stock-search-leading",
        "#stock-view #stock-suggestions.suggestions",
        "background: light-dark(#f7f8fa, #242329) !important",
    ):
        assert contract in v60_rules
    assert "content: none !important" in v60_rules


def test_staging_v61_home_community_selection_only_scrolls_the_horizontal_rail():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'document.body.dataset.stagingFidelity = "20260829-v66"' in js
    assert 'activeRect.left < railRect.left + edgeInset' in js
    assert 'activeRect.right > railRect.right - edgeInset' in js
    assert 'window.setTimeout(() => revealActiveStock("auto"), 320)' in js
    assert 'hotCommunityStocks.scrollTo({' in js
    assert 'top: hotCommunityStocks.scrollTop' in js
    hot_community_render = js.split("const renderHotCommunityStocks = (options = {}) => {", 1)[1].split(
        "const renderHotCommunityFeedStatus =", 1
    )[0]
    assert ".scrollIntoView(" not in hot_community_render


def test_staging_v62_content_feed_uses_one_complete_edition_for_each_publication():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    dashboard_source = client.get("/dashboard-app-v170.js").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'document.body.dataset.stagingFidelity = "20260829-v66"' in js
    assert 'fetchJsonCached("/briefings/morning-money/history?days=7"' in js
    assert "let editorialEditions = [];" in js
    assert 'data-staging-content-key="${escapeText(payload.edition_key)}"' in js
    assert "핵심 소식 ${formatNumber(payload.selected_news_count || 0)}건 전체 읽기" in js
    assert "window.openMorningMoneyBriefingEdition({" in js
    assert "preliminary_buys: stagingPreliminaryBuysForEdition(selected)" in js
    assert "preliminary_buys_available: stagingPreliminaryBuyDataAvailableForEdition(selected)" in js
    assert "confirmed_buys: stagingConfirmedBuysForEdition(selected)" in js
    assert ".staging-editorial-day-head" in css
    assert "one complete briefing per publication" in css
    assert "function openMorningMoneyBriefingEdition(payload = null)" in dashboard_source
    assert "state.morningMoneyBriefingSelection = clonePayload(payload);" in dashboard_source

    render_block = js.split("const renderEditorialFeed = () => {", 1)[1].split(
        "const renderCalendar = () => {",
        1,
    )[0]
    assert ".flatMap(" not in render_block
    assert ".slice(0, 6)" not in render_block
    assert "group.items.map((payload)" in render_block


def test_staging_v63_hot_community_matches_toss_auto_rotation_and_compact_structure():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'document.body.dataset.stagingFidelity = "20260829-v66"' in js
    for contract in (
        "const HOT_COMMUNITY_ROTATION_MS = 5_000",
        "hotCommunityState.rotationTimer = window.setTimeout",
        'hotCommunitySection.dataset.autoAdvanceMs = String(HOT_COMMUNITY_ROTATION_MS)',
        'selectHotCommunityItem(nextItem, { source: "auto", scrollBehavior: "smooth" })',
        'const hotCommunityObserver = new IntersectionObserver',
        'hotCommunityReducedMotion?.addEventListener?.("change", scheduleHotCommunityRotation)',
        "const prefetchHotCommunityFeeds =",
        "hotCommunityState.feedPromises",
        'hotCommunityStocks?.addEventListener("pointerup"',
        'hotCommunityStocks?.addEventListener("keydown"',
        'event.target.closest("[data-hot-community-code]")',
        'hotCommunityPosts.setAttribute("aria-live", options.announce ? "polite" : "off")',
        'avatar.className = "staging-hot-community-post-avatar"',
        "syncHotCommunityRotation();",
    ):
        assert contract in js

    v63_rules = css.split(
        "/* v63 — Toss-like 5-second hot-community carousel and compact content rhythm. */",
        1,
    )[1]
    for contract in (
        ".staging-hot-community-stock.active",
        "width: 156px !important",
        "width: 54px !important",
        ".staging-hot-community-rank",
        "display: none !important",
        ".staging-hot-community-post-avatar",
        ".staging-hot-community-posts.is-changing",
        "@keyframes staging-hot-community-content-in",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in v63_rules

    cascade_seal = css.split(
        "/* v63 cascade seal — preserve the compact Toss carousel after older generic rules. */",
        1,
    )[1]
    assert "#staging-hot-community-title" in cascade_seal
    assert "font-size: 21px !important" in cascade_seal
    assert ".staging-hot-community-stock:not(.active)" in cascade_seal
    assert "width: 44px !important" in cascade_seal


def test_staging_v66_removes_residual_dark_surfaces_and_sheet_focus_ring():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v66_rules = css.split(
        "/* v66 — remove residual fixed-dark surfaces from the adaptive theme. */",
        1,
    )[1]
    for contract in (
        ".staging-home-ranking-watch:not(.active) svg.staging-plump-icon > use",
        ".stock-v3-star:not(.active) svg.staging-plump-icon > use",
        "fill: transparent !important",
        "fill-opacity: 0 !important",
        ".trend-calendar-day.active",
        "background: light-dark(#eef0f3, #2f2e35) !important",
        ".stock-v3-flow-focus-card",
        ".stock-sector-margin-focus-card",
        ".stock-bar-value-tooltip",
        "background: light-dark(#ffffff, #111827) !important",
        ".push-notification-sheet-card",
        "):is(:focus, :focus-visible)",
        "outline: 0 !important",
    ):
        assert contract in v66_rules


def test_staging_v67_watchlist_metrics_match_pinned_stock_metric_card():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v67_rules = css.split(
        "/* v67 — make watchlist metrics use the pinned-stock metric-card language. */",
        1,
    )[1]
    for contract in (
        "#watchlist-view .watch-v2-metrics",
        "overflow: hidden !important",
        "border: 1px solid light-dark(#e5e8eb, #29292f) !important",
        "border-radius: 12px !important",
        "background: light-dark(transparent, #17171a) !important",
        "background: light-dark(#ffffff, #1f1e24) !important",
        ".watch-v2-metrics > div:nth-child(odd)",
        ".watch-v2-metrics > div:nth-child(-n + 2)",
        ".watch-v2-metrics dt",
        ".watch-v2-metrics dd",
        ".watch-v2-metrics dd.positive",
        ".watch-v2-metrics dd.negative",
    ):
        assert contract in v67_rules


def test_staging_v68_softens_only_light_theme_elevation():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v68_rules = css.split(
        "/* v68 — soften light-theme elevation while preserving dark-theme depth. */",
        1,
    )[1]
    for contract in (
        ".morning-money-popover",
        "0 8px 22px light-dark(rgba(25, 31, 40, 0.07), transparent)",
        "0 16px 40px light-dark(transparent, rgba(0, 0, 0, 0.34))",
        "#push-notification-sheet .push-notification-sheet-actions",
        "0 -3px 12px light-dark(rgba(25, 31, 40, 0.05), transparent)",
        "0 -8px 24px light-dark(transparent, rgba(0, 0, 0, 0.18))",
        ".staging-bottom-nav-scrim",
        "light-dark(#f7f8fa, #0b0b0d) 100%",
        ".bottom-nav",
        "0 -4px 14px light-dark(rgba(25, 31, 40, 0.04), transparent)",
        "0 18px 42px light-dark(transparent, rgba(0, 0, 0, 0.64))",
        ".staging-service-sheet-card",
        ".discovery-suggestions",
        ".staging-calendar-today",
        ".stock-v3-flow-focus-card",
    ):
        assert contract in v68_rules


def test_staging_v69_rolls_the_header_through_major_market_indices():
    client = TestClient(staging_app)
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    for contract in (
        'data-staging-index-ticker aria-live="off"',
        'const STAGING_MARKET_CONTEXT_CODES = ["KOSPI", "KOSDAQ", "NASDAQ", "SP500", "DOW", "SOX"]',
        'NASDAQ: "나스닥"',
        'SP500: "S&P500"',
        "const STAGING_MARKET_CONTEXT_ROTATION_MS = 4_000",
        'window.matchMedia?.("(prefers-reduced-motion: reduce)")',
        "!document.hidden",
        "rootViews.has(document.body.dataset.view || \"home\")",
        "marketContextIndex = (marketContextIndex + 1) % cards.length",
        'marketContext.dataset.autoAdvance = "scheduled"',
        "renderMarketContextCard(cards[marketContextIndex], { animate: true })",
        'window.addEventListener("visibilitychange"',
    ):
        assert contract in js

    v69_rules = css.split(
        "/* v69 — roll the global market context through the major indices. */",
        1,
    )[1]
    for contract in (
        ".staging-index-context.is-rolling",
        "animation: staging-market-index-roll-in 240ms cubic-bezier(0.2, 0.8, 0.2, 1)",
        "@keyframes staging-market-index-roll-in",
        "transform: translateY(7px)",
        "@media (prefers-reduced-motion: reduce)",
        "animation: none !important",
    ):
        assert contract in v69_rules


def test_staging_v71_aligns_root_navigation_content_on_one_centerline():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v71_rules = css.split(
        "/* v71 — align every root-tab title, market ticker, and action icon on one row. */",
        1,
    )[1]
    for contract in (
        ".app-topbar:not(.is-staging-contextual)",
        ".staging-market-context",
        "top: 50% !important",
        "bottom: auto !important",
        "min-height: 44px !important",
        "align-items: center !important",
        "transform: translateY(-50%) !important",
        ".staging-market-context > strong",
        "line-height: 1.25 !important",
        ".staging-index-context",
        ".staging-top-actions",
        "height: 44px !important",
    ):
        assert contract in v71_rules


def test_staging_v72_stabilizes_home_signal_alignment_and_section_rhythm():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v72_rules = css.split(
        "/* v72 — stabilize the home AI signal card and keep one section divider. */",
        1,
    )[1]
    for contract in (
        "padding-bottom: 12px !important",
        "border-bottom: 0 !important",
        "min-height: 108px !important",
        "grid-template-columns: minmax(0, 1fr) 24px !important",
        "grid-template-rows: auto auto !important",
        "display: grid !important",
        "align-content: start !important",
        "overflow-wrap: normal !important",
        "padding-top: 22px !important",
        "border-top: 1px solid var(--tc-line) !important",
        "@media (max-width: 360px)",
        "min-height: 126px !important",
        "min-height: 64px !important",
    ):
        assert contract in v72_rules


def test_staging_v74_removes_exchange_metadata_and_aligns_ai_signal_rows():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert 'codeLine.className = "staging-ai-code"' not in js
    assert 'identity?.querySelector(".staging-ai-code")?.remove()' in js

    v74_rules = css.split(
        "/* v74 — remove exchange metadata and align AI signal ListRows to one grid. */",
        1,
    )[1]
    for contract in (
        "min-height: 104px !important",
        "grid-template-columns: 42px minmax(0, 1fr) auto 16px !important",
        "grid-template-rows: auto auto !important",
        "display: contents !important",
        "grid-row: 1 / span 2 !important",
        "grid-column: 2 / 4 !important",
        "margin: 0 !important",
        ".staging-ai-code",
        "display: none !important",
        "@media (max-width: 380px)",
        "grid-template-columns: 40px minmax(0, 1fr) auto 16px !important",
    ):
        assert contract in v74_rules


def test_promoted_ai_signal_copy_preserves_sell_pending_and_confirmation_semantics():
    js = TestClient(staging_app).get("/assets/staging/toss-ia.js").text
    start = js.index("  const compactAiSignalLabel")
    end = js.index("  const selectAiSignalSummaryMetrics", start)
    compact_source = js[start:end]
    script = f"""
{compact_source}
const labels = [
  "2차 수익확정 대기",
  "2차 수익확정·잔여 50% 보유",
  "부분 매도 대기(2차)",
  "부분 수익 확정(2차)",
  "전량 매도 대기",
  "전량 매도",
  "전량 매도 확정",
];
console.log(JSON.stringify(labels.map(compactAiSignalLabel)));
"""

    completed = subprocess.run(
        ["node", "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == [
        "부분 매도 대기(2차)",
        "부분 수익 확정(2차)",
        "부분 매도 대기(2차)",
        "부분 수익 확정(2차)",
        "전량 매도 대기",
        "전량 매도 확정",
        "전량 매도 확정",
    ]
    assert "수익 확정" not in json.loads(completed.stdout)


def test_staging_v75_uses_compact_adaptive_pull_refresh_feedback():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    v75_rules = css.split(
        "/* v75 — compact, theme-aware pull-to-refresh feedback. */",
        1,
    )[1]
    for contract in (
        "top: calc(62px + env(safe-area-inset-top, 0px)) !important",
        "width: max-content !important",
        "min-width: 0 !important",
        "max-width: calc(100vw - 40px) !important",
        "min-height: 38px !important",
        "background: light-dark(",
        "color: var(--tc-text) !important",
        "#pull-refresh-indicator #pull-refresh-label",
        "font-size: 13px !important",
        "width: 16px !important",
        ".pull-refresh-indicator.refreshing",
        ".pull-refresh-indicator.complete",
        "background: var(--tc-success) !important",
        ".pull-refresh-indicator.error",
        "color: var(--tc-danger) !important",
        "@media (max-width: 980px)",
    ):
        assert contract in v75_rules


def test_staging_v77_shortcuts_center_discovery_icon_label_groups():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    v77_shortcut_rules = css.split(
        "/* v77-shortcuts — center every discovery shortcut icon-label group on one shared grid. */",
        1,
    )[1]
    for contract in (
        ".staging-discovery-shortcuts.staging-shortcut-rail > button",
        "height: 84px !important",
        "grid-template-columns: minmax(0, 1fr) !important",
        "grid-template-rows: 32px 18px !important",
        "align-content: center !important",
        "align-items: center !important",
        "justify-items: center !important",
        "padding: 12px 8px !important",
        "> button > span",
        "place-items: center !important",
        "line-height: 0 !important",
        "> span > svg",
        "display: block !important",
        "> button > strong",
        "justify-content: center !important",
        "line-height: 18px !important",
        "text-align: center !important",
    ):
        assert contract in v77_shortcut_rules


def test_staging_v130_removes_obsolete_home_ai_response_leading_divider():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    dashboard_css = client.get("/assets/dashboard/styles.css").text

    assert THEME_VERSION == "20260828-tds-adaptive-v77-shortcuts"
    assert 'id="home-ai-response-factors"' not in shell
    assert 'id="home-ai-response-watch-label">관심종목 영향도<' in shell
    v130_rules = css.split(
        "/* v130 — remove the obsolete leading divider after ranked factors were retired. */",
        1,
    )[1]
    assert "#home-ai-response" in v130_rules
    assert "> .home-ai-response-personal" in v130_rules
    assert "border-top: 0 !important" in v130_rules
    assert "contextual-safe-area-v128-stock-search-v129-ai-response-v130-home-signal-action-v131-notification-sheet-v132-ai-signal-spacing-v133" in shell
    personal_rules = dashboard_css.split(
        'body:not([data-view="stock"]) .home-ai-response-personal {',
        1,
    )[1].split("}", 1)[0]
    interest_row_rules = dashboard_css.split(
        'body:not([data-view="stock"]) .home-ai-interest-row {',
        1,
    )[1].split("}", 1)[0]
    assert "border-top: 0;" in personal_rules
    assert "border-top: 1px solid #eceef2;" in interest_row_rules


def test_staging_v141_opens_a_beginner_friendly_stock_response_in_a_dedicated_page():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    js = client.get("/assets/staging/toss-ia.js").text
    logic = client.get("/assets/staging/ai-stock-response-logic.js").text

    assert "multi-signal-response-v137-discovery-search-contrast-v138" in shell
    assert "ai-response-beginner-v141-semantic-focus-v142" in shell
    assert "/assets/staging/ai-stock-response-logic.js?v=" in shell
    assert 'const STAGING_AI_STOCK_RESPONSE_VIEW = "ai-stock-response";' in js
    assert 'personalHeader.hidden = true;' in js
    assert 'personalStatus.setAttribute("aria-hidden", "true")' in js
    assert 'stagingAiStockResponsePage.id = "staging-ai-stock-response-view";' in js
    assert 'data-staging-response-action' in js
    assert 'data-staging-response-context' in js
    assert 'data-staging-response-reason' in js
    assert 'data-staging-response-direction' in js
    assert 'data-staging-response-direction-guide' in js
    assert 'data-staging-response-data-state' in js
    assert 'data-staging-response-coverage-label' in js
    assert 'data-staging-response-score' in js
    assert 'data-staging-response-confidence' in js
    assert 'data-staging-response-coverage' in js
    assert 'data-staging-response-key-reasons' in js
    assert 'data-staging-response-metrics' in js
    assert 'data-staging-response-warnings' in js
    assert 'data-staging-response-next' in js
    assert 'data-staging-response-live-price' in js
    assert 'data-staging-response-live-rate' in js
    assert 'data-staging-response-decision-plan' in js
    assert 'data-staging-response-retry' in js
    assert 'data-staging-response-stock-link' in js
    assert 'data-staging-response-announcement' in js
    page_markup = js.split('stagingAiStockResponsePage.innerHTML = `', 1)[1].split('`;', 1)[0]
    expected_order = (
        "이 화면이 열린 이유",
        "쉽게 풀어보면",
        "왜 이렇게 보나요?",
        "앞으로 이렇게 확인하세요",
        "왜 이렇게 봤나요?",
        "점수와 계산 방법 알아보기",
    )
    positions = [page_markup.index(label) for label in expected_order]
    assert positions == sorted(positions)
    assert "판단이 바뀌려면" not in page_markup
    assert "판단 신뢰도" not in page_markup
    assert "지금 판단" in page_markup
    assert "신호 방향" not in page_markup
    assert "긍정·주의 신호를 비교하고 있어요" in page_markup
    assert "적중률이나 주가 상승 확률이 아니에요" in page_markup
    assert "실제 계좌·주문 내역과 자동 연동되지 않아요" in page_markup
    assert "대응 참고 정보예요" in page_markup
    assert 'data-staging-response-metrics aria-live=' not in page_markup
    for friendly_label in (
        "가격 흐름",
        "외국인·기관 매매",
            "회사 공식 공시",
            "최근 뉴스 분위기",
            "증권사 리포트",
            "금리·환율·업종 환경",
    ):
        assert friendly_label in js
    assert 'window.SecretNoteAiStockResponse' in js
    assert '/quant-signals' in js
    assert 'include_profile=0&include_live=0' in js
    assert '/home-context?flow_limit=1500' in js
    assert '"/market/impact"' in js
    assert 'const WEIGHTS = Object.freeze({' in logic
    for contract in (
        'chart: 25',
        'flow: 25',
        'disclosure: 15',
        'news: 10',
        'research: 15',
        'market: 10',
    ):
        assert contract in logic
    assert 'stance = "신규 접근 보류";' in logic
    assert 'stance = "정보 확인 우선";' in logic
    assert 'const conflict = positiveMetrics.length > 0 && negativeMetrics.length > 0;' in logic
    assert 'force ? 0 : STAGING_AI_STOCK_RESPONSE_CACHE_MS' in js
    assert 'stagingAiStockResponsePage?.dataset.responseLoaded !== "true"' in js
    assert 'const perspective = stagingAiStockResponsePerspectiveCopy(result, investorState);' in js
    assert 'value: "조금 더 지켜봐요"' in js
    assert 'guide: "주의 신호가 긍정 신호보다 조금 많아요"' in js
    assert 'stagingAiStockResponseText("[data-staging-response-direction-guide]", perspective.guide);' in js
    assert '["수급이", "외국인·기관 매매가"]' in js
    assert 'if (/확인$/.test(text)) text = `${text}해 주세요.`;' in js
    assert 'row.setAttribute("aria-label", `${detail.name} AI 종목 대응 보기`);' in js
    listener = js.split('  const decorateHomeAiStockResponseRows = () => {', 1)[1]
    listener = listener.split('  const upgradePreopenMarketCharts = () => {', 1)[0]
    assert 'event.preventDefault();' in listener
    assert 'openStagingAiStockResponse(detail);' in listener
    assert 'setView("stock"' not in listener

    v141_rules = css.split(
        "/* v141 — make the per-stock AI response understandable before exposing its scoring details. */",
        1,
    )[1]
    for contract in (
        ".staging-ai-stock-response-context",
        ".staging-ai-stock-response-overview",
        ".staging-ai-stock-response-key-reasons",
        ".staging-ai-stock-response-all-reasons",
        ".staging-ai-stock-response-method",
        ".staging-ai-stock-response-metrics",
        ".staging-ai-stock-response-metric-status",
        '[data-metric-tone="positive"]',
        '[data-metric-tone="negative"]',
        ".staging-ai-stock-response-warnings",
        ".staging-ai-stock-response-next",
        "@media (max-width: 359px)",
        "word-break: keep-all !important",
    ):
        assert contract in v141_rules


def test_staging_data_bridge_only_matches_public_read_routes(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "https://secretnote.cloud")

    assert staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/market/indices"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/market/calendar"}
    )
    assert staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/stocks/005930/dashboard"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/stocks/005930/week-chart"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/stocks/005930/news-items"}
    )
    assert staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/insight/feed"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "POST", "path": "/watchlists/demo"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/session/write-token"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/watchlists/demo"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/push/config"}
    )
    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/dashboard"}
    )


def test_staging_quality_proxy_keeps_upstream_data_and_uses_candidate_strategy():
    body = json.dumps(
        {
            "strategy_version": "position-lifecycle-v7.0",
            "datasets": {"fundamentals": {"state": "ready"}},
        }
    ).encode()

    rewritten = json.loads(
        staging_module._rewrite_staging_quality_contract(
            "/meta/signal-data-quality",
            body,
        )
    )

    assert rewritten["strategy_version"] == "position-lifecycle-v7.3"
    assert rewritten["datasets"]["fundamentals"]["state"] == "ready"


def test_staging_data_bridge_is_disabled_without_an_upstream(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "")

    assert not staging_module._is_staging_read_proxy_request(
        {"type": "http", "method": "GET", "path": "/market/indices"}
    )


def test_staging_proxy_rejects_a_synthetic_weekend_quote():
    prices = [
        {
            "trade_date": "2026-08-28",
            "open": 428_500,
            "high": 433_000,
            "low": 422_000,
            "close": 427_500,
            "volume": 2_832,
            "trading_value": 1_210_680_000,
        },
        {"trade_date": "2026-08-27", "close": 427_000},
    ]
    synthetic = {
        "trade_date": "2026-08-29",
        "trade_date_verified": False,
        "price": 450_500,
        "market_session": "closed",
        "market_session_label": "장 마감",
        "is_live": False,
    }

    completed = staging_module._completed_quote_from_prices(
        prices,
        session_quote=synthetic,
    )

    assert completed["price"] == 427_500
    assert completed["change_value"] == 500
    assert completed["change_rate"] == 0.12
    assert completed["trade_date_verified"] is True
    assert staging_module._staging_quote_needs_completed_fallback(
        synthetic,
        completed,
        now=datetime(2026, 8, 29, 0, 20),
    )


def test_staging_quant_signal_uses_the_same_current_state_as_market_feed(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "https://example.test")

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {
                "as_of": "2026-08-28T23:41:34+09:00",
                "items": [
                    {
                        "code": "004370",
                        "current": {
                            "price": 427_500,
                            "score": 77.53,
                            "action": "exited",
                            "live_observation": False,
                        },
                    }
                ],
            }

    class Client:
        async def get(self, *_args, **_kwargs):
            return Response()

    original = {
        "code": "004370",
        "current": {
            "price": 450_500,
            "score": 96.58,
            "action": "exited",
            "live_observation": False,
        },
    }
    corrected = json.loads(
        asyncio.run(
            staging_module._sanitize_staging_stock_payload(
                Client(),
                "/stocks/004370/quant-signals",
                json.dumps(original).encode("utf-8"),
            )
        )
    )

    assert corrected["current"] == {
        "price": 427_500,
        "score": 77.53,
        "action": "exited",
        "live_observation": False,
    }
    assert corrected["as_of"] == "2026-08-28T23:41:34+09:00"


def test_staging_dashboard_proxy_upgrades_old_chart_pattern_snapshot(monkeypatch):
    monkeypatch.setattr(staging_module, "STAGING_DATA_UPSTREAM", "https://example.test")
    detected = [{"key": "rising-wedge", "status": "후보", "score_kind": "pattern_fit"}]
    monkeypatch.setattr(staging_module, "detect_chart_patterns", lambda rows: detected if len(list(rows)) == 20 else [])
    requests = []

    class Response:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return [
                {
                    "trade_date": f"2026-08-{index + 1:02d}",
                    "open": 100 + index,
                    "high": 102 + index,
                    "low": 99 + index,
                    "close": 101 + index,
                    "volume": 1_000 + index,
                }
                for index in range(20)
            ]

    class Client:
        async def get(self, url, **kwargs):
            requests.append((url, kwargs))
            return Response()

    original = {
        "code": "005930",
        "chart_analysis": {
            "patterns": [{"key": "falling-wedge", "status": "확인"}],
        },
    }
    corrected = json.loads(
        asyncio.run(
            staging_module._sanitize_staging_stock_payload(
                Client(),
                "/stocks/005930/dashboard",
                json.dumps(original).encode("utf-8"),
            )
        )
    )

    assert requests[0][1]["params"] == {"limit": 250}
    assert corrected["chart_analysis"]["pattern_schema_version"] == 2
    assert corrected["chart_analysis"]["patterns"] == detected


def test_staging_home_news_uses_sentiment_badge_colors():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert '#home-view .thread-tag.impact-호재' in css
    assert '#home-view .thread-tag.impact-악재' in css
    assert 'background: var(--tc-positive-soft) !important' in css
    assert 'background: var(--tc-negative-soft) !important' in css


def test_staging_home_signal_loading_uses_two_line_skeleton():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text

    assert '#home-ai-signals .home-market-signal-window.is-loading' in css
    assert 'grid-template-rows: 18px 14px !important' in css
    assert '@keyframes staging-home-signal-shimmer' in css
    assert '@media (prefers-reduced-motion: reduce)' in css


def test_staging_root_title_and_market_quote_share_a_baseline():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v80 — align the root title"):]

    assert '.staging-market-context' in rules
    assert '.staging-index-context' in rules
    assert 'align-items: baseline !important' in rules
    assert 'padding-top: 9px !important' in rules


def test_staging_home_signal_card_has_extra_side_padding():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v82 — give the home AI signal copy"):]

    assert '.home-market-signal-ticker.staging-home-signal-card' in rules
    assert 'padding-right: 26px !important' in rules
    assert 'padding-left: 26px !important' in rules


def test_staging_market_news_heading_uses_compact_section_spacing():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v83 — keep the calendar-to-news divider"):]

    assert '#trend-live-panel' in rules
    assert '> .app-section-heading' in rules
    assert 'min-height: 58px !important' in rules
    assert 'margin-bottom: 16px !important' in rules


def test_staging_market_calendar_does_not_stack_section_bands():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v84 — avoid stacking two section bands"):]

    assert '#trend-view' in rules
    assert '> #trend-events-panel' in rules
    assert 'border-top: 0 !important' in rules


def test_staging_market_calendar_places_today_second():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    dashboard_source = client.get("/dashboard-app-v170.js").text

    assert 'dashboard-app-v170.js?v=20260902v461' in shell
    assert 'document.body.dataset.stagingIa === "tds-video"' in dashboard_source
    assert 'addTrendCalendarDays(anchorKey, -1)' in dashboard_source


def test_staging_market_calendar_preserves_country_flags():
    client = TestClient(staging_app)
    staging_js = client.get("/assets/staging/toss-ia.js").text
    dashboard_source = client.get("/dashboard-app-v170.js").text

    assert 'return "🇺🇸"' in dashboard_source
    assert 'flag.innerHTML = svg(icons.flag)' not in staging_js


def test_staging_event_detail_uses_scan_first_scenarios_and_disclosures():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    for expected in (
        'function appendTrendScenario(parent, label, stocks = [], tone = "neutral")',
        'el("span", "event-detail-eyebrow", "한눈에 보기")',
        'el("h3", "", "시장은 이렇게 반응할 수 있어요")',
        'el("summary", "", "영향 경로 자세히 보기")',
        'el("h3", "", "3단계로 확인하세요")',
        'createEventGraphSkeleton()',
    ):
        assert expected in dashboard_source

    rules = css[css.index("/* Event detail 2.0") :]
    for expected in (
        ".event-detail-hero-v2",
        ".event-detail-schedule",
        ".event-scenario-grid",
        ".event-impact-path",
        ".event-detail-watch-list::before",
        ".event-flow-loading",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert expected in rules


def test_staging_stock_quote_uses_reference_hierarchy_and_orderability_status():
    client = TestClient(staging_app)
    staging_js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v86 — use one stable quote hierarchy"):]

    assert 'orderability.textContent = "장 상태 확인 중"' in staging_js
    assert 'separator.textContent = "·"' in staging_js
    assert 'const syncStockOrderability = () =>' in staging_js
    assert '? "장 마감"' in staging_js
    assert 'grid-template-columns: minmax(0, 1fr) !important' in rules
    assert 'grid-row: auto !important' in rules
    assert '[data-staging-stock-market]' in rules
    assert 'display: none !important' in rules
    assert '.staging-stock-hero:is(.positive, .negative, .muted) .staging-stock-hero-price > *' in rules
    assert 'color: var(--tc-text) !important' in rules
    assert 'flex-wrap: nowrap !important' in rules


def test_staging_stock_header_uses_supplied_adaptive_icon_masks():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v87 — use the supplied matching heart and search silhouettes"):]

    assert '--staging-stock-heart-mask: url("data:image/png;base64,' in rules
    assert '--staging-stock-search-mask: url("data:image/png;base64,' in rules
    assert '.stock-v3-search > button,' in rules
    assert '.stock-v3-star' in rules
    assert '> svg' in rules
    assert 'display: none !important' in rules
    assert 'background: currentColor !important' in rules
    assert '-webkit-mask-size: contain !important' in rules
    assert 'mask-image: var(--staging-stock-search-mask) !important' in rules
    assert 'mask-image: var(--staging-stock-heart-mask) !important' in rules


def test_staging_stock_header_orders_search_before_a_symmetric_watch_heart():
    client = TestClient(staging_app)
    staging_js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v107 — final stock-header icon contract") :]

    assert 'const stockSearch = document.getElementById("stock-form")' in staging_js
    assert 'stockStar.parentElement.insertBefore(stockSearch, stockStar);' in staging_js
    assert '--staging-stock-heart-mask: url("data:image/svg+xml,' in rules
    assert '--staging-stock-heart-active-mask: url("data:image/svg+xml,' in rules
    assert 'grid-template-columns: 88px minmax(0, 1fr) 88px !important' in rules
    assert 'width: 44px !important' in rules
    assert 'height: 44px !important' in rules
    assert 'width: 32px !important' in rules
    assert 'height: 32px !important' in rules
    assert 'mask-image: var(--staging-stock-heart-active-mask) !important' in rules


def test_staging_ai_position_summary_matches_watchlist_metric_table():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v88 — match the AI position summary to the watchlist metric table"):]

    assert 'grid-template-columns: repeat(2, minmax(0, 1fr)) !important' in rules
    assert 'min-height: 60px !important' in rules
    assert 'padding: 10px 12px !important' in rules
    assert 'border-right: 1px solid var(--tc-line) !important' in rules
    assert 'border-bottom: 1px solid var(--tc-line) !important' in rules
    assert '> div:last-child:nth-child(odd)' in rules
    assert 'grid-column: 1 / -1 !important' in rules
    assert '.quant-current-position dt' in rules
    assert '.quant-current-position dd' in rules
    assert '.quant-next-confirmation' in rules
    assert 'border-top: 0 !important' in rules


def test_staging_news_temperature_gauge_has_adaptive_text_contrast():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v89 — keep the news-temperature label readable"):]

    assert '.stock-v3-temperature-gauge' in rules
    assert 'var(--tc-positive-soft) 0 var(--positive)' in rules
    assert 'var(--tc-surface-2) var(--positive) calc(100% - var(--negative))' in rules
    assert 'var(--tc-negative-soft) calc(100% - var(--negative)) 100%' in rules
    assert '.stock-v3-temperature-gauge strong' in rules
    assert 'color: var(--tc-text) !important' in rules
    assert '.stock-v3-temperature-gauge span' in rules
    assert 'color: var(--tc-sub) !important' in rules


def test_staging_stock_quote_metrics_match_pinned_stock_metric_table():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v90 — match the stock quote metrics to the pinned-stock metric table"):]

    assert '#stock-summary-section' in rules
    assert '.stock-v3-quote-metrics' in rules
    assert 'border: 1px solid light-dark(#e5e8eb, #29292f) !important' in rules
    assert 'border-radius: 12px !important' in rules
    assert 'background: light-dark(transparent, #17171a) !important' in rules
    assert 'min-height: 58px !important' in rules
    assert 'padding: 9px 12px !important' in rules
    assert 'background: light-dark(#ffffff, #1f1e24) !important' in rules
    assert '> div:nth-child(odd)' in rules
    assert '> div:nth-child(-n + 2)' in rules
    assert '.stock-v3-quote-metrics dt' in rules
    assert 'font-size: 10px !important' in rules
    assert '.stock-v3-quote-metrics dd' in rules
    assert 'font-size: 14px !important' in rules


def test_staging_stock_navigation_title_stays_centered_and_ellipsizes():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v92 — keep the stock navigation title centered"):]

    assert '.stock-v3-commandbar' in rules
    assert 'grid-template-columns: 88px minmax(0, 1fr) 88px !important' in rules
    assert '.stock-v3-back' in rules
    assert 'justify-self: start !important' in rules
    assert '.stock-v3-command-title' in rules
    assert 'grid-column: 2 !important' in rules
    assert 'min-width: 0 !important' in rules
    assert 'max-width: 100% !important' in rules
    assert '.stock-v3-command-title h1' in rules
    assert 'overflow: hidden !important' in rules
    assert 'text-overflow: ellipsis !important' in rules
    assert 'white-space: nowrap !important' in rules
    assert '.stock-v3-search,' in rules
    assert '.stock-v3-star' in rules
    assert 'grid-column: 3 !important' in rules
    assert 'justify-self: end !important' in rules


def test_staging_research_briefing_uses_scan_first_editorial_hierarchy():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v96 — rebuild the briefing as a calm, scan-first editorial page"):]

    assert '--research-accent:' in rules
    assert '--research-surface:' in rules
    assert '.morning-money-commandbar' in rules
    assert 'grid-template-columns: 44px minmax(0, 1fr) 44px !important' in rules
    assert '.staging-article-tag' in rules
    assert '.staging-article-author' in rules
    assert 'background: var(--research-surface) !important' in rules
    assert '.morning-money-digest ol' in rules
    assert 'counter-reset: research-digest !important' in rules
    assert 'grid-template-columns: 28px minmax(0, 1fr) !important' in rules
    assert 'content: counter(research-digest, decimal-leading-zero) !important' in rules
    assert '.morning-money-briefing-divider' in rules
    assert 'background: transparent !important' in rules
    assert '.morning-money-category-section' in rules
    assert 'border-bottom: 1px solid var(--tc-line) !important' in rules
    assert '.morning-money-news-title' in rules
    assert 'display: block !important' in rules
    assert '.morning-money-news-title a:focus-visible' in rules
    assert '@media (hover: hover)' in rules
    assert '.morning-money-loading-state,' in rules
    assert '.morning-money-disclaimer' in rules
    assert '@media (max-width: 359px)' in rules
    assert '@media (prefers-reduced-motion: reduce)' in rules


def test_staging_market_ranking_hero_reads_title_lead_then_basis():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=movers&category=volume&market=ALL").text
    hero_start = shell.index('<header class="market-ranking-hero">')
    hero_end = shell.index('</header>', hero_start)
    hero = shell[hero_start:hero_end]

    assert hero.index('id="market-ranking-title"') < hero.index('id="market-ranking-description"')
    assert hero.index('id="market-ranking-description"') < hero.index('id="market-ranking-meta"')

    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v98 — read ranking context as title, supporting lead, then data basis"):]
    assert '.market-ranking-hero h2' in rules
    assert '.market-ranking-hero p' in rules
    assert 'margin: 8px 0 0 !important' in rules
    assert '.market-ranking-hero time' in rules
    assert 'margin: 11px 0 0 !important' in rules
    assert 'font-variant-numeric: tabular-nums !important' in rules

    hierarchy = css[css.index("/* v116 — lock every TOP 50 hero") :]
    for contract in (
        ".market-ranking-hero h2",
        "order: 1 !important",
        ".market-ranking-hero p",
        "order: 2 !important",
        ".market-ranking-hero time",
        "order: 3 !important",
    ):
        assert contract in hierarchy


def test_staging_recommendation_help_is_compact_and_follows_score_threshold():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    score_start = dashboard_source.index("function recommendationScoreDisplay")
    score_end = dashboard_source.index("function componentTermLabel", score_start)
    score_source = dashboard_source[score_start:score_end]

    assert 'valueRow.append(el("strong", "", formatNumber(value)), el("span", "", "/ 100"));' in score_source
    assert 'levelRow.append(el("b", "", level.label), el("span", "", `· ${level.guide}`), help);' in score_source
    assert score_source.index("const levelRow") < score_source.index("levelRow.append")

    card_start = dashboard_source.index("function createRecommendationCard")
    card_end = dashboard_source.index("function appendRecommendationCard", card_start)
    card_source = dashboard_source[card_start:card_end]
    assert 'createStockListCopy(item.name, item.code)' in card_source

    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v99 — keep recommendation help compact beside the score threshold"):]
    assert '.recommend-name .stock-list-copy > small' in rules
    assert 'display: none !important' in rules
    assert '.recommend-score-level .recommend-score-help' in rules
    assert 'width: 26px !important' in rules
    assert 'height: 26px !important' in rules
    assert 'margin: 0 0 0 2px !important' in rules


def test_staging_recommendation_cards_omit_next_condition_until_detail_view():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    flow_start = dashboard_source.index("function createRecommendationDecisionFlow")
    flow_end = dashboard_source.index("function createRecommendationCard", flow_start)
    flow_source = dashboard_source[flow_start:flow_end]

    assert 'facts.append(changed);' in flow_source
    assert 'if (options.detail) {' in flow_source
    assert 'next.append(el("dt", "", "다음 조건"), nextValue);' in flow_source
    assert 'facts.append(next);' in flow_source
    assert flow_source.index('if (options.detail) {') < flow_source.index('facts.append(next);')


def test_staging_editorial_editions_explain_midday_preliminary_and_close_confirmed_buys():
    client = TestClient(staging_app)
    staging_js = client.get("/assets/staging/toss-ia.js").text
    dashboard_source = client.get("/dashboard-app-v170.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text

    for title in (
        "아침에 보는 돈이 되는 소식",
        "점심에 보는 돈이 되는 소식",
        "장 마감 후 보는 돈이 되는 소식",
    ):
        assert title in staging_js
        assert title in dashboard_source

    assert 'const stagingConfirmedBuysForEdition = (payload = {}) =>' in staging_js
    assert 'payload.edition !== "afternoon"' in staging_js
    assert 'stagingConfirmedBuyDate(item) !== publicationDate' in staging_js
    assert 'const stagingPreliminaryBuysForEdition = (payload = {}) =>' in staging_js
    assert 'payload.edition !== "midday"' in staging_js
    assert 'stagingEditorialSignalPayload?.preliminary_history' in staging_js
    assert 'item?.active === false' in staging_js
    assert 'firstSeenAt >= editionEnd' in staging_js
    assert '.slice(0, 3)' in staging_js
    assert 'data-staging-preliminary-buy-code=' in staging_js
    assert '신규·업데이트 ${formatNumber(preliminaryBuys.length)}종목' in staging_js
    assert '장 마감 전에는 신호가 바뀔 수 있어요.' in staging_js
    assert 'data-staging-confirmed-buy-code=' in staging_js
    assert '오늘 확정 매수 ${formatNumber(confirmedBuys.length)}종목' in staging_js
    assert 'stagingConfirmedBuyReason(item, 88)' in staging_js
    assert '오늘 새로 확정된 매수 종목은 없었어요.' in staging_js
    assert 'fetchJsonCached("/market/quant-signals?universe_limit=150&limit=0&recent_days=30"' in staging_js
    assert 'preliminary_buys: stagingPreliminaryBuysForEdition(selected)' in staging_js
    assert 'preliminary_buys_available: stagingPreliminaryBuyDataAvailableForEdition(selected)' in staging_js
    assert 'confirmed_buys: stagingConfirmedBuysForEdition(selected)' in staging_js
    assert 'className = "staging-article-preliminary-buys"' in staging_js
    assert '오전 중 새로 잡히거나 조건이 갱신된 종목이에요.' in staging_js
    assert 'className = "staging-article-confirmed-buys"' in staging_js
    assert '종가 기준 조건을 통과해 확정된 종목과 실제 판단 근거예요.' in staging_js
    assert 'titleSelector: "#morning-money-briefing-view .morning-money-command-title h1"' in staging_js
    assert 'commandTitle.textContent = presentation.navTitle;' in dashboard_source

    rules = css[css.index("/* v100 — distinguish the three daily briefings and explain confirmed buys after close"):]
    assert '.staging-editorial-confirmed-buys' in rules
    assert '.staging-article-confirmed-buys' in rules
    assert '.staging-article-confirmed-buy:focus-visible' in rules
    assert 'outline: 2px solid var(--tc-red) !important' in rules
    assert '@media (max-width: 359px)' in rules

    preliminary_rules = css[css.index("/* v136 — surface new or refreshed preliminary buys inside the midday briefing") :]
    assert '.staging-editorial-preliminary-buys' in preliminary_rules
    assert '.staging-article-preliminary-buys' in preliminary_rules
    assert '.staging-article-preliminary-buy:focus-visible' in preliminary_rules
    assert 'outline: 2px solid var(--tc-warning) !important' in preliminary_rules
    assert 'min-height: 44px !important' in preliminary_rules


def test_embedded_stock_chart_analysis_omits_duplicate_stock_identity():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    start = dashboard_source.index("function renderChartForecastResult")
    end = dashboard_source.index("function yScale", start)
    chart_source = dashboard_source[start:end]

    assert 'el("h1", "", embedded ? "차트분석"' in chart_source
    assert '[item.code, item.market || dashboard.market]' not in chart_source
    assert "item.name || dashboard.name, item.code" not in chart_source


def test_stock_code_and_market_are_not_rendered_as_redundant_identity_meta():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    staging_source = client.get("/assets/staging/toss-ia.js").text
    nasdaq_source = (ROOT / "app/static/nasdaq/app.js").read_text()
    insight_source = (ROOT / "app/static/insight/app.js").read_text()

    copy_start = dashboard_source.index("function createStockListCopy")
    copy_end = dashboard_source.index("function clonePayload", copy_start)
    copy_source = dashboard_source[copy_start:copy_end]
    assert 'copy.append(el("strong", "", name || code || "-"));' in copy_source
    assert "<small" not in copy_source
    assert "showMeta" not in copy_source

    assert 'elements.recommendDetailCode.textContent = "";' in dashboard_source
    assert "elements.recommendDetailCode.hidden = true;" in dashboard_source
    assert "data-staging-stock-market" not in staging_source

    redundant_pair = re.compile(r"(?:stock_)?code[^\n]{0,100}[·ㆍ][^\n]{0,100}market|market[^\n]{0,100}[·ㆍ][^\n]{0,100}(?:stock_)?code")
    for source in (dashboard_source, staging_source, nasdaq_source, insight_source):
        assert redundant_pair.search(source) is None


def test_stock_quote_hero_uses_seventy_percent_type_scale():
    css = TestClient(staging_app).get("/assets/staging/toss-fidelity.css").text
    rules = css[
        css.index("/* v113 — reduce the stock quote hero to a calmer 70% type scale. */") :
        css.index("/* v114 — make the selected live-news filter unmistakable")
    ]

    assert ".staging-stock-hero-name-row h2" in rules
    assert "font-size: clamp(20px, 5vw, 22px) !important" in rules
    assert ".staging-stock-hero-price strong" in rules
    assert "font-size: clamp(30px, 8.4vw, 35px) !important" in rules
    assert ".staging-stock-hero-price span" in rules
    assert "font-size: 17px !important" in rules


def test_staging_live_news_filters_show_selected_hover_focus_and_pressed_states():
    css = TestClient(staging_app).get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v114 — make the selected live-news filter unmistakable") :]

    for contract in (
        '.trend-live-filter[aria-selected="true"]',
        'content: "✓" !important',
        "background: var(--tc-text) !important",
        '(.is-positive, .positive)[aria-selected="true"]',
        "background: var(--tc-red) !important",
        '(.is-negative, .negative)[aria-selected="true"]',
        "background: var(--tc-blue) !important",
        ".trend-live-filter:active",
        "scale(0.96)",
        ".trend-live-filter:not([aria-selected=\"true\"]):hover",
        ".trend-live-filter:focus-visible",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert contract in rules


def test_staging_market_rankings_color_only_the_return_segment():
    client = TestClient(staging_app)
    dashboard_source = client.get("/dashboard-app-v170.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v115 — apply Korean-market rise/fall colors") :]

    assert 'el("span", "ranking-metric-change", changeText)' in dashboard_source
    assert "setTone(change, item.change_rate);" in dashboard_source
    for contract in (
        "#market-view .ranking-metric-change.positive",
        "color: var(--tc-red) !important",
        "#market-view .ranking-metric-change.negative",
        "color: var(--tc-blue) !important",
        "#market-view .ranking-metric-change.muted",
        "color: var(--tc-muted) !important",
    ):
        assert contract in rules


def test_staging_home_interest_response_has_dark_mode_copy_and_badge_contrast():
    css = TestClient(staging_app).get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v117 — restore dark-mode contrast") :]

    for contract in (
        ".home-ai-interest-action",
        "light-dark(#303641, #d8dae2)",
        ".home-ai-interest-basis",
        "light-dark(#7a828e, #b7bac4)",
        ".home-ai-interest-row.is-negative .home-ai-interest-head em",
        "light-dark(#1769d2, #a8ccff)",
        "light-dark(#eef5ff, #172a43)",
        ".home-ai-interest-row.is-positive .home-ai-interest-head em",
        "light-dark(#d9233f, #ff9bad)",
        ".home-ai-interest-row.is-event .home-ai-interest-head em",
        "light-dark(#9a5a00, #ffd48a)",
        ".home-ai-interest-row.is-neutral .home-ai-interest-head em",
        ".home-ai-interest-row::after",
    ):
        assert contract in rules


def test_stock_orderability_reflects_the_live_market_status():
    js = TestClient(staging_app).get("/assets/staging/toss-ia.js").text
    start = js.index("const syncStockOrderability = () =>")
    end = js.index("const syncStockHero = () =>", start)
    orderability_source = js[start:end]

    assert 'orderability.textContent = "실시간 주문 가능"' not in js
    assert 'tone === "closed" || /마감|종료|휴장/.test(detailText)' in orderability_source
    assert '? "장 마감"' in orderability_source
    assert 'marketStatus.dataset.stagingOrderability = state' in orderability_source
    assert 'separator.hidden = !showDetail' in orderability_source
    assert 'detail.hidden = !showDetail' in orderability_source
    assert 'syncStockOrderability();' in js


def test_stock_change_context_uses_friendly_session_aware_copy():
    client = TestClient(staging_app)
    shell = client.get("/dashboard/005930").text
    js = client.get("/assets/staging/toss-ia.js").text
    logic = client.get("/assets/staging/stock-change-copy-logic.js").text

    assert f'/assets/staging/stock-change-copy-logic.js?v={STAGING_IA_VERSION}' in shell
    assert 'data-staging-stock-change-context>최근 장에서</span>' in js
    assert '<span>어제보다</span>' not in js
    assert 'window.SecretNoteStockChangeCopy?.resolveChangeContext?.({' in js
    assert 'quoteDate === clock.date' in js
    assert 'quote?.is_live === true || clock.minutes >= 9 * 60' in js
    assert 'target.dataset.stagingChangeContext = context.mode' in js
    assert '"어제보다"' in logic
    assert '`${referenceWeekday}보다`' in logic
    assert '"어제 장에서"' in logic
    assert '`${completedWeekday} 장에서`' in logic


def test_staging_chart_study_library_is_mobile_accessible_and_marks_actual_patterns():
    client = TestClient(staging_app)
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v108 — complete 34-pattern chart study library") :]

    for contract in (
        ".chart-study-candle.bullish",
        ".chart-study-candle.bearish",
        ".chart-study-actual-pattern-point",
        ".chart-study-library-details > summary",
        ".chart-study-library-buttons button",
        ".chart-pattern-row-study",
        ":focus-visible",
        "min-height: 40px !important",
        "grid-template-columns: repeat(2, minmax(0, 1fr)) !important",
    ):
        assert contract in rules

    cleanup = css[css.index("/* v110 — end chart study cleanly") :]
    assert '#chart-study-view {' in cleanup
    assert "min-height: 0 !important" in cleanup
    assert "padding-bottom: 0 !important" in cleanup
    assert ".chart-study-content" in cleanup
    assert "margin-bottom: 0 !important" in cleanup
    assert '.service-footer {' in cleanup
    assert "margin-top: 16px !important" in cleanup


def test_staging_v125_collapses_hidden_content_and_pins_both_signal_control_rows():
    client = TestClient(staging_app)
    shell = client.get("/dashboard").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v125 — remove leaked hidden-page height") :]

    assert "contextual-safe-area-v128" in shell
    for contract in (
        '#chart-study-view[hidden]',
        "display: none !important",
        '[data-view="stock"] #stock-view.stock-detail-v3',
        "min-height: 0 !important",
        "#ai-signals-view .ai-signal-mode-tabs",
        "position: sticky !important",
        "top: 0 !important",
        "min-height: calc(57px + var(--tc-safe-area-top)) !important",
        "padding: var(--tc-safe-area-top) var(--tc-gutter) 0 !important",
        ".ai-signal-stage-tabs",
        ".ai-signal-history-filters",
        "top: calc(57px + var(--tc-safe-area-top)) !important",
    ):
        assert contract in rules


def test_staging_v133_compacts_ai_signal_title_gap_without_losing_safe_area():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=ai-signals").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css.split(
        "/* v133 — keep sticky signal tabs below the iOS safe area without widening the title gap. */",
        1,
    )[1].split("/* v132 — make notifications the home action", 1)[0]

    assert "chart-pattern-integrity-v134-ai-stock-response-v135" in shell
    for contract in (
        ".staging-ai-signals-intro",
        "padding-bottom: 14px !important",
        ".ai-signal-mode-tabs",
        "top: var(--tc-safe-area-top) !important",
        "min-height: 57px !important",
        "padding: 0 var(--tc-gutter) !important",
    ):
        assert contract in rules


def test_staging_v129_uses_independent_stock_search_svg_centered_with_watch_heart():
    client = TestClient(staging_app)
    shell = client.get("/dashboard").text
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v129 — use an independent Lucide search glyph") :]

    assert "contextual-safe-area-v128" in shell
    assert 'stockSearch: \'<circle cx="11" cy="11" r="8"></circle><path d="m21 21-4.3-4.3"></path>\'' in js
    assert 'stockSearchButton.innerHTML = svg(icons.stockSearch, "staging-stock-search-glyph")' in js
    for contract in (
        ".stock-v3-search > button",
        ".stock-v3-star",
        "align-self: center !important",
        "place-items: center !important",
        "line-height: 0 !important",
        ".stock-v3-search > button::before",
        "display: none !important",
        "content: none !important",
        "> svg.staging-stock-search-glyph",
        "position: static !important",
        "width: 32px !important",
        "height: 32px !important",
        "grid-area: 1 / 1 !important",
        "transform: none !important",
        "fill: none !important",
        "stroke: currentColor !important",
        "stroke-width: 2.5px !important",
        ".stock-v3-star::before",
        "mask-size: 32px 32px !important",
    ):
        assert contract in rules


def test_staging_v132_uses_home_only_notification_action_and_compact_sheet_rows():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v132 — make notifications the home action") :]

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert "notification-sheet-v132" in shell
    assert 'bell: \'<path d="M27.5 16.5a9.5 9.5 0 0 0-19 0' in js
    for contract in (
        'data-staging-top-action="notifications" aria-label="알림"',
        'const syncPrimaryTopAction = (view = document.body.dataset.view || "home") =>',
        'const isHome = view === "home";',
        'primaryTopAction.removeAttribute("data-staging-view")',
        'primaryTopAction.dataset.stagingView = "ai-signals"',
        'document.getElementById("push-notification-button")?.click()',
        "syncPrimaryTopAction(view);",
    ):
        assert contract in js
    for contract in (
        '[data-staging-top-action="notifications"]',
        "> svg.staging-notification-bell",
        ".push-notification-core",
        ".push-notification-core-state",
        ".push-notification-optional-head",
        ".push-notification-condition:last-child",
        "min-height: 66px !important",
        "border-bottom: 1px solid var(--tc-line) !important",
        "width: 50px !important",
        "height: 30px !important",
        "max-height: min(88dvh, 760px) !important",
        ".push-notification-sheet-status[hidden]",
        ".push-recommendation-feature",
    ):
        assert contract in rules


def test_staging_v143_unifies_root_header_action_icon_geometry():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=portfolio").text
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v143 — one optical outline system") :]

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert "header-action-icons-v143" in shell
    for contract in (
        "const topActionGlyphs = Object.freeze({",
        "const topActionSvg = (name, className = \"\") =>",
        'class="${classes}" viewBox="0 0 36 36" data-staging-top-icon="${name}"',
        'topActionSvg("bell", "staging-notification-bell")',
        'topActionSvg("ai", "staging-ai-signal-glyph")',
        'topActionSvg("search", "staging-search-glyph")',
    ):
        assert contract in js
    assert "bell: '<path" not in js[js.index("const icons = {") : js.index("const SERVICE_UPDATE_RELEASE")]

    for contract in (
        "--staging-top-action-glyph-size: 26px",
        "--staging-top-action-glyph-stroke: 2.6px",
        "> svg.staging-top-action-icon",
        "width: var(--staging-top-action-glyph-size) !important",
        "height: var(--staging-top-action-glyph-size) !important",
        "fill: none !important",
        "stroke: currentColor !important",
        "stroke-width: var(--staging-top-action-glyph-stroke) !important",
        "stroke-linecap: round !important",
        "stroke-linejoin: round !important",
        "pointer-events: none !important",
    ):
        assert contract in rules


def test_staging_v146_explains_two_detail_pages_without_exposing_model_provenance():
    staging_client = TestClient(staging_app)
    production_client = TestClient(production_app)
    staging_shell = staging_client.get("/dashboard?view=home").text
    production_shell = production_client.get("/dashboard?view=home").text
    js = staging_client.get("/assets/staging/toss-ia.js").text
    css = staging_client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v146 — the model stays invisible") :]

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert "plain-language-detail-v146" in staging_shell
    assert "investor-action-copy-v147" in staging_shell
    assert '<meta name="secret-note-environment" content="staging" />' in staging_shell
    assert '<meta name="secret-note-environment" content="staging" />' not in production_shell
    for contract in (
        'const STAGING_PAGE_SUMMARY_PATH = "/staging-ai/page-summary"',
        "const STAGING_PAGE_SUMMARY_CACHE_MS = 30 * 60 * 1000",
        "const stagingPageSummaryCache = new Map()",
        "const cached = stagingPageSummaryCache.get(cacheKey)",
        "stagingPageSummaryCache.set(cacheKey, { savedAt: Date.now(), payload })",
        "stagingGptPageSummaryEnabled",
        'requestStagingPageSummary("stock_response"',
        'requestStagingPageSummary("recommendation_detail"',
        "applyStagingAiStockResponseSummary",
        "applyRecommendationDetailSummary",
        "recommendationDetailFriendlyText",
        "새로 살 가격과 실제 거래 규모 확인이 우선입니다",
        "가격이 흔들릴 때 손실을 줄일 기준을 매일 확인해요",
        'action: recommendationDetailFriendlyText(item?.action)',
        "customer_state: customerState.key",
        "customer_state_label: customerState.label",
        "additional_buy_label: customerState.additionalBuyLabel",
        "쉽게 풀어보면",
        "왜 이렇게 보나요?",
        "지금 어떻게 보면 되나요?",
        "지금은 추가 매수보다 보유 기준을 확인할 때예요",
        "지금 확인할 추천 종목",
        "새로 살 차례인지, 보유할 차례인지 먼저 확인해 보세요.",
        "badge?.remove()",
        'dataset.stagingRecommendDetailReason = "true"',
        'content.dataset.summaryMode = summary.generation_mode || "rules"',
        "설명은 이해하기 쉽게 풀어썼고, 추천 여부와 점수·가격은 공개 시장 데이터를 기준으로 계산했어요.",
    ):
        assert contract in js
    for contract in (
        ".staging-ai-stock-response-explanation",
        ".staging-recommend-detail-reason",
        "/* v147 — put the investor's current decision",
        "grid-template-columns: minmax(0, 1fr) auto !important",
        "justify-content: flex-start !important",
        "overflow-wrap: anywhere !important",
        "@media (max-width: 359px)",
    ):
        assert contract in rules
    assert "data-staging-summary-provenance" not in js
    detail_summary_source = js[js.index("const applyRecommendationDetailSummary") : js.index("const decorateRecommendationDetail")]
    stock_summary_source = js[js.index("const applyStagingAiStockResponseSummary") : js.index("const stagingAiStockResponseKeyReasonRow")]
    for source in (detail_summary_source, stock_summary_source):
        assert "GPT 문구 정리" not in source
        assert "문구 정리 중" not in source
    assert js.count("fetch(") == 1


def test_staging_v149_uses_two_holding_states_average_price_and_finished_copy():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    js = client.get("/assets/staging/toss-ia.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v148 — tailor explanations") :]

    assert "position-guide-v149-position-input-v150" in shell
    for contract in (
        "const STAGING_AI_STOCK_RESPONSE_INVESTOR_STATES = Object.freeze({",
        'not_holding: Object.freeze({',
        'holding: Object.freeze({',
        'data-staging-response-investor-state="not_holding"',
        'data-staging-response-investor-state="holding"',
        "현재 이 종목을 보유하고 있나요?",
        'data-staging-response-average-price',
        'data-staging-response-guide-rows',
        "증권사 리포트",
        "6가지 자료 자세히 보기",
        "실제 계좌·주문 내역과 자동 연동되지 않아요",
        "investor_state: normalizedState",
        "investor_state_label: stateCopy.label",
        "position_mode: perspective.positionMode",
        "average_buy_price: perspective.averageBuyPrice",
        "stagingAiStockResponsePerspectiveCopy",
        'setStagingAiStockResponseDisplay("loading"',
        'setStagingAiStockResponseDisplay("ready")',
        'data-staging-response-loader role="status" aria-live="polite"',
        'content.dataset.summaryDisplay = ready ? "ready" : "loading"',
        'data-staging-recommend-detail-loader',
        'setRecommendationDetailSummaryDisplay(content, "ready")',
        "let recommendationDataPending = false;",
        "if (recommendationDataPending) {",
        "label} 기준으로 반영해 쉬운 말로 정리하고 있어요",
    ):
        assert contract in js
    for contract in (
        ".staging-ai-stock-response-overview > div:first-child",
        "padding-left: 12px !important",
        ".staging-ai-stock-response-investor-state",
        ".staging-ai-stock-response-investor-options",
        ".staging-ai-stock-response-average-price",
        ".staging-ai-stock-response-guide-row",
        "grid-template-columns: repeat(2, minmax(0, 1fr)) !important",
        "min-height: 44px !important",
        '.staging-ai-stock-response-page[data-response-display="loading"]',
        '#recommend-detail-content[data-summary-display="loading"]',
        ".staging-ai-stock-response-loader-spinner",
        "animation: staging-investor-copy-spin 780ms linear infinite !important",
        "@media (prefers-reduced-motion: reduce)",
        "animation: none !important",
    ):
        assert contract in rules
    assert "GPT" not in js[
        js.index('class="staging-ai-stock-response-loader"') :
        js.index('class="staging-ai-stock-response-action"')
    ]


def test_staging_v151_shows_live_quote_and_separates_pullback_from_breakout_confirmation():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=home").text
    js = client.get("/assets/staging/toss-ia.js").text
    logic = client.get("/assets/staging/ai-stock-response-logic.js").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v151 — live quote context") :]

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert "position-input-v150-live-quote-decision-plan-v151" in shell
    for contract in (
        "현재 주당 가격",
        "오늘 등락률",
        'data-staging-response-live-price',
        'data-staging-response-live-rate',
        'data-staging-response-live-state',
        'replaceQuoteStreamScope("staging-ai-stock-response"',
        'clearQuoteStreamScope("staging-ai-stock-response")',
        "장 마감 시세",
        'typeof quote.is_live === "boolean"',
        "가격이 내려올 때와 올라갈 때를 나눠 보세요",
        "앞으로 이렇게 확인하세요",
        'data-staging-response-decision-plan',
        'data-staging-response-next-summary',
        "stagingAiStockResponseDecisionStepRow",
    ):
        assert contract in js
    assert "판단이 바뀌려면" not in js
    status_handler_source = js[
        js.index("onStatus: () => {") : js.index("onQuote: (payload)")
    ]
    assert 'state = "connected"' not in status_handler_source
    assert 'state = "connecting"' in status_handler_source
    quote_scope_source = js[
        js.index("const syncStagingAiStockResponseQuoteScope") :
        js.index("const renderStagingAiStockResponseLoading")
    ]
    assert quote_scope_source.index(
        'typeof replaceQuoteStreamScope !== "function"'
    ) < quote_scope_source.index(
        "signature === stagingAiStockResponseQuoteScopeSignature"
    )
    assert 'stagingAiStockResponseQuoteScopeSignature = ""' in quote_scope_source
    summary_source = js[
        js.index("const applyStagingAiStockResponseSummary") :
        js.index("const stagingAiStockResponseKeyReasonRow")
    ]
    assert "summary.next_check" not in summary_source
    assert 'querySelector("[data-staging-response-next] ul")' not in summary_source
    for contract in (
        '"눌림목 확인 구간"',
        '"상승 흐름 확인선"',
        '"매수가 아님"',
        '"pullback"',
        '"breakout"',
        '"wait"',
        "바로 따라 사기보다",
    ):
        assert contract in logic
    for contract in (
        ".staging-ai-stock-response-live-quote",
        ".staging-ai-stock-response-decision-step",
        '[data-quote-tone="positive"]',
        '[data-quote-tone="negative"]',
        "grid-template-columns: repeat(2, minmax(0, 1fr)) !important",
        "word-break: keep-all !important",
    ):
        assert contract in rules


def test_staging_v145_refines_three_daily_briefings_without_changing_news_or_signal_data():
    staging_client = TestClient(staging_app)
    production_client = TestClient(production_app)
    staging_shell = staging_client.get("/dashboard?view=news").text
    production_shell = production_client.get("/dashboard?view=news").text
    js = staging_client.get("/assets/staging/toss-ia.js").text
    css = staging_client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v145 — GPT refines the current morning") :]

    assert STAGING_IA_VERSION == "20260902-signal-sell-labels-v91"
    assert "gpt-briefing-v145" in staging_shell
    assert '<meta name="secret-note-environment" content="staging" />' in staging_shell
    assert '<meta name="secret-note-environment" content="staging" />' not in production_shell
    for contract in (
        "const stagingBriefingSummaryInput = (payload = {}) =>",
        "const stagingBriefingSummaryPromises = new Map()",
        'requestStagingPageSummary("briefing_edition"',
        "selected_news_count: payload.selected_news_count",
        "opportunity_count: payload.opportunity_count",
        "caution_count: payload.caution_count",
        "const applyStagingBriefingCardSummary = async",
        "const applyStagingBriefingArticleSummary = async",
        "const latestPublicationDate = String(rows[0]?.publication_date || \"\")",
        ".slice(0, 3)",
        'activeFeedMode === "content"',
        '(document.body.dataset.view || "") === "news"',
        "data-staging-briefing-summary-provenance",
        'summaryPrefetch ? "loading" : "deferred"',
        'summaryPrefetch ? "문구 정리 중" : "열면 GPT 정리"',
        'summary.generation_mode === "openai" ? "GPT 문구 정리" : "데이터 요약"',
        '(document.body.dataset.view || "") === "morning-briefing"',
        "void applyStagingBriefingArticleSummary(payload || {})",
        "핵심 소식 ${formatNumber(payload.selected_news_count || 0)}건 전체 읽기",
        "editorialPreliminaryBuysMarkup(payload)",
        "editorialConfirmedBuysMarkup(payload)",
    ):
        assert contract in js
    for contract in (
        ".staging-briefing-card-provenance",
        ".staging-briefing-summary-provenance",
        ".staging-briefing-ai-next",
        "overflow-wrap: anywhere !important",
        "@media (max-width: 359px)",
    ):
        assert contract in rules
    assert js.count("fetch(") == 1


def test_staging_v138_keeps_discovery_search_suggestions_legible_in_dark_mode():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=search&theme=dark").text
    css = client.get("/assets/staging/toss-fidelity.css").text
    rules = css[css.index("/* v138 — keep discovery search suggestions legible in explicit dark mode. */") :]

    assert "discovery-search-contrast-v138" in shell
    for contract in (
        'html[data-staging-theme="dark"] body[data-staging-ia="tds-video"] .discovery-suggestions',
        "color-scheme: dark !important",
        "background: var(--dark-surface-raised) !important",
        "color: var(--dark-text) !important",
        ".discovery-suggestion-item:is(:hover, :focus-visible, [aria-selected=\"true\"])",
        "background: var(--dark-surface-strong) !important",
        "outline: 2px solid var(--dark-focus) !important",
        ".discovery-suggestion-item strong",
        ".discovery-suggestion-item span",
        "color: var(--dark-muted) !important",
    ):
        assert contract in rules


def test_staging_v140_stacks_strategy_basis_below_signal_date_and_scopes_sell_disclaimer():
    client = TestClient(staging_app)
    shell = client.get("/dashboard?view=ai-signals").text
    dashboard_source = client.get("/dashboard-app-v170.js").text
    base_css = client.get("/assets/dashboard/styles.css").text
    staging_css = client.get("/assets/staging/toss-fidelity.css").text
    base_rules = base_css.split(
        "/* AI signal page: the header, status tabs, and list must share one mobile width.",
        1,
    )[1].split(".stock-list-copy", 1)[0]
    staging_rules = staging_css[
        staging_css.index(
            "/* v140 — stack the strategy basis directly below the signal date and keep sell guidance restrained. */"
        ):
    ]

    assert "ai-signal-basis-stack-v140" in shell
    assert (
        '<aside class="ai-signal-sell-disclaimer" id="ai-signal-sell-disclaimer" '
        'role="note" aria-label="AI 매도 시그널 주의사항" hidden>'
    ) in shell
    assert "<strong>주의:</strong> AI의 매도 타이밍을 무조건 따라가지마세요!" in shell
    for contract in (
        'aiSignalSellDisclaimer: $("ai-signal-sell-disclaimer")',
        "function syncAiSignalSellDisclaimer()",
        'state.aiSignalMode === "current" && state.aiSignalStage === "recent-sell"',
        'elements.aiSignalSellDisclaimer.hidden = !visible;',
        'setAttribute("aria-describedby", "ai-signal-sell-disclaimer")',
        'removeAttribute("aria-describedby")',
    ):
        assert contract in dashboard_source
    for contract in (
        ".home-ai-signal-supporting",
        "grid-template-columns: minmax(0, 1fr);",
        "grid-template-rows: repeat(2, auto);",
        "grid-auto-flow: row;",
        "justify-items: start;",
        ".home-ai-signal-metrics",
        "width: 100%;",
        "justify-self: start;",
        "justify-content: start;",
        "text-align: left;",
        ".ai-signal-sell-disclaimer[hidden]",
    ):
        assert contract in base_rules
    for contract in (
        ".home-ai-signal-supporting",
        "grid-template-columns: minmax(0, 1fr) !important",
        "grid-template-rows: repeat(2, auto) !important",
        "grid-auto-flow: row !important",
        "justify-items: start !important",
        ".home-ai-signal-metrics",
        "justify-self: start !important",
        "justify-content: flex-start !important",
        ".home-ai-signal-metric.is-staging-visible",
        ".home-ai-signal-metric-value",
        "text-align: left !important",
        ".ai-signal-sell-disclaimer",
        "color: light-dark(#8b95a1, #7f8089) !important",
        "font-size: 11px !important",
        ".ai-signal-sell-disclaimer[hidden]",
        "display: none !important",
    ):
        assert contract in staging_rules
