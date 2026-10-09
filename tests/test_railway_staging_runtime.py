from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path("scripts/railway_staging_runtime.sh")


def _scale(service: str, replicas: int) -> str:
    return (
        "scale -p project-id --environment staging "
        f"--service {service} us-west={replicas} --json"
    )


def _database_status() -> str:
    return "service list -p project-id --environment staging --json"


def _database_start() -> str:
    return (
        "redeploy -p project-id --environment staging --service database-id "
        "--from-source --yes --json"
    )


def _database_stop() -> str:
    return "down -p project-id --environment staging --service database-id --yes"


def _runtime_env(
    tmp_path: Path,
    *,
    fail_on: str = "",
    database_state: str,
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "railway.log"
    database_state_path = tmp_path / "database-state"
    database_state_path.write_text(database_state, encoding="utf-8")
    railway = bin_dir / "railway"
    railway.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$RAILWAY_TEST_LOG"
if [[ -n "${RAILWAY_TEST_FAIL_ON:-}" && "$*" == *"$RAILWAY_TEST_FAIL_ON"* ]]; then
  exit 23
fi
if [[ "$*" == "service list -p project-id --environment staging --json" ]]; then
  state="$(<"$RAILWAY_TEST_DB_STATE")"
  if [[ "$state" == "running" ]]; then
    printf '%s\\n' '[{"id":"database-id","status":"SUCCESS","deploymentStopped":false,"replicas":{"running":1}}]'
  else
    printf '%s\\n' '[{"id":"database-id","status":"REMOVED","deploymentStopped":true,"replicas":{"running":0}}]'
  fi
elif [[ "$*" == redeploy* ]]; then
  printf '%s' running > "$RAILWAY_TEST_DB_STATE"
elif [[ "$*" == down* ]]; then
  printf '%s' inactive > "$RAILWAY_TEST_DB_STATE"
fi
""",
        encoding="utf-8",
    )
    railway.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "RAILWAY_TEST_LOG": str(log_path),
            "RAILWAY_TEST_DB_STATE": str(database_state_path),
            "RAILWAY_TEST_FAIL_ON": fail_on,
            "RAILWAY_PROJECT_ID": "project-id",
            "RAILWAY_ENVIRONMENT": "staging",
            "RAILWAY_WEB_SERVICE": "web-id",
            "RAILWAY_COLLECTOR_SERVICE": "collector-id",
            "RAILWAY_DATABASE_SERVICE": "database-id",
            "RAILWAY_REGION": "us-west",
            "RAILWAY_DATABASE_WARMUP_SECONDS": "0",
            "RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS": "5",
        }
    )
    return env, log_path


def _run_runtime(
    tmp_path: Path,
    action: str,
    *,
    fail_on: str = "",
    database_state: str | None = None,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    env, log_path = _runtime_env(
        tmp_path,
        fail_on=fail_on,
        database_state=database_state or ("inactive" if action == "up" else "running"),
    )
    result = subprocess.run(
        [str(SCRIPT), action],
        cwd=Path.cwd(),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return result, lines


def test_staging_runtime_starts_and_stops_in_dependency_order(tmp_path: Path) -> None:
    up, up_lines = _run_runtime(tmp_path / "up", "up")
    down, down_lines = _run_runtime(tmp_path / "down", "down")

    assert up.returncode == 0, up.stderr
    assert up_lines == [
        _database_status(),
        _database_start(),
        _database_status(),
        _scale("collector-id", 1),
        _scale("web-id", 1),
    ]
    assert down.returncode == 0, down.stderr
    assert down_lines == [
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _database_status(),
        _database_stop(),
        _database_status(),
    ]


def test_staging_runtime_does_not_gate_new_candidate_deployment_on_old_public_health() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "RAILWAY_READY_URL" not in script
    assert "wait_until_ready" not in script


def test_failed_start_rolls_back_every_staging_service(tmp_path: Path) -> None:
    result, lines = _run_runtime(
        tmp_path,
        "up",
        fail_on="--service collector-id us-west=1",
    )

    assert result.returncode != 0
    assert lines == [
        _database_status(),
        _database_start(),
        _database_status(),
        _scale("collector-id", 1),
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _database_status(),
        _database_stop(),
        _database_status(),
    ]


def test_shutdown_preserves_an_already_stopped_database_volume(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "down", database_state="inactive")

    assert result.returncode == 0, result.stderr
    assert lines == [
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _database_status(),
    ]
