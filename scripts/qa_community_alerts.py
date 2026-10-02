"""Read-only staging acceptance. No real subscriptions, pushes or orders."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


# Runs deployed worker handlers in a browser JS realm with notification and
# window effects replaced. It never grants notification permission.
WORKER_PROBE = """async ({source, url, origin}) => {
  const handlers = {}, opened = [], shown = [];
  const fake = {location: {origin}, addEventListener: (k, v) => handlers[k] = v,
    clients: {openWindow: async u => {opened.push(u);}, matchAll: async () => []},
    registration: {showNotification: async (title, data) => shown.push(data)}};
  new Function('self', source)(fake);
  let pending;
  handlers.push({data: {json: () => ({url, kind: 'community_popular', title: 'Test'})},
    waitUntil: p => {pending = p;}});
  await pending;
  handlers.notificationclick({notification: {data: shown[0].data, close() {}},
    waitUntil: p => {pending = p;}});
  await pending;
  if (opened.length !== 1 || opened[0] !== url) throw new Error('community original URL lost');
  return {original_url: true, actual_pushes: 0};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--market", choices=["us", "kr"], required=True)
    parser.add_argument("--mode", choices=["live", "e2e"], required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    prefix = "/us" if args.market == "us" else ""
    report = dict(qa_id="NOTIFY-COM-003", mode=args.mode, market=args.market, blocked=True)
    try:
        r = requests.get(base+prefix+"/market/community-alerts", timeout=20)
        r.raise_for_status()
        p = r.json()
        assert p["implementation_digest"] == args.expected_digest, "wrong candidate"
        assert p["market"] == args.market and p["mode"] == "shadow", "market/mode mismatch"
        assert p["state"] == "preview", "ranking or today's popular post unavailable"
        assert p["delivery_counts"] == {}, "shadow must never send"
        assert r.headers.get("cache-control") == "no-store", "stale cache possible"
        stamp = datetime.fromisoformat(p["digest"]["prepared_at"])
        assert stamp.astimezone(ZoneInfo("Asia/Seoul")).date() == datetime.now(ZoneInfo("Asia/Seoul")).date(), "stale preview"
        assert not any(k in r.text for k in ('"endpoint"', '"p256dh"', '"auth"', '"subscription_id"')), "private fields"
        report["snapshot"] = p
        if args.mode == "e2e":
            from playwright.sync_api import sync_playwright
            path = "/us-sw.js" if args.market == "us" else "/dashboard-sw.js"
            sw = requests.get(base+path, timeout=20)
            sw.raise_for_status()
            with sync_playwright() as play:
                browser = play.chromium.launch()
                page = browser.new_page()
                response = page.goto(base+prefix+"/market/community-alerts")
                assert response.status == 200
                report["browser"] = page.evaluate(WORKER_PROBE, dict(source=sw.text, url=p["digest"]["post"]["url"], origin=base))
                browser.close()
        report["blocked"] = False
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["error_summary"] = (str(exc).splitlines() or ["check failed"])[0][:250]
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False))
    return int(report["blocked"])


if __name__ == "__main__":
    raise SystemExit(main())
