"""Stop only the unused model deployment after its replacement is verified."""

from __future__ import annotations

import argparse
import re
import subprocess
import time

from railway_runtime_audit import audit, railway_json


def validate_runtime(snapshot: dict, web: str, collector: str, ollama: str, image: str) -> None:
    if len({web, collector, ollama}) != 3:
        raise ValueError("Model and application selectors must be distinct")
    if not re.fullmatch(r"ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", image):
        raise ValueError("An exact verified application image is required")
    rows = {row["id"]: row for row in snapshot["services"]}
    for service, role in ((web, "web"), (collector, "collector")):
        row = rows[service]
        variables = row["variables"]
        if (row.get("status") != "SUCCESS" or row.get("deploymentStopped")
                or (row.get("replicas") or {}).get("running", 0) < 1
                or (row.get("source") or {}).get("image") != image
                or variables.get("PROCESS_ROLE") != role
                or variables.get("STOCK_AI_PROVIDER") != "rules"):
            raise ValueError("Replacement application runtime is not verified")
    model = rows[ollama]
    if not (model.get("source") or {}).get("image", "").startswith("ollama/ollama@sha256:"):
        raise ValueError("Selected service is not the expected Ollama image")
    if any(row["variables"].get("STOCK_AI_PROVIDER") == "ollama" for row in rows.values()):
        raise ValueError("A project service still selects Ollama")


def stop_unused_ollama(project: str, web: str, collector: str, ollama: str, image: str) -> None:
    validate_runtime(audit(project, "production"), web, collector, ollama, image)
    deadline = time.monotonic() + 240
    quiet_since = None
    attempts = 0
    while time.monotonic() < deadline:
        rows = railway_json("service", "list", "-p", project, "--environment", "production")
        row = next(row for row in rows if row["id"] == ollama)
        replicas = row.get("replicas")
        running = (replicas or {}).get("running", 0 if row.get("status") is None else None)
        if running == 0 and row.get("status") in {None, "REMOVED", "SUCCESS", "SLEEPING", "STOPPED", "CRASHED", "FAILED"}:
            quiet_since = quiet_since or time.monotonic()
            if time.monotonic() - quiet_since >= 30:
                print("Unused Ollama stopped; service and volume retained")
                return
        else:
            quiet_since = None
            if running and attempts < 3:
                result = subprocess.run([
                    "railway", "down", "-p", project, "--environment", "production",
                    "--service", ollama, "--yes",
                ], capture_output=True)
                if result.returncode:
                    raise RuntimeError("Ollama stop request failed")
                attempts += 1
        time.sleep(15)
    raise RuntimeError("Ollama shutdown did not remain verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for argument in ("project", "web", "collector", "ollama", "image"):
        parser.add_argument("--" + argument, required=True)
    args = parser.parse_args()
    stop_unused_ollama(args.project, args.web, args.collector, args.ollama, args.image)
