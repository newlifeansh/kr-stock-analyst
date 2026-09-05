from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.db import SessionLocal, get_db, init_db
from app.main import (
    _page_summary_client_requests,
    _page_summary_global_requests,
    _page_summary_rate_lock,
    app,
    api_cache,
    rate_limit_lock,
    rate_limit_windows,
)
from app.models import (
    DashboardAccessIdentity,
    DashboardAccessQuota,
    PushNotificationHistory,
    RecommendationTrackState,
    WatchlistItem,
)


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["strategy_version"] == "position-lifecycle-v7.4"
    assert response.json()["dashboard_version"] == "20260904v465"
    assert response.json()["canonical_base_url"] == "https://secretnote.cloud"

    healthz = client.get("/healthz")
    assert healthz.status_code == 200
    assert healthz.json()["status"] == "ok"

    readyz = client.get("/readyz")
    assert readyz.status_code == 200
    assert readyz.json()["database_ok"] is True


def test_market_recommendations_do_not_keep_empty_payload_for_full_cache_window(monkeypatch):
    calls = []

    def empty_recommendations(_db, **_kwargs):
        calls.append(True)
        return {
            "as_of": datetime(2026, 9, 4, 9, 20, tzinfo=timezone(timedelta(hours=9))),
            "universe_count": 100,
            "screened_count": 100,
            "candidate_count": 0,
            "qualified_count": 0,
            "pending_count": 0,
            "entered_today_count": 0,
            "selection_rule": "confirmed_entry_pending_or_entered_today",
            "methodology": [],
            "items": [],
        }

    api_cache.clear()
    with rate_limit_lock:
        rate_limit_windows.clear()
    monkeypatch.setattr("app.main.build_recommendations", empty_recommendations)
    client = TestClient(app)

    try:
        first = client.get("/market/recommendations?limit=8&candidate_limit=45")
        second = client.get("/market/recommendations?limit=8&candidate_limit=45")
    finally:
        api_cache.clear()

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(calls) == 2
    assert first.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert second.headers["pragma"] == "no-cache"


def test_market_recommendations_do_not_serve_non_empty_in_process_cache(monkeypatch):
    from fastapi import Response
    from app import main as main_module

    calls = []

    def recommendations(_db, **_kwargs):
        calls.append(True)
        return {
            "as_of": datetime(2026, 9, 4, 15, 30, tzinfo=timezone(timedelta(hours=9))),
            "universe_count": 100,
            "screened_count": 1,
            "candidate_count": 1,
            "qualified_count": 1,
            "pending_count": 1,
            "entered_today_count": 0,
            "selection_rule": "confirmed_entry_pending_or_entered_today",
            "methodology": [],
            "items": [{"code": f"00593{len(calls)}"}],
        }

    api_cache.clear()
    with rate_limit_lock:
        rate_limit_windows.clear()
    monkeypatch.setattr("app.main.build_recommendations", recommendations)
    monkeypatch.setattr("app.main._enforce_rate_limit", lambda *_args, **_kwargs: None)

    try:
        first = main_module.market_recommendations(
            request=object(),
            response=Response(),
            limit=8,
            candidate_limit=45,
            refresh=False,
            db=object(),
        )
        second = main_module.market_recommendations(
            request=object(),
            response=Response(),
            limit=8,
            candidate_limit=45,
            refresh=False,
            db=object(),
        )
    finally:
        api_cache.clear()

    assert first["items"][0]["code"] != second["items"][0]["code"]
    assert len(calls) == 2


def test_production_page_summary_endpoint_keeps_holding_unknown_as_input_only():
    with _page_summary_rate_lock:
        _page_summary_client_requests.clear()
        _page_summary_global_requests.clear()
    response = TestClient(app).post(
        "/ai/page-summary",
        json={
            "page_type": "stock_response",
            "facts": {
                "code": "005930",
                "investor_state": "holding",
                "position_mode": "holding_unknown",
                "average_buy_price": None,
                "sources": [{"id": "metric-research", "label": "증권사 리포트"}],
            },
            "fallback": {
                "headline": "평균 매수가를 입력하면 내 보유 전략을 볼 수 있어요",
                "summary": "아직 내 수익·손실을 계산하지 않았어요. 위에서 평균 매수가를 입력해 주세요.",
                "reason": "평균 매수가가 없으면 현재가와 비교할 기준이 없어 수익권·손실권을 구분할 수 없어요.",
                "action_title": "평균 매수가를 입력할 단계예요",
                "next_check": "평균 매수가와 현재가를 비교해요.",
                "evidence_refs": ["metric-research"],
            },
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    payload = response.json()
    assert payload["generation_mode"] == "rules"
    assert payload["model_name"] is None
    assert payload["headline"] == "평균 매수가를 입력하면 내 보유 전략을 볼 수 있어요"
    assert "현재 손실권" not in " ".join(str(value) for value in payload.values())


def test_production_page_summary_endpoint_rejects_cross_site_requests():
    response = TestClient(app).post(
        "/ai/page-summary",
        headers={"sec-fetch-site": "cross-site"},
        json={"page_type": "stock_response", "facts": {}, "fallback": {}},
    )

    assert response.status_code == 403


def test_signal_data_quality_endpoint_can_probe_sources_without_caching(monkeypatch):
    monkeypatch.setattr(
        "app.main.signal_data_quality_status",
        lambda _db, _settings: {
            "status": "ready",
            "strategy_version": "position-lifecycle-v7.4",
        },
    )
    monkeypatch.setattr(
        "app.main.probe_signal_source_apis",
        lambda _settings, sample_code: {
            "status": "ready",
            "sample_code": sample_code,
            "items": [{"key": "price", "state": "ready"}],
        },
    )

    response = TestClient(app).get(
        "/meta/signal-data-quality?probe=true&sample_code=005930"
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["status"] == "ready"
    assert response.json()["strategy_version"] == "position-lifecycle-v7.4"
    assert response.json()["api_probe"]["sample_code"] == "005930"
    assert response.json()["api_probe"]["items"][0]["state"] == "ready"


def test_root_redirects_to_korea_dashboard():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard?view=home"


def test_us_path_serves_unified_market_shell_without_changing_root():
    client = TestClient(app, base_url="https://secretnote.cloud")

    root = client.get("/", follow_redirects=False)
    response = client.get("/us", follow_redirects=False)

    assert root.status_code == 307
    assert root.headers["location"] == "/dashboard?view=home"
    assert response.status_code == 200
    assert "시장 한눈에" in response.text
    assert 'id="overview-view"' in response.text
    assert 'id="overview-korea"' in response.text
    assert 'id="overview-us"' in response.text
    assert "국내증시" in response.text
    assert "미국증시" in response.text


def test_us_stock_path_serves_shell_without_shadowing_us_api_routes():
    client = TestClient(app, base_url="https://secretnote.cloud")

    stock_shell = client.get("/us/stock/AAPL")
    search_api = client.get("/us/stocks/search", params={"query": "AAPL"})

    assert stock_shell.status_code == 200
    assert 'id="stock-view"' in stock_shell.text
    assert search_api.status_code == 200
    assert search_api.headers["content-type"].startswith("application/json")


def test_canonical_dashboard_sets_browser_security_headers():
    client = TestClient(app, base_url="https://secretnote.cloud")

    response = client.get(
        "/dashboard?view=ai-signals",
        headers={"accept": "text/html"},
    )

    assert response.status_code == 200
    assert response.headers["strict-transport-security"] == (
        "max-age=31536000; includeSubDomains"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == (
        "camera=(), microphone=(), geolocation=()"
    )
    policy = response.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "https://cdn.jsdelivr.net" in policy

    api_response = client.get("/dashboard-version", headers={"accept": "application/json"})
    assert api_response.status_code == 200
    assert api_response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in api_response.headers


def test_legacy_railway_host_redirects_to_canonical_service():
    client = TestClient(
        app,
        base_url="https://insight-mcp-production-945f.up.railway.app",
    )

    response = client.get(
        "/market/quant-signals?universe_limit=100&limit=0&recent_days=30",
        follow_redirects=False,
    )

    assert response.status_code == 308
    assert response.headers["location"] == (
        "https://secretnote.cloud/market/quant-signals"
        "?universe_limit=100&limit=0&recent_days=30"
    )

    stock_api = client.get(
        "/stocks/010060/quant-signals?refresh=true",
        headers={"accept": "application/json"},
        follow_redirects=False,
    )
    assert stock_api.status_code == 308
    assert stock_api.headers["location"] == (
        "https://secretnote.cloud/stocks/010060/quant-signals?refresh=true"
    )
    assert client.get("/health", follow_redirects=False).status_code == 200


def test_legacy_railway_browser_visit_shows_migration_bottom_sheet():
    client = TestClient(
        app,
        base_url="https://insight-mcp-production-945f.up.railway.app",
    )

    response = client.get(
        "/dashboard?view=ai-signals&source=legacy",
        headers={"accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.headers["cache-control"].startswith("no-store")
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["link"] == '<https://secretnote.cloud>; rel="canonical"'
    shell = response.text
    assert 'class="migration-sheet"' in shell
    assert 'role="dialog"' in shell
    assert 'aria-modal="true"' in shell
    assert "secretnote.cloud로<br />접속해 주세요!" in shell
    assert "KORNOTE2026" in shell
    assert "코드 복사하고 새 주소로 이동" in shell
    assert "15초 후 새 공식 주소로 자동 이동합니다." in shell
    assert "자동 이동 멈추기" in shell
    assert (
        'href="https://secretnote.cloud/dashboard?view=ai-signals&amp;source=legacy"'
        in shell
    )
    assert (
        'const destination = "https://secretnote.cloud/dashboard?view=ai-signals&source=legacy";'
        in shell
    )
    assert "navigator.clipboard.writeText(inviteCode)" in shell
    assert "window.location.replace(destination)" in shell
    assert 'if (event.key === "Tab")' in shell
    assert "last.focus()" in shell
    assert "@media (prefers-reduced-motion: reduce)" in shell
    assert ":focus-visible" in shell

    stock_api_visit = client.get(
        "/stocks/010060/quant-signals?refresh=true",
        headers={"accept": "text/html,application/xhtml+xml"},
        follow_redirects=False,
    )
    assert stock_api_visit.status_code == 200
    assert 'href="https://secretnote.cloud/dashboard/010060"' in stock_api_visit.text
    assert (
        'const destination = "https://secretnote.cloud/dashboard/010060";'
        in stock_api_visit.text
    )
    assert "secretnote.cloud/stocks/010060/quant-signals" not in stock_api_visit.text

    canonical_stock_ui = TestClient(
        app,
        base_url="https://secretnote.cloud",
    ).get(
        "/dashboard/010060",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert canonical_stock_ui.status_code == 200
    assert canonical_stock_ui.headers["content-type"].startswith("text/html")

    market_signal_visit = client.get(
        "/market/quant-signals?limit=1",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert 'href="https://secretnote.cloud/dashboard?view=ai-signals"' in (
        market_signal_visit.text
    )

    unknown_browser_visit = client.get(
        "/stocks/search?query=OCI",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert 'href="https://secretnote.cloud/dashboard?view=home"' in (
        unknown_browser_visit.text
    )

    root = client.get(
        "/",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert root.status_code == 200
    assert 'href="https://secretnote.cloud/dashboard?view=home"' in root.text

    current_railway = TestClient(
        app,
        base_url="https://insight-mcp-production-b297.up.railway.app",
    )
    current_response = current_railway.get(
        "/dashboard?view=home",
        headers={"accept": "text/html"},
        follow_redirects=False,
    )
    assert current_response.status_code == 200
    assert "KORNOTE2026" in current_response.text
    assert "secretnote.cloud로<br />접속해 주세요!" in current_response.text


def test_dashboard_refresh_removes_only_dashboard_cache_and_preserves_identity_storage():
    client = TestClient(app)

    version = client.get("/dashboard-version")
    assert version.status_code == 200
    assert version.json() == {"version": "20260904v465"}
    assert version.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"

    refresh = client.get("/dashboard-refresh?view=search")
    assert refresh.status_code == 200
    assert refresh.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert 'pathname === "/dashboard-sw.js"' in refresh.text
    assert 'key.startsWith("secret-note-static-")' in refresh.text
    assert "/dashboard?view=${encodeURIComponent(view)}&app_build=20260904v465" in refresh.text
    assert "localStorage.clear" not in refresh.text
    assert "sessionStorage.clear" not in refresh.text


def test_android_back_navigation_restores_history_and_confirms_exit_at_home():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/dashboard-app-v170.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="app-exit-dialog"' in shell
    assert 'role="alertdialog"' in shell
    assert 'id="app-exit-dialog-title">서비스를 종료할까요?</h2>' in shell
    assert 'id="app-exit-dialog-cancel" type="button">취소</button>' in shell
    assert 'id="app-exit-dialog-confirm" type="button">종료</button>' in shell
    for expected in (
        'const DASHBOARD_HISTORY_MARKER = "secret-note-dashboard";',
        "function initializeDashboardHistory()",
        "function writeDashboardHistory(route, url, mode = \"push\"",
        "function restoreDashboardScroll(historyState)",
        "async function handleDashboardPopState(event)",
        "if (isAndroidDevice() && target.rootBase && previous?.rootGuard)",
        "showAppExitDialog();",
        'new CustomEvent("secret-note:exit-requested"',
        'typeof bridge?.exitApp === "function"',
        'setView(routeView, { historyMode: "none" });',
        "navigateBackOrFallback(\"home\")",
    ):
        assert expected in source
    assert "window.history.pushState(guard" in source
    assert "window.history.back();" in source
    assert ".app-exit-dialog-actions button" in styles
    assert "min-height: 48px;" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


def test_dashboard_invite_code_is_validated_server_side_and_remembered(monkeypatch):
    monkeypatch.setattr("app.main.settings.dashboard_invite_code", "KORNOTE2026")
    monkeypatch.setattr("app.main.settings.dashboard_invite_hosts", "secretnote.cloud,www.secretnote.cloud")
    client = TestClient(app, base_url="https://secretnote.cloud")

    initial = client.get("/session/invite-status")
    assert initial.status_code == 200
    assert initial.json() == {"required": True, "authorized": False}

    rejected = client.post("/session/invite-access", json={"invite_code": "NOTE2026"})
    assert rejected.status_code == 401

    accepted = client.post("/session/invite-access", json={"invite_code": "kornote2026"})
    assert accepted.status_code == 200
    assert accepted.json()["required"] is True
    assert accepted.json()["authorized"] is True
    assert accepted.cookies.get("sn_invite_access")

    remembered = client.get("/session/invite-status")
    assert remembered.status_code == 200
    assert remembered.json() == {"required": True, "authorized": True}


def test_dashboard_access_rate_limit_returns_retry_after_and_request_id(monkeypatch):
    monkeypatch.setattr("app.main.settings.dashboard_invite_code", "KORNOTE2026")
    monkeypatch.setattr("app.main.settings.dashboard_invite_hosts", "secretnote.cloud,www.secretnote.cloud")
    client = TestClient(app, base_url="https://secretnote.cloud")
    client_ip = "203.0.113.42"
    key = ("dashboard-access", client_ip)

    accepted = client.post("/session/invite-access", json={"invite_code": "KORNOTE2026"})
    assert accepted.status_code == 200
    with rate_limit_lock:
        rate_limit_windows[key] = [time.monotonic()] * 30
    try:
        response = client.post(
            "/session/dashboard-access",
            json={"share_id": "rate-limit-check"},
            headers={"x-forwarded-for": client_ip},
        )
    finally:
        with rate_limit_lock:
            rate_limit_windows.pop(key, None)

    assert response.status_code == 429
    assert 1 <= int(response.headers["retry-after"]) <= 15 * 60
    assert response.headers["x-request-id"]
    assert response.json()["detail"] == "요청이 많습니다. 잠시 후 다시 시도해주세요."


def test_dashboard_access_db_failure_returns_retryable_503(monkeypatch):
    monkeypatch.setattr("app.main.settings.dashboard_invite_code", "KORNOTE2026")
    monkeypatch.setattr("app.main.settings.dashboard_invite_hosts", "secretnote.cloud,www.secretnote.cloud")
    client = TestClient(app, base_url="https://secretnote.cloud")

    class FailingSession:
        def get(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

        def rollback(self):
            return None

    def failing_db():
        yield FailingSession()

    accepted = client.post("/session/invite-access", json={"invite_code": "KORNOTE2026"})
    assert accepted.status_code == 200
    app.dependency_overrides[get_db] = failing_db
    try:
        response = client.post(
            "/session/dashboard-access",
            json={"share_id": "db-failure-check"},
            headers={"x-forwarded-for": "203.0.113.43"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"
    assert response.headers["x-request-id"]
    assert response.json()["detail"]["code"] == "access_unavailable"


def test_railway_domain_session_api_redirects_to_canonical_host():
    client = TestClient(app, base_url="https://insight-mcp-production-b297.up.railway.app")

    status = client.get("/session/invite-status", follow_redirects=False)
    assert status.status_code == 308
    assert status.headers["location"] == "https://secretnote.cloud/session/invite-status"

    invite = client.post(
        "/session/invite-access",
        json={"invite_code": "KORNOTE2026"},
        follow_redirects=False,
    )
    assert invite.status_code == 308
    assert invite.headers["location"] == "https://secretnote.cloud/session/invite-access"


def test_dashboard_identity_limit_rejects_only_new_custom_domain_ids(monkeypatch):
    init_db()
    test_ids = ["codex-capacity-a", "codex-capacity-b", "codex-capacity-full"]
    with SessionLocal() as db:
        db.execute(delete(DashboardAccessIdentity).where(DashboardAccessIdentity.share_id.in_(test_ids)))
        base_count = int(db.scalar(select(func.count()).select_from(DashboardAccessIdentity)) or 0)
        quota = db.get(DashboardAccessQuota, 1)
        quota.admitted_count = base_count
        db.commit()

    monkeypatch.setattr("app.main.settings.dashboard_invite_code", "KORNOTE2026")
    monkeypatch.setattr("app.main.settings.dashboard_invite_hosts", "secretnote.cloud,www.secretnote.cloud")
    monkeypatch.setattr("app.main.settings.dashboard_identity_limit", base_count + 2)
    client = TestClient(app, base_url="https://secretnote.cloud")

    try:
        unverified = client.post("/session/dashboard-access", json={"share_id": test_ids[0]})
        assert unverified.status_code == 403

        invited = client.post("/session/invite-access", json={"invite_code": "KORNOTE2026"})
        assert invited.status_code == 200

        first = client.post("/session/dashboard-access", json={"share_id": test_ids[0]})
        second = client.post("/session/dashboard-access", json={"share_id": test_ids[1]})
        assert first.status_code == 200
        assert first.json()["newly_registered"] is True
        assert second.status_code == 200
        assert second.json()["registered_count"] == base_count + 2

        full = client.post("/session/dashboard-access", json={"share_id": test_ids[2]})
        assert full.status_code == 409
        assert full.json()["detail"]["code"] == "capacity_full"
        assert full.json()["detail"]["limit"] == base_count + 2

        existing = client.post("/session/dashboard-access", json={"share_id": test_ids[0]})
        assert existing.status_code == 200
        assert existing.json()["newly_registered"] is False
    finally:
        with SessionLocal() as db:
            db.execute(delete(DashboardAccessIdentity).where(DashboardAccessIdentity.share_id.in_(test_ids)))
            quota = db.get(DashboardAccessQuota, 1)
            quota.admitted_count = int(db.scalar(select(func.count()).select_from(DashboardAccessIdentity)) or 0)
            db.commit()


def test_push_notification_history_keeps_only_recent_three_days():
    init_db()
    client = TestClient(app)
    share_id = "codex-push-history"
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    write_token = token_response.json()["write_token"]
    now = datetime.utcnow()
    received_at = now - timedelta(hours=2)
    received_event_date = (
        received_at.replace(tzinfo=timezone.utc)
        .astimezone(ZoneInfo("Asia/Seoul"))
        .date()
    )
    while received_event_date.weekday() >= 5:
        received_at -= timedelta(days=1)
        received_event_date = (
            received_at.replace(tzinfo=timezone.utc)
            .astimezone(ZoneInfo("Asia/Seoul"))
            .date()
        )
    stale_event_date = received_event_date - timedelta(days=8)
    with SessionLocal() as db:
        db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
        db.add_all(
            [
                PushNotificationHistory(
                    share_id=share_id,
                    event_key=f"market-ai-signal:005930:buy:{received_event_date.isoformat()}",
                    notification_kind="market_ai_signal",
                    title="최근 알림",
                    body=f"{received_event_date.isoformat()} 매수 신호가 새로 확정됐습니다.",
                    url="/dashboard/삼성전자",
                    created_at=received_at,
                ),
                PushNotificationHistory(
                    share_id=share_id,
                    event_key=f"market-ai-signal:000660:sell:{stale_event_date.isoformat()}",
                    notification_kind="market_ai_signal",
                    title="과거 신호 재적재 알림",
                    body=f"{stale_event_date.isoformat()} 매도 신호가 뒤늦게 재적재됐습니다.",
                    url="/dashboard/SK하이닉스",
                    created_at=now - timedelta(hours=1),
                ),
                PushNotificationHistory(
                    share_id=share_id,
                    event_key="expired:event",
                    notification_kind="report",
                    title="지난 알림",
                    body="보관 기간을 지났습니다.",
                    url="/dashboard/삼성전자",
                    created_at=now - timedelta(days=4),
                ),
            ]
        )
        db.commit()
    try:
        denied = client.get(f"/push/notifications/{share_id}")
        assert denied.status_code == 403

        response = client.get(
            f"/push/notifications/{share_id}",
            headers={"X-Write-Token": write_token},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["retention_days"] == 3
        assert [item["title"] for item in payload["items"]] == ["최근 알림"]
        assert payload["items"][0]["event_date"] == received_event_date.isoformat()
        assert payload["items"][0]["created_at"].endswith("Z")
        with SessionLocal() as db:
            remaining = list(
                db.scalars(
                    PushNotificationHistory.__table__.select().where(
                        PushNotificationHistory.share_id == share_id
                    )
                )
            )
            assert len(remaining) == 1
    finally:
        with SessionLocal() as db:
            db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
            db.commit()


def test_market_signal_feed_includes_delivered_preliminary_history(monkeypatch):
    init_db()
    client = TestClient(app)
    kst = ZoneInfo("Asia/Seoul")
    signal_date = datetime.now(kst).date()
    delivered_at = datetime(
        signal_date.year,
        signal_date.month,
        signal_date.day,
        0,
        12,
    )
    signal_as_of = datetime(
        signal_date.year,
        signal_date.month,
        signal_date.day,
        13,
        28,
        tzinfo=kst,
    )
    share_id = "codex-market-preliminary-history"
    payload = {
        "status": "ready",
        "snapshot_generated_at": datetime.now(timezone.utc),
        "as_of": signal_as_of,
        "universe_count": 100,
        "preliminary_count": 1,
        "confirmed_count": 0,
        "preliminary_history": [
            {
                "code": "003550",
                "name": "LG",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": signal_date,
                "first_seen_at": signal_as_of,
                "last_seen_at": signal_as_of,
                "active": True,
            }
        ],
        "items": [
            {
                "code": "003550",
                "name": "LG",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": signal_date,
                "status": "preliminary",
                "is_preliminary": True,
            }
        ],
    }
    with SessionLocal() as db:
        db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
        db.add_all(
            [
                PushNotificationHistory(
                    share_id=share_id,
                    event_key=f"market-ai-preliminary:003550:buy:{signal_date.isoformat()}",
                    notification_kind="market_ai_signal",
                    title="✨ [예비 매수] LG",
                    body="장중 조건입니다.",
                    url="/dashboard/LG",
                    created_at=delivered_at,
                ),
                PushNotificationHistory(
                    share_id=share_id,
                    event_key=f"market-ai-preliminary:078930:sell:{signal_date.isoformat()}",
                    notification_kind="market_ai_signal",
                    title="⚠️ [예비 매도] GS",
                    body="장중 조건입니다.",
                    url="/dashboard/GS",
                    created_at=delivered_at,
                ),
                PushNotificationHistory(
                    share_id=share_id,
                    event_key=f"ai-preliminary:005930:buy:{signal_date.isoformat()}",
                    notification_kind="ai_signal",
                    title="삼성전자 AI 시그널 · 예비 매수",
                    body="이 계정의 관심종목에서만 발생했습니다.",
                    url="/dashboard/005930",
                    created_at=delivered_at,
                ),
            ]
        )
        db.commit()
    from app import main as main_module

    main_module.market_quant_signal_cache.clear()
    monkeypatch.setattr(main_module, "load_market_quant_signal_snapshot", lambda *_args, **_kwargs: payload)
    try:
        response = client.get("/market/quant-signals?universe_limit=100&limit=0&recent_days=30")
        assert response.status_code == 200
        history = {item["code"]: item for item in response.json()["preliminary_history"]}
        assert history["003550"]["active"] is True
        assert history["003550"]["first_seen_at"] == f"{signal_date.isoformat()}T09:12:00+09:00"
        assert history["003550"]["last_seen_at"] == f"{signal_date.isoformat()}T13:28:00+09:00"
        assert history["078930"]["active"] is False
        assert history["078930"]["name"] == "GS"
        assert history["078930"]["signal"] == "예비 매도"
        assert "005930" not in history
    finally:
        main_module.market_quant_signal_cache.clear()
        with SessionLocal() as db:
            db.execute(delete(PushNotificationHistory).where(PushNotificationHistory.share_id == share_id))
            db.commit()


def test_stale_market_signal_snapshot_hides_preliminary_rows_and_refreshes(monkeypatch):
    from app import main as main_module

    refresh_calls = []
    stale_age = timedelta(
        seconds=main_module.MARKET_QUANT_SIGNAL_CLOSED_MAX_AGE_SECONDS + 60
    )
    payload = {
        "status": "ready",
        "strategy_version": "position-lifecycle-v7.4",
        "snapshot_generated_at": datetime.now(timezone.utc) - stale_age,
        "as_of": datetime.now(ZoneInfo("Asia/Seoul")) - stale_age,
        "universe_count": 100,
        "recent_days": 29,
        "preliminary_count": 1,
        "confirmed_count": 1,
        "items": [
            {
                "code": "035420",
                "name": "NAVER",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": datetime.now(ZoneInfo("Asia/Seoul")).date(),
                "status": "preliminary",
                "is_preliminary": True,
            },
            {
                "code": "090430",
                "name": "아모레퍼시픽",
                "side": "buy",
                "signal": "확정 매수",
                "signal_date": "2026-07-29",
                "execution_date": "2026-07-30",
                "price": 121_900,
                "entry_price": 121_900,
                "status": "confirmed",
                "is_preliminary": False,
            },
        ],
    }
    main_module.market_quant_signal_cache.clear()
    monkeypatch.setattr(
        main_module,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_market_quant_signal_snapshot",
        lambda *args, **kwargs: refresh_calls.append((args, kwargs)),
    )
    try:
        response = TestClient(app).get(
            "/market/quant-signals?universe_limit=100&limit=0&recent_days=29"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "refreshing"
        assert body["snapshot_state"] == "stale"
        assert body["stale_preliminary_count"] == 1
        assert body["preliminary_count"] == 0
        assert all(item["status"] == "confirmed" for item in body["items"])
        assert "035420" not in {item["code"] for item in body["items"]}
        assert "090430" in {item["code"] for item in body["items"]}
        assert refresh_calls
    finally:
        main_module.market_quant_signal_cache.clear()


def test_market_signal_snapshot_freshness_uses_session_specific_limits(monkeypatch):
    from app import main as main_module

    active_now = datetime(2026, 8, 21, 14, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    monkeypatch.setattr(
        main_module,
        "is_korea_regular_market_session",
        lambda value: value == active_now,
    )
    active_payload = {
        "snapshot_generated_at": (
            active_now
            - timedelta(seconds=main_module.MARKET_QUANT_SIGNAL_ACTIVE_MAX_AGE_SECONDS + 1)
        ).isoformat()
    }
    closed_now = datetime(2026, 8, 21, 20, 0, tzinfo=ZoneInfo("Asia/Seoul"))
    closed_fresh_payload = {
        "snapshot_generated_at": (closed_now - timedelta(hours=1)).isoformat()
    }
    closed_stale_payload = {
        "snapshot_generated_at": (
            closed_now
            - timedelta(seconds=main_module.MARKET_QUANT_SIGNAL_CLOSED_MAX_AGE_SECONDS + 1)
        ).isoformat()
    }

    assert main_module._market_quant_signal_snapshot_freshness(
        active_payload, active_now
    )["snapshot_state"] == "stale"
    assert main_module._market_quant_signal_snapshot_freshness(
        closed_fresh_payload, closed_now
    )["snapshot_state"] == "fresh"
    assert main_module._market_quant_signal_snapshot_freshness(
        closed_stale_payload, closed_now
    )["snapshot_state"] == "stale"
    future_payload = {
        "snapshot_generated_at": (closed_now + timedelta(hours=1)).isoformat()
    }
    future_freshness = main_module._market_quant_signal_snapshot_freshness(
        future_payload, closed_now
    )
    assert future_freshness["snapshot_state"] == "stale"
    assert future_freshness["snapshot_age_seconds"] == 0
    assert future_freshness["snapshot_future_skew_seconds"] == 3600


def test_fresh_market_signal_snapshot_keeps_current_preliminary_rows(monkeypatch):
    from app import main as main_module

    payload = {
        "status": "ready",
        "strategy_version": "position-lifecycle-v7.4",
        "snapshot_generated_at": datetime.now(timezone.utc),
        "as_of": datetime.now(ZoneInfo("Asia/Seoul")),
        "universe_count": 100,
        "recent_days": 28,
        "preliminary_count": 1,
        "confirmed_count": 0,
        "items": [
            {
                "code": "035420",
                "name": "NAVER",
                "side": "buy",
                "signal": "예비 매수",
                "signal_date": datetime.now(ZoneInfo("Asia/Seoul")).date(),
                "status": "preliminary",
                "is_preliminary": True,
            }
        ],
    }
    main_module.market_quant_signal_cache.clear()
    monkeypatch.setattr(
        main_module,
        "load_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected refresh")),
    )
    try:
        response = TestClient(app).get(
            "/market/quant-signals?universe_limit=100&limit=0&recent_days=28"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ready"
        assert body["snapshot_state"] == "fresh"
        assert body["preliminary_count"] == 1
        assert any(item["code"] == "035420" for item in body["items"])
    finally:
        main_module.market_quant_signal_cache.clear()


def test_market_quant_signal_preparing_payload_includes_active_reconciliation(monkeypatch):
    from app import main as main_module

    class BusyRefreshLock:
        @staticmethod
        def acquire(*, blocking):
            assert blocking is False
            return False

    main_module.market_quant_signal_cache.clear()
    monkeypatch.setattr(main_module, "market_quant_signal_refresh_lock", BusyRefreshLock())
    monkeypatch.setattr(main_module, "load_market_quant_signal_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_module, "_refresh_market_quant_signal_snapshot", lambda *_args, **_kwargs: None)
    try:
        response = TestClient(app).get(
            "/market/quant-signals?universe_limit=100&limit=0&recent_days=30"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "preparing"
        assert payload["strategy_version"] == "position-lifecycle-v7.4"
        oci = next(item for item in payload["items"] if item["code"] == "010060")
        assert oci["status"] == "confirmed"
        assert oci["side"] == "sell"
        assert oci["signal_date"] == "2026-08-20"
        assert oci["execution_date"] == "2026-08-20"
        assert oci["reconciliation_id"] == "legacy-v2-oci-010060-close-20260820"
    finally:
        main_module.market_quant_signal_cache.clear()


def test_dashboard_notification_button_opens_notification_page_before_settings():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        'id="notifications-view"',
        'id="push-history-tabs"',
        'data-notification-tab="all"',
        'data-notification-tab="ai_signal"',
        'data-notification-tab="watchlist"',
        'data-notification-tab="major_event"',
        'id="push-history-settings"',
        'id="push-history-list"',
        'id="push-notification-unread-dot"',
        'class="secondary-commandbar notifications-commandbar"',
    ):
        assert expected in shell
    for expected in (
        "async function openPushNotificationCenter()",
        "const likelyEnabled = state.pushNotificationEnabled",
        "function setPushNotificationUnread(unread)",
        "function hydratePushNotificationHistory()",
        "function pushHistoryEventDate(item, formattedTime = \"\")",
        'elements.pushHistoryMeta.textContent = `${items.length}건 · 최근 3일 수신`;',
        'setView("notifications");',
        'if (view === "notifications")',
        'writeDashboardHistory(',
        'const nextTab = tab.dataset.notificationTab || "all";',
        "pushNotificationHistoryScrollTop: new Map()",
        "renderPushNotificationHistory({ restoreScroll: true });",
        'fetch(`/push/notifications/${encodeURIComponent(state.watchlistId)}`',
        'elements.pushHistorySettings?.addEventListener("click", openPushSettingsFromHistory)',
    ):
        assert expected in source
    notification_center = source[
        source.index("async function openPushNotificationCenter()"):
        source.index("async function openPushSettingsFromHistory()")
    ]
    unsupported_state = source[
        source.index("async function refreshPushNotificationState(options = {})"):
        source.index("async function savePushNotificationSettings(options = {})")
    ]
    assert "if (!state.watchlistId)" in notification_center
    assert "if (!state.watchlistId || state.pushNotificationBusy)" not in notification_center
    assert 'label: "알림 안내", buttonText: "알림", disabled: false' in unsupported_state


def test_push_config_includes_morning_briefing_and_korea_market_session_reminders():
    client = TestClient(app)

    response = client.get("/push/config")

    assert response.status_code == 200
    payload = response.json()
    options = {item["id"]: item for item in payload["condition_options"]}
    assert options["morning_briefing"] == {
        "id": "morning_briefing",
        "label": "돈이 되는 소식",
        "description": "매일 오전 8시·낮 12시·오후 4시에 새 소식을 알려드립니다.",
        "required": True,
    }
    assert "morning_briefing" in payload["conditions"]
    assert options["market_session"] == {
        "id": "market_session",
        "label": "국내장 시작·마감",
        "description": "국내 정규장 시작과 마감 5분 전에 알려드립니다.",
    }
    assert options["recommendation_update"] == {
        "id": "recommendation_update",
        "label": "추천 업데이트",
        "description": "상위 10 신규 진입과 추천 종목의 매수·매도 단계 변경을 알려드립니다.",
    }
    assert "recommendation_update" in payload["conditions"]
    source = client.get("/dashboard-app-v170.js").text
    assert 'id: "morning_briefing"' in source
    assert 'label: "돈이 되는 소식"' in source
    assert "매일 오전 8시·낮 12시·오후 4시" in source
    assert 'morning_briefing: "돈이 되는 소식"' in source
    assert 'id: "recommendation_update"' in source
    assert 'recommendation_update: "추천 업데이트"' in source
    shell = client.get("/dashboard?view=notifications").text
    assert 'data-notification-tab="recommendation_update">추천<' in shell


def test_secondary_pages_use_stock_detail_navigation_contract():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'class="secondary-commandbar notifications-commandbar"',
        'class="secondary-commandbar ai-signals-commandbar"',
        'class="secondary-commandbar market-ranking-commandbar"',
        'class="secondary-commandbar recommend-detail-topbar"',
        'class="secondary-commandbar chart-history-commandbar"',
        'class="secondary-commandbar-back notifications-back"',
        'id="ai-signals-back"',
        'class="secondary-commandbar-back market-ranking-back"',
        'id="chart-history-back-button"',
    ):
        assert expected in shell

    assert '<header class="app-page-intro"><span>저장 기록</span>' not in shell
    assert "Secondary navigation 6.0" in styles
    for view in ("notifications", "ai-signals", "movers", "recommend-detail", "chart-history"):
        assert f'[data-view="{view}"]' in styles
    secondary_rules = styles.split("/* Secondary navigation 6.0", 1)[1].split(
        ".secondary-commandbar",
        1,
    )[0]
    assert '[data-view="news"]' not in secondary_rules
    assert ":is(.app-topbar, .bottom-nav)" in styles
    assert "grid-template-columns: 42px minmax(0, 1fr) 42px" in styles

    source = client.get("/dashboard-app-v170.js").text
    active_view_rules = source[source.index("const activeView ="):source.index("for (const item of elements.appNavItems)")]
    assert '"news"' not in active_view_rules


def test_watchlist_share_id_roundtrip():
    init_db()
    client = TestClient(app)
    share_id = f"codex-test-watchlist-{time.time_ns()}"
    payload = {"items": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]}
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    write_token = token_response.json()["write_token"]

    saved = client.put(f"/watchlists/{share_id}", json=payload, headers={"X-Write-Token": write_token})
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["share_id"] == share_id
    assert saved_body["items"] == [
        {
            **payload["items"][0],
            "investor_state": "not_holding",
            "average_buy_price": None,
        }
    ]

    loaded = client.get(f"/watchlists/{share_id}")
    assert loaded.status_code == 200
    assert loaded.json()["items"] == [
        {
            **payload["items"][0],
            "investor_state": "not_holding",
            "average_buy_price": None,
        }
    ]
    assert "no-store" in loaded.headers["cache-control"]

    legacy_alias = client.put(
        f"/watchlists/{share_id}",
        json={
            "items": [
                {
                    **payload["items"][0],
                    "investor_state": "before_buy",
                    "average_buy_price": 70_000,
                }
            ]
        },
        headers={"X-Write-Token": write_token},
    )
    assert legacy_alias.status_code == 200
    assert legacy_alias.json()["items"][0]["investor_state"] == "not_holding"
    assert legacy_alias.json()["items"][0]["average_buy_price"] is None

    holding_payload = {
        "items": [
            {
                **payload["items"][0],
                "investor_state": "holding",
                "average_buy_price": 71_500,
            }
        ]
    }
    holding = client.put(
        f"/watchlists/{share_id}",
        json=holding_payload,
        headers={"X-Write-Token": write_token},
    )
    assert holding.status_code == 200
    assert holding.json()["items"][0]["investor_state"] == "holding"
    assert holding.json()["items"][0]["average_buy_price"] == "71500.00"

    legacy_update = client.put(
        f"/watchlists/{share_id}",
        json=payload,
        headers={"X-Write-Token": write_token},
    )
    assert legacy_update.status_code == 200
    assert legacy_update.json()["items"][0]["investor_state"] == "holding"
    assert legacy_update.json()["items"][0]["average_buy_price"] == "71500.00"

    cleared = client.put(
        f"/watchlists/{share_id}",
        json={
            "items": [
                {**payload["items"][0], "investor_state": "not_holding"}
            ]
        },
        headers={"X-Write-Token": write_token},
    )
    assert cleared.status_code == 200
    assert cleared.json()["items"][0]["investor_state"] == "not_holding"
    assert cleared.json()["items"][0]["average_buy_price"] is None


def test_watchlists_remain_isolated_per_user_and_preserve_each_users_order():
    init_db()
    share_id_a = "codex-isolated-watchlist-a"
    share_id_b = "codex-isolated-watchlist-b"
    client_a = TestClient(app)
    client_b = TestClient(app)
    payload_a = {
        "items": [
            {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
            {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        ]
    }
    payload_b = {
        "items": [
            {"code": "035420", "name": "NAVER", "market": "KOSPI"},
            {"code": "035720", "name": "카카오", "market": "KOSPI"},
        ]
    }
    try:
        token_a = client_a.get(f"/session/write-token?share_id={share_id_a}").json()["write_token"]
        token_b = client_b.get(f"/session/write-token?share_id={share_id_b}").json()["write_token"]

        assert client_a.put(
            f"/watchlists/{share_id_a}",
            json=payload_a,
            headers={"X-Write-Token": token_a},
        ).status_code == 200
        assert client_b.put(
            f"/watchlists/{share_id_b}",
            json=payload_b,
            headers={"X-Write-Token": token_b},
        ).status_code == 200

        loaded_a = client_a.get(f"/watchlists/{share_id_a}").json()
        loaded_b = client_b.get(f"/watchlists/{share_id_b}").json()
        assert [item["code"] for item in loaded_a["items"]] == ["005930", "000660"]
        assert [item["code"] for item in loaded_b["items"]] == ["035420", "035720"]
        assert set(item["code"] for item in loaded_a["items"]).isdisjoint(
            item["code"] for item in loaded_b["items"]
        )

        cross_user_write = client_a.put(
            f"/watchlists/{share_id_b}",
            json=payload_a,
            headers={"X-Write-Token": token_a},
        )
        assert cross_user_write.status_code == 403
        assert [
            item["code"] for item in client_b.get(f"/watchlists/{share_id_b}").json()["items"]
        ] == ["035420", "035720"]
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(WatchlistItem).where(
                    WatchlistItem.share_id.in_([share_id_a, share_id_b])
                )
            )
            db.commit()


def test_recommendation_tracks_sync_and_keep_initialized_empty_state():
    init_db()
    client = TestClient(app)
    share_id = "codex-recommendation-tracks"
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    headers = {"X-Write-Token": token_response.json()["write_token"]}
    payload = {
        "items": [
            {
                "id": "005930-1",
                "code": "005930",
                "name": "삼성전자",
                "market": "KOSPI",
                "tracked_at": "2026-07-30T00:00:00.000Z",
                "tracked_price": 120000,
                "item": {"score": 72, "reasons": ["수급 개선"]},
            }
        ]
    }
    try:
        initial = client.get(f"/watchlists/{share_id}/recommendation-tracks")
        assert initial.status_code == 200
        assert initial.json()["initialized"] is False
        assert initial.json()["items"] == []
        assert "no-store" in initial.headers["cache-control"]

        saved = client.put(
            f"/watchlists/{share_id}/recommendation-tracks",
            json=payload,
            headers=headers,
        )
        assert saved.status_code == 200
        assert saved.json()["initialized"] is True
        assert saved.json()["items"] == payload["items"]

        cleared = client.put(
            f"/watchlists/{share_id}/recommendation-tracks",
            json={"items": []},
            headers=headers,
        )
        assert cleared.status_code == 200
        assert cleared.json()["initialized"] is True
        assert cleared.json()["items"] == []

        loaded = client.get(f"/watchlists/{share_id}/recommendation-tracks")
        assert loaded.status_code == 200
        assert loaded.json()["initialized"] is True
        assert loaded.json()["items"] == []
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(RecommendationTrackState).where(
                    RecommendationTrackState.share_id == share_id
                )
            )
            db.commit()


def test_dashboard_identity_uses_server_as_source_of_truth_and_syncs_pins():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    for expected in (
        'cache: "no-store"',
        "fetchRemoteRecommendationTracks(normalizedId)",
        "remoteTrackPayload.initialized !== true",
        "saveRemoteRecommendationTracks(localTrackItems, normalizedId)",
        "writeWatchlist(remoteItems, { sync: false });",
        "writeRecommendationTracks(remoteTrackItems, { sync: false, shareId: normalizedId });",
        "watchlistSyncPending: false",
        "recommendationTrackSyncPending: false",
        "queueRemoteRecommendationTrackSync();",
        "recommendationTrackStorageKey(currentId)",
    ):
        assert expected in source

    assert "merge: true" not in source
    assert "[...localItems, ...remoteItems]" not in source


def test_watchlist_update_preserves_existing_item_added_at():
    init_db()
    client = TestClient(app)
    share_id = "codex-watchlist-added-at"
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    write_token = token_response.json()["write_token"]
    headers = {"X-Write-Token": write_token}
    first_payload = {
        "items": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]
    }
    second_payload = {
        "items": [
            {"code": "005930", "name": "삼성전자", "market": "KOSPI"},
            {"code": "000660", "name": "SK하이닉스", "market": "KOSPI"},
        ]
    }
    try:
        assert client.put(f"/watchlists/{share_id}", json=first_payload, headers=headers).status_code == 200
        with SessionLocal() as db:
            first_added_at = db.scalar(
                WatchlistItem.__table__.select()
                .with_only_columns(WatchlistItem.created_at)
                .where(
                    WatchlistItem.share_id == share_id,
                    WatchlistItem.code == "005930",
                )
            )

        assert client.put(f"/watchlists/{share_id}", json=second_payload, headers=headers).status_code == 200
        with SessionLocal() as db:
            rows = list(
                db.scalars(
                    WatchlistItem.__table__.select()
                    .with_only_columns(WatchlistItem.created_at)
                    .where(
                        WatchlistItem.share_id == share_id,
                        WatchlistItem.code == "005930",
                    )
                )
            )
        assert rows == [first_added_at]
    finally:
        with SessionLocal() as db:
            db.execute(delete(WatchlistItem).where(WatchlistItem.share_id == share_id))
            db.commit()


def test_briefing_status():
    client = TestClient(app)
    response = client.get("/briefings/status")
    assert response.status_code == 200
    body = response.json()
    assert "enabled" in body
    assert "poll_seconds" in body
    assert "research_enabled" in body
    assert "research_poll_seconds" in body
    assert "disclosure_enabled" in body
    assert "news_enabled" in body
    assert "price_enabled" in body
    assert "toss_enabled" not in body
    assert "toss_sync_holdings_enabled" not in body
    assert "disclosure_poll_seconds" in body
    assert "news_poll_seconds" in body
    assert "price_poll_seconds" in body
    assert "investor_flow_enabled" in body
    assert "investor_flow_poll_seconds" in body
    assert "financials_enabled" in body
    assert "financials_poll_seconds" in body
    assert "fundamental_snapshot_enabled" in body
    assert "fundamental_snapshot_poll_seconds" in body
    assert body["fundamental_snapshot_effective_poll_seconds"] == 86400
    assert body["fundamental_snapshot_refresh_days"] == 2
    assert body["fundamental_snapshot_collection_refresh_days"] == 1
    assert "macro_enabled" in body
    assert "macro_poll_seconds" in body
    assert "toss_poll_seconds" not in body
    assert "toss_order_poll_seconds" not in body
    assert "last_price_at" in body
    assert "last_investor_flow_at" in body
    assert "last_financials_at" in body
    assert "last_fundamental_snapshot_at" in body
    assert body["last_fundamental_snapshot_state"] in {"idle", "ready", "degraded", "error"}
    assert "last_fundamental_snapshot_priority_failed" in body
    assert "last_fundamental_snapshot_full_failed" in body
    assert "next_fundamental_snapshot_retry_at" in body
    assert "last_macro_at" in body
    assert "source_errors" in body


def test_insight_shell_and_feed():
    client = TestClient(app)

    shell = client.get("/insight")
    assert shell.status_code == 200
    assert "text/html" in shell.headers["content-type"]
    assert "<title>인사이트</title>" in shell.text

    dashboard_shell = client.get("/dashboard")
    assert dashboard_shell.status_code == 200
    assert "text/html" in dashboard_shell.headers["content-type"]
    assert "비밀노트" in dashboard_shell.text

    nasdaq_shell = client.get("/nasdaq")
    assert nasdaq_shell.status_code == 200
    assert "text/html" in nasdaq_shell.headers["content-type"]
    assert "미국증시" in nasdaq_shell.text

    portfolio_shell = client.get("/portfolio")
    assert portfolio_shell.status_code == 200
    assert "AI 주식 정보 서비스 제품 사례" in portfolio_shell.text
    assert "AI 사용" in portfolio_shell.text
    assert "데이터가 기준을 만들고, AI가 확인 순서를 만듭니다." in portfolio_shell.text
    assert "가격과 시장 조건은 계산 레이어에서 확인하고" in portfolio_shell.text
    assert "핵심 기능" in portfolio_shell.text
    assert "현재 프로덕션 화면을 기준으로" in portfolio_shell.text
    assert portfolio_shell.text.count('<article class="feature-story') == 5
    feature_ids = [
        "feature-ai-signals",
        "feature-feed-content",
        "feature-company-health",
        "feature-report-analysis",
        "feature-chart-study",
    ]
    feature_assets = [
        "feature-ai-signals-production.jpg",
        "feature-feed-content-production.jpg",
        "feature-sk-hynix-company-health-production.jpg",
        "feature-sk-hynix-report-analysis-production.jpg",
        "feature-sk-hynix-chart-study-production.jpg",
    ]
    feature_positions = [portfolio_shell.text.index(f'id="{feature_id}"') for feature_id in feature_ids]
    assert feature_positions == sorted(feature_positions)
    assert "AI 시그널" in portfolio_shell.text
    assert "피드 콘텐츠" in portfolio_shell.text
    assert "기업 체력" in portfolio_shell.text
    assert "리포트 분석" in portfolio_shell.text
    assert "차트 공부" in portfolio_shell.text
    assert "SK하이닉스" in portfolio_shell.text
    assert "iPhone 13 Pro · 390×844" in portfolio_shell.text
    assert "매수 확정 필터와 종목별 신호 이후 수익률" in portfolio_shell.text
    image_dir = Path(__file__).parents[1] / "app" / "static" / "portfolio" / "images"
    for asset in feature_assets:
        assert asset in portfolio_shell.text
        assert (image_dir / asset).stat().st_size > 0
    assert "feature-home" not in portfolio_shell.text
    assert "portfolio-home-current.png" not in portfolio_shell.text
    assert "https://secretnote.cloud/dashboard?view=home" in portfolio_shell.text
    assert "insight-mcp-production-945f.up.railway.app" not in portfolio_shell.text

    concepts_shell = client.get("/concepts")
    assert concepts_shell.status_code == 200
    assert "주식 정보 서비스 디자인 탐색" in concepts_shell.text
    assert "Market Pulse" in concepts_shell.text
    assert "Equity Lens" in concepts_shell.text
    assert "My Signals" in concepts_shell.text

    feed = client.get("/insight/feed")
    assert feed.status_code == 200
    body = feed.json()
    assert "research_reports" in body
    assert "disclosures" in body
    assert "news_items" in body
    assert "company_briefs" in body
    assert "briefing_quotes" in body
    assert "watch_codes" in body
    assert "latest_prices" in body
    assert "toss_status" not in body
    assert "toss_accounts" not in body
    assert "toss_holdings" not in body
    assert "toss_orders" not in body


def test_watch_point_expansion_survives_market_data_refresh():
    client = TestClient(app)

    for asset_path in ("/assets/dashboard/app.js", "/assets/nasdaq/app.js"):
        response = client.get(asset_path)
        assert response.status_code == 200
        source = response.text
        assert 'const keepExpanded = itemCode ? state.watchPreopenExpanded.has(itemCode) : false;' in source
        assert 'section.dataset.mode !== "regular"' not in source
        assert "state.watchPreopenExpanded.delete(itemCode)" not in source

    dashboard_source = client.get("/assets/dashboard/app.js").text
    assert "이벤트·뉴스·거시·수급·미국 섹터를 종합해 우선순위를 계산합니다." not in dashboard_source


def test_stock_research_links_open_in_current_view_and_tab_survives_refresh():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert 'title.target = "_blank"' not in source
    assert 'title.setAttribute("aria-label", `${report.title || "리포트"} 원문 보기`);' in source
    assert "function naverResearchDetailUrl(row)" in source
    assert 'row?.source !== "naver_finance" || row?.source_category !== "company"' in source
    assert "return naverResearchDetailUrl(row) || naverNewsArticleUrl(row) || row?.pdf_url || row?.detail_url || row?.url || null;" in source
    assert 'const sameStock = previousStock?.code === stock.code;' in source
    assert 'if (previousStock?.code && !sameStock)' in source
    assert 'setActiveStockTab(state.stockActiveTab || "summary", {' in source
    assert "preserveScroll: true," in source
    assert "deferDataLoads: true," in source


def test_dashboard_shows_shared_loading_state_for_navigation_and_stock_lookup():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="page-loading"' in shell
    assert 'id="page-loading-label"' in shell
    assert "function runPageLoading" in source
    assert "function launchPageLoading" in source
    assert "function clearPageLoading" in source
    assert "return runPageLoading(PAGE_LOADING_LABELS.stock" in source
    assert "function launchBriefPageLoading" in source
    for view in ("market", "watchlist", "recommend", "trend", "chart"):
        assert f"PAGE_LOADING_LABELS.{view.replace('-', '_')}" in source or f'PAGE_LOADING_LABELS["{view}"]' in source


def test_home_market_indices_move_left_continuously_and_respect_user_motion_preferences():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for contract in (
        "const HOME_MARKET_CAROUSEL_SPEED_PX_PER_SECOND = 10;",
        "const HOME_MARKET_CAROUSEL_INTERACTION_HOLD_MS = 4_000;",
        "function homeMarketCarouselTrack(carousel = elements.homeMarketCarousel)",
        "function normalizeHomeMarketCarouselPosition(position, loopWidth = state.homeMarketCarouselLoopWidth)",
        'window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true',
        "function useNativeHomeMarketCarouselScroll()",
        "const animation = track.animate(",
        '{ transform: `translate3d(${-loopWidth}px, 0, 0)` },',
        "animation.currentTime = (position / HOME_MARKET_CAROUSEL_SPEED_PX_PER_SECOND) * 1_000;",
        "state.homeMarketCarouselUsesNativeScroll = false;",
        "carousel.scrollLeft = 0;",
        'clone.setAttribute("aria-hidden", "true");',
        "clone.inert = true;",
        "const previousProgress = homeMarketCarouselProgress();",
        'const track = el("div", "home-market-track");',
        "prepareHomeMarketCarouselMotion(previousProgress);",
        'carousel.addEventListener("pointerdown", beginInteraction, { passive: true });',
        "holdHomeMarketCarouselMotion();",
        "stopHomeMarketCarouselMotion();",
    ):
        assert contract in source

    motion_styles = styles[styles.index("/* Home market strip 7.4") :]
    assert ".home-market-carousel > .home-market-track" in motion_styles
    assert ".home-market-carousel.is-auto-scrolling" in motion_styles
    assert "scroll-snap-type: none;" in motion_styles
    assert "will-change: transform;" in motion_styles
    assert "-webkit-font-smoothing: antialiased;" in motion_styles
    assert "backface-visibility: hidden;" in motion_styles
    assert "overflow-x: hidden;" in motion_styles
    assert ".home-market-carousel.is-auto-scrolling.is-user-scrolling" in motion_styles
    assert "will-change: scroll-position;" not in motion_styles
    assert "transform: translateZ(0);" not in motion_styles
    assert "[data-market-carousel-clone=\"true\"]" in motion_styles
    assert "@media (prefers-reduced-motion: reduce)" in motion_styles

    staging_source = client.get("/assets/staging/toss-ia.js").text
    assert '!carousel.classList.contains("is-auto-scrolling")' in staging_source
    assert '!carousel.querySelector(":scope > .home-market-track")' in staging_source
    assert 'if (carousel.classList.contains("is-auto-scrolling") || mainTrack) {' in staging_source
    assert 'carousel.querySelectorAll(":scope > [data-marquee-clone]").forEach((clone) => clone.remove());' in staging_source
    assert "existingClones.length === originals.length" in staging_source
    assert "clones[0].offsetLeft - originals[0].offsetLeft" in staging_source
    assert "homeMarketMarquee.position += elapsed * 0.018;" in staging_source
    assert "carousel.scrollLeft = homeMarketMarquee.position;" in staging_source
    assert "Math.round(homeMarketMarquee.position * devicePixelRatio)" not in staging_source


def test_dashboard_v3_uses_stacked_news_and_event_cards():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    live_index = shell.index('data-trend-tab="live"')
    events_index = shell.index('data-trend-tab="events"')
    impact_index = shell.index('data-trend-tab="impact"')
    assert live_index < events_index < impact_index
    assert '>뉴스</button>' in shell
    assert '>주요 이벤트</button>' in shell
    assert 'id="trend-view" class="home-market-sections" aria-label="증시 캘린더와 뉴스"' in shell
    assert 'id="trend-tabs" role="tablist" aria-label="시장 정보 보기" data-archived="section-switcher" aria-hidden="true" hidden' in shell
    assert 'class="trend-panel home-market-card home-news-card" id="trend-live-panel" role="region"' in shell
    assert 'class="trend-panel home-market-card home-events-card" id="trend-events-panel" role="region"' in shell
    events_card_index = shell.index('class="trend-panel home-market-card home-events-card"')
    news_card_index = shell.index('class="trend-panel home-market-card home-news-card"')
    assert events_card_index < news_card_index
    assert 'id="trend-events-panel" role="region" aria-labelledby="trend-events-title" hidden' not in shell
    assert 'data-trend-tab="impact" data-archived="true" aria-hidden="true" tabindex="-1" hidden>시장 영향</button>' in shell
    assert 'elements.trendEventsPanel.hidden = false;' in source
    assert 'elements.trendLivePanel.hidden = false;' in source
    assert 'elements.trendTabsWrap.hidden = true;' in source
    assert '/* Home market cards 7.1: news and calendar are independent stacked sections. */' in styles
    home_market_card_styles = styles[styles.index("/* Home market cards 7.1"):]
    assert '--home-market-section-title-size: 23px;' in home_market_card_styles
    assert '--home-market-title-control-gap: 10px;' in home_market_card_styles
    assert 'min-width: 0;\n  display: grid;\n  gap: 5px;' in home_market_card_styles
    assert 'font-size: var(--home-market-section-title-size) !important;' in home_market_card_styles
    assert 'line-height: 1.25 !important;' in home_market_card_styles
    assert 'gap: var(--home-market-title-control-gap);' in home_market_card_styles
    assert '.home-events-card .trend-calendar-head {\n  margin-bottom: var(--home-market-title-control-gap);' in home_market_card_styles
    assert "margin: 8px 0;" not in home_market_card_styles
    assert "border-top: 8px solid" not in home_market_card_styles
    assert 'class="trend-summary"' not in shell
    assert 'id="trend-headline"' not in shell
    assert 'id="home-view"' in shell
    assert 'id="search-view"' in shell
    assert 'id="portfolio-view"' in shell
    assert 'id="chart-view"' in shell
    assert 'id="discovery-search-form"' in shell
    assert 'id="recommend-button"' not in shell
    assert '>추천받기<' not in shell
    assert 'loadRecommendations({ auto: true, force: true, recompute: false })' in source
    assert 'loadRecommendations({ auto: true, force: true, recompute: true })' not in source
    assert '추천 종목을 불러오는 중입니다.' in source
    assert 'const liveRefreshPromise = recompute' in source
    assert 'const initialPayload = await fetchLatestRecommendations();' in source
    assert 'id="portfolio-watchlist-panel"' in shell
    assert 'id="chart-stock-search-form"' in shell
    assert 'id="trend-watch-stock-rail"' in shell
    assert 'id="trend-watch-news-board"' in shell
    assert 'id="trend-topbar" hidden' in shell
    assert 'id="home-market-indices"' in shell
    assert 'id="home-market-signal-ticker"' in shell
    assert '<h2 class="home-market-signal-title" id="home-market-signal-title">AI는 무엇을 사고팔까?</h2>' in shell
    assert "최근 30일 시장 신호" in shell
    assert "최근 14일 시장 신호" not in shell
    assert 'id="home-market-snapshot"' not in shell
    assert '>시장 상태<' not in shell
    assert 'id="home-ai-signals"' in shell
    assert 'id="home-ai-signals-more"' in shell
    assert 'id="home-ai-signals-meta">최근 30일 시장 신호 확인 중<' in shell
    assert "최근 30일 시장 전체 AI 시그널을 불러오는 중입니다." in shell
    assert 'id="ai-signals-view" class="app-page app-ai-signals"' in shell
    assert 'id="ai-signals-meta"' not in shell
    assert "최근 30일 시장 AI 시그널을 불러오는 중입니다." in shell
    assert 'id="home-market-carousel"' in shell
    assert "function homeMarketAssetOrder(now = new Date())" in source
    assert 'return ["KOSPI", "KOSDAQ", "SP500", "NASDAQ", "SOX", "DOW", "GOLD", "OIL"];' in source
    assert 'return ["SP500", "NASDAQ", "SOX", "DOW", "KOSPI", "KOSDAQ", "GOLD", "OIL"];' in source
    assert "function formatDateOnlyBasis(value, fallback = \"기준 정보 확인 중\")" in source
    assert "function homeMarketIndexDisplayPhase(item = {}, now = new Date())" in source
    assert "function formatHomeMarketCardDate(value, fallback = \"날짜 확인 중\")" in source
    assert 'const sessionLabel = isPreopen ? "개장전"' in source
    assert 'card.classList.toggle("is-preopen", isPreopen);' in source
    assert "const change = toNumber(item?.change);" in source
    assert "const changeRate = toNumber(item?.change_rate);" in source
    assert 'el("span", "home-index-change-rate", `(${formatPercent(0)})`)' not in source
    assert "function openHomeAttentionWatchlist()" in source
    assert 'id="home-ai-response-watch"' in shell
    assert 'liveUrl("/market/global-assets?limit=30")' in source
    assert 'id="home-index-shared-asof"' in shell
    assert 'id="home-kospi-asof"' not in shell
    assert 'id="home-kosdaq-asof"' not in shell
    assert "/market/indices?limit=30" in source
    assert "const HOME_MARKET_SIGNAL_RECENT_DAYS = 30;" in source
    assert "const AI_SIGNAL_HISTORY_DAYS = 30;" in source
    assert '`/market/quant-signals?universe_limit=150&limit=0&recent_days=${recentDays}`' in source
    assert "function marketAiSignalItems" in source
    assert "function combineAiSignalPayloads" in source
    assert "function fetchCombinedAiSignals" in source
    assert "function isAiSignalWithinDays" in source
    assert "const signalDate = view?.preliminary" in source
    assert "? item.signal_date || view.signalDate || view.signalAt" in source
    assert "cutoff.setDate(cutoff.getDate() - normalizedDays);" in source
    assert "const recentDays = AI_SIGNAL_HISTORY_DAYS;" in source
    assert "marketItems.filter((item) => isAiSignalWithinDays(item, HOME_MARKET_SIGNAL_RECENT_DAYS))" in source
    assert "function fetchMarketAiSignals(options = {})" in source
    assert "const retryDelays = [0, 1200, 2500];" in source
    assert 'if (!isAiSignalMarketUpdating(payload?.status))' in source
    assert 'state.aiSignalMarketStatus = payload.market_status || "ready";' in source
    assert '["preparing", "refreshing"].includes(String(status || ""))' in source
    home_signal_render = source[source.index("function renderHomeAiSignals"):source.index("function renderPendingHomeAiSignals")]
    pending_home_signal_render = source[source.index("function renderPendingHomeAiSignals"):source.index("function aiSignalStageCounts")]
    assert 'classList.remove("show-public-history")' in home_signal_render
    assert "showPublicHistory" not in home_signal_render
    assert "최근 1개월 · 시장 신호" not in home_signal_render
    assert 'classList.remove("show-public-history")' in pending_home_signal_render
    assert '"최근 30일 시장 신호 확인 중"' in pending_home_signal_render
    assert "최근 30일 시장 전체 AI 시그널을 불러오고 있습니다." in pending_home_signal_render
    assert '최근 30일 ${sectorLabel} ${formatNumber(sectorItems.length)}개' not in source
    assert ".home-ai-signals.show-public-history" not in styles
    assert 'signal_scope: "market"' in source
    assert "renderHomeAiResponse(watchlistItems, state.homeAiSignalsAsOf);" in source
    assert "renderHomeMarketSignalTicker({" in source
    assert "const includeHistorical = options.includeHistorical === true;" in source
    assert "function homeInterestMarketContextCandidates" in source
    assert "function homeMarketSignalItems" in source
    assert 'label: view?.label || (isSell ? "확정 매도" : "확정 매수")' in source
    home_ticker_source = source[source.index("function homeMarketSignalItems"):source.index("function homeHoldingSignalItems")]
    assert 'const isSell = view\n          ? view.key === "recent-sell"' in home_ticker_source
    assert "const signalDate = view?.preliminary" in home_ticker_source
    assert "? item.signal_date || view.signalDate || view.signalAt || current.as_of || item.as_of" in home_ticker_source
    archive_row_source = source[source.index("function createHomeAiSignalRow"):source.index("function renderHomeAiSignals")]
    assert "aiSignalReleasedDateLine(item, view)" in archive_row_source
    assert "aiSignalDateLine(item, view)" in archive_row_source
    assert 'signalMeta.dataset.field = "ai_signal_date";' in archive_row_source
    assert 'metrics.dataset.field = "ai_signal_metrics";' in archive_row_source
    assert "renderAiSignalReleasedMetrics(metrics, item, view)" in archive_row_source
    assert "renderAiSignalMetrics(metrics, item, view)" in archive_row_source
    assert '`${item.code || ""} · ${item.market || ""}`' not in archive_row_source
    assert "grid-template-columns: minmax(0, 1fr) max-content;" in styles
    assert "font-variant-numeric: tabular-nums;" in styles
    signal_metric_styles = styles[
        styles.index("#ai-signals-view .home-ai-signal-metrics {") :
        styles.index("#ai-signals-view .home-ai-signal-metric-label,")
    ]
    assert "justify-self: start;" in signal_metric_styles
    assert "justify-content: start;" in signal_metric_styles
    assert signal_metric_styles.count("text-align: left;") >= 2
    assert "justify-content: end;" not in signal_metric_styles
    assert "#ai-signals-view .home-ai-signal-headline," in styles
    assert "#ai-signals-view .home-ai-signal-status {" in styles
    assert 'return formatDottedDate(value, "날짜 확인 중");' in source
    assert '`${signal.label} (${signal.date})`' in source
    assert 'formatPercent(returnRate)' not in source[source.index("function createHomeMarketSignalTickerRow"):source.index("function showHomeMarketSignalTickerItem")]
    assert "추세 유지 · 수익확정·전량 매도 기준 미도달" in source
    assert "function startHomeMarketSignalTicker" in source
    assert '시총 상위 100' not in shell
    assert '시총 상위 종목의 최근 신호' not in shell
    assert 'class="home-flat-section-head"' in shell
    assert 'Home market briefing 7.2: reference-matched market strip and briefing rows.' in styles
    assert 'styles.css?v=20260904v465' in shell
    home_ai_styles = styles[styles.index("/* Home market briefing 7.2"):]
    for expected in (
        "padding: 0 20px 20px;",
        "margin: 24px 0 0;",
        "margin: 12px 0 16px;",
        "gap: 12px;\n  padding: 16px 18px;",
        "padding-top: 12px;",
        "padding-top: 14px;",
    ):
        assert expected in home_ai_styles
    assert '<h2 id="recommend-stage-title">지금 추천 종목</h2><time id="recommend-meta" hidden></time>' in shell
    assert '추천 후보 · 현재 상태' not in shell
    assert '추천 종목의 AI 시그널 진행상황' not in shell
    assert 'elements.recommendMeta.dateTime = payload.as_of || "";' in source
    assert '#recommend-view #recommend-meta {' in styles
    assert 'function createRecommendationDecisionFlow' in source
    assert '"추천 점수는 후보 평가이며, 아래 AI 시그널은 매수·매도 시점을 독립적으로 계산한 기록입니다."' in source
    assert '"AI 시그널 여정"' in source
    assert '"AI 시그널 보기"' in source
    assert 'class="service-footer"' in shell
    assert 'id="service-guide-title">꼭 알아두세요<' in shell
    assert '<summary>AI 시그널 안내</summary>' in shell
    assert '<summary>데이터 출처</summary>' in shell
    assert '<summary>서비스 및 문의</summary>' in shell
    assert '비상업적 무료 베타 서비스' not in shell
    assert '<li>한국거래소(KRX), 한국투자증권 Open API' in shell
    assert '<li>본 서비스는 현재 광고, 유료 결제 및 제휴 수익 없이' in shell
    assert '광고, 유료 결제 및 제휴 수익 없이 비상업적으로 운영됩니다' in shell
    assert '원문 또는 원시데이터의 재판매나 대량 재배포를 목적으로 하지 않습니다' in shell
    assert '권리자의 정당한 요청이 있는 경우' in shell
    assert 'class="login-caution-notice"' in shell
    assert 'class="login-support-contact"' in shell
    assert '로그인 및 서비스 문의 :' in shell
    assert 'id="login-description"' in shell
    assert 'id="login-description">아이디를 입력해 시작하세요.<' in shell
    assert '첫 접속에는 초대 코드가 필요합니다.' not in shell
    assert '첫 접속에는 초대 코드가 필요합니다.' not in source
    assert 'id="login-invite-code"' in shell
    assert 'id="access-capacity-modal"' in shell
    assert '현재 이용 가능 인원을 초과했어요' in shell
    assert '초기 이용 인원을 제한하고 있습니다' in shell
    assert '100명' not in shell
    assert 'id="access-capacity-contact"' in shell
    assert 'href="https://www.linkedin.com/in/connor-sh"' in shell
    assert '>LinkedIn으로 문의하기<' in shell
    assert '초대 코드는 첫 접속 시 한 번만 확인합니다' in shell
    assert 'fetch("/session/invite-access"' in source
    assert 'invite_code: normalizedCode' in source
    assert 'NOTE2026' not in source
    assert 'KORNOTE2026' not in source
    assert 'state.inviteRequired && !state.inviteAuthorized' in source
    assert '아이디만 입력하면 바로 시작됩니다.' in source
    assert 'fetch("/session/dashboard-access"' in source
    assert 'payload?.detail?.code === "capacity_full"' in source
    assert "DASHBOARD_ACCESS_MAX_ATTEMPTS = 2" in source
    assert "dashboardAccessRetryAfterSeconds(response)" in source
    assert 'response.status === 429' in source
    assert 'response?.headers?.get("x-request-id")' in source
    assert "서버 연결이 불안정해 다시 확인하는 중" in source
    assert "인터넷 연결을 확인한 뒤 다시 시도해주세요." in source
    assert "state.loginSubmitting" in source
    assert 'showAccessCapacityModal()' in source
    assert 'function trapAccessCapacityFocus(event)' in source
    assert 'main.href = viewStockUrl(item.code || item.name);' in source
    assert 'row.href = viewStockUrl(item.code || item.name);' in source
    assert 'link.href = viewStockUrl(item.code || item.name);' in source
    assert 'aria-label="서비스 유의사항"' in shell
    assert '투자 권유·자문 또는 수익 보장이 아닙니다' in shell
    assert '무료 베타 서비스 안내' not in shell
    assert '>안석환<' in shell
    assert 'href="https://www.linkedin.com/in/connor-sh"' in shell
    assert '>시장 변수<' not in shell
    assert 'id="home-ai-response-factors"' not in shell
    assert '확인 근거' not in shell
    assert '>관심종목 영향도<' in shell
    assert 'id="home-ai-response-asof">업데이트 확인 중<' in shell
    assert 'id="home-ai-response-watch-label"' in shell
    assert 'function homeMarketVolatilitySentence' in source
    assert 'function homeAttentionSentence' in source
    assert '자료 상태 ·' not in source
    assert '상태 → 한 줄 해석 → 실제 지표 → 관련 업종 순서입니다.' not in source
    assert 'function formatElapsedUpdate' in source
    assert 'return `${elapsedMinutes}분 전 업데이트`;' in source
    assert 'return `${elapsedHours}시간 전 업데이트`;' in source
    assert '"market-thread-updated"' in source
    assert 'src="/dashboard-app-v170.js?v=20260904v465"' in shell
    render_trends_source = source[source.index("function renderTrends"):source.index("async function loadTrends")]
    assert "const timeline = payload.timeline || [];" in render_trends_source
    assert ".filter(isFocusedTrendTimelineItem)" not in render_trends_source
    assert 'data-trend-news-filter="all" aria-selected="true"' in shell
    assert 'data-trend-news-filter="positive" aria-selected="false"' in shell
    assert 'data-trend-news-filter="negative" aria-selected="false"' in shell
    assert 'id="trend-live-toggle" type="button" aria-label="뉴스 전체보기" hidden' in shell
    assert "const TREND_LIVE_PAGE_SIZE = 5;" in source
    assert "function renderTrendTimeline()" in source
    assert "filteredItems.slice(0, TREND_LIVE_PAGE_SIZE)" in source
    assert "function renderNewsPage()" in source
    assert 'const node = el("article", "thread-item");' in source
    assert 'const stockLink = el("a", "thread-tag leader-stock-tag", `#${stock}`);' in source
    assert 'stockLink.href = viewStockUrl(stock);' in source
    assert '.thread-item-story:focus-visible' in styles
    assert '.thread-item-story > strong {' in styles
    assert 'white-space: normal;' in styles
    assert '-webkit-line-clamp: unset;' in styles
    assert 'setView("news");' in source
    assert 'elements.trendLiveToggle.textContent = "더보기";' in source
    assert "trendNewsExpanded" not in source
    assert 'role="tablist" aria-label="실시간 뉴스 필터"' in shell
    assert 'id="news-view" class="app-page news-page"' in shell
    assert 'data-news-page-filter="all"' in shell
    assert 'data-news-page-filter="positive"' in shell
    assert 'data-news-page-filter="negative"' in shell
    assert 'return `/dashboard?view=news&filter=${encodeURIComponent(state.trendNewsFilter || "all")}`;' in source
    assert ".trend-live-filter:focus-visible" in styles
    assert "min-height: 44px;" in styles
    assert 'maximum-scale=1, user-scalable=no, viewport-fit=cover' in shell
    assert '/assets/zoom-lock.js?v=20260728z1' in shell
    assert 'env(safe-area-inset-top, 0px)' in styles
    assert 'min-height: calc(62px + env(safe-area-inset-top, 0px));' in styles
    assert 'border-radius: 50%;' in styles
    assert '0 0 12px rgba(32, 205, 105, 0.72)' in styles
    service_worker = client.get("/dashboard-sw.js").text
    assert 'DASHBOARD_SW_VERSION = "20260904v465"' in service_worker
    assert 'const currentBuild = url.searchParams.get("app_build");' in service_worker
    assert "if (!currentBuild || currentBuild === DASHBOARD_BUILD_VERSION)" in service_worker
    assert 'return [-timestamp, view?.preliminary ? 0 : 1' in source
    assert 'url.searchParams.set("app_build", DASHBOARD_BUILD_VERSION)' in service_worker

    dashboard_app = client.get("/dashboard-app-v170.js").text
    assert 'const currentBuild = url.searchParams.get("app_build");' in dashboard_app
    assert "if (!currentBuild || currentBuild === DASHBOARD_CLIENT_VERSION)" in dashboard_app
    assert 'client.navigate(url.href)' in service_worker
    dashboard_app = client.get("/dashboard-app-v170.js")
    assert dashboard_app.status_code == 200
    assert dashboard_app.headers["cache-control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert '.filter((item) => includeHistorical || isCurrentAiSignalHolding(item) || isRecentAiSignal(item))' in dashboard_app.text
    assert "PUSH_HISTORY_SIGNAL_KINDS" in dashboard_app.text
    assert "eventDate === receivedKstDate" in dashboard_app.text
    assert "window.setInterval(checkForUpdate, 60000);" in dashboard_app.text
    assert 'fetch("/dashboard-version", { cache: "no-store" })' in dashboard_app.text
    assert "registerDashboardVersionWatchdog();" in dashboard_app.text
    assert '#trend-events-panel .trend-event' in styles
    assert 'padding-right: 0;' in styles
    assert 'padding-left: 0;' in styles
    assert 'id="logout-button"' not in shell
    assert ".app-notification-button svg" in styles
    assert "width: 25px;" in styles
    assert "height: 25px;" in styles
    assert "min-width: 44px;" in styles
    assert "min-height: 44px;" in styles
    assert "touch-action: manipulation;" in styles
    assert "pointer-events: none;" in styles
    assert "renderHomeMarketIndices" in source
    assert 'class="side-nav"' not in shell
    nav_order = [
        shell.index('data-app-view="home"'),
        shell.index('data-app-view="search"'),
        shell.index('data-app-view="portfolio"'),
    ]
    assert nav_order == sorted(nav_order)
    assert 'data-app-view="chart"' not in shell
    bottom_nav_styles = styles[styles.index(".bottom-nav {"):styles.index(".bottom-nav-item {")]
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in bottom_nav_styles
    assert 'trend: "home"' in source


def test_chart_view_is_search_first_and_renders_five_or_ten_day_scenarios():
    client = TestClient(app)
    shell = client.get("/dashboard?view=chart").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="chart-view" class="app-page app-chart chart-forecast-host" data-ui-version="4.0"' in shell
    assert 'id="stock-home-chart-analysis"' in shell
    assert 'placeholder="궁금한 종목의 흐름 분석하기"' in shell
    assert "검색하면 이렇게 비교해드려요" in shell
    assert 'class="chart-example-svg"' in shell
    assert "최근 가격 흐름과 5일·10일 예상 범위를 한 차트에서 확인합니다." in shell
    assert 'id="chart-example-search-button"' not in shell
    assert 'id="chart-archive-button"' not in shell
    assert "차트 시나리오" not in shell
    assert 'id="chart-watchlist-picker"' not in shell
    assert "function computeChartForecast" in source
    assert "function renderChartForecastResult" in source
    assert "const CHART_PATTERN_RECENT_DAYS = 10;" in source
    assert "function recentChartPatterns" in source
    assert 'signalAlignment === "mixed"' in source
    assert "신호 엇갈림" in source
    assert "최근 ${CHART_FORECAST_TREND_DAYS}일 추세 분석" in source
    assert 'const CHART_FORECAST_VISIBLE_DAYS = STOCK_PRICE_PERIOD_COUNTS["1M"];' in source
    assert "1개월 일봉 · ${actual.length}거래일" in source
    assert '`1개월 일봉 · ${basis} ${basisPriceType}`' in source
    assert "상단 1개월 차트와 같은 일봉 구간입니다" in source
    assert "당일 현재가도 동일하게 반영했습니다" in source
    assert "최근 패턴 ${forecast.primaryPattern.name}" in source
    assert "function computeWatchChart(prices, quote = null)" in source
    assert "const ordered = stockPriceRowsWithLiveQuote(prices, quote);" in source
    assert "computeWatchChart(state.stockPriceRows, state.currentDashboard?.quote)" in source
    assert "patternPoints.every((point) => point.index >= focusStartIndex)" in source
    assert 'analysis.latest?.is_live_quote ? "현재가" : "종가"' in source
    assert "당일 현재가는 최신 임시 지점에 반영합니다" in source
    assert "캔들 패턴은 완성된 일봉까지만 판정합니다" in source
    assert "최근 패턴 분석" in source
    assert "renderChartPatternAnalysis(analysis, forecast, item)" in source
    assert "function chartPatternBoundaryMarkup" in source
    assert 'chartPatternBoundaryMarkup(pattern, rows, x, y, "chart-study-actual-boundary")' in source
    assert "패턴 적합도 ${confidence}점 · 학습용" in source
    assert "패턴 적합도는 과거 적중 확률이 아니라" in source
    assert '["돌파 거래량", volumeState' in source
    assert "평소 대비 1.15배 이상의 거래량" in source
    assert 'id="chart-study-view" class="app-page chart-study-view"' in shell
    assert 'setView("chart-study", { historyState: { returnView } })' in source
    assert "const CHART_STUDY_GUIDES = Object.freeze" in source
    supported_study_patterns = {
        "double-bottom", "double-top", "head-shoulders", "inverse-head-shoulders",
        "triple-top", "triple-bottom", "ascending-triangle", "descending-triangle",
        "symmetrical-triangle", "rising-wedge", "falling-wedge", "rectangle",
        "rising-channel", "falling-channel", "bull-flag", "bear-flag", "pennant",
        "cup-handle", "rounding-bottom", "rounding-top", "doji", "hammer",
        "shooting-star", "bullish-engulfing", "bearish-engulfing", "bullish-harami",
        "bearish-harami", "piercing-line", "dark-cloud-cover", "morning-star",
        "evening-star", "spinning-top", "bullish-marubozu", "bearish-marubozu",
    }
    study_guides = source.split("const CHART_STUDY_GUIDES = Object.freeze", 1)[1].split(
        "const CHART_STUDY_LINE_SHAPES", 1
    )[0]
    assert len(supported_study_patterns) == 34
    for pattern_key in supported_study_patterns:
        assert f'"{pattern_key}": chartStudyGuide' in study_guides
    assert "function createChartStudyLibrary" in source
    assert "function createChartStudyConceptFigure" in source
    assert "function openChartStudyPage" in source
    assert "function closeChartStudyPage" in source
    assert 'returnView: options.returnView || ""' in source
    assert 'setView("chart-study", { historyState: { returnView } })' in source
    assert 'elements.chartStudyBackButton.addEventListener("click", closeChartStudyPage)' in source
    assert 'setView(safeReturnView, { historyMode: "replace" })' in source
    assert 'el("button", "chart-pattern-row-study", "공부하기")' in source
    assert 'el("aside", "chart-study-disclaimer")' not in source
    assert "공부용 안내" not in source
    assert "가격 기준 구분" not in source
    assert "function renderStockHomeChartAnalysis" in source
    assert "target: elements.stockHomeChartAnalysis" in source
    assert "embedded: true" in source
    assert "for (const days of [5, 10])" in source
    assert "실제 가격은 뉴스와 수급에 따라 예상 범위를 벗어날 수 있습니다." not in source


def test_home_shows_top_five_category_rankings_and_links_to_market_top_fifty_page():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="home-surge"' in shell
    assert 'id="home-surge-more"' in shell
    assert '>더보기</button>' in shell
    assert 'id="home-ranking-market-trigger"' in shell
    assert 'id="home-ranking-market-sheet"' in shell
    assert 'data-home-ranking-market="ALL"' in shell
    assert 'data-home-ranking-market="KOSPI"' in shell
    assert 'data-home-ranking-market="KOSDAQ"' in shell
    assert 'id="home-surge-sector-filters"' in shell
    assert 'aria-label="TOP 50 세부 기준"' in shell
    assert 'data-home-ranking-category="volume">거래량</button>' in shell
    assert 'data-home-ranking-category="surge">수익률</button>' in shell
    assert 'data-home-ranking-category="low52">52주 최저</button>' in shell
    assert 'data-home-ranking-category="high52">52주 최고</button>' in shell
    assert 'AI는 어떤 종목을 사고 팔았을까?' not in shell
    assert 'class="home-market-signal-heading"' not in shell
    assert 'class="home-market-signal-ticker" id="home-market-signal-ticker" aria-label="최근 30일 시장 AI 시그널"' in shell
    assert '<h2 id="recommend-stage-title">지금 추천 종목</h2><time id="recommend-meta" hidden></time>' in shell
    assert 'recommend-stage-caption' not in shell
    assert 'id="market-view" class="app-page app-market-rankings"' in shell
    assert (
        shell.index('id="home-market-indices"')
        < shell.index('id="home-ai-signals"')
        < shell.index('id="home-market-signal-ticker"')
        < shell.index('id="home-surge"')
        < shell.index('id="trend-view"')
    )
    assert shell.index('id="search-view"') > shell.index('id="market-view"')
    assert 'data-market-filter="ALL"' in shell
    assert 'data-market-filter="KOSPI"' in shell
    assert 'data-market-filter="KOSDAQ"' in shell
    assert 'id="market-ranking-back"' in shell
    assert 'class="market-segment market-ranking-tabs"' in shell
    assert 'id="market-view" class="app-page app-market-rankings" data-ui-version="6.0"' in shell
    assert '<h1 id="market-ranking-command-title">TOP 50</h1>' in shell
    assert '<h2 id="market-ranking-title">거래량</h2>' in shell
    for title in ("거래량", "수익률", "시가총액", "ETF", "배당", "저PER", "52주 최저", "52주 최고"):
        assert f'title: "{title}"' in source
        assert f'title: "한국 {title}"' not in source
    assert source.count('column: "시가총액 · 현재 시세"') == 2
    assert '시가총액(억) · 현재 시세' not in source
    assert "function formatRankingMarketCap(value)" in source
    assert "formatMarketCapEok" not in source
    assert "? formatMoney(number)" in source
    assert 'function createMarketLeaderboardMetric' in source
    assert 'navigateBackOrFallback("home")' in source
    assert "function renderHomeSurgeRankings" in source
    assert "function renderHomeSurgeSectorFilters" in source
    assert "function setHomeSurgeSector" in source
    assert 'homeSurgeSector: "all"' in source
    assert "const items = state.homeSurgeItems.slice(0, 5);" in source
    assert 'homeRankingMarket: "ALL"' in source
    assert "const market = homeRankingRequestMarket(category);" in source
    assert "limit: 5" in source
    assert "setMarketFilter(homeRankingRequestMarket(state.rankingCategory));" in source
    assert "limit: 50" in source
    assert "function showHomeRankingMarketSheet()" in source
    assert "function trapHomeRankingMarketSheetFocus(event)" in source
    assert 'elements.homeRankingMarketTrigger?.addEventListener("click", showHomeRankingMarketSheet);' in source
    assert 'elements.homeRankingMarketSheetBackdrop?.addEventListener("click", closeHomeRankingMarketSheet);' in source
    assert 'if (!elements.homeRankingMarketSheet?.hidden && event.key === "Escape")' in source
    assert 'button.dataset.homeRankingMode = option.key;' in source
    assert 'button.setAttribute("aria-selected", String(selected));' in source
    assert 'elements.homeSurgeSectorFilters.scrollLeft = previousScrollLeft;' in source
    home_ranking_shell = shell[shell.index('id="home-surge"'):shell.index('id="trend-view"')]
    home_ranking_mobile_styles = styles[
        styles.index('@media (max-width: 480px) {\n  body:not([data-view="stock"]) #home-surge.home-top50 {'):
        styles.index("/* TOP 50 6.1: market selector sheet")
    ]
    assert home_ranking_shell.index('id="home-surge-list"') < home_ranking_shell.index('id="home-surge-more"')
    assert "50개 전체보기" not in home_ranking_shell
    assert 'min-height: calc(64px + env(safe-area-inset-top, 0px)) !important;' in styles
    assert "padding-right: 24px;\n    padding-left: 24px;" in home_ranking_mobile_styles
    assert "margin-top: 10px;" in home_ranking_mobile_styles
    assert "margin-right: -24px;" in home_ranking_mobile_styles
    assert "margin-left: 0;" in home_ranking_mobile_styles
    assert "padding-right: 24px;" in home_ranking_mobile_styles
    assert "padding-left: 0;" in home_ranking_mobile_styles
    assert "scroll-padding-left: 0;" in home_ranking_mobile_styles
    assert "@media (prefers-reduced-motion: reduce)" in styles
    assert ".home-ranking-market-sheet:not([hidden]) :is(.home-ranking-market-sheet-backdrop, .home-ranking-market-sheet-card)" in styles
    assert 'formattedBasis.replace(/ 기준$/, " 장 마감 기준")' in source
    assert "function isDomesticMarketClosed" in source
    assert "15:30 장 마감 기준" in source
    assert "const basisValue = item.is_realtime" in source
    assert "? item.updated_at || item.as_of" in source
    assert ": item.as_of || item.updated_at;" in source
    assert "function renderHomeAiSignals" in source
    assert "function startHomeMarketSignalTicker" in source
    assert 'row.href = options.linkToList ? "/dashboard?view=ai-signals" : viewStockUrl(item.code || item.name || "");' in source
    assert 'identity.append(el("small", "", "시장 신호"));' in source
    assert 'return { key: "recent-buy", label: "확정 매수", tone: "buy", signalDate' in source
    assert 'return { key: "holding", label: "보유 중", tone: "hold", signalDate' not in source
    assert '"전량 매도 확정 · 전략 버전 통일" : "전량 매도 확정"' in source
    assert "function aiSignalTransitionKey" in source
    assert "function mergeAiSignalItems" not in source
    combine_source = source[source.index("function combineAiSignalPayloads"):source.index("function preliminaryHistoryAiSignalItems")]
    assert "const items = marketItems;" in combine_source
    assert "watchlist_items: watchlistItems" in combine_source
    assert "function isCurrentAiSignalHolding" in source
    assert "function preliminaryHistoryAiSignalItems" in source
    assert "function mergeAiSignalArchiveItems" in source
    assert "function aiSignalStageKey" in source
    assert "function aiSignalMatchesStage" in source
    assert 'return stageName === "all" ? Boolean(homeAiSignalView(item)) : aiSignalStageKey(item) === stageName;' in source
    assert 'items.slice(0, 5).forEach' in source
    assert 'data-ai-signal-stage="all"' in shell
    assert 'data-ai-signal-stage="buy-holding">확정 매수·보유 <span>0</span>' in shell
    assert 'data-ai-signal-stage="recent-sell">매도 확정 <span>0</span>' in shell
    assert 'data-ai-signal-stage="preliminary-buy">예비 매수 <span>0</span>' in shell
    assert 'data-ai-signal-stage="preliminary-sell">매도 대기 <span>0</span>' in shell
    assert 'data-ai-signal-stage="recent-buy"' not in shell
    assert 'data-ai-signal-stage="holding"' not in shell
    assert 'id="ai-signal-sector-filters"' not in shell
    assert 'data-ai-signal-sector=' not in shell
    assert 'id="ai-signal-today"' not in shell
    assert '>오늘 발생한 예비 신호</h2>' not in shell
    assert 'id="ai-signal-today-list"' not in shell
    assert "function renderAiSignalPreliminaryHistory" not in source
    assert 'value: item.preliminary_active ? "조건 유지" : "조건 해제"' in source
    assert 'function writeDashboardHistory' in source
    assert 'setView("ai-signals")' in source
    assert "/quant-signals`" in source
    assert ".slice(0, 5)" in source
    assert 'limit: 50' in source
    assert 'ttlMs: pageEntryTtlMs("market")' in source
    assert 'force: false' in source
    assert 'view: "movers",' in source
    assert 'category: state.rankingCategory,' in source
    assert 'params.set("mode", state.marketRankingMode);' in source
    assert 'market: "movers"' in source
    assert 'watchlist: "portfolio"' in source
    assert 'const initialView = hasStockDetailPath ? "stock" : (LEGACY_VIEW_MAP[requestedView] || "home");' in source
    surge_filter_styles = styles[styles.index('body:not([data-view="stock"]) .home-surge-sector-filters {'):]
    assert "overflow-x: auto;" in surge_filter_styles
    assert "min-height: 44px;" in surge_filter_styles
    assert "scroll-snap-type: x proximity;" in surge_filter_styles
    assert '.home-surge-sector-filters button:focus-visible' in surge_filter_styles


def test_ai_signal_home_preview_opens_full_list_before_stock_detail():
    client = TestClient(app)
    shell = client.get("/dashboard?view=home").text
    source = client.get("/dashboard-app-v170.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'class="home-ai-signals-title-link" href="/dashboard?view=ai-signals"' in shell
    assert 'aria-label="AI 시그널 전체 목록 보기"' in shell
    assert 'data-ai-signal-stage="all">전체 <span>0</span>' in shell
    assert 'aiSignalStage: "all"' in source
    assert "aiSignalSector" not in source
    assert 'items.slice(0, 5).forEach((item) => elements.homeAiSignalsList.appendChild(createHomeAiSignalRow(item, { linkToList: true })))' in source
    assert 'classList.remove("show-public-history")' in source
    assert 'row.dataset.aiSignalListLink = "true";' in source
    assert 'row.setAttribute("aria-label", "AI 시그널 전체 목록 보기");' in source
    assert 'visible.forEach((item) => elements.aiSignalsPageList.appendChild(createHomeAiSignalRow(item, { detail: true })))' in source
    assert 'const modeItems = aiSignalItemsForMode(items, state.aiSignalMode);' in source
    assert "renderAiSignalSectorFilters" not in source
    assert "aiSignalMatchesSector" not in source
    assert 'setAiSignalMode("current", { render: false });' in source
    assert '"semiconductor", label: "반도체"' in source
    assert '"consumer", label: "소비재"' in source
    row_source = source[source.index("function createHomeAiSignalRow"):source.index("function renderHomeAiSignals")]
    assert 'status.append(el("strong", "home-ai-signal-state", view.label));' in row_source
    assert "home-ai-signal-target" not in row_source
    assert 'el("span", "home-ai-signal-metrics")' in row_source
    assert 'renderAiSignalMetrics(metrics, item, view)' in row_source
    assert 'el("span", "home-ai-signal-headline")' in row_source
    assert 'el("span", "home-ai-signal-supporting")' in row_source
    assert "home-ai-signal-sector" not in row_source
    assert 'row.setAttribute("aria-label", `${item.name || item.code || "종목"} 상세 분석 보기`);' in source
    assert 'return { key: "recent-buy", label: "예비 매수"' in source
    assert 'return { key: "recent-sell", label: "전량 매도 대기"' in source
    assert 'label: "확정 매수"' in source
    assert '"전량 매도 확정 · 전략 버전 통일" : "전량 매도 확정"' in source
    assert "function isPreliminaryAiSignal" in source
    signal_view_source = source[source.index("function homeAiSignalView"):source.index("function aiSignalTransitionKey")]
    assert "const preliminary = isPreliminaryAiSignal(item);" in signal_view_source
    assert "current.live_observation === true" in signal_view_source
    assert "item.price_through || current.signal_date" in signal_view_source
    assert 'is_preliminary: preliminary' in source
    assert '장중 예비 ${formatNumber(preliminaryCount)}개' not in source
    assert 'metrics.push({ key: "confirmation", label: "확정 기준", value: "15:40 전" });' in source
    assert "function aiSignalLiveReturnRate" in source
    assert "current.return_basis || {}" in source
    assert "item.live_return_rate" in source
    assert "?? item.display_return_rate" in source
    outcome_source = source[source.index("function aiSignalOutcomeMetrics"):source.index("function aiSignalOutcomeLine")]
    assert outcome_source.index("item.display_return_rate") < outcome_source.index("item.return_rate")
    assert outcome_source.index("current.unrealized_return") < outcome_source.index("item.return_rate")
    assert 'freshnessState === "realtime"' in outcome_source
    assert '"실시간 평가수익률"' in outcome_source
    assert '"확정 수익률"' in outcome_source
    assert 'openPosition ? "다음 수익확정가" : "목표가"' in source
    assert '"\ud574\ub2f9 \ub9e4\ub9e4 \uc218\uc775\ub960"' in source
    assert "function applyStockQuantSignalLiveQuote" in source
    assert "payload.display_return_rate = returnRate;" in source
    assert 'replaceQuoteStreamScope("ai-signals"' in source
    assert 'clearQuoteStreamScope("ai-signals")' in source
    assert 'metrics.dataset.field = "ai_signal_metrics"' in source
    assert 'value.dataset.field = "ai_signal_return"' in source
    assert '"매수 후 수익률"' in source
    assert "elements.aiSignalsMeta" not in source
    assert '종목을 누르면 상세 분석으로 이동합니다.' not in source
    assert 'const aiSignalListLink = event.target.closest("a[data-ai-signal-list-link]");' in source
    assert 'function openAiSignalsPage()' in source
    assert 'setAiSignalStage("all", { render: false });' in source
    tab_styles = styles[styles.index("#ai-signals-view :is(.ai-signal-stage-tabs, .ai-signal-history-filters) {"):]
    assert "display: flex;" in tab_styles
    assert "overflow-x: auto;" in tab_styles
    assert "scroll-snap-type: x proximity;" in tab_styles
    assert "touch-action: pan-x;" in tab_styles
    assert ":is(.ai-signal-stage-tabs, .ai-signal-history-filters) button:focus-visible" in tab_styles
    assert "#ai-signals-view .ai-signal-sector-filters" not in styles
    assert "min-height: 52px;" in tab_styles
    signal_page_styles = styles[styles.index("#ai-signals-view.app-ai-signals {"):]
    assert "align-content: start;" in signal_page_styles.split("}", 1)[0]
    assert '.home-ai-signal-row.is-live-preliminary .home-ai-signal-status strong::before' in styles
    assert 'content: "장중";' in styles
    assert "#ai-signals-view .ai-signals-page-list {\n  width: 100%;\n  padding: 0 20px;" in styles
    assert "#ai-signals-view .ai-signals-commandbar,\n#ai-signals-view .ai-signal-stage-tabs,\n#ai-signals-view .ai-signal-history-filters {\n  width: 100%;" in styles


def test_ai_signal_preliminary_history_is_separated_from_active_signal_tabs():
    client = TestClient(app)
    shell = client.get("/dashboard?view=ai-signals").text
    source = client.get("/dashboard-app-v170.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'role="tablist" aria-label="AI 시그널 상태" aria-orientation="horizontal"' in shell
    assert 'id="ai-signals-page-list" role="tabpanel" aria-labelledby="ai-signal-stage-all"' in shell
    assert 'role="tablist" aria-label="AI 시그널 보기"' in shell
    assert 'data-ai-signal-mode="current">현재 신호 <span>0</span>' in shell
    assert 'data-ai-signal-mode="history">해제 이력 <span>0</span>' in shell
    assert 'id="ai-signal-history-filters" role="tablist" aria-label="해제 이력 상태" aria-orientation="horizontal" hidden' in shell
    assert 'data-ai-signal-history-side="all">전체 <span>0</span>' in shell
    assert 'data-ai-signal-history-side="buy">매수 조건 해제 <span>0</span>' in shell
    assert 'data-ai-signal-history-side="sell">매도 조건 해제 <span>0</span>' in shell
    for stage, label in (
        ("all", "전체"),
        ("buy-holding", "확정 매수·보유"),
        ("recent-sell", "매도 확정"),
        ("preliminary-buy", "예비 매수"),
        ("preliminary-sell", "매도 대기"),
    ):
        assert 'aria-controls="ai-signals-page-list"' in shell
        assert f'data-ai-signal-stage="{stage}">{label} <span>0</span>' in shell

    assert 'id="ai-signal-today"' not in shell
    assert "장중 알림 이력" not in shell
    assert "오늘 발생한 예비 신호" not in shell
    assert "aiSignalToday" not in source
    assert "renderAiSignalPreliminaryHistory" not in source
    assert ".ai-signal-today" not in styles

    history_adapter = source[
        source.index("function preliminaryHistoryAiSignalItems"):
        source.index("function mergeAiSignalArchiveItems")
    ]
    assert 'status: "preliminary"' in history_adapter
    assert "is_preliminary: true" in history_adapter
    assert "preliminary_active: active" in history_adapter
    assert "position_open: false" in history_adapter
    assert 'action: isBuy ? "entry_pending" : "full_exit_pending"' in history_adapter

    archive_merge = source[
        source.index("function mergeAiSignalArchiveItems"):
        source.index("function aiSignalSortValue")
    ]
    assert "historyItems.forEach((item) => addItem(item));" in archive_merge
    assert "currentItems.forEach((item) => addItem(item, true));" in archive_merge
    assert "const key = aiSignalTransitionKey(item);" in archive_merge
    assert "preliminary_active: existing.preliminary_active" in archive_merge
    load_page = source[
        source.index("async function loadAiSignalsPage"):
        source.index("async function fetchMarketAiSignals")
    ]
    assert "normalizedAiSignalItems(mergeAiSignalArchiveItems(" in load_page
    assert "payload.preliminary_history || []" in load_page
    assert "setAiSignalMode(state.aiSignalMode);" in load_page

    mode_filter = source[
        source.index("function aiSignalItemsForMode"):
        source.index("function aiSignalStageCounts")
    ]
    assert 'modeName === "history"' in mode_filter
    assert "normalized.filter((item) => isReleasedPreliminaryAiSignal(item))" in mode_filter
    assert "currentAiSignalItems(normalized)" in mode_filter
    assert "current: currentAiSignalItems(normalized).length" in mode_filter
    assert "history: normalized.filter((item) => isReleasedPreliminaryAiSignal(item)).length" in mode_filter

    stage_key = source[
        source.index("function aiSignalStageKey"):
        source.index("function aiSignalStageCounts")
    ]
    assert "if (view.preliminary)" in stage_key
    assert 'return view.key === "recent-sell" ? "preliminary-sell" : "preliminary-buy";' in stage_key
    assert 'return view.key === "recent-sell" ? "recent-sell" : "buy-holding";' in stage_key
    assert "function currentAiSignalItems" in stage_key
    assert "const selectedByStock = new Map();" in stage_key
    assert "candidateTimestamp > existingTimestamp" in stage_key
    stage_counts = source[
        source.index("function aiSignalStageCounts"):
        source.index("function aiSignalMatchesStage")
    ]
    for key in ("all", "buy-holding", "recent-sell", "preliminary-buy", "preliminary-sell"):
        assert f'"{key}": 0' in stage_counts or (key == "all" and "all: 0" in stage_counts)
    assert "counts.all += 1;" in stage_counts
    assert "counts[stageKey] += 1;" in stage_counts
    matches = source[
        source.index("function aiSignalMatchesStage"):
        source.index("function aiSignalScrollBehavior")
    ]
    assert 'stageName === "all" ? Boolean(homeAiSignalView(item)) : aiSignalStageKey(item) === stageName' in matches

    stage_setter = source[
        source.index("function setAiSignalStage"):
        source.index("function renderAiSignalsPage")
    ]
    assert '"preliminary-buy", "preliminary-sell"' in stage_setter
    assert 'tab.setAttribute("aria-selected", String(selected));' in stage_setter
    assert "tab.tabIndex = selected ? 0 : -1;" in stage_setter
    assert 'elements.aiSignalsPageList.setAttribute("aria-labelledby", selectedTab.id);' in stage_setter
    assert 'selectedTab.scrollIntoView({ behavior: aiSignalScrollBehavior(), block: "nearest", inline: "center" });' in stage_setter
    assert 'window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"' in source

    render_page = source[
        source.index("function renderAiSignalsPage"):
        source.index("async function loadAiSignalsPage")
    ]
    assert "const modeCounts = aiSignalModeCounts(items);" in render_page
    assert "const modeItems = aiSignalItemsForMode(items, state.aiSignalMode);" in render_page
    assert "const counts = aiSignalStageCounts(modeItems);" in render_page
    assert 'if (state.aiSignalMode === "history")' in render_page
    assert "const historyCounts = aiSignalHistorySideCounts(modeItems);" in render_page
    assert "const visibleHistory = modeItems.filter((item) => aiSignalMatchesHistorySide(item, state.aiSignalHistorySide));" in render_page
    assert "createHomeAiSignalRow(item, { detail: true, released: true })" in render_page
    assert "const visible = modeItems.filter((item) => aiSignalMatchesStage(item, state.aiSignalStage));" in render_page
    assert "createHomeAiSignalRow(item, { detail: true })" in render_page
    assert '"preliminary-buy": "예비 매수"' in render_page
    assert '"preliminary-sell": "매도 대기"' in render_page
    assert "활성 신호가 없습니다." in render_page

    released_card = source[
        source.index("function aiSignalReleasedMetrics"):
        source.index("function aiSignalOutcomeMetrics")
    ]
    assert 'label: "포착가"' in released_card
    assert 'label: "전환 결과"' in released_card
    assert '"확정 매수 미전환"' in released_card
    assert '"확정 매도 미전환"' in released_card
    row_source = source[source.index("function createHomeAiSignalRow"):source.index("function renderHomeAiSignals")]
    assert '${view.preliminary && !released ? " is-preliminary" : ""}' in row_source
    assert '${livePreliminary ? " is-live-preliminary" : ""}' in row_source
    assert '${released ? " is-released" : ""}' in row_source
    assert 'label: releasedSide === "buy" ? "매수 조건 해제" : "매도 조건 해제"' in row_source
    assert 'el("span", "home-ai-signal-headline")' in row_source
    assert 'el("span", "home-ai-signal-supporting")' in row_source
    assert "home-ai-signal-sector" not in row_source

    event_bindings_start = source.index("function openAiSignalsPage")
    mode_keyboard_start = source.index("for (const tab of elements.aiSignalModeTabs)", event_bindings_start)
    stage_keyboard_start = source.index("for (const tab of elements.aiSignalStageTabs)", event_bindings_start)
    mode_keyboard = source[mode_keyboard_start:stage_keyboard_start]
    assert '["ArrowLeft", "ArrowRight", "Home", "End"]' in mode_keyboard
    assert 'setAiSignalMode(nextTab.dataset.aiSignalMode, { reveal: true });' in mode_keyboard
    assert "nextTab.focus();" in mode_keyboard
    keyboard = source[stage_keyboard_start:]
    assert '["ArrowLeft", "ArrowRight", "Home", "End"]' in keyboard
    assert "event.preventDefault();" in keyboard
    assert 'setAiSignalStage(nextTab.dataset.aiSignalStage, { reveal: true });' in keyboard
    assert "nextTab.focus();" in keyboard
    history_keyboard = source[source.index("for (const tab of elements.aiSignalHistorySideButtons)", event_bindings_start):]
    assert 'setAiSignalHistorySide(nextTab.dataset.aiSignalHistorySide, { reveal: true });' in history_keyboard
    assert "nextTab.focus();" in history_keyboard
    assert "#ai-signals-view .ai-signal-mode-tabs" in styles
    assert "#ai-signals-view .ai-signal-history-filters" in styles
    assert "#ai-signals-view .home-ai-signal-row.is-released" in styles
    assert "#ai-signals-view .home-ai-signal-metric.is-release-result" in styles


def test_ai_signal_sell_cards_keep_confirmed_entry_price_and_stream_live_returns():
    source = TestClient(app).get("/dashboard-app-v170.js").text

    market_adapter = source[
        source.index("function marketAiSignalItems"):
        source.index("function sanitizePendingEntryAiSignal")
    ]
    assert "const entryPrice = pendingEntry" in market_adapter
    assert "entry_price: entryPrice," in market_adapter
    assert "return sanitizePendingEntryAiSignal(mapped);" in market_adapter
    assert "entry_price: item.entry_price ?? (isBuy && !preliminary ? item.price ?? null : null)," in market_adapter
    assert "entry_price: item.entry_price ?? null," in market_adapter
    assert "holding_context: holdingContext," in market_adapter
    assert "signal_origin: canonicalCurrent?.signal_origin || item.signal_origin || null," in market_adapter
    assert "reconciliation_id: canonicalCurrent?.reconciliation_id || item.reconciliation_id || null," in market_adapter

    transition_key = source[
        source.index("function aiSignalTransitionKey"):
        source.index("function isCurrentAiSignalHolding")
    ]
    assert transition_key.index('(preliminary ? actionSide : "")') < transition_key.index("|| item.side")

    trade_context = source[
        source.index("function aiSignalTradeContext"):
        source.index("function aiSignalPriceLine")
    ]
    for field in (
        "item.entry_price",
        "current.entry_price",
        "transition.entry_price",
        "latestEvent.entry_price",
    ):
        assert field in trade_context
    assert trade_context.index('(view.preliminary ? actionSide : "")') < trade_context.index("|| item.side")
    assert 'if (side === "sell") {\n    return { side, price: entryPrice };\n  }' in trade_context
    assert "current.partial_exit_price" not in trade_context

    price_metric = source[
        source.index("function aiSignalPriceMetric"):
        source.index("function aiSignalDateLine")
    ]
    assert 'trade.side === "sell" ? "매수가"' in price_metric
    assert "매도가" not in price_metric
    assert "장중 현재가" not in price_metric

    live_update = source[
        source.index("function updateAiSignalLiveQuote"):
        source.index("function closeAiSignalQuoteStreams")
    ]
    live_rows = source[
        source.index("function refreshAiSignalLiveRows"):
        source.index("function updateAiSignalLiveQuote")
    ]
    assert 'state.view === "home"\n    ? elements.homeAiSignalsList' in source
    assert 'state.view === "ai-signals" ? elements.aiSignalsPageList' in source
    assert "state.aiSignalLiveQuotes.set(normalizedCode" in live_update
    assert "state.aiSignalQuoteStatuses.delete(normalizedCode);" in live_update
    assert "item.live_return_rate = returnRate;" not in live_update
    assert "item.current.price =" not in live_update
    assert "item.holding_context || item.current || {}" in source
    assert "aiSignalItemWithLiveOverlay(snapshotItem)" in live_rows
    assert "flashTextUpdate(returnValue, returnMetric.value, returnMetric.numericValue);" in live_rows
    assert 'row.setAttribute("aria-label", aiSignalDetailAriaLabel(item, view));' in live_rows
    assert "priceMetric" not in live_update
    assert "renderAiSignalsPage()" not in live_update

    home_render = source[
        source.index("function renderHomeAiSignals"):
        source.index("function renderPendingHomeAiSignals")
    ]
    assert "commitAiSignalSnapshot(items, payload" in home_render
    assert 'if (state.view === "home") connectAiSignalQuoteStreams(items);' in home_render
    assert home_render.index("createHomeAiSignalRow") < home_render.rindex("connectAiSignalQuoteStreams")
    assert 'if (!["home", "ai-signals"].includes(view)) {\n    closeAiSignalQuoteStreams();\n  }' in source
    visibility = source[source.index('document.addEventListener("visibilitychange"'):]
    assert "closeAiSignalQuoteStreams();" in visibility
    assert 'connectAiSignalQuoteStreams(state.aiSignalItems);' in visibility
    assert 'reason: "visibility"' in visibility

    page_loader = source[
        source.index("async function loadAiSignalsPage"):
        source.index("async function fetchMarketAiSignals")
    ]
    home_loader = source[
        source.index("async function loadHomeAiSignals"):
        source.index("function scheduleAiSignalRevisionReconcile")
    ]
    for loader in (page_loader, home_loader):
        assert "const requestSequence = ++state.aiSignalLoadSequence;" in loader
        assert "requestSequence !== state.aiSignalLoadSequence" in loader
    assert "commitAiSignalSnapshot(items, payload" in page_loader
    assert "renderHomeAiSignals(payload, { expectedRevision: options.expectedRevision })" in home_loader


def test_dashboard_restores_the_visible_view_on_browser_history_navigation():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert 'window.addEventListener("popstate"' in source
    assert "syncViewFromLocation" in source


def test_ai_signal_live_trust_status_revision_and_visible_subscription_contract():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text
    shell = client.get("/dashboard").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="ai-signals-live-status"' in shell
    assert (
        'data-state="checking" data-mixed="false" role="status" '
        'aria-live="polite" aria-atomic="false"'
    ) in shell
    assert shell.index('id="ai-signal-stage-tabs"') < shell.index(
        'id="ai-signals-live-status"'
    ) < shell.index('id="ai-signals-page-list"')
    for label in ("실시간", "약 10초 지연", "오프라인", "장 마감", "상태 확인 중"):
        assert f'"{label}"' in source

    revision_handler = source[
        source.index("function handleAiSignalRevisionFrame"):
        source.index("async function reconcileAiSignals")
    ]
    assert "aiSignalRevisionFromPayload(payload)" in revision_handler
    assert "revision === state.aiSignalRevision" in revision_handler
    assert "state.aiSignalLoadSequence += 1;" in revision_handler
    assert "expectedRevision: revision > 0 ? revision : null" in revision_handler
    assert 'reason: payload.initial === true ? "signal_revision_initial" : "signal_revision"' in revision_handler
    assert 'payload.type === "signal_revision"' in source

    commit = source[
        source.index("function commitAiSignalSnapshot"):
        source.index("function aiSignalQuoteUsesActiveSession")
    ]
    assert "Object.freeze" in commit
    assert "state.aiSignalLiveQuotes.delete(code)" in commit
    assert "state.aiSignalQuoteStatuses.delete(code)" in commit
    assert "responseRevision === null || responseRevision === 0" in commit
    assert source.count("state.aiSignalItems =") == 2  # canonical commit plus identity reset

    subscription = source[
        source.index("function connectAiSignalQuoteStreams"):
        source.index("function normalizedAiSignalItems")
    ]
    assert "visibleAiSignalSnapshotItems()" in subscription
    assert 'priority: quoteStreamScopePriority("ai-signals") - index' in subscription
    assert "onStatus: (payload) => updateAiSignalQuoteStatus(code, payload)" in subscription
    assert "rejected_codes" in source
    assert "quoteStreamOverflowCodes" in source

    assert '[data-field="ai_signal_freshness"]' in source
    assert "function aiSignalFreshnessSummary" in source
    assert "function syncAiSignalFreshnessBadgeVisibility" in source
    assert 'badge.hidden = hideAll || ["realtime", "confirmed"].includes(stateName);' in source
    assert 'elements.aiSignalsLiveStatus.hidden = !showStatus;' in source
    assert (
        'body[data-view="ai-signals"] #ai-signals-view.app-ai-signals > '
        ".ai-signals-live-status"
    ) in styles
    assert "background-color: transparent !important;" in styles
    assert "data.returnKind" not in source
    assert "returnValue.dataset.returnKind" in source
    assert "returnValue.dataset.freshnessState" in source
    for contract in (
        ".ai-signals-live-status",
        ".ai-signals-live-status[hidden]",
        ".home-ai-signal-freshness",
        ".home-ai-signal-freshness[hidden]",
        '@media (prefers-reduced-motion: reduce)',
        '@media (forced-colors: active)',
    ):
        assert contract in styles


def test_dashboard_internal_navigation_does_not_render_the_logo_splash():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="app-splash"' not in shell
    assert "showAppSplash" not in source
    assert "APP_SPLASH_DURATION_MS" not in source
    assert "a, button, [role='button'], [role='link']" in source


def test_dashboard_uses_one_data_basis_date_format_across_views():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'function formatDataBasis(value, fallback = "기준 정보 확인 중")' in source
    assert 'return `${dateMatch[1]}${dateMatch[2] ? ` ${dateMatch[2]}` : ""} 기준`;' in source
    assert "setText(elements.stockHomeTodayDate, formatDataBasis(summaryDate));" in source
    assert "formatDataBasis(payload.as_of)" in source
    assert "formatDataBasis(model.dataAsOf || model.asOf)" in source
    assert "기준 시간 :" not in source
    assert "기준 시각 확인 중" not in shell
    assert "최근 장 마감 기준" not in shell


def test_watchlist_news_deduplicates_matching_headlines():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert "const seenTitles = new Set();" in source
    assert "seenTitles.has(normalizedTitle)" in source


def test_trend_watchlist_mobile_layout_stays_inside_viewport():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "width: calc(100vw - 28px);" in styles
    assert "width: calc(100vw - 24px);" in styles
    assert "contain: inline-size;" in styles
    assert ".trend-watch-news-item > span" in styles
    assert "overflow-wrap: anywhere !important;" in styles


def test_mobile_stock_evidence_sections_share_one_alignment():
    client = TestClient(app)
    styles = client.get("/assets/dashboard/styles.css").text

    assert "#stock-view #stock-evidence-section > .evidence-core-grid" in styles
    assert "padding-inline: 0 !important;" in styles


def test_push_settings_include_device_test_action():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="push-notification-sheet-test-button"' in shell
    assert 'class="push-notification-sheet-handle"' in shell
    assert 'id="push-notification-sheet-body"' in shell
    assert 'aria-describedby="push-notification-sheet-subtitle push-notification-sheet-status"' in shell
    assert "/push/subscriptions/${encodeURIComponent(state.watchlistId)}/test" in source
    assert 'PUSH_NOTIFICATION_EXAMPLE_TEXT = "알림 예시\\n✅ [매수 확정] SK하이닉스\\n초기 위험선과 1차 수익확정 기준을 확인하세요."' in source
    assert "Safari의 공유 버튼 → 홈 화면에 추가 → 비밀노트 앱에서 알림 받기" not in source
    assert 'label = "홈 화면 추가 방법 보기";' in source
    assert "saveButton.textContent = label;" in source
    assert '"홈 화면 추가 방법 보기"' in source
    assert "function handlePushNotificationPrimaryAction()" in source
    assert "function trapPushNotificationSheetFocus(event)" in source
    assert "grid-template-rows: auto auto minmax(0, 1fr) auto;" in styles
    assert "border-radius: 28px 28px 0 0 !important;" in styles
    assert "overflow-y: auto;" in styles


def test_push_settings_show_unsubscribed_alerts_as_off_until_permission():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text

    assert 'id="push-notification-sheet-status" role="status" aria-live="polite" hidden' in shell
    for contract in (
        'const requiredOptions = options.filter((option) => option.required);',
        'const optionalOptions = options.filter((option) => !option.required);',
        'el("section", "push-notification-core")',
        'el("span", "push-notification-core-kicker", "기본 알림")',
        'const coreStateLabel = coreEnabled ? "켜짐" : "현재 꺼짐";',
        'coreState.dataset.enabled = String(coreEnabled);',
        'el("section", "push-notification-optional")',
        'el("strong", "", "추가 알림")',
        'summary.textContent = `${selectedCount}/${optionalInputs.length} 선택`;',
        'input.hidden = true;',
        'elements.pushNotificationSheetStatus.hidden = !text;',
        'market_session: "장 시작·마감 5분 전"',
        'recommendation_update: "상위 10 진입·매매 단계 변경"',
    ):
        assert contract in source
    assert 'pushNotificationConditions: PUSH_NOTIFICATION_FALLBACK_OPTIONS\n    .filter((item) => item.required)' in source
    assert '"현재 알림은 꺼져 있어요.' in source
    assert '알림 권한 허용하기' in source
    assert 'data-enabled="false"' in client.get("/assets/dashboard/styles.css").text
    assert '"항상 받기"' not in source
    assert '"항상 켜짐"' not in source
    assert 'el("label", "push-notification-condition")' in source


def test_home_install_sheet_stays_above_navigation_and_scrolls_on_short_iphones():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text
    install_styles = styles[
        styles.index("/* Home install guide 6.1"):
        styles.index("/* Alert settings 6.0")
    ]

    assert 'id="install-sheet" aria-hidden="true" hidden' in shell
    assert 'aria-describedby="install-sheet-subtitle"' in shell
    assert 'class="install-sheet-card"' in shell
    assert 'tabindex="-1"' in shell
    assert 'installSheetCard: document.querySelector(".install-sheet-card")' in source
    assert "function trapInstallSheetFocus(event)" in source
    assert 'elements.installSheet.setAttribute("aria-hidden", "false");' in source
    assert 'document.body.classList.add("modal-open");' in source
    assert "z-index: 910;" in install_styles
    assert "max-height: calc(100dvh" in install_styles
    assert "grid-template-rows: auto minmax(0, 1fr);" in install_styles
    assert "overflow-y: auto;" in install_styles
    assert "safe-area-inset-bottom" in install_styles


def test_push_settings_repairs_missing_server_subscription():
    client = TestClient(app)
    source = client.get("/assets/dashboard/app.js").text

    assert "if (!status?.enabled || options.syncServer)" in source
    assert "status = await savePushSubscription(state.watchlistId, subscription);" in source
    assert "state.pushNotificationEnabled = status?.enabled === true;" in source
    assert "Boolean(status?.enabled ?? true)" not in source
    assert "pushSubscriptionUsesKey(subscription, config.public_key)" in source


def test_push_entry_prompt_is_limited_to_one_impression_per_monday_week():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    assert 'id="push-notification-sheet-subtitle"' in shell
    assert 'id="push-notification-sheet-snooze-button"' in shell
    assert "이번 주 보지 않기" in shell
    assert '? "알림을 켜시겠어요?"' in source
    assert '"현재는 꺼져 있어요. 받을 소식을 확인한 뒤 권한을 허용해주세요."' in source
    assert "${PUSH_NOTIFICATION_EXAMPLE_TEXT}" in source
    assert '["morning_briefing", 0]' in source
    assert '["ai_signal", 1]' in source
    assert 'const PUSH_ENTRY_PROMPT_WEEK_PREFIX = "analyst.pushEntryPromptWeek.v1";' in source
    assert "function localMondayWeekKey(" in source
    assert "function pushEntryPromptShownThisWeek(" in source
    assert "function recordPushEntryPromptShown(" in source
    assert "async function maybeShowPushNotificationEntryPrompt()" in source
    assert "const canPrompt = needsIOSHomeInstall || (" in source
    assert 'showPushNotificationSheet({ mode: "entry", recordWeeklyPrompt: true });' in source
    assert "function dismissPushNotificationEntryPromptForWeek()" in source
    assert 'if (!state.pushNotificationEnabled && pushEntryPromptShownThisWeek()) {' in source
    assert '#push-notification-sheet:is([data-mode="entry"], [data-mode="recommendation-entry"]) .push-notification-sheet-actions' in styles
    assert '.push-notification-sheet-snooze:not([hidden])' in styles


def test_service_update_has_priority_over_push_prompt_until_next_home_entry():
    source = TestClient(app).get("/assets/dashboard/app.js").text

    assert "function serviceUpdateBlocksPushNotificationPrompt()" in source
    assert "window.secretNoteServiceUpdateGate?.blocksNotificationPrompt?.() === true" in source
    assert 'window.addEventListener("secret-note:service-update-priority"' in source
    assert 'window.addEventListener("secret-note:service-update-home-reentry"' in source
    assert "state.pushNotificationEntryPromptChecked = false" in source
    assert 'if (view === "home" && previousView && previousView !== "home")' in source


def test_recommendation_push_entry_prompt_reaches_all_customers_with_state_specific_actions():
    client = TestClient(app)
    shell = client.get("/dashboard").text
    source = client.get("/assets/dashboard/app.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    for expected in (
        'id="push-recommendation-guide"',
        'class="push-recommendation-feature"',
        "추천 업데이트",
        "상위 10 신규 진입과 매매 단계 변경만 알려드려요.",
        "추천 후보와 AI 매매 신호는 별도로 판단합니다.",
    ):
        assert expected in shell
    for expected in (
        'const RECOMMENDATION_PUSH_PROMPT_DECISION_PREFIX = "analyst.recommendationPushPromptDecision.v1";',
        'const isRecommendationEntryPrompt = nextMode === "recommendation-entry";',
        '"추천 업데이트 알림"',
        'const isExistingPushCustomer = isRecommendationEntryPrompt && state.pushNotificationEnabled;',
        '"기존 설정은 유지하고 추천 업데이트만 추가해요."',
        '"확인했어요"',
        '"추천 알림 권한 허용하기"',
        '"다시 보지 않기"',
        "function recommendationPushPromptHandled()",
        "function recommendationPushNotificationEnabled()",
        "function confirmRecommendationPushAnnouncement()",
        'recordRecommendationPushPromptDecision("dismissed");',
        'recordRecommendationPushPromptDecision("confirmed");',
        'recordRecommendationPushPromptDecision(wasPushNotificationEnabled ? "confirmed" : "enabled");',
        'state.pushNotificationConditions.includes("recommendation_update")',
        'if (!recommendationPushPromptHandled()) {',
        'mode: "recommendation-entry",',
        'recordWeeklyPrompt: !state.pushNotificationEnabled,',
        'if (!state.pushNotificationEnabled && pushEntryPromptShownThisWeek()) {',
        'if (!canPrompt || state.pushNotificationEnabled) {',
        'if (isRecommendationEntryPrompt && recommendationPushNotificationEnabled()) {',
        'return normalizePushNotificationConditions([...existingConditions, "recommendation_update"]);',
        "savePushNotificationSettings({ conditions });",
        'addEventListener("click", dismissPushNotificationEntryPrompt)',
    ):
        assert expected in source
    assert '#push-notification-sheet .push-recommendation-guide[hidden]' in styles
    assert '[data-mode="recommendation-entry"]' in styles
    announcement_check = source.index('if (!recommendationPushPromptHandled()) {')
    capability_check = source.index('if (!canPrompt || state.pushNotificationEnabled')
    assert announcement_check < capability_check


def test_meta_endpoints():
    client = TestClient(app)

    cadence = client.get("/meta/insight-cadence")
    assert cadence.status_code == 200
    cadence_body = cadence.json()
    assert cadence_body["thread_id"] == "019ed577-3961-7f30-b9da-05112758804a"
    assert cadence_body["intraday_loops"]
    assert cadence_body["review_cycles"]

    sources = client.get("/meta/research-sources")
    assert sources.status_code == 200
    source_body = sources.json()
    assert any(item["key"] == "naver_finance" for item in source_body)
    assert any(item["is_active_collector"] for item in source_body)

    integrations = client.get("/meta/integrations")
    assert integrations.status_code == 200
    integration_body = integrations.json()
    assert all(item["key"] != "toss_securities" for item in integration_body)


def test_toss_status_endpoint():
    client = TestClient(app)
    response = client.get("/toss/status")
    assert response.status_code == 404


def test_company_briefs_endpoint():
    client = TestClient(app)
    response = client.get("/company-briefs?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_quant_signal_return_labels_separate_open_position_from_one_year_strategy():
    client = TestClient(app)
    mobile = client.get("/assets/dashboard/app.js").text
    desktop = client.get("/assets/desktop/app.js").text

    current_status = mobile[
        mobile.index("function quantCurrentStatusView"):
        mobile.index("function renderQuantSignalChart")
    ]
    strategy_result = mobile[
        mobile.index("function renderQuantSignals"):
        mobile.index("function renderAIAnalysis")
    ]

    assert '"매수 후 수익률"' in current_status
    assert 'partial ? "이번 매매 수익률" : "매수 후 수익률"' in current_status
    assert '"현재 수익률"' not in current_status
    assert 'performancePeriodLabel, formatPercent(performance.strategy_return)' in strategy_result
    assert '["최대 낙폭", formatPercent(performance.max_drawdown)' in strategy_result
    assert '["연환산 변동성", formatPercent(performance.annualized_volatility)' in strategy_result
    assert '"전략 잔여비중"' in current_status
    assert '"종합 신호"' in current_status
    assert '"계좌 참고비중"' not in current_status
    assert '"1회 손실예산"' not in current_status
    assert '"매수 후 수익률(%)"' in desktop
    assert '"1년 모의 누적수익률(%)"' in desktop
    assert '"계좌 참고비중"' not in desktop
    assert '"연환산 변동성(%)"' in desktop
    assert '"평균 전략 보유비중(%)"' in desktop


def test_all_web_entrypoints_disable_pinch_zoom():
    client = TestClient(app)

    for path in ("/dashboard", "/insight", "/nasdaq", "/portfolio", "/concepts"):
        response = client.get(path)
        assert response.status_code == 200
        assert 'maximum-scale=1, user-scalable=no, viewport-fit=cover' in response.text
        assert '/assets/zoom-lock.js?v=20260728z1' in response.text

    zoom_lock = client.get("/assets/zoom-lock.js")
    assert zoom_lock.status_code == 200
    assert "event.touches.length > 1" in zoom_lock.text
    assert '"gesturestart", "gesturechange", "gestureend"' in zoom_lock.text


def test_market_rankings_color_only_the_change_rate_by_direction():
    client = TestClient(app)
    source = client.get("/dashboard-app-v170.js").text
    styles = client.get("/assets/dashboard/styles.css").text

    render_start = source.index("function renderRankingMetricBlock")
    render_end = source.index("function rankingMetricLabel", render_start)
    render_source = source[render_start:render_end]

    assert "const changeText = formatPercent(item.change_rate);" in render_source
    assert 'const change = el("span", "ranking-metric-change", changeText);' in render_source
    assert "setTone(change, item.change_rate);" in render_source
    assert "secondary.append(change" in render_source

    for contract in (
        ".ranking-metric-change.positive",
        "color: var(--app-v3-red, #e03131)",
        ".ranking-metric-change.negative",
        "color: var(--app-v3-blue, #3478df)",
        ".ranking-metric-change.muted",
    ):
        assert contract in styles

    hierarchy = styles[styles.index("/* TOP 50 6.5: keep ranking context") :]
    for contract in (
        ".market-ranking-hero h2",
        "order: 1;",
        ".market-ranking-hero p",
        "order: 2;",
        ".market-ranking-hero time",
        "order: 3;",
    ):
        assert contract in hierarchy
