from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path

import pytest

# CLI helpers are standalone scripts, not an installable application package.
spec = importlib.util.spec_from_file_location('railway_runtime_audit', 'scripts/railway_runtime_audit.py')
audit_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = audit_module
spec.loader.exec_module(audit_module)
spec = importlib.util.spec_from_file_location('railway_stop_unused_ollama', 'scripts/railway_stop_unused_ollama.py')
stop_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stop_module)
IMAGE = 'ghcr.io/owner/repo@sha256:' + 'a' * 64


def _runtime():
    return {'services': [
        {'id': role, 'status': 'SUCCESS', 'replicas': {'running': 1}, 'source': {'image': IMAGE}, 'variables': {'PROCESS_ROLE': role, 'STOCK_AI_PROVIDER': 'rules'}}
        for role in ('web', 'collector')
    ] + [{'id': 'ollama', 'status': 'SUCCESS', 'replicas': {'running': 1}, 'source': {'image': 'ollama/ollama@sha256:' + 'b' * 64}, 'variables': {}}]}


def test_audit_exports_only_operational_values_and_connection_hostnames(monkeypatch):
    def query(*args):
        if args[0] == 'service':
            return [{'id': 'web', 'source': {'image': IMAGE}}]
        return {'PROCESS_ROLE': 'web', 'STOCK_AI_PROVIDER': 'rules', 'DATABASE_URL': 'postgres://user:password@postgres.railway.internal/db', 'OLLAMA_BASE_URL': 'https://token@ollama.internal/path?key=secret', 'KIS_APP_SECRET': 'private', 'UNLISTED': 'private'}
    monkeypatch.setattr(audit_module, 'railway_json', query)
    output = audit_module.audit('project', 'production')
    assert output['services'][0]['variables'] == {'PROCESS_ROLE': 'web', 'STOCK_AI_PROVIDER': 'rules', 'DATABASE_URL_HOST': 'postgres.railway.internal', 'OLLAMA_BASE_URL_HOST': 'ollama.internal'}
    assert not any(secret in str(output) for secret in ('password', 'private', 'token', 'key=secret'))


@pytest.mark.parametrize('change', ['provider', 'role', 'image', 'offline', 'wrong_model', 'other_consumer'])
def test_ollama_stop_refuses_unverified_replacement(change):
    snapshot = _runtime()
    web = snapshot['services'][0]
    if change == 'provider': web['variables']['STOCK_AI_PROVIDER'] = 'ollama'
    elif change == 'role': web['variables']['PROCESS_ROLE'] = 'all'
    elif change == 'image': web['source']['image'] = 'ghcr.io/owner/repo:latest'
    elif change == 'offline': web['replicas']['running'] = 0
    elif change == 'wrong_model': snapshot['services'][2]['source']['image'] = 'postgres:18'
    elif change == 'other_consumer': snapshot['services'].append({'id': 'other', 'variables': {'STOCK_AI_PROVIDER': 'ollama'}})
    with pytest.raises(ValueError):
        stop_module.validate_runtime(snapshot, 'web', 'collector', 'ollama', IMAGE)


def test_ollama_stop_only_removes_model_deployment_and_verifies_quiet_window(monkeypatch):
    snapshot = _runtime()
    monkeypatch.setattr(stop_module, 'audit', lambda *_: deepcopy(snapshot))
    ticks = [1]
    monkeypatch.setattr(stop_module.time, 'monotonic', lambda: ticks[0])
    monkeypatch.setattr(stop_module.time, 'sleep', lambda seconds: ticks.__setitem__(0, ticks[0] + seconds))
    monkeypatch.setattr(stop_module, 'railway_json', lambda *_: deepcopy(snapshot['services']))
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        snapshot['services'][2].update(status=None, replicas=None)
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(stop_module.subprocess, 'run', run)
    stop_module.stop_unused_ollama('project', 'web', 'collector', 'ollama', IMAGE)
    assert commands == [['railway', 'down', '-p', 'project', '--environment', 'production', '--service', 'ollama', '--yes']]
    assert ticks[0] >= 46


def test_us_qa_lifecycle_and_ollama_shutdown_follow_verification():
    for name in ('qa-data-signal-live.yml', 'qa-data-signal-e2e.yml'):
        workflow = Path('.github/workflows', name).read_text()
        for suffix in ('PROJECT_ID', 'WEB_SERVICE', 'COLLECTOR_SERVICE', 'DATABASE_SERVICE', 'REGION'):
            assert f"matrix.surface == 'us' && vars.US_STAGING_RAILWAY_{suffix}" in workflow
        assert "if: matrix.surface == 'dashboard'" not in workflow
        cleanup = workflow.split("  shutdown_staging:", 1)[1]
        assert "if: ${{ always() }}" in cleanup
        assert "needs: " + ("live" if "live.yml" in name else "e2e") in cleanup
        stop = workflow[workflow.index('      - name: Stop selected staging'):]
        assert 'if: ${{ always() }}' in stop
        assert 'run: ./scripts/railway_staging_runtime.sh down' in stop
    workflow = Path('.github/workflows/deploy-main-production.yml').read_text()
    retire = workflow.split('  retire_unused_ollama:', 1)[1]
    assert 'needs: [build_image, verify_production]' in retire
    assert 'needs.build_image.outputs.image_ref' in retire
    assert workflow.count('railway variable set "STOCK_AI_PROVIDER=rules"') == 4
    assert workflow.count('railway variable set "MAINTENANCE_SUBPROCESS_ENABLED=true"') == 2
