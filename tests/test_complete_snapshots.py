from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateIndex

import app.main as main_module
from app.db import Base
from app.models import (
    CompletePayloadSnapshot,
    DisclosureItem,
    InvestorFlow,
    MarketRankingSnapshot,
    ResearchReport,
)
from app.services.complete_snapshots import (
    SnapshotLeaseLostError,
    SnapshotPublishConflictError,
    claim,
    get,
    mark_failed,
    publish,
    request_refresh,
)
from app.services.snapshot_runtime import SnapshotHandler, SnapshotRuntime


@pytest.fixture
def snapshot_sessions(tmp_path):
    database_path = tmp_path / "complete-snapshots.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False, "timeout": 5},
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[CompletePayloadSnapshot.__table__],
    )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        yield factory
    finally:
        engine.dispose()


def test_complete_snapshot_remains_available_after_freshness_expires(snapshot_sessions):
    captured_at = datetime(2026, 8, 13, 1, 2, 3)
    with snapshot_sessions() as db:
        published = publish(
            db,
            "stock_dashboard:005930",
            {
                "code": "005930",
                "items": [{"price": Decimal("123.45")}],
                "captured": captured_at,
            },
            fresh_for_seconds=60,
            captured_at=captured_at,
            now=captured_at,
        )
        assert published.is_fresh is True

    with snapshot_sessions() as db:
        stale = get(
            db,
            "stock_dashboard:005930",
            now=captured_at + timedelta(minutes=5),
        )

    assert stale is not None
    assert stale.is_fresh is False
    assert stale.payload == {
        "code": "005930",
        "items": [{"price": "123.45"}],
        "captured": captured_at.isoformat(),
    }


def test_validation_serialization_and_failure_never_replace_complete_payload(
    snapshot_sessions,
    monkeypatch,
):
    now = datetime(2026, 8, 13, 2, 0, 0)
    key = "stock_home_context:005930:canonical"
    original = {"code": "005930", "items": [{"id": 1}, {"id": 2}]}
    with snapshot_sessions() as db:
        publish(db, key, original, fresh_for_seconds=0, now=now)

        def reject(candidate):
            candidate["items"].clear()
            raise ValueError("incomplete payload")

        with pytest.raises(ValueError, match="incomplete payload"):
            publish(
                db,
                key,
                {"code": "005930", "items": []},
                fresh_for_seconds=60,
                validator=reject,
                now=now + timedelta(seconds=1),
            )
        assert get(db, key).payload == original

        with pytest.raises(TypeError, match="not JSON serializable"):
            publish(
                db,
                key,
                {"code": "005930", "items": [object()]},
                fresh_for_seconds=60,
                now=now + timedelta(seconds=2),
            )
        assert get(db, key).payload == original

        real_commit = db.commit
        monkeypatch.setattr(
            db,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("commit failed")),
        )
        commit_failure_key = f"{key}:commit-failure"
        with pytest.raises(RuntimeError, match="commit failed"):
            publish(
                db,
                commit_failure_key,
                {"code": "005930", "items": [{"id": 3}]},
                fresh_for_seconds=60,
                now=now + timedelta(seconds=2),
            )
        monkeypatch.setattr(db, "commit", real_commit)
        assert get(db, key).payload == original
        assert get(db, commit_failure_key) is None

        request_refresh(db, key, requested_at=now + timedelta(seconds=3))
        snapshot_claim = claim(
            db,
            "worker-a",
            lease_seconds=30,
            now=now + timedelta(seconds=3),
        )
        assert snapshot_claim is not None
        assert mark_failed(
            db,
            key,
            "worker-a",
            "provider unavailable",
            retry_after_seconds=10,
            now=now + timedelta(seconds=4),
        )
        assert get(db, key).payload == original
        row = db.get(CompletePayloadSnapshot, key)
        assert row.failure_count == 1
        assert row.last_error == "provider unavailable"


def test_cross_process_lease_prevents_stale_worker_publish(snapshot_sessions):
    now = datetime(2026, 8, 13, 3, 0, 0)
    key = "market_indices:30"
    with snapshot_sessions() as seed:
        publish(seed, key, {"items": ["old"]}, fresh_for_seconds=0, now=now)
        request_refresh(seed, key, requested_at=now)

    with snapshot_sessions() as worker_a, snapshot_sessions() as worker_b:
        first = claim(worker_a, "worker-a", lease_seconds=10, now=now)
        assert first is not None
        assert claim(
            worker_b,
            "worker-b",
            lease_seconds=10,
            now=now + timedelta(seconds=5),
        ) is None

        reclaimed = claim(
            worker_b,
            "worker-b",
            lease_seconds=10,
            now=now + timedelta(seconds=11),
        )
        assert reclaimed is not None
        assert reclaimed.snapshot_key == key

        with pytest.raises(SnapshotLeaseLostError):
            publish(
                worker_a,
                key,
                {"items": ["late-worker-a"]},
                fresh_for_seconds=30,
                lease_owner="worker-a",
                now=now + timedelta(seconds=12),
            )
        assert get(worker_a, key).payload == {"items": ["old"]}

        publish(
            worker_b,
            key,
            {"items": ["worker-b"]},
            fresh_for_seconds=30,
            lease_owner="worker-b",
            now=now + timedelta(seconds=12),
        )

    with snapshot_sessions() as reader:
        assert get(reader, key).payload == {"items": ["worker-b"]}


def test_unleased_publish_cannot_clear_active_lease_or_replace_newer_complete(
    snapshot_sessions,
):
    now = datetime(2026, 8, 13, 3, 30, 0)
    key = "market_indices:race"
    with snapshot_sessions() as seed:
        request_refresh(seed, key, requested_at=now)

    with snapshot_sessions() as collector, snapshot_sessions() as web:
        assert claim(collector, "collector", lease_seconds=30, now=now) is not None
        with pytest.raises(SnapshotPublishConflictError):
            publish(
                web,
                key,
                {"generation": "web-cold"},
                fresh_for_seconds=60,
                now=now + timedelta(seconds=1),
            )
        web.expire_all()
        row = web.get(CompletePayloadSnapshot, key)
        assert row.payload is None
        assert row.refresh_requested_at == now
        assert row.lease_owner == "collector"

        publish(
            collector,
            key,
            {"generation": "collector-new"},
            fresh_for_seconds=60,
            lease_owner="collector",
            now=now + timedelta(seconds=2),
        )
        with pytest.raises(SnapshotPublishConflictError):
            publish(
                web,
                key,
                {"generation": "late-web-cold"},
                fresh_for_seconds=60,
                now=now + timedelta(seconds=3),
            )
        web.expire_all()
        assert get(web, key).payload == {"generation": "collector-new"}


def test_unleased_publish_can_fill_an_unclaimed_placeholder(snapshot_sessions):
    now = datetime(2026, 8, 13, 3, 45, 0)
    key = "market_indices:placeholder"
    with snapshot_sessions() as db:
        request_refresh(db, key, requested_at=now)
        published = publish(
            db,
            key,
            {"items": ["complete"]},
            fresh_for_seconds=60,
            now=now + timedelta(seconds=1),
        )
        assert published.payload == {"items": ["complete"]}
        db.expire_all()
        row = db.get(CompletePayloadSnapshot, key)
        assert row.refresh_requested_at is None
        assert row.lease_owner is None


def test_cold_publish_serves_validated_candidate_without_touching_active_placeholder(
    snapshot_sessions,
):
    now = datetime(2026, 8, 13, 3, 50, 0)
    key = "market-indices:v1:active-placeholder"
    with snapshot_sessions() as seed:
        request_refresh(seed, key, requested_at=now)

    with snapshot_sessions() as collector, snapshot_sessions() as web:
        assert claim(collector, "collector", lease_seconds=30, now=now) is not None
        served = main_module._publish_cold_snapshot_or_read_winner(
            web,
            key,
            {"items": [{"value": Decimal("123.45")}], "discard": True},
            fresh_for_seconds=60,
            schema_version=main_module.COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            now=now + timedelta(seconds=1),
            validator=lambda candidate: {"items": candidate["items"]},
        )

        assert served.payload == {"items": [{"value": "123.45"}]}
        web.expire_all()
        row = web.get(CompletePayloadSnapshot, key)
        assert row.payload is None
        assert row.refresh_requested_at == now
        assert row.lease_owner == "collector"


def test_cold_publish_serves_existing_complete_winner(snapshot_sessions):
    now = datetime(2026, 8, 13, 3, 55, 0)
    key = "market-indices:v1:complete-winner"
    with snapshot_sessions() as db:
        publish(
            db,
            key,
            {"generation": "collector"},
            fresh_for_seconds=60,
            schema_version=main_module.COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            now=now,
        )
        served = main_module._publish_cold_snapshot_or_read_winner(
            db,
            key,
            {"generation": "late-web"},
            fresh_for_seconds=60,
            schema_version=main_module.COMPLETE_SNAPSHOT_SCHEMA_VERSION,
            now=now + timedelta(seconds=1),
        )

        assert served.payload == {"generation": "collector"}
        assert get(db, key).payload == {"generation": "collector"}


def test_generic_runtime_retries_without_erasing_previous_snapshot(snapshot_sessions):
    key = "stock_dashboard:000660"
    with snapshot_sessions() as db:
        publish(db, key, {"items": ["old"]}, fresh_for_seconds=0)
        request_refresh(db, key)

    attempts = 0

    def builder(_db, snapshot_key):
        nonlocal attempts
        attempts += 1
        assert snapshot_key == key
        if attempts == 1:
            raise RuntimeError("temporary collector failure")
        return {"items": ["new-a", "new-b"]}

    runtime = SnapshotRuntime(
        snapshot_sessions,
        [
            SnapshotHandler(
                key_prefix="stock_dashboard:",
                builder=builder,
                fresh_for_seconds=120,
                validator=lambda payload: payload
                if len(payload.get("items") or []) == 2
                else (_ for _ in ()).throw(ValueError("incomplete")),
            )
        ],
        lease_owner="runtime-worker",
        failure_retry_seconds=0,
    )

    assert runtime.run_once() is True
    with snapshot_sessions() as db:
        assert get(db, key).payload == {"items": ["old"]}
        assert db.get(CompletePayloadSnapshot, key).failure_count == 1

    assert runtime.run_once() is True
    with snapshot_sessions() as db:
        snapshot = get(db, key)
        assert snapshot.payload == {"items": ["new-a", "new-b"]}
        row = db.get(CompletePayloadSnapshot, key)
        assert row.failure_count == 0
        assert row.last_error is None
        assert row.refresh_requested_at is None


def test_runtime_lanes_keep_realtime_work_independent_from_slow_stock_queue(
    snapshot_sessions,
):
    now = datetime(2026, 8, 13, 4, 0, 0)
    slow_key = "stock_dashboard:005930"
    realtime_key = "market_indices:30"
    with snapshot_sessions() as db:
        request_refresh(db, slow_key, requested_at=now)
        request_refresh(db, realtime_key, requested_at=now + timedelta(seconds=1))

    built: list[str] = []

    def builder(_db, snapshot_key):
        built.append(snapshot_key)
        return {"key": snapshot_key}

    runtime = SnapshotRuntime(
        snapshot_sessions,
        [
            SnapshotHandler(
                key_prefix="stock_dashboard:",
                builder=builder,
                fresh_for_seconds=60,
            ),
            SnapshotHandler(
                key_prefix="market_indices:",
                builder=builder,
                fresh_for_seconds=5,
                lane="realtime",
            ),
        ],
        lease_owner="lane-worker",
    )

    assert runtime.run_once("realtime") is True
    assert built == [realtime_key]
    with snapshot_sessions() as db:
        assert get(db, realtime_key).payload == {"key": realtime_key}
        slow_row = db.get(CompletePayloadSnapshot, slow_key)
        assert slow_row.refresh_requested_at == now
        assert slow_row.lease_owner is None

    assert runtime.run_once("default") is True
    assert built == [realtime_key, slow_key]


def test_runtime_start_runs_realtime_lane_while_default_lane_is_blocked(
    snapshot_sessions,
):
    now = datetime(2026, 8, 13, 4, 10, 0)
    slow_key = "stock_dashboard:000660"
    realtime_key = "market_indices:30"
    with snapshot_sessions() as db:
        request_refresh(db, slow_key, requested_at=now)
        request_refresh(db, realtime_key, requested_at=now)

    slow_started = Event()
    release_slow = Event()
    realtime_finished = Event()

    def slow_builder(_db, snapshot_key):
        assert snapshot_key == slow_key
        slow_started.set()
        assert release_slow.wait(timeout=5)
        return {"key": snapshot_key}

    def realtime_builder(_db, snapshot_key):
        assert snapshot_key == realtime_key
        realtime_finished.set()
        return {"key": snapshot_key}

    runtime = SnapshotRuntime(
        snapshot_sessions,
        [
            SnapshotHandler(
                key_prefix="stock_dashboard:",
                builder=slow_builder,
                fresh_for_seconds=60,
            ),
            SnapshotHandler(
                key_prefix="market_indices:",
                builder=realtime_builder,
                fresh_for_seconds=5,
                lane="realtime",
            ),
        ],
        lease_owner="concurrent-lane-worker",
        poll_seconds=0.05,
    )

    async def exercise_runtime() -> None:
        await runtime.start()
        try:
            assert await asyncio.to_thread(slow_started.wait, 2)
            assert await asyncio.to_thread(realtime_finished.wait, 2)
            deadline = asyncio.get_running_loop().time() + 2
            realtime_snapshot = None
            while realtime_snapshot is None and asyncio.get_running_loop().time() < deadline:
                with snapshot_sessions() as db:
                    realtime_snapshot = get(db, realtime_key)
                if realtime_snapshot is None:
                    await asyncio.sleep(0.01)
            assert realtime_snapshot is not None
            assert realtime_snapshot.payload == {"key": realtime_key}
            with snapshot_sessions() as db:
                assert get(db, slow_key) is None
        finally:
            release_slow.set()
            await runtime.stop()

    asyncio.run(exercise_runtime())

    with snapshot_sessions() as db:
        assert get(db, slow_key).payload == {"key": slow_key}


def _complete_index_payload() -> dict[str, object]:
    return {
        "items": [
            {
                "code": code,
                "current": 100.0,
                "previous_close": 99.0,
                "change": 1.0,
                "change_rate": 1.01,
                "as_of": "2026-08-13",
                "points": [{"date": "2026-08-13", "value": 100.0}],
            }
            for code in ("KOSPI", "KOSDAQ")
        ]
    }


def test_market_index_validator_rejects_missing_values_and_history():
    payload = _complete_index_payload()
    assert main_module._validate_market_indices_snapshot(payload)["items"][0]["current"] == 100.0

    missing_value = json.loads(json.dumps(payload))
    missing_value["items"][0]["current"] = None
    with pytest.raises(ValueError, match="current or previous"):
        main_module._validate_market_indices_snapshot(missing_value)

    missing_history = json.loads(json.dumps(payload))
    missing_history["items"][1]["points"] = []
    with pytest.raises(ValueError, match="chart history"):
        main_module._validate_market_indices_snapshot(missing_history)


def test_global_and_us_sector_validators_reject_data_omissions():
    global_payload = {
        "items": [
            {
                "code": definition[0],
                "current": 100.0,
                "previous_close": 99.0,
                "change": 1.0,
                "change_rate": 1.01,
                "as_of": "2026-08-13T00:00:00+00:00",
                "points": [{"date": "2026-08-13", "value": 100.0}],
            }
            for definition in main_module.GLOBAL_MARKET_DEFINITIONS
        ]
    }
    assert len(main_module._validate_global_market_assets_snapshot(global_payload)["items"]) == 6
    global_payload["items"][2]["previous_close"] = None
    with pytest.raises(ValueError, match="current or previous"):
        main_module._validate_global_market_assets_snapshot(global_payload)

    sector_payload = {
        "items": [
            {
                "symbol": definition["symbol"],
                "label": definition["label"],
                "sector": definition["sector"],
                "price": 100.0,
                "previous_close": 99.0,
                "change_rate": 1.01,
                "trade_date": "2026-08-13",
            }
            for definition in main_module.US_SECTOR_ETFS
        ]
    }
    assert len(main_module._validate_us_sector_moves_snapshot(sector_payload)["items"]) == len(
        main_module.US_SECTOR_ETFS
    )
    sector_payload["items"][0]["price"] = None
    with pytest.raises(ValueError, match="price data"):
        main_module._validate_us_sector_moves_snapshot(sector_payload)


def _home_context_payload() -> dict[str, object]:
    return {
        "code": "005930",
        "name": "삼성전자",
        "as_of": "2026-08-13T00:00:00",
        "flows": [],
        "research_reports": [],
        "disclosures": [],
        "news_items": [],
        "community": {
            "code": "005930",
            "name": "삼성전자",
            "as_of": "2026-08-13T00:00:00",
            "providers": [
                {
                    "key": "naver_board",
                    "label": "네이버",
                    "source": "naver_finance_board",
                    "configured": True,
                    "search_url": "https://finance.naver.com/item/board.naver?code=005930",
                    "more_label": "종토방 더 보기",
                    "items": [],
                }
            ],
        },
    }


def test_home_context_validator_keeps_legal_empty_sections_but_rejects_broken_slots():
    payload = _home_context_payload()
    validated = main_module._validate_stock_home_context_snapshot(payload)
    assert validated["flows"] == []
    assert validated["community"]["providers"][0]["items"] == []

    mismatched = json.loads(json.dumps(payload))
    mismatched["community"]["code"] = "000660"
    with pytest.raises(ValueError, match="does not match"):
        main_module._validate_stock_home_context_snapshot(mismatched)

    missing_slots = json.loads(json.dumps(payload))
    missing_slots["community"]["providers"] = []
    with pytest.raises(ValueError, match="provider slots"):
        main_module._validate_stock_home_context_snapshot(missing_slots)


def test_home_context_refresh_preserves_prior_evidence_on_transient_empty_result():
    previous = _home_context_payload()
    previous["flows"] = [{"id": "old-flow"}]
    previous["research_reports"] = [{"id": "old-report"}]
    previous["disclosures"] = [{"id": "old-disclosure"}]
    previous["news_items"] = [{"id": "old-news"}]
    previous["community"]["providers"][0]["items"] = [{"post_id": "old-post"}]

    candidate = _home_context_payload()
    candidate["community"]["providers"][0]["configured"] = False
    preserved = main_module._preserve_stock_home_context_complete_sections(previous, candidate)

    assert preserved["flows"] == previous["flows"]
    assert preserved["research_reports"] == previous["research_reports"]
    assert preserved["disclosures"] == previous["disclosures"]
    assert preserved["news_items"] == previous["news_items"]
    assert preserved["community"]["providers"][0]["items"] == [{"post_id": "old-post"}]


def _surge_payload(*, include_all: bool = True) -> dict[str, object]:
    kospi = {
        "rank": 1,
        "category": "surge",
        "code": "005930",
        "name": "삼성전자",
        "market": "KOSPI",
        "change_rate": 1.0,
    }
    kosdaq = {
        "rank": 1,
        "category": "surge",
        "code": "035420",
        "name": "NAVER",
        "market": "KOSDAQ",
        "change_rate": 2.0,
    }
    return {
        "as_of": "2026-08-13T00:00:00+09:00",
        "markets": {
            "KOSPI": {"universe_count": 1, "matching_count": 1, "items": [kospi]},
            "KOSDAQ": {"universe_count": 1, "matching_count": 1, "items": [kosdaq]},
            "ALL": {
                "universe_count": 2,
                "matching_count": 2 if include_all else 1,
                "items": [kospi, kosdaq] if include_all else [kospi],
            },
        },
    }


def _surge_snapshot(snapshot_id: str, payload: dict[str, object]) -> MarketRankingSnapshot:
    now = datetime(2026, 8, 13, 5, 0, 0)
    return MarketRankingSnapshot(
        snapshot_id=snapshot_id,
        category="surge",
        payload=json.dumps(payload, ensure_ascii=False),
        captured_at=now,
        expires_at=now + timedelta(days=1),
    )


def test_surge_complete_shape_rejects_empty_buckets_and_all_mismatch():
    assert main_module._surge_snapshot_has_complete_shape(
        _surge_snapshot("complete", _surge_payload())
    )
    empty = _surge_payload()
    empty["markets"]["KOSDAQ"]["items"] = []
    assert not main_module._surge_snapshot_has_complete_shape(_surge_snapshot("empty", empty))
    assert not main_module._surge_snapshot_has_complete_shape(
        _surge_snapshot("mismatch", _surge_payload(include_all=False))
    )


def test_surge_complete_shape_allows_legitimate_zero_match_session():
    payload = _surge_payload()
    for market_name in ("KOSPI", "KOSDAQ", "ALL"):
        payload["markets"][market_name]["matching_count"] = 0
        payload["markets"][market_name]["items"] = []

    assert main_module._surge_snapshot_has_complete_shape(
        _surge_snapshot("complete-zero-match", payload)
    )


def test_incomplete_surge_refresh_never_deletes_previous_complete_snapshot(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[MarketRankingSnapshot.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    previous = _surge_snapshot("previous-complete", _surge_payload())
    previous.expires_at = datetime(2026, 8, 12, 5, 0, 0)
    with factory() as db:
        db.add(previous)
        db.commit()
        monkeypatch.setattr(
            main_module,
            "_build_surge_ranking_snapshot_payload",
            lambda *_args, **_kwargs: {
                "as_of": "2026-08-13T00:00:00+09:00",
                "markets": {
                    name: {"universe_count": 0, "matching_count": 0, "items": []}
                    for name in ("KOSPI", "KOSDAQ", "ALL")
                },
            },
        )
        with pytest.raises(ValueError, match="incomplete snapshot"):
            main_module._build_surge_complete_snapshot(db, main_module.SURGE_COMPLETE_SNAPSHOT_KEY)
        rows = list(
            db.scalars(
                select(MarketRankingSnapshot).order_by(MarketRankingSnapshot.snapshot_id)
            )
        )
        assert [row.snapshot_id for row in rows] == ["previous-complete"]
        assert main_module._surge_snapshot_has_complete_shape(rows[0])
    engine.dispose()


def test_complete_surge_refresh_cleans_only_expired_previous_snapshots(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[MarketRankingSnapshot.__table__])
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.utcnow()
    expired = _surge_snapshot("expired-previous", _surge_payload())
    expired.expires_at = now - timedelta(seconds=1)
    retained = _surge_snapshot("unexpired-previous", _surge_payload())
    retained.expires_at = now + timedelta(days=1)
    expired_id = expired.snapshot_id
    retained_id = retained.snapshot_id
    with factory() as db:
        db.add_all([expired, retained])
        db.commit()
        monkeypatch.setattr(
            main_module,
            "_build_surge_ranking_snapshot_payload",
            lambda *_args, **_kwargs: _surge_payload(),
        )

        current = main_module._load_surge_ranking_snapshot(
            db,
            snapshot_id=None,
            refresh=True,
        )
        rows = list(
            db.scalars(
                select(MarketRankingSnapshot).order_by(MarketRankingSnapshot.snapshot_id)
            )
        )

        assert current.snapshot_id not in {expired_id, retained_id}
        assert {row.snapshot_id for row in rows} == {
            current.snapshot_id,
            retained_id,
        }
        assert all(main_module._surge_snapshot_has_complete_shape(row) for row in rows)
    engine.dispose()


def test_performance_indexes_are_declared_for_sqlite_and_postgresql():
    expected = {
        "ix_investor_flow_code_trade_date_desc_type": InvestorFlow.__table__,
        "ix_research_report_stock_published_id_desc": ResearchReport.__table__,
        "ix_disclosure_item_stock_published_external_id_desc": DisclosureItem.__table__,
        "ix_market_ranking_snapshot_category_captured_desc": MarketRankingSnapshot.__table__,
    }
    for index_name, table in expected.items():
        index = next(item for item in table.indexes if item.name == index_name)
        sqlite_ddl = str(CreateIndex(index).compile(dialect=sqlite.dialect()))
        postgres_ddl = str(CreateIndex(index).compile(dialect=postgresql.dialect()))
        assert " DESC" in sqlite_ddl
        assert " DESC" in postgres_ddl

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    try:
        inspector = inspect(engine)
        for index_name, table in expected.items():
            reflected_names = {
                item["name"] for item in inspector.get_indexes(table.name)
            }
            assert index_name in reflected_names
    finally:
        engine.dispose()


def test_surge_cold_start_failure_never_masquerades_as_an_empty_complete_snapshot(
    monkeypatch,
):
    queued = []
    monkeypatch.setattr(main_module, "get_complete_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        main_module,
        "_latest_complete_surge_ranking_snapshot",
        lambda _db: None,
    )
    monkeypatch.setattr(
        main_module,
        "_load_surge_ranking_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("provider down")),
    )
    monkeypatch.setattr(
        main_module,
        "_queue_complete_snapshot_refresh",
        lambda _db, key: queued.append(key),
    )

    with pytest.raises(HTTPException) as exc_info:
        main_module.market_rankings(
            category="surge",
            market=None,
            limit=50,
            refresh=False,
            snapshot_id=None,
            db=object(),
        )

    assert exc_info.value.status_code == 503
    assert queued == [main_module.SURGE_COMPLETE_SNAPSHOT_KEY]
