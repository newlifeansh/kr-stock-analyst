"""Scoped read-only live/browser QA; never creates a signal or push subscription."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["live", "e2e"], required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--market", choices=["kr", "us"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-digest")
    args = parser.parse_args()
    prefix = "/us" if args.market == "us" else ""
    base = args.base_url.rstrip("/")
    report = {"qa_id": "SIG-INTRA-004", "mode": args.mode, "market": args.market,
              "base_url": base, "checks": [], "deployment_blocked": True}
    try:
        response = requests.get(base+prefix+"/market/intraday-signals", timeout=20)
        response.raise_for_status()
        payload = response.json()
        assert payload["strategy_version"] == "intraday-top100-v1-rc1"
        assert payload["market"] == args.market
        if args.expected_digest:
            assert payload["implementation_digest"] == args.expected_digest
        assert payload["mode"] == "shadow", "staging must not send user alerts"
        assert response.headers.get("cache-control") == "no-store"
        assert payload["monitor"]["state"] in ("closed", "monitoring"), "collector unavailable or degraded"
        report["checks"].append({"api": "pass", "monitor": payload["monitor"]})
        monitor = payload["monitor"]
        report["regular_session_verified"] = bool(
            monitor["state"] == "monitoring" and monitor.get("universe_count") == 100
            and monitor.get("evaluated", 0) >= 100)
        report["production_ready"] = False  # device delivery and exact-candidate approval still required
        if args.mode == "e2e":
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for width, theme in [(320,"light"), (458,"dark"), (1280,"light")]:
                    page = browser.new_page(viewport={"width":width,"height":900},color_scheme=theme)
                    page.goto(base+prefix+"/intraday-alerts",wait_until="networkidle")
                    page.locator("#state").filter(has_text="시험 모드").wait_for()
                    assert page.locator("#heading").inner_text().startswith("미국" if args.market=="us" else "국내")
                    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
                    page.locator("#refresh").focus()
                    page.keyboard.press("Enter")
                    from playwright.sync_api import expect
                    expect(page.locator("#refresh")).to_be_enabled()
                    # Simulate a failed fetch and ensure the old success label
                    # cannot remain visible as if collection were healthy.
                    page.route("**/market/intraday-signals",lambda route:route.fulfill(status=503,body="{}"))
                    page.locator("#refresh").click()
                    page.locator("#state").filter(has_text="상태 조회 실패").wait_for()
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    page.screenshot(path=str(args.output.with_name(f"{args.market}-{width}-{theme}.png")),full_page=True)
                    report["checks"].append({"width":width,"theme":theme,"overflow":False,"failure_state":"pass"})
                    page.close()
                browser.close()
        report["deployment_blocked"] = False
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        # This probe reads public pages only; keep the first diagnostic line,
        # never browser storage, cookies, headers, or credentials.
        report["error_summary"] = str(exc).splitlines()[0][:300]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False))
    return int(report["deployment_blocked"])


if __name__ == "__main__":
    raise SystemExit(main())
