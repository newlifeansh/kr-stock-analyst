"""Bounded, redacted collector diagnostics for signal freshness investigation."""
from __future__ import annotations

import argparse
import json
import re
import subprocess

SIGNAL_ERROR = re.compile(
    r"position.lifecycle|market quant signal|screener|Yahoo|source_error|"
    r"refresh failed|degraded data|ValueError:|HTTPError:|429 Too Many Requests",
    re.IGNORECASE,
)
SECRET = re.compile(
    r"(?i)\b(authorization|api[_-]?key|token|password|secret)\b\s*[:=]\s*[^\s,;]+"
)
URL = re.compile(r"https?://[^\s,;]+")


def redact(message: str) -> str:
    return SECRET.sub(r"\1=[REDACTED]", URL.sub("[URL]", message))[:800]


def audit(project: str, service: str, environment: str) -> dict:
    command = [
        "railway", "logs", "--project", project, "--service", service,
        "--environment", environment, "--lines", "1500", "--json",
    ]
    result = subprocess.run(command, text=True, capture_output=True, timeout=90)
    if result.returncode:
        return {"status": "query_failed", "exit_code": result.returncode, "events": []}
    events = []
    for line in result.stdout.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        message = str(record.get("message") or record.get("text") or "")
        if SIGNAL_ERROR.search(message):
            events.append({
                "timestamp": record.get("timestamp") or record.get("createdAt"),
                "message": redact(message),
            })
    return {
        "status": "ok", "service": service, "matched_count": len(events),
        "events": events[-80:],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--environment", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.project, args.service, args.environment), ensure_ascii=False))
