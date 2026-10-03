from scripts.wait_release_data_ready import dashboard_readiness, us_readiness


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
