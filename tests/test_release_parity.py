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
    assert contract["product_version"] == "20261009v560"
    assert contract["dashboard_version"] == "20261009v560"
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
    assert contract["product_version"] == "20261009us132"
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
    assert workflow.count('--project="$US_STAGING_RAILWAY_PROJECT_ID"') == 4
    assert workflow.count('--project="$DASHBOARD_STAGING_RAILWAY_PROJECT_ID"') == 5
    assert workflow.count('--project "$TARGET_PRODUCTION_RAILWAY_PROJECT_ID"') == 6
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
    assert workflow.count('RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}') == 4
    assert workflow.count('test -n "$RAILWAY_API_TOKEN"') == 2
    assert "      RAILWAY_TOKEN:" not in workflow
    assert workflow.count("npm install --global @railway/cli@5.45.7") == 4
    assert "railway up" not in workflow
    assert "name: production" in workflow
    assert "--production-url \"$TARGET_PRODUCTION_BASE_URL\"" in workflow
    assert "Wait for the staged product surface" in workflow
    assert "Wait for current staging data" in workflow
    assert "Wait for current US gateway data" in workflow
    assert "Wait for current production data" in workflow
    assert "python -m app.qa.release_data_readiness" in workflow
    assert "staging-data-readiness.json" in workflow
    assert "us-gateway-data-readiness.json" in workflow
    assert "production-data-readiness.json" in workflow
    assert "product_surface:" in workflow
    assert workflow.count('--surface "$PRODUCT_SURFACE"') == 7
    assert workflow.count('railway variable set "US_MARKET_ENABLED=true"') == 4
    assert workflow.count('railway variable set "US_MARKET_ENABLED=false"') == 2
    assert workflow.count('railway variable set "PROCESS_ROLE=web"') == 3
    assert workflow.count('railway variable set "PROCESS_ROLE=collector"') == 3
    assert 'web:{PROCESS_ROLE:"web"}' in workflow
    assert 'collector:{PROCESS_ROLE:"collector"}' in workflow
    assert 'railway variable set "US_PUBLIC_BACKEND_URL=$US_STAGING_BASE_URL"' in workflow
    assert "staging_us_gateway_qa:" in workflow
    gateway_section = workflow.split("  staging_us_gateway_qa:", 1)[1].split(
        "  shutdown_domestic_staging:", 1
    )[0]
    assert "needs: [validate_request, deploy_staging, staging_qa]" in gateway_section
    assert "Let shared US API rate limits reset before gateway live QA" in gateway_section
    assert "run: sleep 65" in gateway_section
    assert workflow.count("playwright install chromium") == 2
    assert "playwright install --with-deps chromium" not in workflow
    assert "--surface us-gateway" in workflow
    assert "/us/market/" not in workflow
    assert "shutdown_domestic_staging:" in workflow
    assert "stop-staging" in workflow
    assert "observe_session:" in workflow
    assert "type: boolean" in workflow
    assert "inputs.action == 'stage' && !inputs.observe_session" in workflow
    assert "inputs.action == 'stop-staging'" in workflow
    assert "[[ \"$REQUESTED_ACTION\" == \"stage\" && \"$PRODUCT_SURFACE\" == \"dashboard\" ]]" in workflow
    assert "Start domestic staging only for deployment and QA" in workflow
    assert "Stop domestic staging after QA or explicit session observation" in workflow
    assert "Start domestic staging for production parity" in workflow
    assert "Stop domestic staging after production parity" in workflow
    assert "DASHBOARD_STAGING_RAILWAY_DATABASE_SERVICE" in workflow
    assert "DASHBOARD_STAGING_RAILWAY_REGION" in workflow
    assert workflow.index("Start domestic staging only for deployment and QA") < workflow.index(
        "Deploy the exact image to domestic staging"
    )


def test_manual_community_push_workflow_is_confirmed_scoped_and_receipted() -> None:
    workflow = Path(".github/workflows/send-community-popular.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "environment:\n      name: production" in workflow
    assert 'test "$CONFIRM" = "SEND-COMMUNITY-POPULAR"' in workflow
    assert "PRODUCTION_RAILWAY_PROJECT_ID" in workflow
    assert "PRODUCTION_RAILWAY_COLLECTOR_SERVICE" in workflow
    assert "railway run --no-local" in workflow
    assert "--environment production" in workflow
    assert "send-community-popular" in workflow
    assert "--expected-post-id" in workflow
    assert "community-popular-receipt.json" in workflow


def test_tested_main_auto_deploys_one_digest_to_both_production_markets() -> None:
    workflow = Path(".github/workflows/deploy-main-production.yml").read_text(
        encoding="utf-8"
    )

    assert "push:" in workflow
    assert "- main" in workflow
    assert "Run deterministic fixtures and contracts" in workflow
    assert "Enforce production gate" in workflow
    assert "docker/build-push-action@v6" in workflow
    assert 'image_ref="${IMAGE_NAME}@${IMAGE_DIGEST}"' in workflow
    assert "needs: [gate, build_image]" in workflow
    assert "name: production" in workflow
    assert "Deploy the exact image to US production first" in workflow
    assert "Deploy the same image to domestic production" in workflow
    assert "Wait for all four exact-image deployments" in workflow
    assert workflow.count("wait_for_exact_image \"") == 4
    assert "did not reach the exact image within 15 minutes" in workflow
    assert workflow.count('railway service source connect --image "$IMAGE_REF"') == 4
    assert "US_STAGING_RAILWAY_PROJECT_ID" not in workflow
    assert "DASHBOARD_STAGING_RAILWAY_PROJECT_ID" not in workflow
    assert "deploy_staging:" not in workflow
    assert "staging_qa:" not in workflow
    assert "Verify domestic production version and asset hashes" in workflow
    assert "Verify US production version and asset hashes" in workflow
    assert "Run domestic production read-only checks" in workflow
    assert "Run US production read-only checks" in workflow
    assert "Capture failed US collector runtime evidence" in workflow
    assert "us-production-collector-runtime.jsonl" in workflow
    assert "Enforce post-deployment verification" in workflow
    enforcement = workflow.split("- name: Enforce post-deployment verification", 1)[1]
    assert 'steps.dashboard_readiness.outcome }}\" = \"success\"' in enforcement
    assert 'steps.us_readiness.outcome }}\" = \"success\"' in enforcement
    assert 'steps.dashboard_live.outcome }}\" = \"success\"' not in enforcement
    assert 'steps.us_live.outcome }}\" = \"success\"' not in enforcement
    assert "::warning::Domestic read-only live QA" in enforcement
    assert "::warning::US read-only live QA" in enforcement

    catalog = {case["id"]: case for case in load_qa_catalog()["cases"]}
    release_case = catalog["DATA-COM-009"]
    assert release_case["priority"] == "P0"
    assert release_case["inputs"]["default_order"] == (
        "main push→gate→build once→US production→dashboard production→"
        "production parity/readiness/live"
    )
    assert release_case["inputs"]["staging_required"] is False


def test_us_canonical_route_activation_requires_exact_production_candidate() -> None:
    workflow = Path(".github/workflows/activate-us-canonical-route.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "name: production" in workflow
    assert "url: https://secretnote.cloud/us" in workflow
    assert 'test "$SOURCE_SHA" = "$(git rev-parse HEAD)"' in workflow
    assert '.[0].status == "SUCCESS" and .[0].meta.image == $image' in workflow
    assert 'test "$US_USER_DATA_MIGRATED_SOURCE_SHA" = "$SOURCE_SHA"' in workflow
    assert ".us_cutover_freeze == true and .us_public_gateway_enabled == false" in workflow
    for target in (
        'check_image "$US_PROJECT" "$US_WEB"',
        'check_image "$US_PROJECT" "$US_COLLECTOR"',
        'check_image "$DOMESTIC_PROJECT" "$DOMESTIC_WEB"',
        'check_image "$DOMESTIC_PROJECT" "$DOMESTIC_COLLECTOR"',
    ):
        assert target in workflow
    assert workflow.index("Recheck both staged artifacts") < workflow.index(
        "Switch the canonical US route"
    )
    assert 'railway variable set "US_PUBLIC_BACKEND_URL=$US_PRODUCTION_BASE_URL"' in workflow
    assert 'railway variable set "US_MARKET_ENABLED=false"' in workflow
    assert 'railway variable set "US_CUTOVER_FREEZE=false"' in workflow
    assert 'DASHBOARD_INVITE_CODE=$invite_code" --skip-deploys' in workflow
    assert "us-gateway-production-live.json" in workflow


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
    assert release_case["inputs"]["dashboard_staging_runtime"] == {
        "services": [
            "DASHBOARD_STAGING_RAILWAY_DATABASE_SERVICE",
            "DASHBOARD_STAGING_RAILWAY_COLLECTOR_SERVICE",
            "DASHBOARD_STAGING_RAILWAY_WEB_SERVICE",
        ],
        "region": "DASHBOARD_STAGING_RAILWAY_REGION",
        "idle_state": {
            "web_replicas": 0,
            "collector_replicas": 0,
            "database_deployment": "stopped",
        },
        "qa_state": {
            "web_replicas": 1,
            "collector_replicas": 1,
            "database_deployment": "running",
        },
        "database_start": "redeploy-configured-source-and-wait",
        "database_stop": "remove-active-deployment-preserve-volume",
        "database_state_timeout_seconds": 300,
        "start_order": ["database", "collector", "web"],
        "stop_order": ["web", "collector", "database"],
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


def test_staging_e2e_does_not_retrigger_itself_from_deployment_status() -> None:
    workflow = Path(".github/workflows/qa-data-signal-e2e.yml").read_text(
        encoding="utf-8"
    )
    assert "  workflow_dispatch:" in workflow
    assert "  deployment_status:" not in workflow
    assert "playwright install chromium" in workflow
    assert "playwright install --with-deps chromium" not in workflow
    assert "group: domestic-staging-runtime" in workflow


def test_scheduled_qa_starts_domestic_runtime_only_while_collecting_evidence() -> None:
    for name, start, stop in (
        (
            "qa-data-signal-live.yml",
            "Start domestic staging for live QA",
            "Stop domestic staging after live QA",
        ),
        (
            "qa-data-signal-e2e.yml",
            "Start domestic staging for browser QA",
            "Stop domestic staging after browser QA",
        ),
    ):
        workflow = Path(".github/workflows", name).read_text(encoding="utf-8")

        assert "group: domestic-staging-runtime" in workflow
        assert "RAILWAY_API_TOKEN: ${{ secrets.RAILWAY_API_TOKEN }}" in workflow
        assert "RAILWAY_DATABASE_SERVICE" in workflow
        assert "RAILWAY_REGION" in workflow
        assert start in workflow
        assert stop in workflow
        assert workflow.index(start) < workflow.index("Upload") < workflow.index(stop)
