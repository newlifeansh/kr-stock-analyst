"""Read runtime topology without exporting credentials or connection strings."""

from __future__ import annotations

import argparse
import json
import subprocess
from urllib.parse import urlparse


SAFE_VARIABLES = {
    "MAINTENANCE_SUBPROCESS_ENABLED", "MAINTENANCE_JOB_TIMEOUT_SECONDS",
    "PROCESS_ROLE", "APP_MODULE", "STOCK_AI_PROVIDER", "OLLAMA_MODEL",
    "BRIEFING_POLL_SECONDS", "US_MARKET_ENABLED", "RAILWAY_PRIVATE_DOMAIN",
    "STOCK_UNIVERSE_ENABLED", "STOCK_LOGO_ENABLED", "FINANCIALS_ENABLED",
    "FUNDAMENTAL_SNAPSHOT_ENABLED", "STOCK_COMPANY_SNAPSHOT_ENABLED",
}


def railway_json(*args: str):
    result = subprocess.run(["railway", *args, "--json"], text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Railway {args[0]} query failed (exit {result.returncode})")
    return json.loads(result.stdout)


def audit(project: str, environment: str) -> dict:
    services = railway_json("service", "list", "-p", project, "--environment", environment)
    result = []
    for service in services:
        row = {key: service.get(key) for key in (
            "id", "name", "status", "deploymentStopped", "replicas", "regions", "source",
        )}
        variables = railway_json(
            "variable", "list", "-p", project, "--environment", environment,
            "--service", service["id"],
        )
        row["variables"] = {key: value for key, value in variables.items() if key in SAFE_VARIABLES}
        for key in ("DATABASE_URL", "OLLAMA_BASE_URL"):
            value = variables.get(key)
            if value:
                row["variables"][key + "_HOST"] = urlparse(value).hostname
        result.append(row)
    return {"project": project, "environment": environment, "services": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.project, args.environment), indent=2))
