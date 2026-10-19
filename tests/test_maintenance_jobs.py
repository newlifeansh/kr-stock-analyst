from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from app.config import Settings
from app.db import Base
from app import models  # noqa: F401
from app.services import maintenance_jobs as jobs


def test_real_worker_uses_parent_database_and_exits_after_each_job(tmp_path, monkeypatch, caplog):
    database_url = f"sqlite:///{tmp_path / 'worker.db'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    settings = Settings(database_url=database_url, dart_api_key="private-test-key", maintenance_job_timeout_seconds=30)
    real_popen = subprocess.Popen
    children = []
    def spawn(command, **kwargs):
        assert 'private-test-key' not in str(command)
        child = real_popen(command, **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(jobs.subprocess, 'Popen', spawn)
    # A conflicting inherited URL must not redirect the worker to another DB.
    monkeypatch.setenv('DATABASE_URL', 'sqlite:////nonexistent/forbidden.db')
    caplog.set_level(logging.INFO)
    before = jobs.maintenance_status()['completed']
    for _ in range(2):
        assert jobs.run_maintenance_job('stock_logos', settings) == {'candidates': 0, 'ready': 0, 'missing': 0, 'failed': 0}
    assert len({child.pid for child in children}) == 2
    for child in children:
        assert child.poll() == 0
        with pytest.raises(ProcessLookupError):
            os.kill(child.pid, 0)
    assert jobs.maintenance_status()['completed'] == before + 2
    assert jobs.maintenance_status()['running'] is None
    assert 'private-test-key' not in caplog.text


@pytest.mark.parametrize('mode', ['timeout', 'failed', 'invalid', 'oversized'])
def test_worker_failures_are_reaped_and_do_not_expose_output(mode, monkeypatch, caplog):
    programs = {
        'timeout': 'import time; time.sleep(60)',
        'failed': 'import sys; print("secret-provider-key", file=sys.stderr); sys.exit(7)',
        'invalid': 'print("secret-provider-key")',
        'oversized': 'print("x" * 70000)',
    }
    real_popen = subprocess.Popen
    children = []
    def spawn(_command, **kwargs):
        child = real_popen([sys.executable, '-c', programs[mode]], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(jobs.subprocess, 'Popen', spawn)
    with pytest.raises(RuntimeError, match='Maintenance job stock_logos failed') as error:
        jobs.run_maintenance_job('stock_logos', Settings(maintenance_job_timeout_seconds=1))
    assert children[0].poll() is not None
    if mode == 'timeout':
        assert children[0].returncode == -9
    assert jobs.maintenance_status()['running'] is None
    assert 'secret-provider-key' not in str(error.value) + caplog.text


def test_unknown_job_is_rejected_before_process_creation(monkeypatch):
    monkeypatch.setattr(jobs.subprocess, 'Popen', lambda *_a, **_k: pytest.fail('spawned unknown job'))
    with pytest.raises(ValueError):
        jobs.run_maintenance_job('arbitrary-command', Settings())


def test_bulk_jobs_are_serialized(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    real_popen = subprocess.Popen
    children = []
    def spawn(_command, **kwargs):
        assert all(child.poll() is not None for child in children)
        child = real_popen([sys.executable, '-c', 'import time; time.sleep(0.1); print("{}")'], **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(jobs.subprocess, 'Popen', spawn)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: jobs.run_maintenance_job('stock_logos', Settings()), range(2)))
    assert results == [{}, {}]
    assert len(children) == 2


def test_linux_worker_accepts_container_pid_one_and_rejects_reparenting(monkeypatch):
    from app import maintenance_job as worker
    monkeypatch.setattr(worker.sys, 'platform', 'linux')
    monkeypatch.setenv('MAINTENANCE_PARENT_PID', '1')
    monkeypatch.setattr(worker.os, 'getppid', lambda: 1)
    class LibC:
        def prctl(self, *args):
            assert args == (1, 9, 0, 0, 0)
            return 0
    monkeypatch.setattr(worker.ctypes, 'CDLL', lambda *_a, **_k: LibC())
    worker._exit_with_parent()
    monkeypatch.setenv('MAINTENANCE_PARENT_PID', '7')
    with pytest.raises(SystemExit):
        worker._exit_with_parent()
    monkeypatch.setenv('MAINTENANCE_PARENT_PID', '1')
    parents = iter([1, 2])
    monkeypatch.setattr(worker.os, 'getppid', lambda: next(parents))
    with pytest.raises(SystemExit):
        worker._exit_with_parent()
