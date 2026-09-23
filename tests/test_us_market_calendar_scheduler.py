from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import MarketQuantSignalSnapshot, MarketRankingSnapshot
from app.services import us_position_lifecycle as lifecycle
from app.services import us_signal_universe as universe
from app.services.us_market_calendar import USMarketCalendarUnavailable
from tests.test_us_position_lifecycle_runtime import (
    _complete_feed as _runtime_complete_feed,
    _universe_audit_metadata,
)


UTC = timezone.utc


class _StopScheduler(Exception):
    pass


def _complete_feed() -> dict[str, object]:
    payload = deepcopy(_runtime_complete_feed())
    session_date = date(2026, 11, 25)
    payload["as_of"] = datetime(2026, 11, 25, 21, 15, tzinfo=UTC)
    payload["universe_as_of"] = session_date
    for member in payload["universe_members"]:
        member["screen_as_of"] = session_date
        member["quote_date"] = session_date
    universe_checksum = universe._snapshot_checksum(payload["universe_members"])
    payload["universe_checksum"] = universe_checksum
    shadow = payload["shadow_comparison"]
    shadow["universe_as_of"] = session_date
    shadow["universe_checksum"] = universe_checksum
    item = payload["items"][0]
    item["signal_date"] = session_date
    item["signal_at"] = datetime(2026, 11, 25, 21, 0, tzinfo=UTC)
    item["price_through"] = session_date.isoformat()
    for reason in item["public_reasons"]:
        reason["as_of"] = datetime(2026, 11, 25, 21, 0, tzinfo=UTC)
    transition = item["current"]["lifecycle"]["latest_transition"]
    transition["signal_date"] = session_date
    transition["transition_date"] = session_date
    return payload


def _seed_authoritative_universe(
    db: Session,
    payload: dict[str, object],
    *,
    captured_at: datetime,
) -> None:
    session_date = str(payload["universe_as_of"])
    stored_at = captured_at.astimezone(UTC).replace(tzinfo=None)
    db.add(
        MarketRankingSnapshot(
            snapshot_id=f"{lifecycle.US_SIGNAL_UNIVERSE_VERSION}:{session_date}",
            category=universe.US_SIGNAL_UNIVERSE_CATEGORY,
            payload=universe._serialize_payload(
                {
                    "status": "ready",
                    "data_state": "ready",
                    "universe_version": lifecycle.US_SIGNAL_UNIVERSE_VERSION,
                    "universe_as_of": payload["universe_as_of"],
                    "generated_at": captured_at,
                    "universe_count": 100,
                    "source_candidate_count": 101,
                    "validated_quote_count": 100,
                    "checksum": payload["universe_checksum"],
                    **_universe_audit_metadata(payload["universe_members"]),
                    "new_entries_allowed": True,
                    "items": payload["universe_members"],
                }
            ),
            captured_at=stored_at,
            expires_at=stored_at + timedelta(days=400),
        )
    )
    db.commit()


def _run_one_scheduler_iteration(
    monkeypatch,
    now: datetime,
    *,
    schema_upgrade_due: bool = False,
) -> None:
    from app import main as main_module

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    async def inline_to_thread(function, /, *args, **kwargs):
        return function(*args, **kwargs)

    async def stop_after_iteration(_seconds):
        raise _StopScheduler

    monkeypatch.setattr(main_module, "datetime", FixedDatetime)
    monkeypatch.setattr(
        main_module,
        "_us_position_lifecycle_schema_upgrade_due",
        lambda _now: schema_upgrade_due,
    )
    monkeypatch.setattr(main_module.asyncio, "to_thread", inline_to_thread)
    monkeypatch.setattr(main_module.asyncio, "sleep", stop_after_iteration)

    with pytest.raises(_StopScheduler):
        asyncio.run(main_module._run_us_position_lifecycle_refresh_loop())


def test_us_scheduler_does_not_refresh_during_official_regular_session(monkeypatch):
    from app import main as main_module

    refreshes: list[bool] = []
    monkeypatch.setattr(
        main_module,
        "_us_position_lifecycle_snapshot_due",
        lambda _now: True,
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_us_position_lifecycle_snapshot",
        lambda: refreshes.append(True),
    )

    # Black Friday is still open one minute before its official 18:00 UTC close.
    _run_one_scheduler_iteration(
        monkeypatch,
        datetime(2026, 11, 27, 17, 59, tzinfo=UTC),
    )

    assert refreshes == []
    assert main_module.us_position_lifecycle_refresh_lock.locked() is False


def test_us_scheduler_does_not_refresh_inside_post_close_provider_grace(monkeypatch):
    from app import main as main_module

    refreshes: list[bool] = []
    monkeypatch.setattr(
        main_module,
        "_us_position_lifecycle_snapshot_due",
        lambda _now: True,
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_us_position_lifecycle_snapshot",
        lambda: refreshes.append(True),
    )

    _run_one_scheduler_iteration(
        monkeypatch,
        datetime(2026, 11, 27, 18, 1, tzinfo=UTC),
    )

    assert refreshes == []
    assert main_module.us_position_lifecycle_refresh_lock.locked() is False


def test_us_scheduler_refreshes_once_after_post_close_grace_when_due(monkeypatch):
    from app import main as main_module

    refreshes: list[bool] = []
    monkeypatch.setattr(
        main_module,
        "_us_position_lifecycle_snapshot_due",
        lambda _now: True,
    )
    monkeypatch.setattr(
        main_module,
        "_refresh_us_position_lifecycle_snapshot",
        lambda: refreshes.append(True) or {"status": "ready"},
    )

    _run_one_scheduler_iteration(
        monkeypatch,
        datetime(2026, 11, 27, 18, 16, tzinfo=UTC),
    )

    assert refreshes == [True]
    assert main_module.us_position_lifecycle_refresh_lock.locked() is False


def test_calendar_unavailable_blocks_stored_pending_entry_and_requires_refresh(
    monkeypatch,
):
    engine = create_engine("sqlite:///:memory:")
    MarketQuantSignalSnapshot.__table__.create(engine)
    MarketRankingSnapshot.__table__.create(engine)
    now = datetime(2026, 11, 25, 21, 15, tzinfo=UTC)

    try:
        with Session(engine) as db:
            feed = _complete_feed()
            _seed_authoritative_universe(db, feed, captured_at=now)
            lifecycle.save_us_position_lifecycle_snapshot(
                db,
                feed,
                generated_at=now,
            )
            monkeypatch.setattr(
                lifecycle,
                "expected_completed_us_session_date",
                lambda _now=None: (_ for _ in ()).throw(
                    USMarketCalendarUnavailable("calendar unavailable")
                ),
            )

            loaded = lifecycle.load_us_position_lifecycle_snapshot(db, now=now)

            assert loaded is not None
            assert loaded["data_state"] == "calendar_unavailable"
            assert loaded["new_entries_allowed"] is False
            assert loaded["entry_pending_count"] == 0
            assert loaded["items"][0]["current"]["action"] == "entry_watch"
            assert lifecycle.us_position_lifecycle_refresh_due(loaded, now=now) is True
    finally:
        engine.dispose()
