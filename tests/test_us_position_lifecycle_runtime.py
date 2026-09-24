from __future__ import annotations

from copy import deepcopy
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import MarketQuantSignalSnapshot, MarketRankingSnapshot
from app.services import us_position_lifecycle as lifecycle
from app.services import us_signal_universe as universe


UTC = timezone.utc


def _universe_audit_metadata(
    members: list[dict[str, object]],
) -> dict[str, object]:
    digest = universe._canonical_digest
    source_audit = {
        "version": universe.US_SIGNAL_UNIVERSE_AUDIT_VERSION,
        "trust_model": "trusted_database_integrity_checksum_not_external_signature",
        "screen": {
            "exchanges": [
                {
                    "exchange": exchange,
                    "raw_count": count,
                    "eligible_count": count,
                    "ranking_dataset_digest": digest([exchange, "ranking", count]),
                    "eligible_dataset_digest": digest([exchange, "eligible", count]),
                    "classification_dataset_digest": digest(
                        [exchange, "classification", count]
                    ),
                    "classification_as_of": None,
                    "classification_date_state": "provider_unreported",
                    "classification_missing_count": 0,
                }
                for exchange, count in (("NASDAQ", 51), ("NYSE", 50))
            ],
            "prefilter_candidate_count": 101,
            "prefilter_candidate_digest": digest(["candidates", 101]),
        },
        "quotes": {
            "requested_count": 101,
            "returned_count": 100,
            "observation_digest": digest(["quotes", 100]),
        },
        "sec_identities": {
            "requested_count": 101,
            "mapped_count": 101,
            "identity_digest": digest(["sec", 101]),
        },
    }
    rank_100 = members[-1]
    boundary_evidence = {
        "ranking_authority": "nasdaq_screener_market_cap",
        "issuer_identity": "sec_cik",
        "proven_issuer_count": 101,
        "rank_100": {
            "rank": 100,
            "issuer_key": rank_100["issuer_key"],
            "market_cap": str(rank_100["market_cap"]),
            "candidate_codes": [rank_100["code"]],
            "selected_code": rank_100["code"],
        },
        "rank_101": {
            "rank": 101,
            "issuer_key": "cik:0000000101",
            "market_cap": str(int(str(rank_100["market_cap"])) - 1),
            "candidate_codes": ["Z101"],
        },
        "tie": {
            "applied": False,
            "market_cap": None,
            "tie_breaker": "sec_cik_ascending",
            "issuer_keys": [],
            "selected_issuer_keys": [],
            "excluded_issuer_keys": [],
        },
    }
    member_checksum = universe._snapshot_checksum(members)
    universe_as_of = members[0]["screen_as_of"]
    return {
        "source_audit": source_audit,
        "boundary_evidence": boundary_evidence,
        "audit_checksum": universe._snapshot_audit_checksum(
            source_audit,
            boundary_evidence,
            member_checksum=member_checksum,
            universe_version=universe.US_SIGNAL_UNIVERSE_VERSION,
            universe_as_of=universe_as_of,
        ),
    }


@pytest.fixture
def snapshot_db():
    engine = create_engine("sqlite:///:memory:")
    MarketQuantSignalSnapshot.__table__.create(engine)
    MarketRankingSnapshot.__table__.create(engine)
    with Session(engine) as db:
        feed = _complete_feed()
        session_date = str(feed["universe_as_of"])
        captured_at = datetime(2026, 9, 8, 21, 0)
        db.add(
            MarketRankingSnapshot(
                snapshot_id=(
                    f"{lifecycle.US_SIGNAL_UNIVERSE_VERSION}:{session_date}"
                ),
                category=universe.US_SIGNAL_UNIVERSE_CATEGORY,
                payload=universe._serialize_payload(
                    {
                        "status": "ready",
                        "data_state": "ready",
                        "universe_version": lifecycle.US_SIGNAL_UNIVERSE_VERSION,
                        "universe_as_of": feed["universe_as_of"],
                        "generated_at": datetime(2026, 9, 8, 21, 0, tzinfo=UTC),
                        "universe_count": 100,
                        "source_candidate_count": 101,
                        "validated_quote_count": 100,
                        "checksum": feed["universe_checksum"],
                        **_universe_audit_metadata(feed["universe_members"]),
                        "new_entries_allowed": True,
                        "items": feed["universe_members"],
                    }
                ),
                captured_at=captured_at,
                expires_at=captured_at + timedelta(days=400),
            )
        )
        db.commit()
        yield db
    engine.dispose()


def _universe_members(session_date: date) -> list[dict[str, object]]:
    members = []
    for rank in range(1, 101):
        code = "NVDA" if rank == 1 else f"T{rank:03d}"
        cik = "0001045810" if rank == 1 else f"{rank:010d}"
        members.append(
            {
                "market_cap_rank": rank,
                "code": code,
                "name": "NVIDIA" if rank == 1 else f"Issuer {rank}",
                "market": "NASDAQ",
                "exchange": "NMS",
                "market_cap": str(200_000_000_000 - rank),
                "issuer_key": f"cik:{cik}",
                "cik": cik,
                "sector": "Technology",
                "currency": "USD",
                "screen_as_of": session_date,
                "quote_date": session_date,
            }
        )
    return members


def _complete_feed() -> dict[str, object]:
    session_date = date(2026, 9, 8)
    members = _universe_members(session_date)
    universe_checksum = universe._snapshot_checksum(members)
    return {
        "status": "ready",
        "strategy_version": lifecycle.US_STRATEGY_VERSION,
        "baseline_strategy_version": lifecycle.US_BASELINE_STRATEGY_VERSION,
        "rollout_mode": lifecycle.US_ROLLOUT_MODE,
        "execution_enabled": False,
        "stateful_lifecycle_replay_enabled": lifecycle.US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
        "reentry_runtime_enabled": lifecycle.US_REENTRY_RUNTIME_ENABLED,
        "lifecycle_replay_version": lifecycle.US_LIFECYCLE_REPLAY_VERSION,
        "as_of": datetime(2026, 9, 8, 21, 0, tzinfo=UTC),
        "universe_as_of": session_date,
        "universe_count": 100,
        "universe_members": members,
        "universe_version": lifecycle.US_SIGNAL_UNIVERSE_VERSION,
        "sector_classification_version": lifecycle.US_SECTOR_ETF_CLASSIFICATION_VERSION,
        "universe_checksum": universe_checksum,
        "universe_data_state": "ready",
        "evaluated_count": 100,
        "data_coverage_count": 100,
        "signal_eligible_count": 100,
        "insufficient_history_count": 0,
        "insufficient_history_codes": [],
        "history_error_count": 0,
        "sector_classification_error_count": 0,
        "stateful_lifecycle_replay_complete": True,
        "stateful_lifecycle_replay_eligible_count": 100,
        "stateful_lifecycle_replay_completed_count": 100,
        "confirmed_count": 0,
        "preliminary_count": 1,
        "preliminary_history": [],
        "methodology": ["completed-session top 100"],
        "universe_policy": {
            "limit": 100,
            "version": lifecycle.US_SIGNAL_UNIVERSE_VERSION,
            "new_entries_allowed": True,
        },
        "source_errors": {},
        "sector_classification_errors": {},
        "shadow_comparison": {
            "candidate": lifecycle.US_STRATEGY_VERSION,
            "baseline": lifecycle.US_BASELINE_STRATEGY_VERSION,
            "universe_version": lifecycle.US_SIGNAL_UNIVERSE_VERSION,
            "universe_as_of": session_date,
            "universe_checksum": universe_checksum,
            "universe_count": 100,
            "same_snapshot_evaluated_count": 100,
            "comparison_complete": True,
            "candidate_preliminary_count": 1,
            "candidate_actions": {
                str(member["code"]): "entry_pending" if member["code"] == "NVDA" else "no_signal"
                for member in members
            },
            "candidate_action_counts": {"entry_pending": 1, "entry_watch": 0, "no_signal": 99},
            "baseline_action_counts": {"entry_watch": 100},
            "candidate_entry_pending_count": 1,
            "displayed_entry_pending_count": 1,
            "baseline_entry_pending_count": 0,
            "entry_pending_overlap_count": 0,
            "entry_pending_overlap_codes": [],
            "candidate_only_entry_pending_count": 1,
            "baseline_only_entry_pending_count": 0,
            "action_agreement_count": 0,
            "action_agreement_rate": "0.00",
            "candidate_only_entry_pending_codes": ["NVDA"],
            "baseline_only_entry_pending_codes": [],
            "action_disagreement_codes": [
                str(member["code"]) for member in members
            ],
            "baseline_method": {
                "entry_score": "60",
                "point_in_time_inputs": [
                    "regularMarketChangePercent",
                    "fiftyDayAverageChangePercent",
                    "twoHundredDayAverageChangePercent",
                    "regularMarketVolume",
                    "trailingPE",
                    "priceToBook",
                ],
                "price_weights": {
                    "one_month_return": "1.2",
                    "three_month_return": "0.35",
                    "one_day_return": "0.25",
                },
                "composite_weights": {
                    "price_momentum": "0.65",
                    "valuation": "0.15",
                    "liquidity": "0.12",
                    "sentiment": "0.08",
                },
                "fallback_scores": {
                    "valuation": "45",
                    "liquidity_with_regular_market_volume": "60",
                    "sentiment": "50",
                },
            },
            "rejection_counts": {"technical_or_evidence": 99},
            "promotion_state": "simulation_only",
            "promotion_reason": "완료 일봉과 다음 정규장 시가의 모델 replay만 제공합니다. 실제 주문은 비활성입니다.",
        },
        "items": [
            {
                "code": "NVDA",
                "name": "NVIDIA",
                "data_state": "ready",
                "strategy_version": lifecycle.US_STRATEGY_VERSION,
                "rollout_mode": lifecycle.US_ROLLOUT_MODE,
                "execution_enabled": False,
                "stateful_lifecycle_replay_enabled": lifecycle.US_STATEFUL_LIFECYCLE_REPLAY_ENABLED,
                "reentry_runtime_enabled": lifecycle.US_REENTRY_RUNTIME_ENABLED,
                "lifecycle_replay_version": lifecycle.US_LIFECYCLE_REPLAY_VERSION,
                "side": "buy",
                "currency": "USD",
                "market_cap_rank": 1,
                "status": "preliminary",
                "is_preliminary": True,
                "signal": "예비 매수",
                "signal_date": session_date,
                "signal_at": datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
                "price_through": session_date.isoformat(),
                "market": "NASDAQ",
                "signal_scope": "market",
                "universe_tier": "core",
                "is_current_universe_member": True,
                "flow_semantics": "dollar_volume_participation_proxy",
                "public_reasons": [
                    {
                        "key": "trend_20d",
                        "label": "20일 가격",
                        "state": "positive",
                        "summary": "20일 흐름이 우호적입니다.",
                        "as_of": datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
                        "available": True,
                    },
                    {
                        "key": "trend_60d",
                        "label": "60일 가격",
                        "state": "positive",
                        "summary": "60일 흐름이 우호적입니다.",
                        "as_of": datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
                        "available": True,
                    },
                    {
                        "key": "flow",
                        "label": "거래대금 참여도",
                        "state": "positive",
                        "summary": "거래대금 참여도가 우호적입니다.",
                        "as_of": datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
                        "available": True,
                        "note": lifecycle.US_DOLLAR_VOLUME_NOTICE,
                    },
                ],
                "score": "70",
                "entry_score_threshold": "65",
                "entry_setup": "trend_continuation",
                "chase_veto": None,
                "price": "100",
                "guard_state": "clear",
                "us_evidence": {
                    "quality_state": "ready",
                    "allowed": True,
                    "available_count": 4,
                    "supportive_count": 4,
                    "market_regime": {
                        "state": "risk_on",
                        "score": "100",
                        "supportive": True,
                    },
                    "relative_strength_20d": "0.00",
                    "stock_sector_relative_strength_20d": "0.00",
                    "market_relative_supportive": True,
                    "sector_relative_supportive": True,
                    "stock_dollar_volume_participation": "1.00",
                    "stock_accumulation_pressure": "0.00",
                    "sector_dollar_volume_participation": "1.00",
                    "sector_market_relative_strength_20d": "0.00",
                    "sector_etf": "XLK",
                },
                "events": [],
                "current": {
                    "action": "entry_pending",
                    "label": "예비 매수",
                    "position_open": False,
                    "model_exposure_percent": 0,
                    "live_observation": False,
                    "score": "70",
                    "price": "100",
                    "next_confirmation": "next close",
                    "lifecycle": {
                        "state": "entry_pending",
                        "label": "예비 매수",
                        "latest_transition": {
                            "side": "buy",
                            "signal_date": session_date,
                            "transition_date": session_date,
                        },
                    },
                },
            }
        ],
    }


def test_canonical_snapshot_round_trip_and_stale_state_blocks_entries(
    snapshot_db,
    monkeypatch,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )
    stored = lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )

    loaded = lifecycle.load_us_position_lifecycle_snapshot(
        snapshot_db,
        now=generated_at,
    )

    assert loaded is not None
    assert loaded["snapshot_id"] == stored["snapshot_id"]
    assert loaded["snapshot_checksum"] == stored["snapshot_checksum"]
    assert loaded["coverage"]["complete"] is True
    assert loaded["items"][0]["current"]["action"] == "entry_pending"

    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 9),
    )
    stale = lifecycle.load_us_position_lifecycle_snapshot(
        snapshot_db,
        now=datetime(2026, 9, 9, 21, 0, tzinfo=UTC),
    )

    assert stale is not None
    assert stale["status"] == "degraded"
    assert stale["data_state"] == "stale"
    assert stale["new_entries_allowed"] is False
    assert stale["entry_pending_count"] == 0
    assert stale["items"][0]["current"]["action"] == "entry_watch"


def test_canonical_snapshot_waits_for_provider_grace_after_official_close():
    before_time = datetime(2026, 9, 8, 20, 14, 59, tzinfo=UTC)
    at_time = datetime(2026, 9, 8, 20, 15, tzinfo=UTC)
    before_payload = _complete_feed()
    before_payload["as_of"] = before_time
    at_payload = _complete_feed()
    at_payload["as_of"] = at_time

    before = lifecycle.canonical_us_position_lifecycle_snapshot(
        before_payload,
        generated_at=before_time,
    )
    at_grace = lifecycle.canonical_us_position_lifecycle_snapshot(
        at_payload,
        generated_at=at_time,
    )

    assert before["status"] == "degraded"
    assert before["new_entries_allowed"] is False
    assert before["entry_pending_count"] == 0
    assert at_grace["status"] == "ready"
    assert at_grace["new_entries_allowed"] is True


def test_canonical_snapshot_keeps_model_holdings_when_raw_candidates_are_pending():
    """A next-open model fill must not invalidate its complete Top100 scan."""

    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    payload = _complete_feed()
    item = payload["items"][0]
    assert isinstance(item, dict)
    item.update(
        {
            "side": "buy",
            "status": "confirmed",
            "is_preliminary": False,
            "signal": "전략 보유",
            "events": [{"side": "buy", "execution_date": date(2026, 9, 8)}],
        }
    )
    current = item["current"]
    assert isinstance(current, dict)
    current.update(
        {
            "action": "holding",
            "label": "전략 보유",
            "position_open": True,
            "model_exposure_percent": 100,
            "live_observation": False,
            "as_of": datetime(2026, 9, 8, 20, 0, tzinfo=UTC),
            "entry_date": date(2026, 9, 8),
            "entry_price": "100",
            "stop_reference": "95",
        }
    )
    lifecycle_state = current["lifecycle"]
    assert isinstance(lifecycle_state, dict)
    lifecycle_state.update(
        {
            "state": "holding",
            "label": "전략 보유",
            "latest_transition": {"label": "전략 보유"},
        }
    )
    payload["confirmed_count"] = 1
    payload["preliminary_count"] = 0
    payload["entry_pending_count"] = 0
    shadow = payload["shadow_comparison"]
    assert isinstance(shadow, dict)
    shadow["displayed_entry_pending_count"] = 0

    canonical = lifecycle.canonical_us_position_lifecycle_snapshot(
        payload,
        generated_at=generated_at,
    )

    assert canonical["status"] == "ready"
    assert canonical["data_state"] == "ready"
    assert canonical["confirmed_count"] == 1
    assert canonical["entry_pending_count"] == 0
    assert canonical["shadow_comparison"]["candidate_entry_pending_count"] == 1
    assert canonical["shadow_comparison"]["displayed_entry_pending_count"] == 0


def test_future_dated_snapshot_is_blocked_and_refresh_is_due(
    snapshot_db,
    monkeypatch,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 7),
    )

    loaded = lifecycle.load_us_position_lifecycle_snapshot(
        snapshot_db,
        now=generated_at,
    )

    assert loaded is not None
    assert loaded["status"] == "degraded"
    assert loaded["data_state"] == "stale"
    assert loaded["new_entries_allowed"] is False
    assert loaded["entry_pending_count"] == 0
    assert loaded["items"][0]["current"]["action"] == "entry_watch"
    assert lifecycle.us_position_lifecycle_refresh_due(loaded, now=generated_at) is True


def test_legacy_snapshot_requires_one_time_public_member_evidence_upgrade() -> None:
    legacy = {
        "status": "ready",
        "data_state": "ready",
        "universe_count": lifecycle.US_SIGNAL_UNIVERSE_LIMIT,
        "universe_members": [
            {"code": f"A{index:03d}"}
            for index in range(lifecycle.US_SIGNAL_UNIVERSE_LIMIT)
        ],
        "items": [],
    }
    upgraded = {
        **legacy,
        "public_member_signals": [
            {"code": f"A{index:03d}"}
            for index in range(lifecycle.US_SIGNAL_UNIVERSE_LIMIT)
        ],
    }

    assert lifecycle.us_position_lifecycle_schema_upgrade_due(legacy) is True
    assert lifecycle.us_position_lifecycle_schema_upgrade_due(upgraded) is False
    assert (
        lifecycle.us_position_lifecycle_schema_upgrade_due(
            {"status": "preparing", "data_state": "preparing"}
        )
        is False
    )


@pytest.mark.parametrize(
    ("mutation", "value"),
    [
        ("top_level_coverage", 99),
        ("nested_coverage", 99),
        ("status", "degraded"),
        ("execution_enabled", True),
        ("entry_pending_count", 999),
        ("preliminary_count", 999),
        ("policy", False),
        ("coverage_percent", 99.0),
        ("sector_classification_error_count", 1),
        ("coverage_sector_classification_error_count", 1),
        ("stateful_lifecycle_replay_enabled", False),
        ("reentry_runtime_enabled", False),
        pytest.param("item_currency", "KRW", id="item_currency-KRW"),
        pytest.param("item_rank", 101, id="item_rank-101"),
        pytest.param("item_position", True, id="item_position-true"),
        pytest.param("item_exposure", 100, id="item_exposure-100"),
        pytest.param("item_status", "confirmed", id="item_status-confirmed"),
        pytest.param("item_action", "holding", id="item_action-holding"),
        pytest.param("item_events", [{"side": "buy"}], id="item_events-nonempty"),
        pytest.param("item_signal_date", "2026-09-09", id="item_signal_date-future"),
        pytest.param(
            "item_signal_at",
            "2026-09-09T20:00:00+00:00",
            id="item_signal_at-wrong-session",
        ),
        pytest.param(
            "item_price_through", "2026-09-09", id="item_price_through-future"
        ),
        pytest.param("item_market", "CRYPTO", id="item_market-crypto"),
        pytest.param("item_member", False, id="item_member-false"),
        pytest.param("item_guard", "blocked", id="item_guard-blocked"),
        pytest.param("item_entry_setup", None, id="item_entry_setup-none"),
        pytest.param(
            "item_evidence_allowed", False, id="item_evidence_allowed-false"
        ),
        pytest.param("item_regime_state", "risk_off", id="item_regime_state-risk-off"),
        pytest.param(
            "item_flow_semantics", "investor_net_buy", id="item_flow_semantics-wrong"
        ),
        pytest.param("item_sector_etf", "XLF", id="item_sector_etf-cik-mismatch"),
        pytest.param("item_public_reasons", [], id="item_public_reasons-missing"),
        pytest.param(
            "item_public_reason_available",
            False,
            id="item_public_reason_available-false",
        ),
        pytest.param("item_score", 101, id="item_score-out-of-range"),
        pytest.param(
            "temporal_metadata",
            "2099-01-01T00:00:00+00:00",
            id="temporal_metadata-future",
        ),
        pytest.param("universe_checksum", "", id="universe_checksum-empty"),
        pytest.param(
            "shadow_comparison_complete", False, id="shadow_comparison-incomplete"
        ),
    ],
)
def test_structurally_incomplete_snapshot_is_rejected_even_with_valid_checksum(
    snapshot_db,
    monkeypatch,
    mutation,
    value,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    row = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )
    assert row is not None
    payload = json.loads(row.payload)
    if mutation == "top_level_coverage":
        payload["data_coverage_count"] = value
    elif mutation == "nested_coverage":
        payload["coverage"]["data_coverage_count"] = value
    elif mutation == "policy":
        payload["universe_policy"]["new_entries_allowed"] = value
    elif mutation == "coverage_percent":
        payload["coverage"]["coverage_percent"] = value
    elif mutation == "coverage_sector_classification_error_count":
        payload["coverage"]["sector_classification_error_count"] = value
    elif mutation == "item_currency":
        payload["items"][0]["currency"] = value
    elif mutation == "item_rank":
        payload["items"][0]["market_cap_rank"] = value
    elif mutation == "item_position":
        payload["items"][0]["current"]["position_open"] = value
    elif mutation == "item_exposure":
        payload["items"][0]["current"]["model_exposure_percent"] = value
    elif mutation == "item_status":
        payload["items"][0]["status"] = value
    elif mutation == "item_action":
        payload["items"][0]["current"]["action"] = value
        payload["items"][0]["current"]["lifecycle"]["state"] = value
    elif mutation == "item_events":
        payload["items"][0]["events"] = value
    elif mutation == "item_signal_date":
        payload["items"][0]["signal_date"] = value
    elif mutation == "item_signal_at":
        payload["items"][0]["signal_at"] = value
    elif mutation == "item_price_through":
        payload["items"][0]["price_through"] = value
    elif mutation == "item_market":
        payload["items"][0]["market"] = value
    elif mutation == "item_member":
        payload["items"][0]["is_current_universe_member"] = value
    elif mutation == "item_guard":
        payload["items"][0]["guard_state"] = value
    elif mutation == "item_entry_setup":
        payload["items"][0]["entry_setup"] = value
    elif mutation == "item_evidence_allowed":
        payload["items"][0]["us_evidence"]["allowed"] = value
    elif mutation == "item_regime_state":
        payload["items"][0]["us_evidence"]["market_regime"]["state"] = value
    elif mutation == "item_flow_semantics":
        payload["items"][0]["flow_semantics"] = value
    elif mutation == "item_sector_etf":
        payload["items"][0]["us_evidence"]["sector_etf"] = value
    elif mutation == "item_public_reasons":
        payload["items"][0]["public_reasons"] = value
    elif mutation == "item_public_reason_available":
        payload["items"][0]["public_reasons"][0]["available"] = value
    elif mutation == "item_score":
        payload["items"][0]["score"] = value
        payload["items"][0]["current"]["score"] = value
    elif mutation == "temporal_metadata":
        payload["as_of"] = value
        payload["snapshot_generated_at"] = value
    elif mutation == "shadow_comparison_complete":
        payload["shadow_comparison"]["comparison_complete"] = value
    else:
        payload[mutation] = value
    checksum = lifecycle._snapshot_member_checksum(payload)
    payload["snapshot_checksum"] = checksum
    payload["snapshot_id"] = (
        f"{lifecycle.US_STRATEGY_VERSION}:2026-09-08:{checksum[:16]}"
    )
    row.payload = json.dumps(payload)
    snapshot_db.commit()
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )

    loaded = lifecycle.load_us_position_lifecycle_snapshot(
        snapshot_db,
        now=generated_at,
    )

    assert loaded is None


def test_snapshot_identity_must_match_strategy_date_and_checksum(
    snapshot_db,
    monkeypatch,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    row = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )
    assert row is not None
    payload = json.loads(row.payload)
    payload["snapshot_id"] = "position-lifecycle-us-v1-rc1:2026-09-07:wrong"
    row.payload = json.dumps(payload)
    snapshot_db.commit()
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )

    assert (
        lifecycle.load_us_position_lifecycle_snapshot(
            snapshot_db,
            now=generated_at,
        )
        is None
    )


def test_failed_refresh_keeps_last_good_snapshot_and_blocks_returned_entries(
    snapshot_db,
    monkeypatch,
    caplog,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )
    stored = lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    monkeypatch.setattr(
        lifecycle,
        "build_us_position_lifecycle_feed",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("provider outage")),
    )

    returned = lifecycle.refresh_us_position_lifecycle_snapshot(
        snapshot_db,
        now=generated_at,
    )
    persisted = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )

    assert persisted is not None
    assert json.loads(persisted.payload)["snapshot_id"] == stored["snapshot_id"]
    assert returned["snapshot_id"] == stored["snapshot_id"]
    assert returned["data_state"] == "degraded"
    assert returned["entry_pending_count"] == 0
    assert returned["items"][0]["current"]["action"] == "entry_watch"
    assert "refresh failed before publication" in caplog.text


def test_incomplete_refresh_never_overwrites_last_good(
    snapshot_db,
    monkeypatch,
    caplog,
):
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )
    stored = lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    incomplete = _complete_feed()
    incomplete["data_coverage_count"] = 99
    incomplete["history_error_count"] = 1
    monkeypatch.setattr(
        lifecycle,
        "build_us_position_lifecycle_feed",
        lambda **_kwargs: incomplete,
    )

    returned = lifecycle.refresh_us_position_lifecycle_snapshot(
        snapshot_db,
        now=generated_at,
    )

    assert returned["snapshot_id"] == stored["snapshot_id"]
    persisted = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )
    assert persisted is not None
    assert json.loads(persisted.payload)["snapshot_id"] == stored["snapshot_id"]
    assert "refresh produced degraded data" in caplog.text
    assert "history_error_count=1" in caplog.text


def test_invalid_ready_save_never_overwrites_last_good(snapshot_db) -> None:
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    stored = lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=generated_at,
    )
    invalid = _complete_feed()
    invalid["execution_enabled"] = True
    invalid["items"][0]["current"]["position_open"] = True

    with pytest.raises(ValueError, match="Refusing to replace"):
        lifecycle.save_us_position_lifecycle_snapshot(
            snapshot_db,
            invalid,
            generated_at=generated_at,
        )

    persisted = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )
    assert persisted is not None
    assert json.loads(persisted.payload)["snapshot_id"] == stored["snapshot_id"]


def test_older_worker_cannot_overwrite_newer_canonical_snapshot(snapshot_db) -> None:
    older_time = datetime(2026, 9, 8, 20, 30, tzinfo=UTC)
    newer_time = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    newer = lifecycle.save_us_position_lifecycle_snapshot(
        snapshot_db,
        _complete_feed(),
        generated_at=newer_time,
    )

    older_feed = _complete_feed()
    older_feed["as_of"] = older_time
    with pytest.raises(ValueError, match="newer US signal snapshot"):
        lifecycle.save_us_position_lifecycle_snapshot(
            snapshot_db,
            older_feed,
            generated_at=older_time,
        )

    snapshot_db.rollback()
    persisted = snapshot_db.get(
        MarketQuantSignalSnapshot,
        lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
    )
    assert persisted is not None
    assert persisted.generated_at == newer_time.replace(tzinfo=None)
    assert json.loads(persisted.payload)["snapshot_id"] == newer["snapshot_id"]


def test_truncated_candidate_projection_is_not_publishable(snapshot_db) -> None:
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    truncated = _complete_feed()
    truncated["shadow_comparison"]["candidate_preliminary_count"] = 100

    with pytest.raises(ValueError, match="Refusing to replace"):
        lifecycle.save_us_position_lifecycle_snapshot(
            snapshot_db,
            truncated,
            generated_at=generated_at,
        )

    assert (
        snapshot_db.get(
            MarketQuantSignalSnapshot,
            lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
        )
        is None
    )


def test_lifecycle_snapshot_must_match_immutable_universe_row(snapshot_db) -> None:
    generated_at = datetime(2026, 9, 8, 21, 0, tzinfo=UTC)
    tampered = deepcopy(_complete_feed())
    tampered["universe_members"][0]["market_cap"] = "300000000000"
    tampered_checksum = universe._snapshot_checksum(tampered["universe_members"])
    tampered["universe_checksum"] = tampered_checksum
    tampered["shadow_comparison"]["universe_checksum"] = tampered_checksum

    with pytest.raises(ValueError, match="Refusing to replace"):
        lifecycle.save_us_position_lifecycle_snapshot(
            snapshot_db,
            tampered,
            generated_at=generated_at,
        )

    assert (
        snapshot_db.get(
            MarketQuantSignalSnapshot,
            lifecycle.US_POSITION_LIFECYCLE_SNAPSHOT_KEY,
        )
        is None
    )


def test_snapshot_save_rolls_back_on_commit_failure(monkeypatch):
    class BrokenSession:
        def __init__(self):
            self.rollback_count = 0

        def get(self, *_args):
            return None

        def add(self, _value):
            return None

        def commit(self):
            raise RuntimeError("database unavailable")

        def rollback(self):
            self.rollback_count += 1

    db = BrokenSession()
    monkeypatch.setattr(
        lifecycle,
        "_authoritative_universe_matches",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        lifecycle,
        "expected_completed_us_session_date",
        lambda _now=None: date(2026, 9, 8),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        lifecycle.save_us_position_lifecycle_snapshot(
            db,
            _complete_feed(),
            generated_at=datetime(2026, 9, 8, 21, 0, tzinfo=UTC),
        )

    assert db.rollback_count == 1
