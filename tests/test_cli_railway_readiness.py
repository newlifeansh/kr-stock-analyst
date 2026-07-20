from __future__ import annotations

from pathlib import Path

from app.cli import railway_readiness_payload


def test_railway_readiness_payload_reports_missing_remote_and_auth(monkeypatch, tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "railway.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n", encoding="utf-8")
    (tmp_path / ".dockerignore").write_text("data\n", encoding="utf-8")
    (tmp_path / ".env").write_text("KIS_APP_KEY=test\n", encoding="utf-8")

    def fake_command_status(command, *, cwd=None):
        joined = " ".join(command)
        if joined.endswith("git remote -v"):
            return {"ok": True, "code": 0, "stdout": "", "stderr": ""}
        if joined.endswith("gh auth status"):
            return {"ok": True, "code": 0, "stdout": "ok", "stderr": ""}
        if joined.endswith("@railway/cli --version"):
            return {"ok": True, "code": 0, "stdout": "railway 5.23.3", "stderr": ""}
        if joined.endswith("@railway/cli whoami"):
            return {"ok": False, "code": 1, "stdout": "", "stderr": "Unauthorized"}
        raise AssertionError(joined)

    monkeypatch.setattr("app.cli._command_status", fake_command_status)

    payload = railway_readiness_payload(
        "insight.example.com",
        workdir=str(tmp_path),
        source_env_path=str(tmp_path / ".env"),
        check_endpoint=False,
    )

    assert payload["ok"] is False
    assert payload["git"]["initialized"] is True
    assert payload["git"]["remote_configured"] is False
    assert payload["railway_cli"]["available"] is True
    assert payload["railway_cli"]["authenticated"] is False
    assert any("railway login" in item for item in payload["next_actions"])
    assert any("railway up" in item for item in payload["notes"])


def test_railway_readiness_payload_can_pass_without_warnings(monkeypatch, tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / "railway.json").write_text("{}", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM python:3.11-slim\n", encoding="utf-8")
    (tmp_path / ".dockerignore").write_text("data\n", encoding="utf-8")

    def fake_command_status(command, *, cwd=None):
        joined = " ".join(command)
        if joined.endswith("git remote -v"):
            return {"ok": True, "code": 0, "stdout": "origin\thttps://github.com/example/repo.git (fetch)", "stderr": ""}
        if joined.endswith("gh auth status"):
            return {"ok": True, "code": 0, "stdout": "ok", "stderr": ""}
        if joined.endswith("@railway/cli --version"):
            return {"ok": True, "code": 0, "stdout": "railway 5.23.3", "stderr": ""}
        if joined.endswith("@railway/cli whoami"):
            return {"ok": True, "code": 0, "stdout": "me@example.com", "stderr": ""}
        raise AssertionError(joined)

    monkeypatch.setattr("app.cli._command_status", fake_command_status)
    monkeypatch.setattr(
        "app.cli.verify_mcp_endpoint_payload",
        lambda url, limit=1: {"tool_count": 11, "search_count": 1, "server_name": "한국증시 비밀노트"},
    )

    payload = railway_readiness_payload(
        "https://insight.example.com",
        workdir=str(tmp_path),
        source_env_path=str(tmp_path / ".env"),
        check_endpoint=True,
    )

    assert payload["ok"] is True
    assert payload["endpoint_check"]["ok"] is True
    assert payload["next_actions"] == []
