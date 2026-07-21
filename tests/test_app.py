from fastapi.testclient import TestClient

from app.main import app


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    healthz = client.get("/healthz")
    assert healthz.status_code == 200
    assert healthz.json()["status"] == "ok"

    readyz = client.get("/readyz")
    assert readyz.status_code == 200
    assert readyz.json()["database_ok"] is True


def test_root_redirects_to_korea_dashboard():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard?view=trend"


def test_watchlist_share_id_roundtrip():
    client = TestClient(app)
    share_id = "codex-test-watchlist"
    payload = {"items": [{"code": "005930", "name": "삼성전자", "market": "KOSPI"}]}
    token_response = client.get(f"/session/write-token?share_id={share_id}")
    assert token_response.status_code == 200
    write_token = token_response.json()["write_token"]

    saved = client.put(f"/watchlists/{share_id}", json=payload, headers={"X-Write-Token": write_token})
    assert saved.status_code == 200
    saved_body = saved.json()
    assert saved_body["share_id"] == share_id
    assert saved_body["items"] == payload["items"]

    loaded = client.get(f"/watchlists/{share_id}")
    assert loaded.status_code == 200
    assert loaded.json()["items"] == payload["items"]


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
    assert "toss_enabled" in body
    assert "toss_sync_holdings_enabled" in body
    assert "disclosure_poll_seconds" in body
    assert "news_poll_seconds" in body
    assert "price_poll_seconds" in body
    assert "investor_flow_enabled" in body
    assert "investor_flow_poll_seconds" in body
    assert "financials_enabled" in body
    assert "financials_poll_seconds" in body
    assert "macro_enabled" in body
    assert "macro_poll_seconds" in body
    assert "toss_poll_seconds" in body
    assert "toss_order_poll_seconds" in body
    assert "last_price_at" in body
    assert "last_investor_flow_at" in body
    assert "last_financials_at" in body
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
    assert "6가지" in portfolio_shell.text
    assert "핵심 기능" in portfolio_shell.text

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
    assert "toss_status" in body
    assert "toss_accounts" in body
    assert "toss_holdings" in body
    assert "toss_orders" in body


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
    toss = next(item for item in integration_body if item["key"] == "toss_securities")
    assert toss["integration_type"] == "broker_api"
    assert toss["required_settings"]


def test_toss_status_endpoint():
    client = TestClient(app)
    response = client.get("/toss/status")
    assert response.status_code == 200
    body = response.json()
    assert "configured" in body
    assert "base_url" in body
    assert "order_poll_seconds" in body


def test_company_briefs_endpoint():
    client = TestClient(app)
    response = client.get("/company-briefs?limit=5")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
