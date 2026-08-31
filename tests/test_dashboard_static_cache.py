from fastapi.testclient import TestClient

from app.main import DASHBOARD_CLIENT_VERSION, app


IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
NO_STORE_CACHE_CONTROL = "no-store, no-cache, must-revalidate, max-age=0"


def test_dashboard_shell_is_not_cached_but_references_versioned_assets():
    client = TestClient(app)

    response = client.get("/dashboard?view=home")

    assert response.status_code == 200
    assert response.headers["cache-control"] == NO_STORE_CACHE_CONTROL
    assert (
        f'href="/assets/dashboard/styles.css?v={DASHBOARD_CLIENT_VERSION}'
        in response.text
    )
    assert (
        f'src="/dashboard-app-v170.js?v={DASHBOARD_CLIENT_VERSION}"'
        in response.text
    )


def test_current_dashboard_assets_are_immutable_without_changing_content():
    client = TestClient(app)
    asset_pairs = (
        (
            f"/assets/dashboard/styles.css?v={DASHBOARD_CLIENT_VERSION}&build={DASHBOARD_CLIENT_VERSION}",
            "/assets/dashboard/styles.css",
        ),
        (
            f"/dashboard-app-v170.js?v={DASHBOARD_CLIENT_VERSION}",
            "/dashboard-app-v170.js",
        ),
    )

    for versioned_url, mutable_url in asset_pairs:
        versioned = client.get(versioned_url)
        mutable = client.get(mutable_url)

        assert versioned.status_code == 200
        assert versioned.headers["cache-control"] == IMMUTABLE_CACHE_CONTROL
        assert mutable.status_code == 200
        assert mutable.headers["cache-control"] == NO_STORE_CACHE_CONTROL
        assert versioned.content == mutable.content


def test_unknown_dashboard_asset_version_is_never_cached_as_immutable():
    client = TestClient(app)

    for url in (
        "/assets/dashboard/styles.css?v=outdated-build",
        "/dashboard-app-v170.js?v=outdated-build",
    ):
        response = client.get(url)

        assert response.status_code == 200
        assert response.headers["cache-control"] == NO_STORE_CACHE_CONTROL
        assert "immutable" not in response.headers["cache-control"]


def test_dashboard_asset_head_uses_the_same_cache_policy_as_get():
    client = TestClient(app)

    for path in (
        "/assets/dashboard/styles.css",
        "/dashboard-app-v170.js",
    ):
        for query, expected in (
            (f"?v={DASHBOARD_CLIENT_VERSION}", IMMUTABLE_CACHE_CONTROL),
            ("", NO_STORE_CACHE_CONTROL),
            ("?v=outdated-build", NO_STORE_CACHE_CONTROL),
        ):
            get_response = client.get(f"{path}{query}")
            head_response = client.head(f"{path}{query}")

            assert head_response.status_code == get_response.status_code == 200
            assert head_response.headers["cache-control"] == expected
            assert head_response.headers["cache-control"] == get_response.headers["cache-control"]
            assert head_response.headers["content-type"] == get_response.headers["content-type"]
            assert head_response.headers["content-length"] == get_response.headers["content-length"]
            assert head_response.content == b""
