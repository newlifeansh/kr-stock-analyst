from __future__ import annotations

from pathlib import Path

from app.cli import export_railway_env_payload


def test_export_railway_env_payload_uses_postgres_reference_and_public_host(tmp_path: Path):
    source_env = tmp_path / ".env"
    source_env.write_text(
        "\n".join(
            [
                "APP_NAME=KR Stock Analyst Backend",
                "KIS_APP_KEY=test-key",
                "KIS_APP_SECRET=test-secret",
                "MCP_SERVER_NAME=한국증시 비밀노트",
                "TOSS_ENABLED=false",
            ]
        ),
        encoding="utf-8",
    )

    payload = export_railway_env_payload(
        "insight.example.com",
        source_env_path=str(source_env),
        database_mode="postgres-ref",
    )

    assert "APP_MODULE=app.mcp_app:app" in payload
    assert "DATABASE_URL=${{Postgres.DATABASE_URL}}" in payload
    assert "KIS_APP_KEY=test-key" in payload
    assert "KIS_APP_SECRET=test-secret" in payload
    assert "MCP_PUBLIC_BASE_URL=https://insight.example.com" in payload
    assert "MCP_ALLOWED_HOSTS=insight.example.com,healthcheck.railway.app" in payload
    assert "MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com" in payload


def test_export_railway_env_payload_supports_sqlite_volume_mode(tmp_path: Path):
    payload = export_railway_env_payload(
        "https://insight.example.com",
        source_env_path=str(tmp_path / "missing.env"),
        database_mode="sqlite-volume",
    )

    assert "DATABASE_URL=sqlite:////data/analyst.db" in payload


def test_export_railway_env_payload_can_redact_secrets(tmp_path: Path):
    source_env = tmp_path / ".env"
    source_env.write_text(
        "\n".join(
            [
                "KIS_APP_KEY=test-key",
                "KIS_APP_SECRET=test-secret",
            ]
        ),
        encoding="utf-8",
    )

    payload = export_railway_env_payload(
        "https://insight.example.com",
        source_env_path=str(source_env),
        database_mode="postgres-ref",
        redact_secrets=True,
    )

    assert "KIS_APP_KEY=***REDACTED***" in payload
    assert "KIS_APP_SECRET=***REDACTED***" in payload
