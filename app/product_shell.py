from __future__ import annotations

from typing import Literal


MarketUniverse = Literal["kr", "us"]


def render_dashboard_product_shell(
    source: str,
    *,
    market_universe: MarketUniverse,
    client_version: str,
) -> str:
    """Render one visual dashboard shell with an isolated market contract."""

    if market_universe == "us":
        values = {
            "__MARKET_UNIVERSE__": "us",
            "__PRODUCT_TITLE__": "비밀노트 | 미국증시",
            "__WEB_MANIFEST_PATH__": "/us.webmanifest",
            "__APP_BASE_PATH__": "/us",
            "__CLIENT_VERSION__": client_version,
        }
    else:
        values = {
            "__MARKET_UNIVERSE__": "kr",
            "__PRODUCT_TITLE__": "비밀노트 | 국내증시",
            "__WEB_MANIFEST_PATH__": "/dashboard.webmanifest",
            "__APP_BASE_PATH__": "/dashboard",
            "__CLIENT_VERSION__": client_version,
        }

    document = source
    for placeholder, value in values.items():
        document = document.replace(placeholder, value)
    unresolved = [placeholder for placeholder in values if placeholder in document]
    if unresolved:
        raise ValueError(f"dashboard shell placeholder replacement failed: {unresolved}")
    return document
