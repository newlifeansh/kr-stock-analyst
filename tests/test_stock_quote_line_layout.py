from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.staging_app import STAGING_STYLE_VERSION


@pytest.mark.qa_gate
def test_stock_quote_stylesheet_matches_both_shells_and_offline_caches():
    client = TestClient(app)
    asset = f"/assets/staging/toss-fidelity.css?v={STAGING_STYLE_VERSION}"
    for path in ("/dashboard/005930", "/us/stock/AAPL", "/dashboard-sw.js", "/us-sw.js"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert asset in response.text, path


@pytest.mark.qa_e2e
def test_stock_quote_text_stays_on_one_line_on_mobile():
    playwright = pytest.importorskip("playwright.sync_api")
    client = TestClient(app)
    stock = {"code": "005930", "name": "삼성전자", "market": "KOSPI", "currency": "KRW"}
    session = "실시간 시세 확인 중 · 세션 미분리 일봉"
    quote = {
        "price": 180900, "change_value": -15800, "change_rate": -8.03,
        "trade_date": "2026-11-20", "market_session": "krx_opening_auction",
        "market_session_label": session, "volume": 17710000, "trading_value": 3300000000000,
    }

    def serve_fixture(route):
        url = urlsplit(route.request.url)
        if url.hostname != "stock.test":
            return route.abort()
        if url.path.startswith(("/assets/", "/dashboard/", "/dashboard-app-")):
            response = client.get(url.path, params=url.query)
            return route.fulfill(
                body=response.content,
                content_type=response.headers["content-type"],
                status=response.status_code,
            )
        payloads = {
            "/session/invite-status": {"required": False},
            "/stocks/resolve": stock,
            "/stocks/005930/dashboard": {**stock, "quote": quote, "profile": stock},
            "/stocks/005930/quote": {
                "type": "quote", "code": stock["code"], "quote": quote,
                "as_of": "2026-11-23T08:53:00+09:00",
            },
            "/stocks/005930/prices": [],
        }
        return route.fulfill(json=payloads.get(url.path, {"items": []}))

    with playwright.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip("Browser QA requires Playwright Chromium")
        browser = runtime.chromium.launch()
        page = browser.new_page(
            is_mobile=True, has_touch=True, locale="ko-KR",
            timezone_id="Asia/Seoul", service_workers="block",
        )
        page.route("**/*", serve_fixture)
        page.route_web_socket("**/*", lambda socket: None)
        page.clock.set_fixed_time("2026-11-22T23:53:00Z")
        page.add_init_script("""
            localStorage.setItem('analyst.watchlistId', 'quote-qa');
            localStorage.setItem('analyst.pushEntryPromptWeek.v1.quote-qa', '2026-11-23');
        """)
        page.goto("http://stock.test/dashboard/005930")
        status = page.locator("#stock-pre-market")
        detail = status.locator("#stock-market-status-label")
        playwright.expect(detail).to_have_text(f"{session} · 정규장 대기")
        playwright.expect(status.locator(".staging-stock-orderability")).to_have_text("주문 대기")

        for theme in ("dark", "light"):
            page.emulate_media(color_scheme=theme)
            for width in (320, 375, 390, 430, 768):
                page.set_viewport_size({"width": width, "height": 850})
                labels = page.locator(
                    ".staging-stock-hero h2, .staging-stock-hero-price > *, "
                    ".staging-stock-hero-change > *, #stock-pre-market > span, "
                    "#stock-v2-price-periods button, .stock-v3-quote-metrics :is(dt, dd)"
                )
                wrapped = labels.evaluate_all("""nodes => nodes.filter(node => {
                    if (!node.getClientRects().length || node.childElementCount) return false;
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    return new Set([...range.getClientRects()].map(rect => rect.top)).size > 1;
                }).map(node => node.textContent)""")
                assert not wrapped, (theme, width, wrapped)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                help_box = status.locator(".stock-market-status-help").bounding_box()
                assert help_box and help_box["x"] + help_box["width"] <= width
                assert status.bounding_box()["height"] >= 44
                if width == 320:
                    assert detail.evaluate("""node => {
                        node.scrollLeft = node.scrollWidth;
                        return node.scrollLeft > 0 &&
                            node.scrollLeft + node.clientWidth >= node.scrollWidth - 1;
                    }""")
                    assert status.locator(".stock-market-status-help").bounding_box() == help_box
                else:
                    assert detail.evaluate("node => node.scrollWidth <= node.clientWidth + 1")
        stock["name"] = "KODEX 미국반도체장비기업과 인공지능테마 장기투자 상장지수펀드"
        page.set_viewport_size({"width": 320, "height": 850})
        page.reload()
        title = page.locator(".staging-stock-hero h2")
        playwright.expect(title).to_have_text(stock["name"])
        assert title.evaluate("""node => {
            const range = document.createRange();
            range.selectNodeContents(node);
            node.scrollLeft = node.scrollWidth;
            return range.getClientRects().length === 1 && node.scrollLeft > 0 &&
                range.getBoundingClientRect().right <= node.getBoundingClientRect().right + 1;
        }""")
        status.click()
        playwright.expect(page.locator("#stock-trading-hours-sheet")).to_be_visible()
        browser.close()
