#!/usr/bin/env python3
"""External health monitor that sends outage/recovery alerts to KakaoTalk."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import sys
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = Path(os.environ.get("SECRET_NOTE_MONITOR_HOME") or ROOT).expanduser().resolve()
ENV_PATH = RUNTIME_ROOT / ".kakao-monitor.env"
STATE_PATH = RUNTIME_ROOT / ".kakao-monitor-state.json"
KAKAO_AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
KAKAO_MEMO_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


@dataclass
class Config:
    rest_api_key: str
    client_secret: str
    access_token: str
    refresh_token: str
    redirect_uri: str
    monitor_url: str
    dashboard_url: str
    interval_seconds: int
    timeout_seconds: int
    failure_threshold: int
    repeat_alert_seconds: int
    invite_report_url: str
    operations_token: str


def load_config() -> Config:
    values = {**dotenv_values(ENV_PATH), **os.environ}
    return Config(
        rest_api_key=str(values.get("KAKAO_REST_API_KEY") or ""),
        client_secret=str(values.get("KAKAO_CLIENT_SECRET") or ""),
        access_token=str(values.get("KAKAO_ACCESS_TOKEN") or ""),
        refresh_token=str(values.get("KAKAO_REFRESH_TOKEN") or ""),
        redirect_uri=str(values.get("KAKAO_REDIRECT_URI") or "http://127.0.0.1:8765/kakao/oauth/callback"),
        monitor_url=str(values.get("MONITOR_URL") or "https://secretnote.cloud/readyz"),
        dashboard_url=str(values.get("MONITOR_DASHBOARD_URL") or "https://secretnote.cloud"),
        interval_seconds=int(values.get("MONITOR_INTERVAL_SECONDS") or 60),
        timeout_seconds=int(values.get("MONITOR_TIMEOUT_SECONDS") or 10),
        failure_threshold=int(values.get("MONITOR_FAILURE_THRESHOLD") or 2),
        repeat_alert_seconds=int(values.get("MONITOR_REPEAT_ALERT_SECONDS") or 1800),
        invite_report_url=str(
            values.get("INVITE_REPORT_URL")
            or "https://secretnote.cloud/internal/operations/invite-access-report"
        ),
        operations_token=str(values.get("OPERATIONS_REPORT_TOKEN") or ""),
    )


def require(value: str, name: str) -> str:
    if not value:
        raise SystemExit(f"{name} is missing in {ENV_PATH}")
    return value


def update_env(updates: dict[str, str]) -> None:
    current: dict[str, str] = {
        str(key): str(value)
        for key, value in dotenv_values(ENV_PATH).items()
        if value is not None
    }
    current.update(updates)
    ENV_PATH.write_text(
        "".join(f"{key}={value}\n" for key, value in current.items()),
        encoding="utf-8",
    )
    ENV_PATH.chmod(0o600)


def exchange_token(config: Config, *, code: str | None = None) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code" if code else "refresh_token",
        "client_id": require(config.rest_api_key, "KAKAO_REST_API_KEY"),
        "client_secret": require(config.client_secret, "KAKAO_CLIENT_SECRET"),
    }
    if code:
        data.update({"redirect_uri": config.redirect_uri, "code": code})
    else:
        data["refresh_token"] = require(config.refresh_token, "KAKAO_REFRESH_TOKEN")
    response = requests.post(KAKAO_TOKEN_URL, data=data, timeout=15)
    if not response.ok:
        raise requests.HTTPError(
            f"Kakao token exchange failed ({response.status_code}): {response.text[:500]}",
            response=response,
        )
    payload = response.json()
    updates = {"KAKAO_ACCESS_TOKEN": payload["access_token"]}
    if payload.get("refresh_token"):
        updates["KAKAO_REFRESH_TOKEN"] = payload["refresh_token"]
    update_env(updates)
    return payload


def authorize(config: Config) -> None:
    state = secrets.token_urlsafe(24)
    callback_completed = False
    params = {
        "client_id": require(config.rest_api_key, "KAKAO_REST_API_KEY"),
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": "talk_message",
        "state": state,
    }
    print(f"AUTH_URL={KAKAO_AUTH_URL}?{urlencode(params)}", flush=True)
    parsed = urlparse(config.redirect_uri)

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            nonlocal callback_completed
            query = parse_qs(urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_error(400, "Invalid OAuth state")
                return
            code = query.get("code", [""])[0]
            if not code:
                self.send_error(400, query.get("error_description", ["Missing code"])[0])
                return
            try:
                exchange_token(load_config(), code=code)
                callback_completed = True
                body = "카카오톡 연결이 완료되었습니다. 이 창을 닫아도 됩니다.".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as exc:  # pragma: no cover - network path
                self.send_error(500, str(exc))

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    server = HTTPServer((parsed.hostname or "127.0.0.1", parsed.port or 8765), CallbackHandler)
    server.timeout = 600
    server.handle_request()
    if not callback_completed:
        raise SystemExit("OAuth callback was not completed.")
    print("Kakao OAuth connected.")


def send_message(config: Config, message: str) -> None:
    require(config.access_token, "KAKAO_ACCESS_TOKEN")
    template = {
        "object_type": "text",
        "text": message[:1900],
        "link": {"web_url": config.dashboard_url, "mobile_web_url": config.dashboard_url},
        "button_title": "상태 확인",
    }

    def request(token: str) -> requests.Response:
        return requests.post(
            KAKAO_MEMO_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
            timeout=15,
        )

    response = request(config.access_token)
    if response.status_code == 401 and config.refresh_token:
        exchange_token(config)
        response = request(load_config().access_token)
    if not response.ok:
        raise requests.HTTPError(
            f"Kakao message send failed ({response.status_code}): {response.text[:500]}",
            response=response,
        )


def format_qa_report(reports: list[dict[str, Any]], *, note: str = "") -> str:
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    lines = ["\U0001f9ea [데이터·시그널 정기 QA]", f"기준: {timestamp}"]
    deployment_blocked = False
    p0_failures: list[str] = []

    if not reports:
        lines.extend(["", "⚠️ 실행 결과 JSON이 없습니다."])

    for report in reports:
        summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
        mode = str(report.get("mode") or summary.get("mode") or "unknown").upper()
        passed = int(summary.get("pass") or 0)
        warned = int(summary.get("warn") or 0)
        failed = int(summary.get("fail") or 0)
        skipped = int(summary.get("skip") or 0)
        blocked = bool(report.get("deployment_blocked") or summary.get("deployment_blocked"))
        deployment_blocked = deployment_blocked or blocked
        icon = "🚨" if failed or blocked else "⚠️" if warned else "✅"
        lines.extend(
            [
                "",
                f"{icon} {mode}: PASS {passed} / WARN {warned} / FAIL {failed} / SKIP {skipped}",
            ]
        )
        failed_ids = [
            str(item.get("id"))
            for item in report.get("checks") or []
            if isinstance(item, dict) and item.get("status") == "fail" and item.get("id")
        ]
        if failed_ids:
            lines.append(f"실패: {', '.join(failed_ids[:8])}")
        for qa_id in summary.get("p0_failures") or []:
            normalized = str(qa_id)
            if normalized and normalized not in p0_failures:
                p0_failures.append(normalized)

    lines.extend(
        [
            "",
            f"배포 판정: {'🚫 차단' if deployment_blocked else '✅ 가능'}",
            f"P0 실패: {', '.join(p0_failures) if p0_failures else '없음'}",
        ]
    )
    if note.strip():
        lines.extend(["", f"메모: {note.strip()}"])
    return "\n".join(lines)


def send_qa_report(
    config: Config,
    reports: list[dict[str, Any]],
    *,
    note: str = "",
) -> str:
    message = format_qa_report(reports, note=note)
    send_message(load_config(), message)
    print(message)
    return message


def check_health(config: Config) -> tuple[bool, str, int]:
    started = time.monotonic()
    try:
        response = requests.get(config.monitor_url, timeout=config.timeout_seconds)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}", elapsed_ms
        payload = response.json()
        if payload.get("status") != "ok":
            return False, f"status={payload.get('status')!r}", elapsed_ms
        if "database_ok" in payload and payload["database_ok"] is not True:
            return False, "database_ok=false", elapsed_ms
        return True, "정상", elapsed_ms
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}", int((time.monotonic() - started) * 1000)


def read_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"status": "unknown", "failures": 0, "last_alert_at": 0}


def write_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def monitor_once(config: Config) -> bool:
    state = read_state()
    healthy, detail, elapsed_ms = check_health(config)
    now = int(time.time())
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    previous = state.get("status", "unknown")
    failures = 0 if healthy else int(state.get("failures", 0)) + 1
    new_status = "up" if healthy else previous
    should_alert = False
    message = ""
    if healthy and previous == "down":
        should_alert = True
        new_status = "up"
        message = f"✅ [복구] 비밀노트 서비스가 정상화되었습니다.\n시각: {timestamp}\n응답: {elapsed_ms}ms"
    elif not healthy and failures >= config.failure_threshold:
        new_status = "down"
        repeated = previous == "down"
        should_alert = (not repeated) or now - int(state.get("last_alert_at", 0)) >= config.repeat_alert_seconds
        if should_alert:
            label = "장애 지속" if repeated else "장애 발생"
            message = f"🚨 [{label}] 비밀노트 서비스 점검이 실패했습니다.\n시각: {timestamp}\n대상: {config.monitor_url}\n원인: {detail}"
    elif healthy:
        new_status = "up"
    if should_alert:
        send_message(load_config(), message)
        state["last_alert_at"] = now
    state.update({"status": new_status, "failures": failures, "last_detail": detail, "last_checked_at": now})
    write_state(state)
    print(json.dumps({"healthy": healthy, "detail": detail, "elapsed_ms": elapsed_ms, "alerted": should_alert}, ensure_ascii=False))
    return healthy


def fetch_invite_report(config: Config) -> dict[str, Any]:
    if not config.operations_token:
        raise RuntimeError("OPERATIONS_REPORT_TOKEN is missing")
    response = requests.get(
        config.invite_report_url,
        headers={"x-operations-token": config.operations_token},
        timeout=config.timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def send_invite_report(config: Config) -> dict[str, Any]:
    payload = fetch_invite_report(config)
    message = (
        "👥 [매시간 사용자 리포트]\n"
        f"기준: {payload['as_of']}\n"
        f"현재 등록: {payload['registered_count']}명 / {payload['limit']}명\n"
        f"남은 초대 인원: {payload['remaining_count']}명\n"
        f"오늘 00시 이후 신규: {payload['today_new_count']}명\n"
        f"오늘 00시 이후 접속: {payload['today_active_count']}명"
    )
    send_message(load_config(), message)
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def send_hourly_report(config: Config) -> dict[str, Any]:
    healthy, health_detail, elapsed_ms = check_health(config)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    health_icon = "✅" if healthy else "🚨"
    lines = [
        "📊 [비밀노트 정각 운영 리포트]",
        f"기준: {timestamp}",
        "",
        f"{health_icon} API·DB 헬스체크: {'정상' if healthy else '문제 감지'}",
        f"응답: {elapsed_ms}ms",
        f"상세: {health_detail}",
    ]
    payload: dict[str, Any] = {
        "healthy": healthy,
        "health_detail": health_detail,
        "elapsed_ms": elapsed_ms,
    }
    try:
        usage = fetch_invite_report(config)
        payload["usage"] = usage
        lines.extend(
            [
                "",
                "👥 초대코드 사용 현황",
                f"현재 등록: {usage['registered_count']}명 / {usage['limit']}명",
                f"남은 인원: {usage['remaining_count']}명",
                f"오늘 00시 이후 신규: {usage['today_new_count']}명",
                f"오늘 00시 이후 접속: {usage['today_active_count']}명",
            ]
        )
    except Exception as exc:
        payload["usage_error"] = f"{type(exc).__name__}: {exc}"
        lines.extend(["", "⚠️ 초대코드 사용 현황: 조회 실패", "헬스체크 보고는 정상 전송됨"])
    send_message(load_config(), "\n".join(lines))
    print(json.dumps(payload, ensure_ascii=False))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("authorize")
    send_parser = subparsers.add_parser("send")
    send_parser.add_argument("message")
    monitor_parser = subparsers.add_parser("monitor")
    monitor_parser.add_argument("--once", action="store_true")
    subparsers.add_parser("invite-report")
    subparsers.add_parser("hourly-report")
    qa_report_parser = subparsers.add_parser("qa-report")
    qa_report_parser.add_argument(
        "--report",
        action="append",
        default=[],
        type=Path,
        help="QA result JSON path. Repeat for gate, live, and e2e reports.",
    )
    qa_report_parser.add_argument("--note", default="")
    args = parser.parse_args()
    config = load_config()
    if args.command == "authorize":
        authorize(config)
    elif args.command == "send":
        send_message(config, args.message)
    elif args.command == "monitor":
        while True:
            monitor_once(load_config())
            if args.once:
                break
            time.sleep(max(10, config.interval_seconds))
    elif args.command == "invite-report":
        send_invite_report(config)
    elif args.command == "hourly-report":
        send_hourly_report(config)
    elif args.command == "qa-report":
        reports = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in args.report
        ]
        send_qa_report(config, reports, note=args.note)


if __name__ == "__main__":
    try:
        main()
    except requests.RequestException as exc:
        print(f"Request failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
