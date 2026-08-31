from fastapi.testclient import TestClient
from pathlib import Path
import json

import app.desktop_app as desktop_module
from app.desktop_app import app


client = TestClient(app)


def test_desktop_only_app_serves_shell_and_health():
    shell = client.get("/desktop")
    health = client.get("/healthz")

    assert shell.status_code == 200
    assert '/assets/desktop/app.js?v=20260829h4' in shell.text
    assert health.json() == {"status": "ok", "service": "secret-note-desktop"}


def test_desktop_only_app_serves_dedicated_push_worker():
    worker = client.get("/desktop-sw.js")

    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/desktop"
    assert "/desktop?view=notifications&notification_url=" in worker.text


def test_desktop_only_app_redirects_root():
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/desktop"


def test_desktop_only_app_does_not_import_backend_runtime():
    source = (Path(__file__).resolve().parents[1] / "app" / "desktop_app.py").read_text(encoding="utf-8")

    assert "from app.main" not in source
    assert "app.models" not in source
    assert "app.db" not in source
    assert "briefing_runtime" not in source
    assert "web_push_runtime" not in source


def test_desktop_session_protects_and_saves_user_preferences(monkeypatch):
    stored = {}

    async def authorize(share_id, request):
        assert share_id == "desktop-user"
        assert request.url.path == "/desktop/session"

    def read_preference(share_id):
        return stored.get(share_id, {"document_title": "한국증시 비밀노트", "updated_at": None})

    def save_preference(share_id, document_title):
        stored[share_id] = {"document_title": document_title, "updated_at": "2026-08-07T00:00:00+00:00"}
        return stored[share_id]

    monkeypatch.setattr(desktop_module, "_authorize_upstream_session", authorize)
    monkeypatch.setattr(desktop_module, "_read_document_preference", read_preference)
    monkeypatch.setattr(desktop_module, "_save_document_preference", save_preference)

    with TestClient(app) as browser:
        assert browser.get("/desktop/preferences").status_code == 401

        session = browser.post("/desktop/session", json={"share_id": "desktop-user"})
        assert session.status_code == 200
        assert "sn_desktop_session=" in session.headers["set-cookie"]
        assert "HttpOnly" in session.headers["set-cookie"]

        initial = browser.get("/desktop/preferences")
        saved = browser.put("/desktop/preferences", json={"document_title": "나의 투자 워크북"})
        restored = browser.get("/desktop/preferences")

    assert initial.json()["document_title"] == "한국증시 비밀노트"
    assert saved.status_code == 200
    assert restored.json()["document_title"] == "나의 투자 워크북"


def test_desktop_preferences_are_isolated_by_user(tmp_path, monkeypatch):
    database_path = tmp_path / "desktop-preferences.db"
    monkeypatch.setattr(desktop_module, "DESKTOP_DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setattr(desktop_module, "DEFAULT_DATABASE_PATH", database_path)
    monkeypatch.setattr(desktop_module, "_desktop_engine", None)
    monkeypatch.setattr(desktop_module, "_desktop_table_ready", False)

    desktop_module._save_document_preference("first-user", "첫 번째 워크북")
    desktop_module._save_document_preference("second-user", "두 번째 워크북")

    assert desktop_module._read_document_preference("first-user")["document_title"] == "첫 번째 워크북"
    assert desktop_module._read_document_preference("second-user")["document_title"] == "두 번째 워크북"


def test_desktop_proxies_live_quote_websocket(monkeypatch):
    payload = {
        "type": "quote",
        "code": "005930",
        "source": "kis_realtime",
        "quote": {"price": 81200, "change_rate": 1.75},
    }

    class FakeUpstream:
        def __init__(self):
            self.messages = iter([json.dumps(payload)])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration:
                raise StopAsyncIteration from None

    def connect(url, **options):
        assert url == "wss://secretnote.cloud/ws/stocks/005930/quote"
        assert options["open_timeout"] == 15
        return FakeUpstream()

    monkeypatch.setattr(desktop_module.websockets, "connect", connect)

    with client.websocket_connect("/ws/stocks/005930/quote") as socket:
        assert socket.receive_json() == payload
