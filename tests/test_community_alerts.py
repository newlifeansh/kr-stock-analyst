from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base
from app.models import PushSubscription, PushDelivery
from app.services import community_alerts as ca, web_push

NOW = datetime(2026, 10, 2, 14, 30, tzinfo=timezone.utc)
STOCK = {"code": "NVDA", "name": "NVIDIA", "market": "NASDAQ"}


def selected(now=NOW):
    return {"stock": STOCK, "ranking_as_of": "2026-10-01", "post": {
        "title": "오늘 인기글", "url": "https://m.stock.naver.com/worldstock/stock/NVDA.O/discussion/123",
        "created_at": (now-timedelta(hours=1)).isoformat(), "likes": 10, "views": 100, "replies": 1}}


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield sessionmaker(engine)
    engine.dispose()


def config(mode="alerts", market="us", **kwargs):
    return Settings(_env_file=None, community_popular_mode=mode, us_market_enabled=market == "us",
                    web_push_enabled=True, web_push_vapid_private_key="fixture-private",
                    web_push_vapid_public_key="fixture-public", **kwargs)


def subscribe(db, key, market="us", **kwargs):
    values = dict(share_id=("us." if market == "us" else "kr.")+key,
                  endpoint="https://push.example/"+key, p256dh="fixture", auth="fixture",
                  created_at=(NOW-timedelta(days=1)).replace(tzinfo=None),
                  updated_at=(NOW-timedelta(days=1)).replace(tzinfo=None))
    if hasattr(PushSubscription, "market_scope"):
        values["market_scope"] = market
    sub = PushSubscription(**(values | kwargs))
    db.add(sub)
    db.commit()
    return sub


def test_community_schedule_and_one_shot_expiry():
    assert ca.window("us", NOW)
    assert ca.window("kr", NOW) is None
    assert ca.window("kr", NOW.replace(hour=3, minute=0))
    assert ca.window("us", NOW-timedelta(seconds=1)) is None
    assert ca.window("us", NOW+timedelta(minutes=5)) is None
    immediate = NOW.replace(hour=11)
    assert ca.window("us", immediate, immediate.isoformat())
    assert ca.window("us", immediate+timedelta(minutes=5), immediate.isoformat()) is None
    assert ca.window("kr", immediate, immediate.isoformat()) is None
    # Fixed KST wall clock, including DST transitions, weekends and midnight.
    assert ca.window("us", NOW.replace(month=11, day=1))
    assert ca.window("us", NOW.replace(hour=15, minute=0), NOW.isoformat()) is None
    with pytest.raises(ValueError):
        config(community_popular_immediate_at="2026-10-02T11:00:00")


def test_community_today_post_and_safe_original_url():
    base = {"title": "Hello", "url": selected()["post"]["url"], "created_at": NOW-timedelta(hours=1)}
    def feed(items):
        return {"providers": [{"key": "naver_board", "configured": True, "items": items}]}
    best = ca.select_post(feed([base | {"like_count": 1}, base | {"title": "Best", "like_count": 5}]), STOCK, "us", NOW)
    assert best["title"] == "Best"
    for changed in [
        {"created_at": NOW-timedelta(days=1)}, {"created_at": NOW+timedelta(seconds=1)},
        {"url": "https://evil.example/NVDA.O/discussion/123"},
        {"url": base["url"].replace("NVDA.O", "MSFT.O")}, {"url": "javascript:alert(1)"},
        {"url": base["url"]+"?redirect=evil"}, {"created_at": None}, {"title": " "},
    ]:
        with pytest.raises(ValueError):
            ca.select_post(feed([base | changed]), STOCK, "us", NOW)
    domestic = base | {"url": "https://m.stock.naver.com/domestic/stock/005930/discussion/123"}
    assert ca.select_post(feed([domestic]), {"code": "005930"}, "kr", NOW)["title"] == "Hello"


def test_community_off_shadow_restart_and_blocked_source(factory, monkeypatch):
    calls = []
    monkeypatch.setattr(ca, "prepare", lambda *args: calls.append("source") or selected())
    push = SimpleNamespace(configured=True, _send=lambda *args: calls.append("send"))
    ca.CommunityAlertRuntime(config("off"), push, factory).run_once(NOW)
    assert calls == []
    ca.CommunityAlertRuntime(config("alerts"), push, factory).run_once(NOW-timedelta(hours=1))
    assert calls == []
    ca.CommunityAlertRuntime(config("shadow"), push, factory).run_once(NOW)
    ca.CommunityAlertRuntime(config("shadow"), push, factory).run_once(NOW)
    assert calls == ["source"]
    with factory() as db:
        state = ca.status(db, config("shadow"), NOW)
        assert state["state"] == "preview" and not state["delivery_counts"]
    def fail(*args):
        raise ValueError("private token should never leak")
    monkeypatch.setattr(ca, "prepare", fail)
    ca.CommunityAlertRuntime(config("alerts"), push, factory).run_once(NOW)
    with factory() as db:
        state = ca.status(db, config(), NOW)
        assert state["state"] == "blocked"
        assert "private" not in json.dumps(state)
        assert not list(db.scalars(select(PushDelivery)))


def test_community_broadcast_scope_all_enabled_and_durable_dedup(factory, monkeypatch):
    monkeypatch.setattr(ca, "prepare", lambda *args: selected())
    accepted = []
    monkeypatch.setattr(web_push, "webpush", lambda **kwargs: accepted.append(kwargs))
    with factory() as db:
        subscribe(db, "enabled", notification_preferences="[]")
        subscribe(db, "other", market="kr")
        subscribe(db, "disabled", enabled=False)
        subscribe(db, "future", created_at=(NOW+timedelta(seconds=1)).replace(tzinfo=None))
        subscribe(db, "changed", updated_at=(NOW+timedelta(seconds=1)).replace(tzinfo=None))
    runtime = ca.CommunityAlertRuntime(config(), web_push.WebPushRuntime(config()), factory)
    runtime.run_once(NOW)
    assert len(accepted) == 1
    assert accepted[0]["ttl"] == 300
    assert json.loads(accepted[0]["data"])["kind"] == "community_popular"
    # Restart + changed ranking/post still keeps immutable daily payload.
    monkeypatch.setattr(ca, "prepare", lambda *args: pytest.fail("outbox must not change"))
    ca.CommunityAlertRuntime(config(), runtime.push, factory).run_once(NOW+timedelta(seconds=30))
    assert len(accepted) == 1
    with factory() as db:
        state = ca.status(db, config(), NOW)
        assert state["delivery_counts"] == {"sent": 1}
        assert "endpoint" not in json.dumps(state)


def test_community_bounded_retry_and_unsubscribe(factory, monkeypatch):
    monkeypatch.setattr(ca, "prepare", lambda *args: selected())
    attempts = []
    def fail(**kwargs):
        attempts.append(1)
        raise web_push.WebPushException("fixture failure")
    monkeypatch.setattr(web_push, "webpush", fail)
    with factory() as db:
        sub = subscribe(db, "retry")
        sub_id = sub.id
    runtime = ca.CommunityAlertRuntime(config(), web_push.WebPushRuntime(config()), factory)
    for _ in range(4):
        runtime.run_once(NOW)
    assert len(attempts) == 3
    with factory() as db:
        db.get(PushSubscription, sub_id).enabled = False
        db.commit()
    runtime.run_once(NOW)
    assert len(attempts) == 3


def test_community_rank_one_uses_completed_snapshot(factory, monkeypatch):
    from app.services import intraday_monitor, community_feed
    members = [dict(STOCK, market_cap_rank=2), dict(STOCK, code="MSFT", name="Microsoft", market_cap_rank=1)]
    observed = []
    monkeypatch.setattr(intraday_monitor, "universe", lambda db, market, date: observed.append(date.isoformat()) or members)
    monkeypatch.setattr(community_feed, "build_us_stock_community_feed", lambda stock, **kwargs: stock)
    monkeypatch.setattr(ca, "select_post", lambda feed, stock, *args: {"title": stock["code"]})
    with factory() as db:
        result = ca.prepare(db, config(), "us", NOW)
        assert result["stock"]["code"] == "MSFT" and observed == ["2026-10-01"]
        members[1]["market_cap_rank"] = 2
        with pytest.raises(ValueError):
            ca.prepare(db, config(), "us", NOW)


def test_community_http_read_only_market_isolation(factory, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    def database():
        with factory() as db:
            yield db
    main.app.dependency_overrides[main.get_db] = database
    monkeypatch.setattr(main.settings, "us_market_enabled", False)
    monkeypatch.setattr(main.settings, "community_popular_mode", "off")
    try:
        client = TestClient(main.app)
        response = client.get("/market/community-alerts")
        assert response.status_code == 200 and response.json()["state"] == "off"
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/us/market/community-alerts").status_code == 404
        assert client.post("/market/community-alerts").status_code == 405
    finally:
        main.app.dependency_overrides.clear()


def test_community_worker_opens_original_post():
    import subprocess
    from pathlib import Path
    from scripts.qa_community_alerts import WORKER_PROBE
    # Node supplies a JS realm without any browser permissions or network.
    files = [Path("app/static/dashboard/dashboard-sw.js")]
    us = Path("app/static/nasdaq/dashboard-sw.js")
    if 'self.addEventListener("push"' in us.read_text():
        files.append(us)
    for file in files:
        args = {"source": file.read_text(), "url": selected()["post"]["url"], "origin": "https://app.example"}
        result = subprocess.run(["node", "-e", f"({WORKER_PROBE})({json.dumps(args)}).catch(e=>{{console.error(e);process.exit(1)}})"], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr


def test_community_staging_never_sends():
    from pathlib import Path
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text()
    job = workflow.split("  intraday_shadow_staging:", 1)[1].split("  validate_request:", 1)[0]
    assert "COMMUNITY_POPULAR_MODE=shadow" in job
    assert "COMMUNITY_POPULAR_MODE=alerts" not in job
    assert "--environment production" not in job
    assert "community-us-prerequisite.json" in job
    assert "community-e2e.json" in job
