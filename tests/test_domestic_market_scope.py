from pathlib import Path

import app.main as main_module
from app.config import Settings
from app.product_shell import render_dashboard_product_shell


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_domestic_market_is_the_default_product_boundary():
    assert Settings(us_market_enabled=False).us_market_enabled is False

    shell = render_dashboard_product_shell(
        _read("app/static/dashboard/index.html"),
        market_universe="kr",
        client_version="test-kr",
    )
    styles = _read("app/static/dashboard/styles.css")
    dashboard_source = _read("app/static/dashboard/app.js")
    staging_source = _read("app/static/staging/toss-ia.js")

    assert '<html lang="ko" data-market-universe="kr">' in shell
    assert '<meta name="secret-note-market-universe" content="kr" />' in shell
    assert 'window.location.replace(serverUrl.toString());' in shell
    assert 'html[data-market-universe="kr"] :is(' in styles

    assert 'const US_MARKET_ENABLED = PRODUCT_MARKET_UNIVERSE !== "kr";' in dashboard_source
    assert 'const IS_US_ONLY_PRODUCT = PRODUCT_MARKET_UNIVERSE === "us";' in dashboard_source
    assert 'const requestedMarketScopeValue = IS_US_ONLY_PRODUCT' in dashboard_source
    assert 'function applyDomesticMarketStructure()' in dashboard_source
    assert 'document.title = "비밀노트 | 국내증시";' in dashboard_source
    for selector in (
        '#unified-market-scope',
        '#recommend-market-scope',
        '#watch-market-map-market-toggle',
        '#service-source-us',
        '#us-stock-ai-content',
        '[data-home-ranking-market="NASDAQ"]',
        '[data-home-ranking-market="SP500"]',
        '[data-market-filter="MIXED"]',
        '[data-market-filter="NASDAQ"]',
        '[data-market-filter="SP500"]',
    ):
        assert selector in dashboard_source

    assert 'const stagingUsOnlyProduct = stagingProductMarketUniverse === "us";' in staging_source
    assert 'const stagingUsMarketEnabled = stagingUsOnlyProduct || stagingUnifiedProduct;' in staging_source
    assert 'const stagingUsHubContext = stagingUsMarketEnabled && (' in staging_source


def test_domestic_home_never_requests_us_market_feeds():
    source = _read("app/static/dashboard/app.js")
    loader = source[
        source.index("async function loadHomeMarketIndices") :
        source.index("function stopHomeMarketIndexRefresh")
    ]

    assert 'return ["KOSPI", "KOSDAQ"];' in source
    assert 'const expectedCodes = new Set(IS_US_ONLY_PRODUCT' in loader
    assert ': ["KOSPI", "KOSDAQ"]);' in loader
    assert 'IS_US_ONLY_PRODUCT\n        ? Promise.resolve(null)' in loader
    assert 'US_MARKET_ENABLED\n        ? fetchHomeJsonWithRetry(liveUrl("/market/global-assets?limit=30")' in loader
    assert 'if (!US_MARKET_ENABLED) return null;' in source[
        source.index("async function loadUsSectorMoves") :
        source.index("function clearUsSectorRefreshTimer")
    ]
    assert 'if (!US_MARKET_ENABLED) return;' in source[
        source.index("function connectUsSectorStream") :
        source.index("function scheduleUsSectorRefresh")
    ]


def test_domestic_runtime_does_not_schedule_us_market_snapshots(monkeypatch):
    monkeypatch.setattr(main_module.settings, "us_market_enabled", False)
    assert main_module._periodic_complete_snapshot_keys() == (
        f"{main_module.MARKET_INDICES_SNAPSHOT_PREFIX}30",
        main_module.SURGE_COMPLETE_SNAPSHOT_KEY,
    )

    monkeypatch.setattr(main_module.settings, "us_market_enabled", True)
    assert main_module._periodic_complete_snapshot_keys() == (
        f"{main_module.MARKET_INDICES_SNAPSHOT_PREFIX}30",
        main_module.SURGE_COMPLETE_SNAPSHOT_KEY,
        f"{main_module.GLOBAL_MARKET_ASSETS_SNAPSHOT_PREFIX}30",
        main_module.US_SECTOR_MOVES_SNAPSHOT_KEY,
    )


def test_us_spinout_shell_is_separate_from_the_domestic_product():
    template = _read("app/static/dashboard/index.html")
    domestic_shell = render_dashboard_product_shell(
        template,
        market_universe="kr",
        client_version="kr-version",
    )
    us_shell = render_dashboard_product_shell(
        template,
        market_universe="us",
        client_version="us-version",
    )
    us_source = _read("app/static/dashboard/app.js")

    assert '<html lang="ko" data-market-universe="us">' in us_shell
    assert '<meta name="secret-note-market-universe" content="us" />' in us_shell
    assert '<title>비밀노트 | 미국증시</title>' in us_shell
    assert 'href="/assets/dashboard/styles.css?v=us-version&amp;build=us-version"' in us_shell
    assert 'src="/dashboard-app-v170.js?v=us-version"' in us_shell
    normalized_us = (
        us_shell.replace('data-market-universe="us"', 'data-market-universe="kr"')
        .replace('content="us"', 'content="kr"')
        .replace("비밀노트 | 미국증시", "비밀노트 | 국내증시")
        .replace("/us.webmanifest", "/dashboard.webmanifest")
        .replace("127.0.0.1:8001/us", "127.0.0.1:8001/dashboard")
        .replace('href="/us?view=ai-signals"', 'href="/dashboard?view=ai-signals"')
        .replace("us-version", "kr-version")
    )
    assert normalized_us == domestic_shell
    assert 'const IS_US_ONLY_PRODUCT = PRODUCT_MARKET_UNIVERSE === "us";' in us_source
    assert 'const requestedMarketScopeValue = IS_US_ONLY_PRODUCT\n  ? "us"' in us_source
    assert 'IS_US_ONLY_PRODUCT\n        ? Promise.resolve(null)' in us_source
    assert 'liveUrl("/market/global-assets?limit=30")' in us_source
    assert 'const PRODUCT_SERVICE_WORKER_PATH = IS_US_ONLY_PRODUCT ? "/us-sw.js"' in us_source
