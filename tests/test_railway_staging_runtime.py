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


def _runtime_env(tmp_path: Path, *, fail_on: str = "") -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "railway.log"
    railway = bin_dir / "railway"
    railway.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$RAILWAY_TEST_LOG"
if [[ -n "${RAILWAY_TEST_FAIL_ON:-}" && "$*" == *"$RAILWAY_TEST_FAIL_ON"* ]]; then
  exit 23
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
            "RAILWAY_TEST_FAIL_ON": fail_on,
            "RAILWAY_PROJECT_ID": "project-id",
            "RAILWAY_ENVIRONMENT": "staging",
            "RAILWAY_WEB_SERVICE": "web-id",
            "RAILWAY_COLLECTOR_SERVICE": "collector-id",
            "RAILWAY_DATABASE_SERVICE": "database-id",
            "RAILWAY_REGION": "us-west",
            "RAILWAY_DATABASE_WARMUP_SECONDS": "0",
        }
    )
    return env, log_path


def _run_runtime(
    tmp_path: Path,
    action: str,
    *,
    fail_on: str = "",
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    env, log_path = _runtime_env(tmp_path, fail_on=fail_on)
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


def test_staging_runtime_scales_up_and_down_in_dependency_order(tmp_path: Path) -> None:
    up, up_lines = _run_runtime(tmp_path / "up", "up")
    down, down_lines = _run_runtime(tmp_path / "down", "down")

    assert up.returncode == 0, up.stderr
    assert up_lines == [
        _scale("database-id", 1),
        _scale("collector-id", 1),
        _scale("web-id", 1),
    ]
    assert down.returncode == 0, down.stderr
    assert down_lines == [
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _scale("database-id", 0),
    ]


def test_failed_start_rolls_every_service_back_to_zero(tmp_path: Path) -> None:
    result, lines = _run_runtime(
        tmp_path,
        "up",
        fail_on="--service collector-id us-west=1",
    )

    assert result.returncode != 0
    assert lines == [
        _scale("database-id", 1),
        _scale("collector-id", 1),
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _scale("database-id", 0),
    ]


def test_shutdown_attempts_every_service_when_one_scale_fails(tmp_path: Path) -> None:
    result, lines = _run_runtime(
        tmp_path,
        "down",
        fail_on="--service collector-id us-west=0",
    )

    assert result.returncode != 0
    assert len(lines) == 3
    assert "--service web-id" in lines[0]
    assert "--service collector-id" in lines[1]
    assert "--service database-id" in lines[2]
