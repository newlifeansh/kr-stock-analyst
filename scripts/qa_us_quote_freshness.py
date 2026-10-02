"""Read-only live probes + browser UI fixtures; never send pushes or orders."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import requests

VERSION = "20261003us133"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", choices=["live", "e2e"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    report = {"mode": args.mode, "qa_ids": ["QUOTE-US-LIVE-001", "QUOTE-US-LIVE-003"], "blocked": True, "checks": []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        version = requests.get(base+"/us-version", timeout=20)
        version.raise_for_status()
        assert version.json()["version"] == VERSION, "wrong UI candidate"
        r = requests.get(base+"/us/stocks/quotes", params={"symbols": "NVDA,AAPL,MSFT", "refresh": "true"}, timeout=30)
        r.raise_for_status()
        payload = r.json()
        checked = datetime.now(timezone.utc)
        assert len(payload["items"]) == 3, "incomplete quotes"
        observations = []
        for item in payload["items"]:
            quote = item["quote"]
            assert item["source"] == "yahoo_quote_batch"
            assert quote["observed_at"] == item["observed_at"] and quote["observed_at"], "missing source timestamp"
            age = (checked-datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00"))).total_seconds()
            assert age >= -5, "future source timestamp"
            if payload["market_session"] == "regular":
                assert age <= 30 and quote["freshness"] == "recent", "source quote is stale during regular session"
            observations.append({"code": item["code"], "observed_at": item["observed_at"], "age_seconds": age, "freshness": quote["freshness"]})
        report["checks"].append({"live_api": observations})
        if args.mode == "e2e":
            from playwright.sync_api import sync_playwright, expect
            with sync_playwright() as play:
                browser = play.chromium.launch(headless=True)
                for width in (320, 458, 1280):
                    theme = "dark" if width == 458 else "light"
                    context = browser.new_context(viewport={"width": width, "height": 900}, color_scheme=theme, locale="ko-KR", timezone_id="Asia/Seoul", reduced_motion="reduce", service_workers="block")
                    # These fixtures are local to the browser. Protected APIs
                    # are not unlocked on the server and mutations are blocked.
                    def guard(route):
                        path = route.request.url
                        if "/session/dashboard-access" in path:
                            route.fulfill(json={"required": True, "authorized": True, "newly_registered": False})
                        elif route.request.method not in {"GET", "HEAD", "OPTIONS"}:
                            route.fulfill(status=200, json={})
                        elif "/watchlists/qa-us-quotes" in path or "/watchlists/us.qa-us-quotes" in path:
                            route.fulfill(json=[])
                        else:
                            route.continue_()
                    context.route("**/*", guard)
                    context.add_init_script("localStorage.setItem('analyst.watchlistId','qa-us-quotes');localStorage.setItem('analyst.us.watchlistId','us.qa-us-quotes');")
                    context.add_init_script("""for (const id of ['qa-us-quotes','us.qa-us-quotes']) {
                      localStorage.setItem('analyst.recommendationPushPromptDecision.v1.'+id,'dismissed');
                    }
                    localStorage.setItem('secret-note-service-update-dismissed:20260829-chart-analysis-v1','1');""")
                    page = context.new_page()
                    page.goto(base+"/us/stock/NVDA", wait_until="domcontentloaded")
                    expect(page.locator("#stock-market-status-label")).to_contain_text("KST", timeout=60000)
                    expect(page.locator("#page-loading")).to_be_hidden(timeout=30000)
                    expect(page.locator("#login-gate")).to_be_hidden(timeout=30000)
                    visible_status = page.locator(".staging-stock-orderability")
                    expect(visible_status).to_be_visible()
                    expect(page.locator("#stock-market-status-label")).to_be_visible()
                    assert "실시간 주문" not in visible_status.inner_text()
                    for selector in ("#recommendation-push-prompt-close", "#push-notification-sheet-close"):
                        button = page.locator(selector)
                        if button.count() and button.is_visible():
                            button.click()
                    assert page.evaluate("usVisibleQuotes.scopes.get('detail')?.has('NVDA')"), "detail polling disconnected"
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "horizontal overflow"
                    # Keep the real render/transport callbacks and simulate a
                    # stale provider frame; its price must not overwrite live UI.
                    mode = {"kind": "fresh"}
                    def quotes(route):
                        if mode["kind"] == "error":
                            route.fulfill(status=503, json={})
                            return
                        age = 1800 if mode["kind"] == "stale" else 0
                        from datetime import timedelta
                        stamp = (datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat()
                        route.fulfill(json={"items": [{"type": "quote", "code": "NVDA", "source": "yahoo_quote_batch", "observed_at": stamp, "as_of": stamp,
                            "quote": {"price": 1 if age else 235, "change_rate": 1.0, "change_value": 2.0, "previous_close": 233,
                                      "market_session": "regular", "observed_at": stamp, "is_live": not age, "freshness": "delayed" if age else "recent"}}]})
                    page.route("**/us/stocks/quotes?**", quotes)
                    page.evaluate("++usVisibleQuotes.generation; usVisibleQuotes.frames.delete('NVDA'); window.clearTimeout(usVisibleQuotes.timer)")
                    page.evaluate("pollUsVisibleQuotes(usVisibleQuotes.generation)")
                    expect(page.locator("#quote-price")).to_have_text("$235.00")
                    mode["kind"] = "stale"
                    page.evaluate("usVisibleQuotes.frames.delete('NVDA'); window.clearTimeout(usVisibleQuotes.timer)")
                    original = page.locator("#quote-price").inner_text()
                    original_time = page.locator("#stock-market-status-label").inner_text()
                    page.evaluate("pollUsVisibleQuotes(usVisibleQuotes.generation)")
                    expect(visible_status).to_contain_text("지연")
                    assert page.locator("#quote-price").inner_text() == original, "stale frame overwrote displayed price"
                    assert page.locator("#stock-market-status-label").inner_text() == original_time, "rejected frame overwrote displayed price timestamp"
                    mode["kind"] = "error"
                    page.evaluate("pollUsVisibleQuotes(usVisibleQuotes.generation)")
                    expect(visible_status).to_contain_text("재시도")
                    mode["kind"] = "fresh"
                    page.evaluate("pollUsVisibleQuotes(usVisibleQuotes.generation)")
                    expect(visible_status).to_contain_text("15초 갱신")
                    expect(page.locator("#stock-market-status-label")).to_be_visible()
                    assert "동부시간" not in page.locator("[data-quote-freshness]").get_attribute("aria-label")
                    # Read-only DOM fixture for the same watchlist callback.
                    page.evaluate("""() => {
                      const card=document.createElement('article');card.dataset.watchCard='';card.dataset.code='NVDA';
                      elements.watchlistBody.append(card);
                      connectWatchlistQuoteStream('NVDA',{code:'NVDA',market_scope:'us',market:'NASDAQ',currency:'USD'});
                    }""")
                    page.evaluate("pollUsVisibleQuotes(usVisibleQuotes.generation)")
                    assert "KST" in page.locator("[data-us-quote-basis]").last.inner_text()
                    page.screenshot(path=str(args.output.with_name(f"us-quotes-{width}.png")), full_page=False)
                    report["checks"].append({"width": width, "theme": theme, "real_detail_subscription": True, "stale_price_preserved": True,
                                             "failure_and_recovery": True, "watchlist_time": True, "overflow": False})
                    context.close()
                browser.close()
        report["blocked"] = False
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error_summary"] = (str(exc).splitlines() or ["check failed"])[0][:300]
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return int(report["blocked"])


if __name__ == "__main__":
    raise SystemExit(main())
