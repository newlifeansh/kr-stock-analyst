"""Private subprocess entrypoint. No web server, timers or persistent worker."""

from __future__ import annotations

import contextlib
import ctypes
import json
import os
import signal
import sys


def _exit_with_parent() -> None:
    if sys.platform == "linux":
        parent = os.getppid()
        # A container shutdown must not leave an orphan doing batch work.
        if ctypes.CDLL(None, use_errno=True).prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
            raise RuntimeError("Could not bind maintenance worker lifetime")
        if parent == 1 or os.getppid() != parent:
            raise SystemExit(1)


def execute_job(job: str, settings) -> dict:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from app.db import SessionLocal, engine

    try:
        with SessionLocal() as db:
            if job == "stock_universe":
                from app.collectors.krx import collect_stocks
                return {"rows_loaded": collect_stocks(db, datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y%m%d"), settings.stock_universe_markets)}
            if job == "research_backfill":
                from app.collectors.research import collect_research_reports
                collect_research_reports(db, settings=settings, categories=["company"], max_pages=settings.research_backfill_max_pages, days_back=settings.research_backfill_days_back, include_detail=False)
                return {"completed": True}
            if job == "financials":
                from app.services.briefing import BriefingRuntime
                return BriefingRuntime(settings)._collect_financials(db)
            if job == "fundamentals":
                from app.collectors.stock_snapshots import collect_stock_fundamental_snapshots
                return collect_stock_fundamental_snapshots(db, max_workers=settings.fundamental_snapshot_max_workers, refresh_days=settings.fundamental_snapshot_refresh_days)
            if job == "company_snapshots":
                from app.collectors.stock_snapshots import collect_stock_company_snapshots
                return collect_stock_company_snapshots(db, max_workers=settings.stock_company_snapshot_max_workers, refresh_days=settings.stock_company_snapshot_refresh_days)
            if job == "stock_logos":
                from app.services.stock_logos import sync_stock_logos
                return sync_stock_logos(db, markets=settings.stock_universe_markets, timeout_seconds=settings.stock_logo_timeout_seconds, max_workers=settings.stock_logo_max_workers, missing_retry_days=settings.stock_logo_missing_retry_days)
            raise ValueError("Unknown maintenance job")
    finally:
        engine.dispose()


def main() -> int:
    from app.services.maintenance_jobs import JOB_NAMES, MAX_RESULT_BYTES
    if len(sys.argv) != 2 or sys.argv[1] not in JOB_NAMES:
        return 2
    try:
        _exit_with_parent()
        from app import config
        settings = config.Settings.model_validate_json(sys.stdin.buffer.read(1_048_576))
        # Imports below must use exactly the parent's settings (including test
        # databases); neither a local .env nor inherited defaults may override.
        settings.maintenance_subprocess_enabled = False
        config.get_settings = lambda: settings
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = execute_job(sys.argv[1], settings)
        payload = json.dumps(result)
        if len(payload.encode()) > MAX_RESULT_BYTES:
            return 1
        print(payload)
        return 0
    except Exception:
        # Parent reports job + exit status. Provider exceptions can contain keys.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
