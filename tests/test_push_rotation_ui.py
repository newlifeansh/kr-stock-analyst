from pathlib import Path
import subprocess


def test_dashboard_recovers_provider_proven_vapid_key_rotation():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/node/push_rotation.cjs"), str(root / "app/static/dashboard/app.js")],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dashboard VAPID rotation recovered" in result.stdout


def test_desktop_recovers_provider_proven_vapid_key_rotation():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", str(root / "tests/node/desktop_push_rotation.cjs"), str(root / "app/static/desktop/app.js")],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "desktop VAPID rotation recovered" in result.stdout
