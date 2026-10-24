import subprocess
from pathlib import Path


def test_first_service_worker_install_preserves_login_and_updates_stale_builds():
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["node", "tests/dashboard_login_lifecycle.cjs"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
    )
