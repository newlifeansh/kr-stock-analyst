from __future__ import annotations

from pathlib import Path

from app.qa.release_parity import (
    compare_release_contracts,
    local_release_contract,
)
from app.qa.catalog import load_qa_catalog
from app.qa.runner import DEFAULT_STAGING_BASE_URLS


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
    assert contract["product_version"] == "20260924us113"
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
    assert workflow.count('railway service source connect --image "$IMAGE_REF"') == 6
    assert workflow.count('--project "$US_STAGING_RAILWAY_PROJECT_ID"') == 2
    assert workflow.count('--project "$DASHBOARD_STAGING_RAILWAY_PROJECT_ID"') == 2
    assert workflow.count('--project "$TARGET_PRODUCTION_RAILWAY_PROJECT_ID"') == 4
    assert 'RAILWAY_PROJECT_ID: ${{ vars.RAILWAY_PROJECT_ID }}' not in workflow
    assert 'US_STAGING_RAILWAY_PROJECT_ID: ${{ vars.US_STAGING_RAILWAY_PROJECT_ID }}' in workflow
    assert 'DASHBOARD_STAGING_RAILWAY_PROJECT_ID: ${{ vars.DASHBOARD_STAGING_RAILWAY_PROJECT_ID }}' in workflow
    assert (
        'PRODUCTION_RAILWAY_PROJECT_ID: ${{ vars.PRODUCTION_RAILWAY_PROJECT_ID }}'
        in workflow
    )
    assert (
        'US_PRODUCTION_RAILWAY_PROJECT_ID: ${{ vars.US_PRODUCTION_RAILWAY_PROJECT_ID }}'
        in workflow
    )
    assert '--service "$US_STAGING_RAILWAY_WEB_SERVICE"' in workflow
    assert '--service "$US_STAGING_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert '--service "$DASHBOARD_STAGING_RAILWAY_WEB_SERVICE"' in workflow
    assert '--service "$DASHBOARD_STAGING_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert '--service "$TARGET_PRODUCTION_RAILWAY_WEB_SERVICE"' in workflow
    assert '--service "$TARGET_PRODUCTION_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert workflow.count('RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}') == 2
    assert workflow.count('test -n "$RAILWAY_API_TOKEN"') == 2
    assert "      RAILWAY_TOKEN:" not in workflow
    assert workflow.count("npm install --global @railway/cli@5.45.7") == 2
    assert "railway up" not in workflow
    assert "name: production" in workflow
    assert "--production-url \"$TARGET_PRODUCTION_BASE_URL\"" in workflow
    assert "Wait for the staged product surface" in workflow
    assert "product_surface:" in workflow
    assert workflow.count('--surface "$PRODUCT_SURFACE"') == 5
    assert workflow.count('railway variable set "US_MARKET_ENABLED=true"') == 4
    assert workflow.count('railway variable set "US_MARKET_ENABLED=false"') == 2
    assert "staging_runtime:{dashboard:{US_MARKET_ENABLED:false},us:{US_MARKET_ENABLED:true}}" in workflow
    assert "/us/market/" not in workflow


def test_staging_targets_and_qa_evidence_are_separate_for_both_products() -> None:
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text(
        encoding="utf-8"
    )
    us_deploy = workflow.index("Deploy the exact image to us-market staging")
    dashboard_deploy = workflow.index("Deploy the exact image to domestic staging")
    qa = workflow.index("  staging_qa:")
    production = workflow.index("  deploy_production:")
    assert us_deploy < dashboard_deploy < qa < production
    assert 'test "$US_STAGING_RAILWAY_PROJECT_ID" != "$DASHBOARD_STAGING_RAILWAY_PROJECT_ID"' in workflow
    assert 'test "$US_STAGING_BASE_URL" != "$DASHBOARD_STAGING_BASE_URL"' in workflow
    assert 'matrix:\n        surface: [dashboard, us]' in workflow[qa:]
    assert "matrix.surface == 'us' && vars.US_STAGING_BASE_URL || vars.DASHBOARD_STAGING_BASE_URL" in workflow
    assert '--staging-url "$QA_BASE_URL"' in workflow
    assert '--base-url "$QA_BASE_URL"' in workflow
    assert workflow.count("matrix:\n        surface: [dashboard, us]") == 1
    assert "dark-theme-preview-staging" not in workflow
    assert "id: live_qa\n        continue-on-error: true" in workflow
    assert "id: browser_qa\n        continue-on-error: true" in workflow
    assert "Enforce both staging QA reports" in workflow
    assert 'test -f artifacts/qa-data-signal/live.json' in workflow
    assert 'test -f artifacts/qa-data-signal/e2e.json' in workflow

    assert DEFAULT_STAGING_BASE_URLS["dashboard"] != DEFAULT_STAGING_BASE_URLS["us"]
    assert "domestic-market-web-staging" in DEFAULT_STAGING_BASE_URLS["dashboard"]
    assert "us-market-web-staging" in DEFAULT_STAGING_BASE_URLS["us"]

    catalog = {case["id"]: case for case in load_qa_catalog()["cases"]}
    release_case = catalog["DATA-COM-005"]
    assert release_case["priority"] == "P0"
    assert release_case["inputs"]["railway_projects"] == {
        "dashboard_staging": "DASHBOARD_STAGING_RAILWAY_PROJECT_ID",
        "us_staging": "US_STAGING_RAILWAY_PROJECT_ID",
        "dashboard_production": "PRODUCTION_RAILWAY_PROJECT_ID",
        "us_production": "US_PRODUCTION_RAILWAY_PROJECT_ID",
    }
    assert release_case["inputs"]["production_urls"] == {
        "dashboard": "PRODUCTION_BASE_URL",
        "us": "US_PRODUCTION_BASE_URL",
    }
    assert release_case["inputs"]["staging_market_flags"] == {
        "dashboard": False,
        "us": True,
    }


def test_production_promotion_selects_only_the_requested_existing_project() -> None:
    workflow = Path(".github/workflows/deploy-staging-production.yml").read_text(
        encoding="utf-8"
    )
    deploy = workflow.split("  deploy_production:", 1)[1].split("  verify_production:", 1)[0]
    verify = workflow.split("  verify_production:", 1)[1]

    for suffix in ("RAILWAY_PROJECT_ID", "RAILWAY_WEB_SERVICE", "RAILWAY_COLLECTOR_SERVICE"):
        assert (
            f"TARGET_PRODUCTION_{suffix}: ${{{{ inputs.product_surface == 'us' "
            f"&& vars.US_PRODUCTION_{suffix} || vars.PRODUCTION_{suffix} }}}}"
        ) in deploy
    assert (
        "TARGET_PRODUCTION_BASE_URL: ${{ inputs.product_surface == 'us' "
        "&& vars.US_PRODUCTION_BASE_URL || vars.PRODUCTION_BASE_URL }}"
    ) in deploy
    assert '--project "$TARGET_PRODUCTION_RAILWAY_PROJECT_ID"' in deploy
    assert 'if [[ "$PRODUCT_SURFACE" == "us" ]]; then' in deploy
    assert 'railway variable set "US_MARKET_ENABLED=false"' not in deploy
    assert "matrix:" not in verify
    assert 'PRODUCT_SURFACE: ${{ inputs.product_surface }}' in verify
    assert '--production-url "$TARGET_PRODUCTION_BASE_URL"' in verify
    assert '--base-url "$TARGET_PRODUCTION_BASE_URL"' in verify
    assert 'test "$US_PRODUCTION_RAILWAY_PROJECT_ID" != "$PRODUCTION_RAILWAY_PROJECT_ID"' in workflow
    assert 'test "$US_PRODUCTION_RAILWAY_PROJECT_ID" != "$US_STAGING_RAILWAY_PROJECT_ID"' not in workflow
    assert 'test "$US_PRODUCTION_RAILWAY_WEB_SERVICE" != "$US_STAGING_RAILWAY_WEB_SERVICE"' in workflow
    assert 'test "$US_PRODUCTION_RAILWAY_COLLECTOR_SERVICE" != "$US_STAGING_RAILWAY_COLLECTOR_SERVICE"' in workflow
    assert 'test "$US_PRODUCTION_BASE_URL" != "$US_STAGING_BASE_URL"' in workflow


def test_scheduled_qa_never_reuses_the_preview_proxy() -> None:
    for name in ("qa-data-signal-live.yml", "qa-data-signal-e2e.yml"):
        workflow = Path(".github/workflows", name).read_text(encoding="utf-8")
        assert "surface: [dashboard, us]" in workflow
        assert 'surface "${{ matrix.surface }}"' in workflow
        assert "vars.US_STAGING_BASE_URL || vars.DASHBOARD_STAGING_BASE_URL" in workflow
        assert "dark-theme-preview-staging" not in workflow
