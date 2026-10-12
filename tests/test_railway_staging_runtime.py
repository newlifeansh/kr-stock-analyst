from __future__ import annotations

import os
import json
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
    application_state: str = "running",
    ready: bool = True,
    scale_stops_process: bool = True,
) -> tuple[dict[str, str], Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    log_path = tmp_path / "railway.log"
    database_state_path = tmp_path / "database-state"
    database_state_path.write_text(database_state, encoding="utf-8")
    app_state_path = tmp_path / "app-state.json"
    app_state_path.write_text(json.dumps({"web-id": application_state, "collector-id": application_state}))
    railway = bin_dir / "railway"
    railway.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$RAILWAY_TEST_LOG"
if [[ -n "${RAILWAY_TEST_FAIL_ON:-}" && "$*" == *"$RAILWAY_TEST_FAIL_ON"* ]]; then
  exit 23
fi
if [[ "$*" == "service list -p project-id --environment staging --json" ]]; then
  python3 - <<'PY'
import json, os
from pathlib import Path
db_running = Path(os.environ['RAILWAY_TEST_DB_STATE']).read_text() == 'running'
rows = [{'id':'database-id', 'status':'SUCCESS' if db_running else 'REMOVED', 'deploymentStopped': not db_running, 'replicas':{'running':int(db_running)}}]
for service, state in json.loads(Path(os.environ['RAILWAY_TEST_APP_STATE']).read_text()).items():
    rows.append({'id': service, 'status': 'CRASHED' if state == 'crashed' else 'SUCCESS', 'deploymentStopped': state == 'crashed', 'replicas': {'running': int(state == 'running')}})
print(json.dumps(rows))
PY
elif [[ "$*" == redeploy* ]]; then
  printf '%s' running > "$RAILWAY_TEST_DB_STATE"
elif [[ "$*" == down* ]]; then
  python3 - "$@" <<'PY'
import json, os, sys
from pathlib import Path
service = sys.argv[sys.argv.index('--service') + 1]
if service == 'database-id':
    Path(os.environ['RAILWAY_TEST_DB_STATE']).write_text('inactive')
else:
    path = Path(os.environ['RAILWAY_TEST_APP_STATE'])
    states = json.loads(path.read_text())
    states[service] = 'idle'
    path.write_text(json.dumps(states))
PY
elif [[ "$*" == scale* || "$*" == restart* ]]; then
  python3 - "$@" <<'PY'
import json, os, sys
from pathlib import Path
path = Path(os.environ['RAILWAY_TEST_APP_STATE'])
states = json.loads(path.read_text())
service = sys.argv[sys.argv.index('--service') + 1]
if 'us-west=0' in sys.argv:
    if os.environ.get('RAILWAY_TEST_SCALE_STOPS') == 'true':
        states[service] = 'idle'
elif sys.argv[1] == 'restart' or states[service] != 'crashed':
    states[service] = 'running'
path.write_text(json.dumps(states))
PY
fi
""",
        encoding="utf-8",
    )
    railway.chmod(0o755)
    curl = bin_dir / "curl"
    curl.write_text('#!/usr/bin/env bash\nprintf \'%s\\n\' \'{"status":"ok","database_ok":' + str(ready).lower() + "}'\n")
    curl.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
            "RAILWAY_TEST_LOG": str(log_path),
            "RAILWAY_TEST_DB_STATE": str(database_state_path),
            "RAILWAY_TEST_APP_STATE": str(app_state_path),
            "RAILWAY_TEST_FAIL_ON": fail_on,
            "RAILWAY_TEST_SCALE_STOPS": str(scale_stops_process).lower(),
            "RAILWAY_PROJECT_ID": "project-id",
            "RAILWAY_ENVIRONMENT": "staging",
            "RAILWAY_WEB_SERVICE": "web-id",
            "RAILWAY_COLLECTOR_SERVICE": "collector-id",
            "RAILWAY_DATABASE_SERVICE": "database-id",
            "RAILWAY_REGION": "us-west",
            "RAILWAY_DATABASE_WARMUP_SECONDS": "0",
            "RAILWAY_DATABASE_STATE_TIMEOUT_SECONDS": "5",
            "RAILWAY_APPLICATION_STATE_TIMEOUT_SECONDS": "1",
            "QA_BASE_URL": "https://staging.example.test",
        }
    )
    return env, log_path


def _run_runtime(
    tmp_path: Path,
    action: str,
    *,
    fail_on: str = "",
    database_state: str | None = None,
    application_state: str = "running",
    ready: bool = True,
    scale_stops_process: bool = True,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    env, log_path = _runtime_env(
        tmp_path,
        fail_on=fail_on,
        database_state=database_state or ("inactive" if action == "up" else "running"),
        application_state=application_state,
        ready=ready,
        scale_stops_process=scale_stops_process,
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
        _database_status(),
        _database_status(),
        _database_status(),
        _database_status(),
    ]
    assert down.returncode == 0, down.stderr
    assert down_lines == [
        _scale("web-id", 0),
        _scale("collector-id", 0),
        _database_status(),
        _database_status(),
        _database_status(),
        _database_status(),
        _database_status(),
        _database_stop(),
        _database_status(),
    ]


def test_staging_prepare_does_not_gate_new_candidate_on_broken_old_image(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "prepare", application_state="crashed", ready=False)
    assert result.returncode == 0, result.stderr
    assert not any(line.startswith("restart") for line in lines)


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
        _database_status(),
        _database_status(),
        _database_status(),
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
        _database_status(),
        _database_status(),
        _database_status(),
        _database_status(),
    ]


def test_staging_up_restarts_crashed_same_deployments(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "up", application_state="crashed")
    assert result.returncode == 0, result.stderr
    for service in ("collector-id", "web-id"):
        assert f"restart -p project-id --environment staging --service {service} --yes --json" in lines
    assert not any("--from-source" in line and "database-id" not in line for line in lines)


def test_staging_up_requires_database_backed_readiness(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "up", ready=False)
    assert result.returncode != 0
    assert "database-backed readiness" in result.stderr
    assert _database_stop() in lines


def test_shutdown_keeps_db_when_a_scale_down_fails(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "down", fail_on="--service web-id us-west=0")
    assert result.returncode != 0
    assert _database_stop() not in lines


def test_shutdown_stops_active_deployments_when_scale_only_changes_configuration(tmp_path: Path) -> None:
    result, lines = _run_runtime(tmp_path, "down", scale_stops_process=False)
    assert result.returncode == 0, result.stderr
    for service in ("web-id", "collector-id"):
        stop = f"down -p project-id --environment staging --service {service} --yes"
        assert stop in lines
        assert lines.index(stop) < lines.index(_database_stop())
    assert not any("delete" in line or "--from-source" in line for line in lines)


def test_shutdown_preserves_database_if_active_deployment_cannot_stop(tmp_path: Path) -> None:
    result, lines = _run_runtime(
        tmp_path, "down", scale_stops_process=False,
        fail_on="down -p project-id --environment staging --service web-id",
    )
    assert result.returncode != 0
    assert _database_stop() not in lines
