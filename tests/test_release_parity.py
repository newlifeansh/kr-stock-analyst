from __future__ import annotations

from pathlib import Path

from app.qa.release_parity import (
    compare_release_contracts,
    local_release_contract,
)


def test_local_release_contract_tracks_all_versioned_frontend_assets() -> None:
    contract = local_release_contract()

    assert contract["dashboard_version"] == "20260904v463"
    assert len(contract["assets"]) == 8
    assert len(contract["asset_sha256"]) == 8
    assert set(contract["asset_sha256"]) == {
        asset.split("?", 1)[0] for asset in contract["assets"]
    }
    assert all(
        len(digest) == 64 for digest in contract["asset_sha256"].values()
    )
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


def test_release_parity_rejects_changed_content_behind_the_same_asset_url() -> None:
    expected = {
        "dashboard_version": "v2",
        "assets": ["/assets/staging/toss-ia.js?v=v2"],
        "asset_sha256": {"/assets/staging/toss-ia.js": "new-content"},
    }
    targets = {
        "staging": {
            "dashboard_version": "v2",
            "assets": ["/assets/staging/toss-ia.js?v=v2"],
            "asset_sha256": {"/assets/staging/toss-ia.js": "stale-content"},
        }
    }

    failures = compare_release_contracts(expected, targets)

    assert failures == [
        {
            "target": "staging",
            "contract": "frontend_asset_content",
            "mismatched_paths": ["/assets/staging/toss-ia.js"],
            "expected": {"/assets/staging/toss-ia.js": "new-content"},
            "actual": {"/assets/staging/toss-ia.js": "stale-content"},
        }
    ]


def test_deployment_workflow_enforces_staging_before_production() -> None:
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text(
        encoding="utf-8"
    )

    assert "deploy_staging:\n    needs: gate" in workflow
    assert "deploy_production_bootstrap:" in workflow
    assert "needs: [gate, deploy_staging]" in workflow
    assert "staging_qa:\n    needs: [deploy_staging, deploy_production_bootstrap]" in workflow
    assert "deploy_production:" in workflow
    assert "needs: staging_qa" in workflow
    assert "always() &&" in workflow
    assert "verify_production:\n    needs: [staging_qa, deploy_production, deploy_production_bootstrap]" in workflow
    assert workflow.count("ref: ${{ github.sha }}") == 6
    assert "--environment staging" in workflow
    assert "--environment production" in workflow
    assert '--project "$STAGING_RAILWAY_PROJECT_ID"' in workflow
    assert '--service "$STAGING_RAILWAY_SERVICE"' in workflow
    assert '--project "$PRODUCTION_RAILWAY_PROJECT_ID"' in workflow
    assert '--service "$PRODUCTION_RAILWAY_SERVICE"' in workflow
    assert 'RAILWAY_PROJECT_ID: ${{ vars.RAILWAY_PROJECT_ID }}' not in workflow
    assert workflow.count('RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}') == 3
    assert workflow.count('test -n "$RAILWAY_API_TOKEN"') == 3
    assert "      RAILWAY_TOKEN:" not in workflow
    assert workflow.count("npm install --global @railway/cli@5.45.7") == 3
    assert workflow.count("railway up --detach --json") == 3
    assert workflow.count('--message "github-sha=${{ github.sha }}"') == 3
    assert "railway up --ci" not in workflow
    assert "name: production" in workflow
    assert "--production-url \"$PRODUCTION_BASE_URL\"" in workflow
