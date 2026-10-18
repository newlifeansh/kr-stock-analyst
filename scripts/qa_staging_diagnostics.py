"""Read only the explicitly selected domestic staging services; omit secrets."""
import json
import os
from pathlib import Path
import re
import subprocess


def railway(*args):
    result = subprocess.run(
        ["railway", *args, "--project", os.environ["RAILWAY_PROJECT_ID"],
         "--environment", "staging"],
        capture_output=True, text=True, timeout=90, check=False,
    )
    # Never copy unfiltered CLI stderr (it may include connection details).
    if result.returncode:
        return None
    return result.stdout


def safe_message(value):
    message = str(value or "")
    if re.search(r"(?i)secret|token|api.?key|app.?key|password|authorization|cookie|postgres(?:ql)?://", message):
        return "[credential-related log line omitted]"
    # URLs are not needed to diagnose the runtime; remove credentials/query too.
    return re.sub(r"https?://\S+", "[URL omitted]", message)[:2000]


def main():
    records = []
    raw = railway("service", "list", "--json")
    services = json.loads(raw) if raw else []
    for role, key in (("web", "RAILWAY_WEB_SERVICE"), ("collector", "RAILWAY_COLLECTOR_SERVICE")):
        service_id = os.environ[key]
        service = next((row for row in services if row.get("id") == service_id), {})
        record = {"role": role, **{name: service.get(name) for name in
                  ("id", "name", "status", "replicas", "deploymentStopped")}}
        image = (service.get("source") or {}).get("image") or ""
        record["image"] = image if re.fullmatch(r"ghcr.io/[a-z0-9./_-]+@sha256:[a-f0-9]{64}", image) else "[not an immutable GHCR image]"
        # Select only non-secret behavior flags; never persist the raw response.
        raw_flags = railway("variable", "list", "--json", "--service", service_id)
        flags = json.loads(raw_flags) if raw_flags else {}
        record["flags"] = {name: flags.get(name) for name in (
            "PROCESS_ROLE", "US_MARKET_ENABLED", "BRIEFING_REALTIME_ENABLED",
            "FUNDAMENTAL_SNAPSHOT_ENABLED", "FUNDAMENTAL_SNAPSHOT_REFRESH_DAYS",
            "STOCK_NEWS_SNAPSHOT_ENABLED", "CANONICAL_DOMESTIC_SYNC_ENABLED",
            "BOOTSTRAP_ON_START", "FINANCIALS_ENABLED", "PRICE_CODE_LIMIT",
        )}
        raw_logs = railway("logs", "--latest", "--json", "--lines", "300", "--service", service_id)
        record["logs"] = []
        for line in (raw_logs or "").splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            record["logs"].append({"timestamp": event.get("timestamp"), "message": safe_message(event.get("message"))})
        records.append(record)
    output = Path("artifacts/qa-data-signal/staging-runtime-diagnostics.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"read_only": True, "environment": "staging", "services": records}, ensure_ascii=False, indent=2) + "\n")
    print("Saved sanitized, read-only staging runtime evidence")


if __name__ == "__main__":
    main()
