from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "kakao_service_monitor.py"
SPEC = importlib.util.spec_from_file_location("kakao_service_monitor", SCRIPT)
assert SPEC and SPEC.loader
monitor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = monitor
SPEC.loader.exec_module(monitor)


def test_healthy_transition_sends_recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "STATE_PATH", tmp_path / "state.json")
    monitor.write_state({"status": "down", "failures": 2, "last_alert_at": 0})
    monkeypatch.setattr(monitor, "check_health", lambda _config: (True, "정상", 42))
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))
    monkeypatch.setattr(monitor, "load_config", lambda: config())

    assert monitor.monitor_once(config()) is True
    assert "[복구]" in sent[0]
    assert monitor.read_state()["status"] == "up"


def test_failure_threshold_sends_only_after_consecutive_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(monitor, "check_health", lambda _config: (False, "HTTP 503", 80))
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))
    monkeypatch.setattr(monitor, "load_config", lambda: config())

    assert monitor.monitor_once(config()) is False
    assert sent == []
    assert monitor.monitor_once(config()) is False
    assert "[장애 발생]" in sent[0]


def config():
    return monitor.Config(
        rest_api_key="key",
        client_secret="secret",
        access_token="token",
        refresh_token="refresh",
        redirect_uri="http://127.0.0.1:8765/kakao/oauth/callback",
        monitor_url="https://example.com/readyz",
        dashboard_url="https://example.com",
        interval_seconds=60,
        timeout_seconds=10,
        failure_threshold=2,
        repeat_alert_seconds=1800,
        invite_report_url="https://example.com/internal/operations/invite-access-report",
        operations_token="operations-token",
    )


def test_authorize_does_not_treat_existing_refresh_token_as_completed(monkeypatch):
    class Server:
        timeout = None

        def __init__(self, *_args, **_kwargs):
            return None

        def handle_request(self):
            return None

    monkeypatch.setattr(monitor, "HTTPServer", Server)

    with pytest.raises(SystemExit, match="OAuth callback was not completed"):
        monitor.authorize(config())


def test_invite_report_message_includes_capacity_and_daily_counts(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "as_of": "2026-08-12T08:00:00+09:00",
                "registered_count": 17,
                "limit": 100,
                "remaining_count": 83,
                "today_new_count": 3,
                "today_active_count": 11,
            }

    monkeypatch.setattr(monitor.requests, "get", lambda *_args, **_kwargs: Response())
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))
    monkeypatch.setattr(monitor, "load_config", lambda: config())

    result = monitor.send_invite_report(config())

    assert result["today_new_count"] == 3
    assert "현재 등록: 17명 / 100명" in sent[0]
    assert "오늘 00시 이후 접속: 11명" in sent[0]


def test_hourly_report_combines_health_and_usage(monkeypatch):
    usage = {
        "as_of": "2026-08-12T09:00:00+09:00",
        "registered_count": 21,
        "limit": 100,
        "remaining_count": 79,
        "today_new_count": 4,
        "today_active_count": 13,
    }
    monkeypatch.setattr(monitor, "check_health", lambda _config: (True, "정상", 321))
    monkeypatch.setattr(monitor, "fetch_invite_report", lambda _config: usage)
    monkeypatch.setattr(monitor, "load_config", lambda: config())
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))

    result = monitor.send_hourly_report(config())

    assert result["healthy"] is True
    assert "API·DB 헬스체크: 정상" in sent[0]
    assert "현재 등록: 21명 / 100명" in sent[0]


def test_hourly_report_still_sends_when_usage_lookup_fails(monkeypatch):
    monkeypatch.setattr(monitor, "check_health", lambda _config: (False, "HTTP 503", 900))
    monkeypatch.setattr(
        monitor,
        "fetch_invite_report",
        lambda _config: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    monkeypatch.setattr(monitor, "load_config", lambda: config())
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))

    result = monitor.send_hourly_report(config())

    assert "usage_error" in result
    assert "API·DB 헬스체크: 문제 감지" in sent[0]
    assert "사용 현황: 조회 실패" in sent[0]


def test_qa_report_includes_mode_counts_p0_and_deployment_decision(monkeypatch):
    reports = [
        {
            "mode": "gate",
            "summary": {
                "pass": 59,
                "warn": 0,
                "fail": 0,
                "skip": 0,
                "p0_failures": [],
                "deployment_blocked": False,
            },
            "checks": [],
        },
        {
            "mode": "live",
            "summary": {
                "pass": 24,
                "warn": 1,
                "fail": 2,
                "skip": 3,
                "p0_failures": ["DATA-COM-004", "DATA-FUND-RESEARCH-001"],
                "deployment_blocked": True,
            },
            "checks": [
                {"id": "DATA-COM-004", "status": "fail"},
                {"id": "DATA-FUND-RESEARCH-001", "status": "fail"},
            ],
        },
    ]
    sent = []
    monkeypatch.setattr(monitor, "send_message", lambda _config, message: sent.append(message))
    monkeypatch.setattr(monitor, "load_config", lambda: config())

    message = monitor.send_qa_report(config(), reports, note="신규 QA 2건 추가")

    assert sent == [message]
    assert "GATE: PASS 59 / WARN 0 / FAIL 0 / SKIP 0" in message
    assert "LIVE: PASS 24 / WARN 1 / FAIL 2 / SKIP 3" in message
    assert "DATA-COM-004, DATA-FUND-RESEARCH-001" in message
    assert "배포 판정: 🚫 차단" in message
    assert "메모: 신규 QA 2건 추가" in message
