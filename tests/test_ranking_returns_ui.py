from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.qa_e2e
def test_mobile_return_tabs_and_snapshot_navigation():
    playwright = pytest.importorskip("playwright.sync_api")
    client = TestClient(app)
    generation = 1
    board_requests = []

    def serve(route):
        url = urlsplit(route.request.url)
        if url.hostname != "stock.test":
            return route.abort()
        if url.path in {"/dashboard", "/us"} or url.path.startswith(("/assets/", "/dashboard-app-")):
            result = client.get(url.path, params=url.query)
            return route.fulfill(body=result.content, content_type=result.headers["content-type"])
        if url.path not in {"/market/rankings", "/us/market/rankings"}:
            return route.fulfill(json={"required": False} if url.path == "/session/invite-status" else {"items": []})
        params = parse_qs(url.query)
        category = params["category"][0]
        mode = params.get("mode", ["daily"])[0]
        us = url.path.startswith("/us/")
        items = [
            {"code": "451250", "name": "삐아", "price": 8850, "change_rate": 13.32,
             "one_week_return": 17.50, "one_month_return": 61.50},
            {"code": "123690", "name": "한국화장품", "price": 7190, "change_rate": 11.30,
             "one_week_return": 45.45, "one_month_return": None},
        ]
        if us:
            items = [{"code": "AAPL", "name": "Apple", "price": 188, "change_rate": 1.23,
                      "one_week_return": 4.56, "one_month_return": 7.89}]
        elif mode == "week":
            items.reverse()
        elif generation == 2 and mode == "daily":
            items[1].update(price=7800, change_rate=20.74)
            items.reverse()
        live = not us and mode == "daily" and generation == 2
        for rank, item in enumerate(items, 1):
            item.update(rank=rank, market="NASDAQ" if us else "KOSPI", category=category,
                        currency="USD" if us else "KRW", trade_date="2026-11-23" if live else "2026-11-20")
        payload = {"market": "NASDAQ" if us else "ALL", "category": category, "mode": mode,
                   "source": "naver_market_rise" if live else "database", "as_of": "2026-11-23T09:07:00+09:00", "items": items}
        if category == "surge" and mode == "daily" and not us:
            payload["snapshot_id"] = f"daily-return-{generation}"
            if params["limit"] != ["5"]:
                board_requests.append(params.get("snapshot_id"))
        return route.fulfill(json=payload)

    with playwright.sync_playwright() as runtime:
        if not Path(runtime.chromium.executable_path).exists():
            pytest.skip("Browser QA requires Playwright Chromium")
        browser = runtime.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True,
                                locale="ko-KR", timezone_id="Asia/Seoul", service_workers="block")
        page.route("**/*", serve)
        page.route_web_socket("**/*", lambda socket: None)
        page.clock.install(time="2026-11-23T00:06:00Z")
        page.add_init_script("""
            localStorage.setItem('analyst.watchlistId', 'rank-qa');
            localStorage.setItem('analyst.pushEntryPromptWeek.v1.rank-qa', '2026-11-23');
        """)
        page.goto("http://stock.test/dashboard?view=home")
        rates = page.locator("#home-surge-list .staging-home-ranking-rate")
        expect = playwright.expect
        expect(rates).to_have_text(["+13.32%", "+11.30%"])
        basis = page.locator("#home-surge-meta")
        expect(basis).to_contain_text("2026-11-20 저장 일봉 기준")
        expect(basis).to_be_visible()
        page.evaluate("updateHomeRankingQuote('451250', {price: 1, change_rate: -99})")
        expect(rates.first).to_have_text("+13.32%")
        expect(page.locator("#home-surge-list .staging-home-ranking-price").first).to_have_text("8,850원")

        tabs = page.locator("#home-surge-sector-filters")
        tabs.get_by_role("tab", name="주간").click()
        expect(rates).to_have_text(["+45.45%", "+17.50%"])
        tabs.get_by_role("tab", name="월간").click()
        expect(rates).to_have_text(["+61.50%", "등락률 확인 중"])

        tabs.get_by_role("tab", name="일간").click()
        expect(rates).to_have_text(["+13.32%", "+11.30%"])
        generation = 2
        page.clock.fast_forward(61_000)
        expect(rates).to_have_text(["+20.74%", "+13.32%"])
        expect(basis).to_contain_text("2026-11-23 09:07 기준")
        page.locator("#home-surge-more").click()
        rows = page.locator("#ranking-body .market-ranking-row")
        expect(rows.first).to_contain_text("한국화장품")
        expect(rows.first).to_contain_text("20.74%")
        assert board_requests[-1] == ["daily-return-2"]
        page.evaluate("updateMarketLeaderboardQuote('123690', {price: 1, change_rate: -99})")
        expect(rows.first).to_contain_text("20.74%")
        page.goto("http://stock.test/us?view=home")
        us_tabs = page.locator("#home-surge-sector-filters-us")
        us_rates = page.locator("#home-surge-list-us .staging-home-ranking-rate")
        us_tabs.get_by_role("tab", name="주간").click()
        expect(us_rates).to_have_text(["+4.56%"])
        us_tabs.get_by_role("tab", name="월간").click()
        expect(us_rates).to_have_text(["+7.89%"])
        browser.close()
