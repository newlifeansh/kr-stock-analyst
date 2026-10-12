from app.qa.release_data_readiness import dashboard_readiness, us_readiness


def test_dashboard_readiness_checks_canonical_and_exact_live_scope(monkeypatch):
    from app.qa import release_data_readiness as readiness
    urls = []
    def get(url):
        urls.append(url)
        if "signal-data-quality" in url:
            return {"status":"ready", "datasets":{"news":{"state":"ready"}, "stock_news":{"state":"ready","covered":100,"total":100}}}
        return {"status":"ready", "execution_model":"close-confirmed-intraday-trigger-v1"}
    monkeypatch.setattr(readiness, "_get_json", get)
    result = readiness.wait_for_readiness(surface="dashboard", base_url="https://fixture.test", wait_seconds=1, poll_seconds=1)
    assert result["status"] == "ready"
    assert urls[1].endswith("?universe_limit=150&limit=0&recent_days=30")
    assert urls[2].endswith("?universe_limit=100&limit=100&recent_days=30")
    assert result["evidence"]["top100_live_scope"]["market_signal_status"] == "ready"


def test_dashboard_readiness_requires_current_general_and_complete_stock_news():
    ready, evidence = dashboard_readiness(
        {
            "status": "ready",
            "datasets": {
                "news": {
                    "state": "ready",
                    "latest_published_at": "2026-10-03T09:46:16",
                },
                "stock_news": {
                    "state": "ready",
                    "covered": 100,
                    "total": 100,
                    "api": {"last_success_at": "2026-10-03T00:47:44Z"},
                },
            },
        }
    )

    assert ready is True
    assert evidence["stock_news_covered"] == 100

    stale, _ = dashboard_readiness(
        {
            "status": "ready",
            "datasets": {
                "news": {"state": "ready"},
                "stock_news": {"state": "stale", "covered": 99, "total": 100},
            },
        }
    )
    assert stale is False


def test_dashboard_readiness_waits_for_current_market_signal_snapshot():
    quality = {
        "status": "ready",
        "datasets": {
            "news": {"state": "ready"},
            "stock_news": {
                "state": "ready",
                "covered": 100,
                "total": 100,
            },
        },
    }
    refreshing, evidence = dashboard_readiness(
        quality,
        {
            "status": "refreshing",
            "execution_model": "close-confirmed-intraday-trigger-v1",
        },
    )
    assert refreshing is False
    assert evidence["market_signal_status"] == "refreshing"

    ready, evidence = dashboard_readiness(
        quality,
        {
            "status": "ready",
            "execution_model": "close-confirmed-intraday-trigger-v1",
            "snapshot_generated_at": "2026-10-09T12:40:00+09:00",
        },
    )
    assert ready is True
    assert evidence["market_signal_snapshot_generated_at"] is not None


def test_us_readiness_rejects_schema_upgrade_and_empty_recommendations():
    quant = {
        "status": "ready",
        "data_state": "ready",
        "snapshot_id": "position-lifecycle-us-v2-rc1:2026-10-02:0123456789abcdef",
        "universe_count": 100,
        "evaluated_count": 100,
        "data_coverage_count": 100,
        "schema_upgrade_required": False,
    }
    recommendation = {
        "status": "ready",
        "data_state": "ready",
        "items": [{"code": "RIO"}],
    }

    ready, evidence = us_readiness(quant, recommendation)
    assert ready is True
    assert evidence["recommendation_count"] == 1

    quant["schema_upgrade_required"] = True
    blocked, _ = us_readiness(quant, recommendation)
    assert blocked is False

    quant["schema_upgrade_required"] = False
    empty, _ = us_readiness(quant, {**recommendation, "items": []})
    assert empty is False
