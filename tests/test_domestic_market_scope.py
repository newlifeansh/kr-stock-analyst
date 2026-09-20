from pathlib import Path

import app.main as main_module
from app.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_domestic_market_is_the_default_product_boundary():
    assert Settings(us_market_enabled=False).us_market_enabled is False

    shell = _read("app/static/dashboard/index.html")
    styles = _read("app/static/dashboard/styles.css")
    dashboard_source = _read("app/static/dashboard/app.js")
    staging_source = _read("app/static/staging/toss-ia.js")

    assert '<html lang="ko" data-market-universe="kr">' in shell
    assert '<meta name="secret-note-market-universe" content="kr" />' in shell
    assert 'window.location.replace(destination);' in shell
    assert 'html[data-market-universe="kr"] :is(' in styles

    assert 'const US_MARKET_ENABLED = PRODUCT_MARKET_UNIVERSE === "unified";' in dashboard_source
    assert 'const requestedMarketScopeValue = !US_MARKET_ENABLED' in dashboard_source
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

    assert 'const stagingUsMarketEnabled = document' in staging_source
    assert 'const stagingUsHubContext = stagingUsMarketEnabled && (' in staging_source
    assert '${stagingUsHubContext ? `' in staging_source


def test_domestic_home_never_requests_us_market_feeds():
    source = _read("app/static/dashboard/app.js")
    loader = source[
        source.index("async function loadHomeMarketIndices") :
        source.index("function stopHomeMarketIndexRefresh")
    ]

    assert 'return ["KOSPI", "KOSDAQ"];' in source
    assert 'const expectedCodes = new Set(US_MARKET_ENABLED' in loader
    assert ': ["KOSPI", "KOSDAQ"]);' in loader
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


def test_legacy_nasdaq_surface_redirects_to_domestic_home():
    legacy_shell = _read("app/static/nasdaq/index.html")

    assert 'window.location.replace("/dashboard?view=home");' in legacy_shell
