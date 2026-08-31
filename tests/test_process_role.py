import inspect

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

import app.main as main_module
from app.config import Settings


def test_process_role_separates_web_and_collector_workloads():
    assert Settings(process_role="all").runs_web_services() is True
    assert Settings(process_role="all").runs_collectors() is True
    assert Settings(process_role="web").runs_web_services() is True
    assert Settings(process_role="web").runs_collectors() is False
    assert Settings(process_role="collector").runs_web_services() is False
    assert Settings(process_role="collector").runs_collectors() is True


def test_process_role_is_normalized_and_invalid_values_fail_fast():
    assert Settings(process_role=" WEB ").process_role == "web"
    with pytest.raises(ValidationError):
        Settings(process_role="worker")


def test_lifespan_starts_mutating_collectors_only_for_collector_role():
    source = inspect.getsource(main_module.lifespan)

    assert "if settings.runs_collectors():" in source
    assert "recover_interrupted_ingestions()" in source
    assert "await briefing_runtime.start()" in source
    assert "await web_push_runtime.start()" in source
    assert "await _get_complete_snapshot_runtime().start()" in source
    assert "if settings.runs_web_services() and mcp_server is not None:" in source


def test_web_role_cold_shared_endpoints_queue_and_stable_dashboard_serves_db_only(monkeypatch):
    queued = []
    dashboard_builds = []

    def forbidden(*_args, **_kwargs):
        raise AssertionError("web role must not run a cold external builder")

    monkeypatch.setattr(main_module.settings, "process_role", "web")
    monkeypatch.setattr(main_module, "get_complete_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main_module,
        "_queue_complete_snapshot_refresh",
        lambda _db, key: queued.append(key),
    )
    monkeypatch.setattr(main_module, "us_sector_moves", forbidden)
    monkeypatch.setattr(main_module, "_resolve_stock_master", forbidden)
    monkeypatch.setattr(main_module, "_build_stock_home_context_payload", forbidden)
    monkeypatch.setattr(main_module, "build_market_indices", forbidden)
    monkeypatch.setattr(main_module, "build_stored_global_market_assets", forbidden)
    monkeypatch.setattr(main_module, "fetch_live_global_market_assets", forbidden)
    monkeypatch.setattr(main_module, "_latest_complete_surge_ranking_snapshot", lambda _db: None)
    monkeypatch.setattr(main_module, "_load_surge_ranking_snapshot", forbidden)
    monkeypatch.setattr(
        main_module,
        "build_stock_dashboard",
        lambda _db, code, **kwargs: dashboard_builds.append((code, kwargs)) or {"code": code},
    )
    monkeypatch.setattr(main_module, "_ensure_stock_master_from_naver", forbidden)
    monkeypatch.setattr(main_module, "_enforce_rate_limit", lambda *_args, **_kwargs: None)

    class ExistingStockDb:
        @staticmethod
        def get(_model, _key):
            return type("ExistingStock", (), {"is_active": True})()

    response = Response()
    assert main_module.stock_dashboard(
        "005930",
        response,
        refresh=False,
        include_profile=False,
        include_live=False,
        db=ExistingStockDb(),
    ) == {"code": "005930", "source": "stored_database_warming"}
    assert response.headers["Cache-Control"] == "no-store"
    assert dashboard_builds == [("005930", {"allow_external": False})]

    calls = (
        lambda: main_module.stock_ai_analysis(
            "005930",
            object(),
            refresh=False,
            db=object(),
        ),
        lambda: main_module.market_us_sector_moves(refresh=False, db=object()),
        lambda: main_module.stock_home_context(
            "005930",
            Response(),
            flow_limit=1500,
            research_limit=100,
            disclosure_limit=30,
            news_limit=60,
            community_limit=12,
            db=object(),
        ),
        lambda: main_module.market_indices(Response(), limit=30, refresh=False, db=object()),
        lambda: main_module.global_market_assets(Response(), limit=30, db=object()),
        lambda: main_module.market_rankings(
            category="surge",
            market=None,
            limit=50,
            refresh=False,
            snapshot_id=None,
            db=object(),
        ),
    )
    for call in calls:
        with pytest.raises(HTTPException) as exc_info:
            call()
        assert exc_info.value.status_code == 503
        assert exc_info.value.headers == {"Retry-After": "1"}

    assert queued == [
        main_module._stock_dashboard_snapshot_key("005930"),
        main_module._stock_dashboard_snapshot_key("005930"),
        main_module.US_SECTOR_MOVES_SNAPSHOT_KEY,
        main_module._stock_home_context_snapshot_key(
            "005930",
            flow_limit=1500,
            research_limit=100,
            disclosure_limit=30,
            news_limit=60,
            community_limit=12,
        ),
        f"{main_module.MARKET_INDICES_SNAPSHOT_PREFIX}30",
        f"{main_module.GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX}30",
        main_module.SURGE_COMPLETE_SNAPSHOT_KEY,
    ]


def test_web_role_serves_stale_complete_market_snapshot_without_external_build(monkeypatch):
    payload = {"items": [{"code": "KOSPI"}, {"code": "KOSDAQ"}]}
    queued = []

    class StaleComplete:
        def __init__(self, value):
            self.is_fresh = False
            self.payload = value

    monkeypatch.setattr(main_module.settings, "process_role", "web")
    monkeypatch.setattr(
        main_module,
        "get_complete_snapshot",
        lambda *_args, **_kwargs: StaleComplete(payload),
    )
    monkeypatch.setattr(
        main_module,
        "_queue_complete_snapshot_refresh",
        lambda _db, key: queued.append(key),
    )
    monkeypatch.setattr(
        main_module,
        "build_market_indices",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("external build")),
    )

    assert main_module.market_indices(Response(), limit=30, refresh=False, db=object()) == payload
    assert queued == [f"{main_module.MARKET_INDICES_SNAPSHOT_PREFIX}30"]
