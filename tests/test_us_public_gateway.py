from __future__ import annotations

from pathlib import Path
import json
import subprocess

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app, settings
from app.product_shell import render_dashboard_product_shell
from app.us_public_gateway import checked_backend_url, gateway_target, should_freeze_us_write


ROOT = Path(__file__).resolve().parents[1]


def _shell(market: str) -> str:
    return render_dashboard_product_shell(
        (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8"),
        market_universe=market,
        client_version="us-test" if market == "us" else "kr-test",
    )


def test_canonical_us_gateway_routes_shell_assets_api_and_isolates_cookies(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/us":
            return httpx.Response(200, text=_shell("us"), headers={"content-type": "text/html"})
        if request.url.path == "/session/invite-access":
            return httpx.Response(
                200,
                json={"authorized": True},
                headers={"set-cookie": "sn_invite_access=us-only; Path=/; HttpOnly; Secure"},
            )
        if request.url.path == "/dashboard-app-v170.js":
            return httpx.Response(200, text='const icon = "/assets/staging/icon.svg";', headers={"content-type": "application/javascript"})
        return httpx.Response(200, json={"source": "us-dedicated"})

    native_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "us_public_backend_url", "https://us.example.test")
    monkeypatch.setattr(
        "app.us_public_gateway.httpx.AsyncClient",
        lambda **kwargs: native_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    client = TestClient(app)

    shell = client.get("/us?view=home")
    assert shell.status_code == 200
    assert shell.headers["x-us-market-route"] == "dedicated-service"
    assert '<meta name="secret-note-market-universe" content="us" />' in shell.text
    assert 'src="/us-gateway/assets/us-public-bridge.js"' in shell.text
    assert 'src="/us-gateway/dashboard-app-v170.js' in shell.text
    assert 'href="/us-gateway/assets/dashboard/styles.css' in shell.text
    assert 'href="/us-gateway/us.webmanifest"' in shell.text
    assert client.get("/dashboard").headers.get("x-us-market-route") is None

    us_api = client.get("/us/stocks/AAPL")
    assert us_api.json() == {"source": "us-dedicated"}
    assert us_api.headers["x-us-market-route"] == "dedicated-service"
    assert seen[-1].url.path == "/us/stocks/AAPL"

    auth = client.post(
        "/us-gateway/session/invite-access",
        json={"invite_code": "sample"},
        headers={"cookie": "sn_invite_access=domestic; us_sn_invite_access=us-only"},
    )
    assert auth.status_code == 200
    assert "us_sn_invite_access=us-only" in auth.headers["set-cookie"]
    assert "Path=/us-gateway" in auth.headers["set-cookie"]
    assert seen[-1].headers["cookie"] == "sn_invite_access=us-only"
    assert seen[-1].headers["x-forwarded-host"] == "testserver"

    script = client.get("/us-gateway/dashboard-app-v170.js?v=us-test")
    assert script.status_code == 200
    assert '"/us-gateway/assets/staging/icon.svg"' in script.text
    assert seen[-1].url.path == "/dashboard-app-v170.js"
    assert seen[-1].url.query == b"v=us-test"

    logo = client.get("/us-gateway/stock-logos/AAPL.png")
    assert logo.json() == {"source": "us-dedicated"}
    assert seen[-1].url.path == "/stock-logos/AAPL.png"


def test_us_gateway_unavailable_or_wrong_market_shell_never_falls_back(monkeypatch):
    native_client = httpx.AsyncClient
    monkeypatch.setattr(settings, "us_public_backend_url", "https://us.example.test")

    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("upstream down", request=request)

    monkeypatch.setattr(
        "app.us_public_gateway.httpx.AsyncClient",
        lambda **kwargs: native_client(transport=httpx.MockTransport(unavailable), **kwargs),
    )
    client = TestClient(app)
    response = client.get("/us")
    assert response.status_code == 502
    assert response.headers["x-us-market-route"] == "upstream-unavailable"
    assert "국내증시" not in response.text

    def wrong_market(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_shell("kr"), headers={"content-type": "text/html"})

    monkeypatch.setattr(
        "app.us_public_gateway.httpx.AsyncClient",
        lambda **kwargs: native_client(transport=httpx.MockTransport(wrong_market), **kwargs),
    )
    response = client.get("/us")
    assert response.status_code == 502
    assert response.headers["x-us-market-route"] == "invalid-upstream-shell"


def test_us_gateway_requires_distinct_https_origin_and_does_not_route_domestic():
    assert checked_backend_url("https://us.example.test/", "secretnote.cloud") == "https://us.example.test"
    for invalid in ("http://us.example.test", "https://secretnote.cloud", "https://us.example.test/path"):
        with pytest.raises(ValueError):
            checked_backend_url(invalid, "secretnote.cloud")
    assert gateway_target("/dashboard") is None
    assert gateway_target("/market/rankings") is None
    assert gateway_target("/us/market/rankings") == "/us/market/rankings"
    assert gateway_target("/us-gateway/session/invite-status") == "/session/invite-status"
    assert gateway_target("/us-gateway/internal/operations") is None


def test_us_cutover_freezes_only_us_writes(monkeypatch):
    assert should_freeze_us_write("PUT", "/us/watchlists/member", "", "secretnote.cloud")
    assert should_freeze_us_write("POST", "/session/invite-access", "https://secretnote.cloud/us", "secretnote.cloud")
    assert should_freeze_us_write("PUT", "/watchlists/us.member/groups", "", "secretnote.cloud")
    assert not should_freeze_us_write("GET", "/us/watchlists/member", "", "secretnote.cloud")
    assert not should_freeze_us_write("PUT", "/watchlists/member/groups", "https://secretnote.cloud/dashboard", "secretnote.cloud")
    monkeypatch.setattr(settings, "us_cutover_freeze", True)
    client = TestClient(app)
    blocked = client.put("/us/watchlists/member", json={"items": []})
    assert blocked.status_code == 503
    assert blocked.headers["x-us-market-route"] == "cutover-freeze"
    assert blocked.headers["retry-after"] == "120"
    assert client.get("/health").json()["us_cutover_freeze"] is True


def test_public_us_bridge_rewrites_fetch_and_websocket_without_changing_us_staging():
    bridge = (ROOT / "app/static/us-public-bridge.js").read_text(encoding="utf-8")
    dashboard = (ROOT / "app/static/dashboard/app.js").read_text(encoding="utf-8")
    staging = (ROOT / "app/static/staging/toss-ia.js").read_text(encoding="utf-8")
    assert 'window.__US_PUBLIC_GATEWAY__ = prefix;' in bridge
    assert 'url.origin !== window.location.origin' in bridge
    assert 'new Request(url, input)' in bridge
    assert 'if (window.__US_PUBLIC_GATEWAY__)' in dashboard
    assert 'window.__US_PUBLIC_GATEWAY__}${path}' in dashboard
    for script in (dashboard, staging):
        assert 'const logoOrigin = window.__US_PUBLIC_GATEWAY__ || "";' in script
        assert '${logoOrigin}/stock-logos/' in script


def test_public_us_bridge_routes_only_same_origin_fetches():
    bridge = (ROOT / "app/static/us-public-bridge.js").read_text(encoding="utf-8")
    script = """
const window = {
  location: { origin: "https://secretnote.cloud", href: "https://secretnote.cloud/us" },
  fetch: async (input, init) => ({
    url: input instanceof Request ? input.url : String(input),
    method: input instanceof Request ? input.method : (init?.method || "GET"),
    body: input instanceof Request ? await input.text() : (init?.body || ""),
  }),
};
""" + bridge + """
(async () => {
  const api = await window.fetch("/us/market/quant-signals?limit=1");
  const auth = await window.fetch(new Request("https://secretnote.cloud/session/invite-access", {
    method: "POST", body: "invite_code=sample",
  }));
  const external = await window.fetch("https://news.example.test/story");
  console.log(JSON.stringify({ api, auth, external }));
})();
"""
    completed = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    assert payload["api"]["url"] == "https://secretnote.cloud/us-gateway/us/market/quant-signals?limit=1"
    assert payload["auth"] == {
        "url": "https://secretnote.cloud/us-gateway/session/invite-access",
        "method": "POST",
        "body": "invite_code=sample",
    }
    assert payload["external"]["url"] == "https://news.example.test/story"
