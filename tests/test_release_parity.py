from __future__ import annotations

from pathlib import Path

from app.qa.release_parity import (
    compare_release_contracts,
    local_release_contract,
)


def test_local_release_contract_tracks_all_versioned_frontend_assets() -> None:
    contract = local_release_contract()

    assert contract["surface"] == "dashboard"
    assert contract["product_version"] == "20260923v553"
    assert contract["dashboard_version"] == "20260923v553"
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


def test_local_us_release_contract_tracks_its_own_versioned_assets() -> None:
    contract = local_release_contract(surface="us")

    assert contract["surface"] == "us"
    assert contract["product_version"] == "20260924us106"
    assert len(contract["assets"]) == 12
    assert len(contract["asset_sha256"]) == 12
    assert set(contract["asset_sha256"]) == {
        asset.split("?", 1)[0] for asset in contract["assets"]
    }
    assert all(len(digest) == 64 for digest in contract["asset_sha256"].values())
    assert all(
        "?v=" in asset
        for asset in contract["assets"]
        if not asset.endswith("/us.webmanifest")
    )
    assert any("/dashboard-app-v170.js" in asset for asset in contract["assets"])
    assert any("/assets/dashboard/styles.css" in asset for asset in contract["assets"])
    assert not any("/assets/nasdaq/app.js" in asset for asset in contract["assets"])


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

    assert ("staging", "product_version") in contracts
    assert ("staging", "frontend_assets") in contracts
    assert ("staging-production", "same_product_version") in contracts
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


def test_deployment_workflow_promotes_one_immutable_image_after_staging() -> None:
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text(
        encoding="utf-8"
    )

    assert "packages: write" in workflow
    assert "docker/build-push-action@v6" in workflow
    assert 'image_ref="${IMAGE_NAME}@${IMAGE_DIGEST}"' in workflow
    assert "deploy_staging:" in workflow
    assert "needs: [validate_request, gate, build_image]" in workflow
    assert "staging_qa:" in workflow
    assert "needs: [validate_request, build_image, deploy_staging]" in workflow
    assert "inputs.action == 'promote-production'" in workflow
    assert "needs: [validate_request, deploy_production]" in workflow
    assert "^ghcr\\.io/.+@sha256:[0-9a-f]{64}$" in workflow
    assert "--environment staging" in workflow
    assert "--environment production" in workflow
    assert workflow.count('railway service source connect --image "$IMAGE_REF"') == 4
    assert workflow.count('--project "$STAGING_RAILWAY_PROJECT_ID"') == 4
    assert workflow.count('--project "$PRODUCTION_RAILWAY_PROJECT_ID"') == 4
    assert 'RAILWAY_PROJECT_ID: ${{ vars.RAILWAY_PROJECT_ID }}' not in workflow
    assert (
        'STAGING_RAILWAY_PROJECT_ID: ${{ vars.STAGING_RAILWAY_PROJECT_ID }}'
        in workflow
    )
    assert (
        'PRODUCTION_RAILWAY_PROJECT_ID: ${{ vars.PRODUCTION_RAILWAY_PROJECT_ID }}'
        in workflow
    )
    assert '--service "$STAGING_RAILWAY_WEB_SERVICE"' in workflow
    assert '--service "$STAGING_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert '--service "$PRODUCTION_RAILWAY_WEB_SERVICE"' in workflow
    assert '--service "$PRODUCTION_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert workflow.count('RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}') == 2
    assert workflow.count('test -n "$RAILWAY_API_TOKEN"') == 2
    assert "      RAILWAY_TOKEN:" not in workflow
    assert workflow.count("npm install --global @railway/cli@5.45.7") == 2
    assert "railway up" not in workflow
    assert "name: production" in workflow
    assert "--production-url \"$PRODUCTION_BASE_URL\"" in workflow
    assert "Wait for the staged product surface" in workflow
    assert "product_surface:" in workflow
    assert workflow.count('--surface "$PRODUCT_SURFACE"') == 5
    assert workflow.count('railway variable set "US_MARKET_ENABLED=true"') == 4
    assert "US_MARKET_ENABLED=false" not in workflow
    assert "runtime_config:{US_MARKET_ENABLED:true}" in workflow
    assert "/us/market/" not in workflow
