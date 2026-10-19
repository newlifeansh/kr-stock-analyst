"""Run infrequent bulk collectors in disposable processes, one at a time."""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from threading import Lock
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config import Settings

logger = logging.getLogger("uvicorn.error.maintenance")
JOB_NAMES = frozenset({
    "stock_universe", "research_backfill", "financials", "fundamentals",
    "company_snapshots", "stock_logos",
})
_job_lock = Lock()
_status_lock = Lock()
_status: dict[str, object] = {"running": None, "completed": 0, "failed": 0}
MAX_RESULT_BYTES = 65_536


def maintenance_status() -> dict[str, object]:
    with _status_lock:
        return dict(_status)


def _kill_process_group(process: subprocess.Popen) -> None:
    # Kill descendants as well; a timed-out collector must not keep charging.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_maintenance_job(job: str, settings: Settings) -> dict:
    if job not in JOB_NAMES:
        raise ValueError("Unknown maintenance job")
    with _job_lock:
        started = time.monotonic()
        with _status_lock:
            _status["running"] = job
        logger.info("Maintenance job started job=%s", job)
        try:
            # Settings travel only over stdin, never argv, files or logs. Child
            # stdout is bounded when read; provider noise cannot consume RAM.
            with tempfile.TemporaryFile() as result_file:
                process = subprocess.Popen(
                    [sys.executable, "-m", "app.maintenance_job", job],
                    stdin=subprocess.PIPE, stdout=result_file,
                    stderr=subprocess.DEVNULL, start_new_session=True,
                    env={**os.environ, "MAINTENANCE_PARENT_PID": str(os.getpid())},
                )
                try:
                    process.communicate(
                        input=settings.model_dump_json().encode(),
                        timeout=max(1, settings.maintenance_job_timeout_seconds),
                    )
                except BaseException:
                    _kill_process_group(process)
                    raise
                if process.returncode:
                    raise RuntimeError(f"Maintenance job {job} exited {process.returncode}")
                result_file.seek(0)
                payload = result_file.read(MAX_RESULT_BYTES + 1)
            if len(payload) > MAX_RESULT_BYTES:
                raise RuntimeError(f"Maintenance job {job} result exceeded limit")
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise RuntimeError(f"Maintenance job {job} returned an invalid result")
            with _status_lock:
                _status["completed"] += 1
                _status["last_completed_job"] = job
                _status["last_exit_code"] = 0
            logger.info("Maintenance job exited job=%s exit=0 elapsed_seconds=%.1f", job, time.monotonic() - started)
            return result
        except Exception as exc:
            with _status_lock:
                _status["failed"] += 1
            # Do not pass provider output or serialized settings into status/logs.
            logger.warning("Maintenance job failed job=%s error_type=%s", job, type(exc).__name__)
            raise RuntimeError(f"Maintenance job {job} failed ({type(exc).__name__})") from None
        finally:
            with _status_lock:
                _status["running"] = None
