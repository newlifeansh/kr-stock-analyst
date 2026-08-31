import asyncio
import time
from datetime import datetime, timedelta
from threading import Lock

from fastapi import BackgroundTasks, Response
from fastapi.testclient import TestClient

import app.main as main_module


def test_concurrent_clients_share_one_public_quote_fetch(monkeypatch):
    calls = 0
    calls_lock = Lock()
    main_module.live_quote_cache.clear()

    def fake_payload(code):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.03)
        return {
            "type": "quote",
            "code": code,
            "source": "test",
            "quote": {"price": 100_000},
        }

    monkeypatch.setattr(main_module, "_stock_quote_stream_payload", fake_payload)

    async def fetch_for_clients():
        return await asyncio.gather(
            *(
                main_module._stock_quote_stream_payload_async("999999")
                for _ in range(300)
            )
        )

    results = asyncio.run(fetch_for_clients())

    assert calls == 1
    assert len(results) == 300
    assert all(result["code"] == "999999" for result in results)


def test_kis_realtime_selection_never_exceeds_documented_safe_cap(monkeypatch):
    subscribers = {f"{index:06d}": {object()} for index in range(75)}
    popular_code = "000074"
    subscribers[popular_code] = {object() for _ in range(20)}

    monkeypatch.setattr(main_module, "kis_quote_subscribers", subscribers)
    monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"000073"})
    monkeypatch.setattr(main_module.settings, "kis_realtime_max_codes", 100)
    monkeypatch.setattr(
        main_module.kis_realtime_provider, "is_configured", lambda: True
    )

    selected = main_module._desired_kis_realtime_codes()

    assert len(selected) == 40
    assert selected <= set(subscribers)
    assert popular_code in selected
    assert "000073" in selected


def test_kis_realtime_session_stays_warm_then_closes_after_idle_grace(monkeypatch):
    async def exercise():
        stop = asyncio.Event()

        async def fake_hub():
            await stop.wait()

        monkeypatch.setattr(main_module, "kis_quote_lock", asyncio.Lock())
        monkeypatch.setattr(main_module, "kis_realtime_control_queue", asyncio.Queue())
        monkeypatch.setattr(main_module, "kis_quote_subscribers", {})
        monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"005930"})
        monkeypatch.setattr(main_module, "kis_realtime_idle_disconnect_task", None)
        monkeypatch.setattr(main_module, "quote_fallback_poll_task", None)
        monkeypatch.setattr(main_module.settings, "kis_realtime_idle_grace_seconds", 0.01)
        monkeypatch.setattr(
            main_module.kis_realtime_provider,
            "is_configured",
            lambda: True,
        )
        hub_task = asyncio.create_task(fake_hub())
        monkeypatch.setattr(main_module, "kis_realtime_hub_task", hub_task)

        await main_module._sync_kis_realtime_codes_locked()
        retained_codes = set(main_module.kis_realtime_active_codes)
        idle_task = main_module.kis_realtime_idle_disconnect_task
        await asyncio.sleep(0.03)
        await asyncio.sleep(0)

        return retained_codes, idle_task, hub_task

    retained_codes, idle_task, hub_task = asyncio.run(exercise())

    assert retained_codes == {"005930"}
    assert idle_task is not None and idle_task.done()
    assert main_module.kis_realtime_active_codes == set()
    assert hub_task.cancelled()
    assert main_module.kis_realtime_idle_disconnect_task is None


def test_kis_realtime_idle_close_is_cancelled_by_a_new_subscriber(monkeypatch):
    async def exercise():
        stop = asyncio.Event()

        async def wait_forever():
            await stop.wait()

        monkeypatch.setattr(main_module, "kis_quote_lock", asyncio.Lock())
        monkeypatch.setattr(main_module, "kis_realtime_control_queue", asyncio.Queue())
        monkeypatch.setattr(main_module, "kis_quote_subscribers", {})
        monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"005930"})
        monkeypatch.setattr(main_module, "kis_realtime_idle_disconnect_task", None)
        monkeypatch.setattr(main_module, "quote_fallback_poll_task", None)
        monkeypatch.setattr(main_module.settings, "kis_realtime_idle_grace_seconds", 60)
        monkeypatch.setattr(
            main_module.kis_realtime_provider,
            "is_configured",
            lambda: True,
        )
        monkeypatch.setattr(main_module, "_quote_fallback_poll_worker", wait_forever)
        hub_task = asyncio.create_task(wait_forever())
        monkeypatch.setattr(main_module, "kis_realtime_hub_task", hub_task)

        await main_module._sync_kis_realtime_codes_locked()
        idle_task = main_module.kis_realtime_idle_disconnect_task
        main_module.kis_quote_subscribers = {"005930": {object()}}
        await main_module._sync_kis_realtime_codes_locked()
        await asyncio.sleep(0)
        fallback_task = main_module.quote_fallback_poll_task

        hub_still_running = not hub_task.done()
        active_codes = set(main_module.kis_realtime_active_codes)
        if fallback_task and not fallback_task.done():
            fallback_task.cancel()
        hub_task.cancel()
        for task in (fallback_task, hub_task):
            if task is None:
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
        return idle_task, hub_still_running, active_codes

    idle_task, hub_still_running, active_codes = asyncio.run(exercise())

    assert idle_task is not None and idle_task.cancelled()
    assert hub_still_running is True
    assert active_codes == {"005930"}
    assert main_module.kis_realtime_idle_disconnect_task is None


def test_kis_hub_restarts_after_subscriber_arrives_during_idle_close(monkeypatch):
    original_worker = main_module._kis_realtime_hub_worker

    async def exercise():
        approval_wait = asyncio.Event()
        replacement_started = asyncio.Event()

        async def blocked_approval_key():
            await approval_wait.wait()
            return "unused"

        async def replacement_worker():
            replacement_started.set()

        monkeypatch.setattr(main_module, "kis_quote_lock", asyncio.Lock())
        monkeypatch.setattr(
            main_module,
            "kis_quote_subscribers",
            {"005930": {object()}},
        )
        monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"005930"})
        monkeypatch.setattr(
            main_module.kis_realtime_provider,
            "approval_key",
            blocked_approval_key,
        )
        monkeypatch.setattr(
            main_module,
            "_kis_realtime_hub_worker",
            replacement_worker,
        )

        closing_task = asyncio.create_task(original_worker())
        monkeypatch.setattr(main_module, "kis_realtime_hub_task", closing_task)
        await asyncio.sleep(0)
        closing_task.cancel()
        try:
            await closing_task
        except asyncio.CancelledError:
            pass
        await asyncio.wait_for(replacement_started.wait(), timeout=1)
        replacement_task = main_module.kis_realtime_hub_task
        if replacement_task is not None:
            await replacement_task
        return replacement_task

    replacement_task = asyncio.run(exercise())

    assert replacement_task is not None
    assert replacement_task.done()


def test_quote_fanout_only_reaches_clients_subscribed_to_that_public_code(monkeypatch):
    payload = {
        "type": "quote",
        "code": "005930",
        "source": "test",
        "quote": {"price": 100_000},
    }

    async def exercise_fanout():
        queue_a = asyncio.Queue()
        queue_b = asyncio.Queue()
        monkeypatch.setattr(
            main_module,
            "kis_quote_subscribers",
            {
                "005930": {queue_a},
                "000660": {queue_b},
            },
        )
        await main_module._broadcast_kis_quote("005930", payload)
        return queue_a.get_nowait(), queue_b.empty()

    delivered, unrelated_queue_empty = asyncio.run(exercise_fanout())
    assert delivered["code"] == payload["code"]
    assert delivered["quote"] == payload["quote"]
    assert delivered["sequence"] >= 1
    assert delivered["observed_at"]
    assert delivered["published_at"]
    assert unrelated_queue_empty is True


def test_realtime_ticks_are_coalesced_per_code_to_protect_the_event_loop(monkeypatch):
    monkeypatch.setattr(main_module, "kis_quote_last_broadcast_at", {})
    monkeypatch.setattr(main_module, "kis_quote_last_received_at", {})
    monkeypatch.setattr(main_module, "kis_quote_pending_payloads", {})
    monkeypatch.setattr(main_module, "kis_quote_flush_tasks", {})
    monkeypatch.setattr(main_module, "quote_stream_sequences", {})
    monkeypatch.setattr(main_module, "quote_stream_last_observed_at", {})
    monkeypatch.setattr(main_module, "quote_stream_last_published_at", {})
    monkeypatch.setattr(
        main_module.settings, "quote_stream_min_broadcast_interval_ms", 30
    )
    observed = datetime.now(main_module.KST)

    def payload(price, offset_ms):
        return {
            "type": "quote",
            "code": "005930",
            "source": "kis_realtime",
            "as_of": (observed + timedelta(milliseconds=offset_ms)).isoformat(),
            "quote": {"price": price},
        }

    async def broadcast_three_ticks():
        queue = asyncio.Queue()
        monkeypatch.setattr(main_module, "kis_quote_subscribers", {"005930": {queue}})
        await main_module._broadcast_kis_quote("005930", payload(100_000, 0))
        await main_module._broadcast_kis_quote("005930", payload(100_100, 1))
        await main_module._broadcast_kis_quote("005930", payload(100_200, 2))
        await asyncio.sleep(0.05)
        return [queue.get_nowait(), queue.get_nowait()]

    delivered = asyncio.run(broadcast_three_ticks())
    assert [item["quote"]["price"] for item in delivered] == [100_000, 100_200]
    assert delivered[0]["sequence"] < delivered[1]["sequence"]
    assert main_module.kis_quote_pending_payloads == {}


def test_kis_fanout_stamps_once_and_caches_the_exact_published_frame(monkeypatch):
    main_module.live_quote_cache.clear()
    monkeypatch.setattr(main_module, "kis_quote_last_broadcast_at", {})
    monkeypatch.setattr(main_module, "kis_quote_last_received_at", {})
    monkeypatch.setattr(main_module, "kis_quote_pending_payloads", {})
    monkeypatch.setattr(main_module, "kis_quote_flush_tasks", {})
    monkeypatch.setattr(main_module, "quote_stream_sequences", {})
    monkeypatch.setattr(main_module, "quote_stream_last_observed_at", {})
    monkeypatch.setattr(main_module, "quote_stream_last_published_at", {})
    monkeypatch.setattr(
        main_module.settings, "quote_stream_min_broadcast_interval_ms", 0
    )

    async def exercise():
        queue = asyncio.Queue()
        monkeypatch.setattr(main_module, "kis_quote_subscribers", {"005930": {queue}})
        await main_module._broadcast_kis_quote(
            "005930",
            {
                "type": "quote",
                "code": "005930",
                "source": "kis_realtime",
                "as_of": datetime.now(main_module.KST).isoformat(),
                "sequence": 999,
                "quote": {"price": 100_000},
            },
        )
        return queue.get_nowait()

    delivered = asyncio.run(exercise())
    cached = main_module.live_quote_cache.get(("live_quote", "005930"))

    assert delivered["sequence"] == 1
    assert cached["sequence"] == delivered["sequence"]
    assert cached["observed_at"] == delivered["observed_at"]
    assert cached["published_at"] == delivered["published_at"]


def test_quote_stamp_advances_past_lower_or_repeated_supplied_sequences(monkeypatch):
    monkeypatch.setattr(main_module, "quote_stream_sequences", {"005930": 10})
    payload = {
        "type": "quote",
        "code": "005930",
        "as_of": datetime.now(main_module.KST).isoformat(),
        "quote": {"price": 100_000},
    }

    lower = main_module._stamp_quote_payload({**payload, "sequence": 3})
    repeated = main_module._stamp_quote_payload(
        {**payload, "sequence": lower["sequence"]}
    )

    assert lower["sequence"] == 11
    assert repeated["sequence"] == 12


def test_multiplex_websocket_accepts_many_codes_over_one_connection(monkeypatch):
    async def fake_payloads(codes):
        return [
            {
                "type": "quote",
                "code": code,
                "source": "test",
                "quote": {"price": 100_000},
            }
            for code in codes
        ]

    monkeypatch.setattr(main_module, "_quote_payloads_for_codes", fake_payloads)
    monkeypatch.setattr(
        main_module, "_active_stock_quote_codes", lambda codes: set(codes)
    )
    monkeypatch.setattr(
        main_module.kis_realtime_provider, "is_configured", lambda: False
    )
    monkeypatch.setattr(
        main_module.settings, "quote_stream_fallback_poll_seconds", 3600
    )

    with TestClient(main_module.app).websocket_connect("/ws/quotes") as socket:
        assert socket.receive_json()["type"] == "ready"
        revision = socket.receive_json()
        assert revision["type"] == "signal_revision"
        assert isinstance(revision["revision"], int) and revision["revision"] >= 0
        assert revision["initial"] is True
        assert revision["changed_codes"] == []
        socket.send_json({"type": "set", "codes": ["005930", "000660"]})

        messages = [socket.receive_json() for _ in range(3)]

    subscribed = next(
        message for message in messages if message["type"] == "subscribed"
    )
    quotes = [message for message in messages if message["type"] == "quote"]
    assert subscribed["codes"] == ["000660", "005930"]
    assert subscribed["rejected_codes"] == []
    assert {message["code"] for message in quotes} == {"005930", "000660"}
    assert all(message["sequence"] >= 1 for message in quotes)
    assert all(message["observed_at"] and message["published_at"] for message in quotes)


def test_fallback_selection_skips_codes_with_fresh_realtime_ticks(monkeypatch):
    now = 500.0
    monkeypatch.setattr(
        main_module,
        "kis_quote_subscribers",
        {"005930": {object()}, "000660": {object()}, "035420": {object()}},
    )
    monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"005930", "000660"})
    monkeypatch.setattr(
        main_module,
        "kis_quote_last_received_at",
        {"005930": now - 2, "000660": now - 30},
    )
    monkeypatch.setattr(main_module, "quote_fallback_last_polled_at", {})
    monkeypatch.setattr(main_module.settings, "quote_stream_realtime_stale_seconds", 15)
    monkeypatch.setattr(
        main_module.settings, "quote_stream_fallback_max_codes_per_cycle", 2
    )

    assert main_module._select_quote_fallback_codes(now) == ["000660", "035420"]


def test_quote_fanout_suppresses_older_observations(monkeypatch):
    monkeypatch.setattr(main_module, "quote_stream_sequences", {})
    monkeypatch.setattr(main_module, "quote_stream_last_observed_at", {})
    monkeypatch.setattr(main_module, "quote_stream_last_published_at", {})
    observed = datetime.now(main_module.KST)

    async def exercise():
        queue = asyncio.Queue()
        monkeypatch.setattr(
            main_module,
            "kis_quote_subscribers",
            {"005930": {queue}},
        )
        await main_module._broadcast_kis_quote(
            "005930",
            {
                "type": "quote",
                "code": "005930",
                "source": "fallback",
                "as_of": observed.isoformat(),
                "quote": {"price": 100_000},
            },
        )
        await main_module._broadcast_kis_quote(
            "005930",
            {
                "type": "quote",
                "code": "005930",
                "source": "fallback",
                "as_of": (observed - timedelta(seconds=1)).isoformat(),
                "quote": {"price": 99_000},
            },
        )
        return queue.qsize(), queue.get_nowait()

    queue_size, delivered = asyncio.run(exercise())
    assert queue_size == 1
    assert delivered["quote"]["price"] == 100_000


def test_signal_revision_publishes_changed_codes_without_full_payload(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "ai_signal_revision_state",
        {"revision": 0, "as_of": None, "code_signatures": {}},
    )
    monkeypatch.setattr(main_module, "ai_signal_revision_clients", {})
    base = {
        "strategy_version": "test-v1",
        "as_of": "2026-08-31T10:00:00+09:00",
        "items": [
            {
                "code": "005930",
                "side": "buy",
                "status": "confirmed",
                "current": {
                    "action": "holding",
                    "position_open": True,
                    "target_sell_price": 110_000,
                },
                "holding_context": {
                    "return_basis": {"price": 100_000, "return_rate": 1.0}
                },
            }
        ],
    }

    async def exercise():
        queue = asyncio.Queue()
        main_module._register_ai_signal_revision_client(
            queue, asyncio.get_running_loop()
        )
        main_module._record_ai_signal_revision(base, publish=False)
        changed = {
            **base,
            "as_of": "2026-08-31T10:05:00+09:00",
            "items": [
                {
                    **base["items"][0],
                    "current": {
                        **base["items"][0]["current"],
                        "target_sell_price": 111_000,
                    },
                    "holding_context": {
                        "return_basis": {"price": 101_000, "return_rate": 2.0}
                    },
                }
            ],
        }
        main_module._record_ai_signal_revision(changed, publish=True)
        await asyncio.sleep(0)
        main_module._unregister_ai_signal_revision_client(queue)
        return queue.get_nowait()

    frame = asyncio.run(exercise())
    assert frame["type"] == "signal_revision"
    assert isinstance(frame["revision"], int) and frame["revision"] > 0
    assert frame["changed_codes"] == ["005930"]
    assert frame["initial"] is False
    assert "items" not in frame


def test_canonical_signal_response_exposes_the_same_revision_as_the_socket_frame(
    monkeypatch,
):
    snapshot_time = "2026-08-31T10:00:00+09:00"
    payload = {
        "strategy_version": "test-v1",
        "snapshot_generated_at": snapshot_time,
        "as_of": snapshot_time,
        "items": [
            {
                "code": "005930",
                "side": "buy",
                "status": "confirmed",
                "current": {"action": "holding", "position_open": True},
            }
        ],
    }
    monkeypatch.setattr(
        main_module,
        "ai_signal_revision_state",
        {"revision": 0, "as_of": None, "code_signatures": {}},
    )
    monkeypatch.setattr(main_module, "ai_signal_revision_clients", {})
    monkeypatch.setattr(
        main_module, "_enforce_rate_limit", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        main_module.market_quant_signal_cache, "get", lambda _key: payload
    )
    monkeypatch.setattr(
        main_module.market_quant_signal_cache, "set", lambda *_args: None
    )
    monkeypatch.setattr(
        main_module,
        "_market_quant_signal_snapshot_freshness",
        lambda *_args: {"snapshot_state": "fresh"},
    )
    monkeypatch.setattr(
        main_module,
        "apply_market_signal_reconciliations",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        main_module,
        "enrich_market_quant_signal_sectors",
        lambda _db, value: value,
    )
    monkeypatch.setattr(
        main_module,
        "_merge_market_preliminary_notification_history",
        lambda _db, value: value,
    )

    result = main_module.get_market_quant_signals(
        request=object(),
        response=Response(),
        background_tasks=BackgroundTasks(),
        universe_limit=main_module.MARKET_SIGNAL_UNIVERSE_LIMIT,
        limit=0,
        recent_days=30,
        db=object(),
    )
    frame = main_module._current_ai_signal_revision_frame()

    assert result["signal_revision"] == frame["revision"]
    assert result["signal_revision_as_of"] == frame["as_of"] == snapshot_time
    assert result["snapshot_generated_at"] == snapshot_time
    assert result["as_of"] == snapshot_time
    assert result["signal_revision_scope"] == "canonical_market_feed"


def test_nondefault_signal_response_cannot_replace_the_canonical_revision(monkeypatch):
    canonical_state = {
        "revision": 12345,
        "as_of": "2026-08-31T10:00:00+09:00",
        "code_signatures": {"005930": "canonical"},
        "strategy_version": "test-v1",
    }
    monkeypatch.setattr(main_module, "ai_signal_revision_state", canonical_state)
    monkeypatch.setattr(
        main_module, "_enforce_rate_limit", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        main_module.market_quant_signal_cache,
        "get",
        lambda _key: {
            "strategy_version": "test-v1",
            "as_of": "2026-08-31T10:05:00+09:00",
            "items": [{"code": "000660", "side": "sell"}],
        },
    )
    monkeypatch.setattr(
        main_module.market_quant_signal_cache, "set", lambda *_args: None
    )
    monkeypatch.setattr(
        main_module,
        "_market_quant_signal_snapshot_freshness",
        lambda *_args: {"snapshot_state": "fresh"},
    )
    monkeypatch.setattr(
        main_module,
        "apply_market_signal_reconciliations",
        lambda value, **_kwargs: value,
    )
    monkeypatch.setattr(
        main_module,
        "enrich_market_quant_signal_sectors",
        lambda _db, value: value,
    )
    monkeypatch.setattr(
        main_module,
        "_merge_market_preliminary_notification_history",
        lambda _db, value: value,
    )

    result = main_module.get_market_quant_signals(
        request=object(),
        response=Response(),
        background_tasks=BackgroundTasks(),
        universe_limit=20,
        limit=0,
        recent_days=30,
        db=object(),
    )

    assert result["signal_revision"] == 12345
    assert main_module.ai_signal_revision_state == canonical_state


def test_only_default_market_signal_scope_can_publish_the_global_revision():
    assert main_module._is_canonical_market_signal_scope(
        main_module.MARKET_SIGNAL_UNIVERSE_LIMIT,
        0,
        30,
    )
    assert not main_module._is_canonical_market_signal_scope(20, 0, 30)
    assert not main_module._is_canonical_market_signal_scope(
        main_module.MARKET_SIGNAL_UNIVERSE_LIMIT,
        10,
        30,
    )
    assert not main_module._is_canonical_market_signal_scope(
        main_module.MARKET_SIGNAL_UNIVERSE_LIMIT,
        0,
        7,
    )


def test_canonical_refresh_swaps_cache_before_publishing_transformed_revision(
    monkeypatch,
):
    events = []
    stored = {
        "strategy_version": "test-v1",
        "items": [{"code": "005930", "side": "buy"}],
    }
    canonical = {
        **stored,
        "items": [
            {
                **stored["items"][0],
                "current": {"action": "holding", "target_sell_price": 110_000},
            }
        ],
    }

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(main_module, "SessionLocal", FakeSession)
    monkeypatch.setattr(
        main_module, "_repair_market_quant_signal_ohlc", lambda *_args, **_kwargs: 0
    )
    monkeypatch.setattr(
        main_module,
        "_build_market_quant_signal_payload",
        lambda *_args, **_kwargs: stored,
    )
    monkeypatch.setattr(
        main_module,
        "save_market_quant_signal_snapshot",
        lambda *_args, **_kwargs: stored,
    )
    monkeypatch.setattr(
        main_module.market_quant_signal_cache,
        "set",
        lambda *_args, **_kwargs: events.append("cache"),
    )

    def canonicalize(*_args, **_kwargs):
        events.append("canonicalize")
        return canonical

    def record(payload, *, publish):
        assert payload is canonical
        assert publish is True
        events.append("revision")
        return {"revision": 1}

    monkeypatch.setattr(
        main_module, "_canonical_ai_signal_revision_payload", canonicalize
    )
    monkeypatch.setattr(main_module, "_record_ai_signal_revision", record)

    result = main_module._refresh_market_quant_signal_snapshot()

    assert result is stored
    assert events == ["cache", "canonicalize", "revision"]


def test_kis_recovery_status_only_reaches_realtime_codes(monkeypatch):
    async def exercise():
        realtime_queue = asyncio.Queue()
        fallback_queue = asyncio.Queue()
        monkeypatch.setattr(
            main_module,
            "kis_quote_subscribers",
            {"005930": {realtime_queue}, "000660": {fallback_queue}},
        )
        monkeypatch.setattr(main_module, "kis_realtime_active_codes", {"005930"})
        monkeypatch.setattr(
            main_module, "kis_quote_last_received_at", {"005930": 500.0}
        )
        await main_module._broadcast_kis_status_to_active(
            "fallback",
            "KIS realtime unavailable",
        )
        fallback = realtime_queue.get_nowait()
        status, message = main_module._kis_connection_ready_status(1)
        await main_module._broadcast_kis_status_to_active(status, message)
        return fallback, realtime_queue.get_nowait(), fallback_queue.empty()

    fallback, delivered, fallback_empty = asyncio.run(exercise())

    assert fallback["status"] == "fallback"
    assert "005930" not in main_module.kis_quote_last_received_at
    assert delivered == {
        "type": "status",
        "code": "005930",
        "source": "kis_realtime",
        "status": "recovered",
        "message": "KIS realtime recovered",
    }
    assert fallback_empty is True
    assert main_module._kis_connection_ready_status(0)[0] == "connected"


def test_multiplex_rejects_inactive_codes_and_throttles_command_bursts(monkeypatch):
    monkeypatch.setattr(main_module, "_active_stock_quote_codes", lambda codes: set())
    monkeypatch.setattr(main_module.settings, "quote_stream_max_commands_per_window", 1)
    monkeypatch.setattr(main_module.settings, "quote_stream_command_window_seconds", 60)

    with TestClient(main_module.app).websocket_connect("/ws/quotes") as socket:
        assert socket.receive_json()["type"] == "ready"
        assert socket.receive_json()["type"] == "signal_revision"
        socket.send_json({"type": "set", "codes": ["999999"]})
        subscribed = socket.receive_json()
        assert subscribed == {
            "type": "subscribed",
            "codes": [],
            "count": 0,
            "rejected_codes": ["999999"],
        }
        socket.send_json({"type": "set", "codes": []})
        limited = socket.receive_json()

    assert limited["type"] == "error"
    assert limited["code"] == "subscription_rate_limited"
    assert limited["retry_after_ms"] > 0


def test_quote_code_limit_rejects_oversized_client_subscription(monkeypatch):
    monkeypatch.setattr(main_module.settings, "quote_stream_max_codes_per_client", 2)

    try:
        main_module._normalize_quote_code_list(["005930", "000660", "035420"])
    except ValueError as exc:
        assert "at most 2" in str(exc)
    else:
        raise AssertionError("Oversized quote subscription was accepted")
