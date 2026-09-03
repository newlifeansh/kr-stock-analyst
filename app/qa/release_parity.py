from __future__ import annotations

import html
from hashlib import sha256
import json
import re
from datetime import datetime
from pathlib import Path
from time import monotonic, sleep
from typing import Any
from urllib.parse import urljoin
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

KST = ZoneInfo("Asia/Seoul")
BUILD_VERSION_RE = re.compile(r'^DASHBOARD_CLIENT_VERSION\s*=\s*"([^"]+)"', re.MULTILINE)
ASSET_URL_RE = re.compile(r'(?:href|src)="([^"]+)"')
RELEASE_ASSET_PATHS = (
    "/assets/dashboard/styles.css",
    "/assets/staging/adaptive-theme.js",
    "/assets/staging/dark-theme.css",
    "/assets/staging/toss-fidelity.css",
    "/assets/staging/ai-stock-response-logic.js",
    "/assets/staging/stock-change-copy-logic.js",
    "/assets/staging/toss-ia.js",
    "/dashboard-app-v170.js",
)


def _asset_path(asset_url: str) -> str:
    return urlsplit(asset_url).path


def _local_asset_file(root: Path, asset_url: str) -> Path:
    path = _asset_path(asset_url)
    if path == "/dashboard-app-v170.js":
        return root / "app/static/dashboard/app.js"
    if path.startswith("/assets/dashboard/"):
        return root / "app/static/dashboard" / path.removeprefix(
            "/assets/dashboard/"
        )
    if path.startswith("/assets/staging/"):
        return root / "app/static/staging" / path.removeprefix(
            "/assets/staging/"
        )
    raise ValueError(f"지원하지 않는 릴리스 자산 경로입니다: {path}")


def _release_assets(shell: str) -> list[str]:
    assets = []
    for raw_url in ASSET_URL_RE.findall(shell):
        url = html.unescape(raw_url)
        if any(url.startswith(path) for path in RELEASE_ASSET_PATHS):
            assets.append(url)
    return sorted(set(assets))


def local_release_contract(root: Path | str = ".") -> dict[str, Any]:
    project_root = Path(root)
    main_source = (project_root / "app/main.py").read_text(encoding="utf-8")
    match = BUILD_VERSION_RE.search(main_source)
    if match is None:
        raise ValueError("DASHBOARD_CLIENT_VERSION을 app/main.py에서 찾지 못했습니다.")
    shell = (project_root / "app/static/dashboard/index.html").read_text(
        encoding="utf-8"
    )
    assets = _release_assets(shell)
    if len(assets) != len(RELEASE_ASSET_PATHS):
        raise ValueError("로컬 대시보드 릴리스 자산 목록이 완전하지 않습니다.")
    asset_sha256 = {
        _asset_path(asset): sha256(
            _local_asset_file(project_root, asset).read_bytes()
        ).hexdigest()
        for asset in assets
    }
    return {
        "dashboard_version": match.group(1),
        "assets": assets,
        "asset_sha256": asset_sha256,
    }


def fetch_remote_release_contract(base_url: str, timeout: float = 20.0) -> dict[str, Any]:
    normalized = base_url.rstrip("/")
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        version_response = client.get(urljoin(normalized + "/", "dashboard-version"))
        shell_response = client.get(
            urljoin(normalized + "/", "dashboard"),
            params={"view": "home", "release_parity": "1"},
            headers={"Cache-Control": "no-cache"},
        )
        version_response.raise_for_status()
        shell_response.raise_for_status()
        version_payload = version_response.json()
        assets = _release_assets(shell_response.text)
        asset_sha256: dict[str, str] = {}
        asset_http: dict[str, int] = {}
        for asset in assets:
            asset_response = client.get(
                urljoin(normalized + "/", asset.lstrip("/")),
                headers={"Cache-Control": "no-cache"},
            )
            asset_response.raise_for_status()
            path = _asset_path(asset)
            asset_sha256[path] = sha256(asset_response.content).hexdigest()
            asset_http[path] = asset_response.status_code
    return {
        "base_url": normalized,
        "dashboard_version": version_payload.get("version"),
        "assets": assets,
        "asset_sha256": asset_sha256,
        "http": {
            "dashboard_version": version_response.status_code,
            "dashboard": shell_response.status_code,
            "assets": asset_http,
        },
    }


def compare_release_contracts(
    expected: dict[str, Any],
    targets: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    expected_version = expected.get("dashboard_version")
    expected_assets = expected.get("assets") or []
    expected_hashes = expected.get("asset_sha256") or {}
    for name, contract in targets.items():
        if contract.get("dashboard_version") != expected_version:
            failures.append(
                {
                    "target": name,
                    "contract": "dashboard_version",
                    "expected": expected_version,
                    "actual": contract.get("dashboard_version"),
                }
            )
        if contract.get("assets") != expected_assets:
            failures.append(
                {
                    "target": name,
                    "contract": "frontend_assets",
                    "expected": expected_assets,
                    "actual": contract.get("assets") or [],
                }
            )
        actual_hashes = contract.get("asset_sha256") or {}
        mismatched_paths = sorted(
            path
            for path in set(expected_hashes) | set(actual_hashes)
            if expected_hashes.get(path) != actual_hashes.get(path)
        )
        if expected_hashes and mismatched_paths:
            failures.append(
                {
                    "target": name,
                    "contract": "frontend_asset_content",
                    "mismatched_paths": mismatched_paths,
                    "expected": {
                        path: expected_hashes.get(path) for path in mismatched_paths
                    },
                    "actual": {
                        path: actual_hashes.get(path) for path in mismatched_paths
                    },
                }
            )
    if len(targets) > 1:
        versions = {item.get("dashboard_version") for item in targets.values()}
        assets = {tuple(item.get("assets") or []) for item in targets.values()}
        if len(versions) != 1:
            failures.append(
                {
                    "target": "staging-production",
                    "contract": "same_dashboard_version",
                    "actual": {
                        name: item.get("dashboard_version")
                        for name, item in targets.items()
                    },
                }
            )
        if len(assets) != 1:
            failures.append(
                {
                    "target": "staging-production",
                    "contract": "same_frontend_assets",
                }
            )
        hashes = {
            tuple(sorted((item.get("asset_sha256") or {}).items()))
            for item in targets.values()
        }
        if any(item.get("asset_sha256") for item in targets.values()) and len(hashes) != 1:
            failures.append(
                {
                    "target": "staging-production",
                    "contract": "same_frontend_asset_content",
                }
            )
    return failures


def verify_release_parity(
    *,
    staging_url: str,
    production_url: str | None = None,
    source_sha: str | None = None,
    timeout: float = 20.0,
    wait_seconds: float = 0.0,
    root: Path | str = ".",
) -> dict[str, Any]:
    expected = local_release_contract(root)
    urls = {"staging": staging_url}
    if production_url:
        urls["production"] = production_url
    deadline = monotonic() + max(0.0, wait_seconds)
    targets: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    while True:
        targets = {}
        failures = []
        for name, url in urls.items():
            try:
                targets[name] = fetch_remote_release_contract(url, timeout=timeout)
            except Exception as exc:  # noqa: BLE001 - convert remote readiness to evidence.
                targets[name] = {"base_url": url.rstrip("/"), "error": type(exc).__name__}
                failures.append(
                    {"target": name, "contract": "reachable", "error": type(exc).__name__}
                )
        if not failures:
            failures = compare_release_contracts(expected, targets)
        if not failures or monotonic() >= deadline:
            break
        sleep(min(5.0, max(0.0, deadline - monotonic())))
    return {
        "schema_version": "1.0",
        "as_of": datetime.now(KST).isoformat(),
        "source_sha": source_sha or None,
        "expected": expected,
        "targets": targets,
        "failures": failures,
        "status": "pass" if not failures else "fail",
        "deployment_blocked": bool(failures),
    }


def write_release_parity_report(report: dict[str, Any], output: Path | str) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination
