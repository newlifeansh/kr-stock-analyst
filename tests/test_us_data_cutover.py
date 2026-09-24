from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import (
    DesktopUserPreference,
    PushSubscription,
    RecommendationTrackState,
    WatchlistGroupState,
    WatchlistItem,
)
from app.us_data_cutover import export_us_rows, migration_plan


NOW = datetime(2026, 9, 24, 9, 0)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    for model in (
        WatchlistItem, WatchlistGroupState, RecommendationTrackState,
        PushSubscription, DesktopUserPreference,
    ):
        model.__table__.create(engine)
    return Session(engine)


def test_us_cutover_copies_only_missing_us_namespaced_state_idempotently():
    with _session() as source, _session() as target:
        source.add_all([
            WatchlistItem(
                share_id="us.member", code="AAPL", name="Apple", market="NASDAQ",
                investor_state="holding", average_buy_price=Decimal("180.00"),
                sort_order=1, created_at=NOW, updated_at=NOW,
            ),
            WatchlistItem(
                share_id="domestic.member", code="005930", name="Samsung", market="KOSPI",
                sort_order=1, created_at=NOW, updated_at=NOW,
            ),
            WatchlistGroupState(
                share_id="us.member", payload='[{"name":"core"}]',
                created_at=NOW, updated_at=NOW,
            ),
            RecommendationTrackState(
                share_id="us.member", payload='[{"code":"AAPL"}]',
                created_at=NOW, updated_at=NOW,
            ),
        ])
        source.commit()
        payload = export_us_rows(source)
        assert [row["code"] for row in payload["tables"]["watchlist_item"]] == ["AAPL"]
        assert payload["manual_review_counts"] == {
            "push_subscription": 0,
            "desktop_user_preferences": 0,
        }

        report, pending = migration_plan(target, payload)
        assert report["conflicts"] == 0
        assert sum(item["insert"] for item in report["tables"].values()) == 3
        target.add_all(pending)
        target.commit()
        assert len(target.scalars(select(WatchlistItem)).all()) == 1
        assert target.scalar(select(WatchlistItem)).share_id == "us.member"

        repeated, pending = migration_plan(target, payload)
        assert repeated["conflicts"] == 0
        assert not pending
        assert sum(item["already_present"] for item in repeated["tables"].values()) == 3


def test_us_cutover_blocks_conflicts_and_private_subscription_state():
    with _session() as source, _session() as target:
        source.add(WatchlistGroupState(
            share_id="us.member", payload='[{"name":"original"}]',
            created_at=NOW, updated_at=NOW,
        ))
        target.add(WatchlistGroupState(
            share_id="us.member", payload='[{"name":"different"}]',
            created_at=NOW, updated_at=NOW,
        ))
        source.commit()
        target.commit()
        payload = export_us_rows(source)
        report, pending = migration_plan(target, payload)
        assert report["conflicts"] == 1
        assert not pending

        payload["manual_review_counts"]["push_subscription"] = 1
        with pytest.raises(ValueError, match="separate review"):
            migration_plan(target, payload)
