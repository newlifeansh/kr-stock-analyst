from __future__ import annotations

from pathlib import Path

from app.qa.release_parity import (
    compare_release_contracts,
    local_release_contract,
)


def test_local_release_contract_tracks_all_versioned_frontend_assets() -> None:
    contract = local_release_contract()

    assert contract["dashboard_version"] == "20260901v459"
    assert len(contract["assets"]) == 8
    assert all("?v=" in asset for asset in contract["assets"])
    assert any("contextual-safe-area-v128" in asset for asset in contract["assets"])


def test_release_parity_rejects_a_stale_staging_asset() -> None:
    expected = {
        "dashboard_version": "v2",
        "assets": ["/dashboard-app.js?v=v2"],
    }
    targets = {
        "staging": {
            "dashboard_version": "v1",
            "assets": ["/dashboard-app.js?v=v1"],
        },
        "production": {
            "dashboard_version": "v2",
            "assets": ["/dashboard-app.js?v=v2"],
        },
    }

    failures = compare_release_contracts(expected, targets)
    contracts = {(item["target"], item["contract"]) for item in failures}

    assert ("staging", "dashboard_version") in contracts
    assert ("staging", "frontend_assets") in contracts
    assert ("staging-production", "same_dashboard_version") in contracts
    assert ("staging-production", "same_frontend_assets") in contracts


def test_deployment_workflow_enforces_staging_before_production() -> None:
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text(
        encoding="utf-8"
    )

    assert "deploy_staging:\n    needs: gate" in workflow
    assert "staging_qa:\n    needs: deploy_staging" in workflow
    assert "deploy_production:\n    needs: staging_qa" in workflow
    assert "verify_production:\n    needs: deploy_production" in workflow
    assert workflow.count("ref: ${{ github.sha }}") == 5
    assert "--environment staging" in workflow
    assert "--environment production" in workflow
    assert '--project "$STAGING_RAILWAY_PROJECT_ID"' in workflow
    assert '--service "$STAGING_RAILWAY_SERVICE"' in workflow
    assert '--project "$PRODUCTION_RAILWAY_PROJECT_ID"' in workflow
    assert '--service "$PRODUCTION_RAILWAY_SERVICE"' in workflow
    assert 'RAILWAY_PROJECT_ID: ${{ vars.RAILWAY_PROJECT_ID }}' not in workflow
    assert workflow.count('RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}') == 2
    assert workflow.count('test -n "$RAILWAY_API_TOKEN"') == 2
    assert "      RAILWAY_TOKEN:" not in workflow
    assert workflow.count("npm install --global @railway/cli@5.45.7") == 2
    assert "name: production" in workflow
    assert "--production-url \"$PRODUCTION_BASE_URL\"" in workflow
