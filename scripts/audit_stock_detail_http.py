from __future__ import annotations

import argparse
import json
import ssl
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_CODES = ("011200", "005930", "247540", "105560", "023160", "0005D0")


class ProductionClient:
    def __init__(self, base_url: str, timeout: float, insecure: bool) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.context = ssl._create_unverified_context() if insecure else None

    def get(self, path: str) -> tuple[int, Any, float]:
        started = time.monotonic()
        request = Request(
            f"{self.base_url}{path}",
            headers={"Accept": "application/json", "User-Agent": "stock-detail-audit/1"},
        )
        try:
            with urlopen(request, timeout=self.timeout, context=self.context) as response:
                return response.status, json.load(response), time.monotonic() - started
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                payload: Any = json.loads(body)
            except ValueError:
                payload = {"detail": body[:500]}
            return exc.code, payload, time.monotonic() - started


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _request_until_ready(
    client: ProductionClient,
    path: str,
    *,
    warm_timeout: float,
    reject_warming_shell: bool = False,
) -> tuple[int, Any, float, int]:
    deadline = time.monotonic() + warm_timeout
    attempts = 0
    elapsed_total = 0.0
    while True:
        attempts += 1
        status, payload, elapsed = client.get(path)
        elapsed_total += elapsed
        warming = (
            reject_warming_shell
            and isinstance(payload, dict)
            and payload.get("source") == "stored_database_warming"
        )
        if status != 503 and not warming:
            return status, payload, elapsed_total, attempts
        if time.monotonic() >= deadline:
            return status, payload, elapsed_total, attempts
        time.sleep(2)


def _endpoint_record(status: int, seconds: float, **values: Any) -> dict[str, Any]:
    return {"status": status, "seconds": round(seconds, 3), **values}


def _validate_sga(payload: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        errors.append("sga response is not an object")
        return {}
    available = payload.get("available") is True
    categories = payload.get("categories")
    if not isinstance(categories, list):
        errors.append("sga categories is not a list")
        categories = []
    total = _number(payload.get("total_amount"))
    coverage = _number(payload.get("coverage_ratio"))
    if available:
        if total is None or total <= 0:
            errors.append(f"sga total_amount is invalid: {payload.get('total_amount')}")
        if coverage is None or not 0 <= coverage <= 105:
            errors.append(f"sga coverage_ratio is invalid: {payload.get('coverage_ratio')}")
        if not categories:
            errors.append("sga is available without categories")
    elif categories:
        errors.append("unavailable sga contains categories")
    return {
        "available": available,
        "total_amount": payload.get("total_amount"),
        "coverage_ratio": payload.get("coverage_ratio"),
        "categories": len(categories),
        "message": payload.get("message"),
    }


def audit_code(
    client: ProductionClient,
    code: str,
    *,
    warm_timeout: float,
    include_ai: bool,
) -> dict[str, Any]:
    encoded = quote(code, safe="")
    errors: list[str] = []
    endpoints: dict[str, Any] = {}

    dashboard_status, dashboard, elapsed, attempts = _request_until_ready(
        client,
        f"/stocks/{encoded}/dashboard?include_profile=0&include_live=0",
        warm_timeout=warm_timeout,
        reject_warming_shell=True,
    )
    endpoints["dashboard"] = _endpoint_record(
        dashboard_status,
        elapsed,
        attempts=attempts,
        name=dashboard.get("name") if isinstance(dashboard, dict) else None,
        as_of=dashboard.get("as_of") if isinstance(dashboard, dict) else None,
        source=dashboard.get("source") if isinstance(dashboard, dict) else None,
    )
    status, prices, elapsed = client.get(f"/stocks/{encoded}/prices?limit=1000")
    price_rows = prices if isinstance(prices, list) else []
    price_dates = sorted(
        {str(row.get("trade_date")) for row in price_rows if isinstance(row, dict) and row.get("trade_date")}
    )
    latest_price = max(
        (row for row in price_rows if isinstance(row, dict)),
        key=lambda row: str(row.get("trade_date") or ""),
        default={},
    )
    endpoints["prices"] = _endpoint_record(
        status,
        elapsed,
        rows=len(price_rows),
        days=len(price_dates),
        newest=price_dates[-1] if price_dates else None,
        oldest=price_dates[0] if price_dates else None,
    )
    if status != 200 or not isinstance(prices, list):
        errors.append(f"prices failed with HTTP {status}")
    elif not price_rows:
        errors.append("prices is empty")
    else:
        values = {key: _number(latest_price.get(key)) for key in ("open", "high", "low", "close")}
        if any(value is None or value <= 0 for value in values.values()):
            errors.append(f"latest OHLC is incomplete: {values}")
        elif not (
            values["low"] <= values["open"] <= values["high"]
            and values["low"] <= values["close"] <= values["high"]
        ):
            errors.append(f"latest OHLC is inconsistent: {values}")
        if price_dates[-1] > datetime.now(timezone.utc).date().isoformat():
            errors.append(f"future price date: {price_dates[-1]}")

    dashboard_quote_date = (
        str((dashboard.get("quote") or {}).get("trade_date") or "")
        if isinstance(dashboard, dict)
        else ""
    )
    if price_dates and dashboard_quote_date != price_dates[-1]:
        deadline = time.monotonic() + warm_timeout
        while time.monotonic() < deadline:
            time.sleep(2)
            retry_status, retry_payload, retry_elapsed = client.get(
                f"/stocks/{encoded}/dashboard?include_profile=0&include_live=0"
            )
            dashboard_status = retry_status
            endpoints["dashboard"]["status"] = retry_status
            endpoints["dashboard"]["attempts"] += 1
            endpoints["dashboard"]["seconds"] = round(
                endpoints["dashboard"]["seconds"] + retry_elapsed,
                3,
            )
            if retry_status == 200 and isinstance(retry_payload, dict):
                dashboard = retry_payload
                dashboard_quote_date = str(
                    (dashboard.get("quote") or {}).get("trade_date") or ""
                )
                endpoints["dashboard"].update(
                    {
                        "as_of": dashboard.get("as_of"),
                        "source": dashboard.get("source"),
                    }
                )
                if dashboard_quote_date == price_dates[-1]:
                    break
    endpoints["dashboard"]["quote_date"] = dashboard_quote_date or None
    if dashboard_status != 200 or not isinstance(dashboard, dict):
        errors.append(f"dashboard failed with HTTP {dashboard_status}")
    elif dashboard.get("code") != code:
        errors.append(f"dashboard code mismatch: {dashboard.get('code')}")
    if price_dates and dashboard_quote_date != price_dates[-1]:
        errors.append(
            f"dashboard quote date {dashboard_quote_date or None} does not match "
            f"price date {price_dates[-1]}"
        )

    status, flows, elapsed = client.get(f"/stocks/{encoded}/flows?limit=1500")
    flow_rows = flows if isinstance(flows, list) else []
    flow_dates = sorted(
        {str(row.get("trade_date")) for row in flow_rows if isinstance(row, dict) and row.get("trade_date")}
    )
    if status == 200 and len(flow_dates) < 66:
        status, flows, expanded_elapsed = client.get(
            f"/stocks/{encoded}/flows?limit=1500&refresh=true&pages=4"
        )
        elapsed += expanded_elapsed
        flow_rows = flows if isinstance(flows, list) else []
        flow_dates = sorted(
            {
                str(row.get("trade_date"))
                for row in flow_rows
                if isinstance(row, dict) and row.get("trade_date")
            }
        )
    latest_types = sorted(
        {
            str(row.get("investor_type"))
            for row in flow_rows
            if isinstance(row, dict)
            and flow_dates
            and str(row.get("trade_date")) == flow_dates[-1]
        }
    )
    endpoints["flows"] = _endpoint_record(
        status,
        elapsed,
        rows=len(flow_rows),
        days=len(flow_dates),
        newest=flow_dates[-1] if flow_dates else None,
        oldest=flow_dates[0] if flow_dates else None,
        newest_types=latest_types,
    )
    if status != 200 or not isinstance(flows, list):
        errors.append(f"flows failed with HTTP {status}")
    elif len(flow_dates) < 7:
        errors.append(f"flows has only {len(flow_dates)} trading days")
    else:
        if not {"외국인", "기관합계"}.issubset(latest_types):
            errors.append(f"latest flow pair is incomplete: {latest_types}")
        if price_dates and flow_dates[-1] != price_dates[-1]:
            errors.append(
                f"flow date {flow_dates[-1]} does not match price date {price_dates[-1]}"
            )

    home_path = (
        f"/stocks/{encoded}/home-context?flow_limit=1500&research_limit=100"
        "&disclosure_limit=100&news_limit=60&community_limit=12"
    )
    status, home, elapsed, attempts = _request_until_ready(
        client,
        home_path,
        warm_timeout=warm_timeout,
    )
    home_counts = {
        key: len(home.get(key) or [])
        for key in ("flows", "research_reports", "disclosures", "news_items")
        if isinstance(home, dict)
    }
    endpoints["home_context"] = _endpoint_record(
        status,
        elapsed,
        attempts=attempts,
        **home_counts,
    )
    if status != 200 or not isinstance(home, dict):
        errors.append(f"home-context failed with HTTP {status}")
    elif home.get("code") != code:
        errors.append(f"home-context code mismatch: {home.get('code')}")

    simple_paths = {
        "intraday": f"/stocks/{encoded}/intraday?limit=390",
        "financials": f"/stocks/{encoded}/financials?limit=500",
        "sector_margins": f"/stocks/{encoded}/sector-operating-margins?limit=5&per_pair=1",
        "sga": f"/stocks/{encoded}/sga-analysis",
        "community": f"/stocks/{encoded}/community-feed?limit=12",
    }
    simple_payloads: dict[str, Any] = {}
    for label, path in simple_paths.items():
        status, payload, elapsed = client.get(path)
        simple_payloads[label] = payload
        record: dict[str, Any] = {}
        if isinstance(payload, list):
            record["rows"] = len(payload)
        elif isinstance(payload, dict):
            if isinstance(payload.get("points"), list):
                record["points"] = len(payload["points"])
            if isinstance(payload.get("providers"), list):
                record["providers"] = len(payload["providers"])
            if isinstance(payload.get("companies"), list):
                record["companies"] = len(payload["companies"])
        endpoints[label] = _endpoint_record(status, elapsed, **record)
        if status != 200:
            errors.append(f"{label} failed with HTTP {status}")

    intraday = simple_payloads.get("intraday")
    if isinstance(intraday, dict) and (
        intraday.get("code") != code or not isinstance(intraday.get("points"), list)
    ):
        errors.append("intraday contract is invalid")
    financials = simple_payloads.get("financials")
    if not isinstance(financials, list):
        errors.append("financials response is not a list")
    margins = simple_payloads.get("sector_margins")
    if not isinstance(margins, dict) or margins.get("code") != code:
        errors.append("sector margins contract is invalid")
    community = simple_payloads.get("community")
    if not isinstance(community, dict) or not isinstance(community.get("providers"), list):
        errors.append("community contract is invalid")
    endpoints["sga"].update(_validate_sga(simple_payloads.get("sga"), errors))

    if include_ai:
        for label, path in (
            ("ai", f"/stocks/{encoded}/ai-analysis"),
            ("quant", f"/stocks/{encoded}/quant-signals"),
        ):
            status, payload, elapsed = client.get(path)
            endpoints[label] = _endpoint_record(
                status,
                elapsed,
                state=payload.get("data_state") if isinstance(payload, dict) else None,
            )
            if status != 200 or not isinstance(payload, dict):
                errors.append(f"{label} failed with HTTP {status}")
            elif payload.get("code") != code:
                errors.append(f"{label} code mismatch: {payload.get('code')}")
            elif label == "ai" and not str(payload.get("summary") or "").strip():
                errors.append("ai summary is empty")
            elif label == "quant" and payload.get("data_state") not in {"ready", "limited"}:
                errors.append(f"quant data_state is {payload.get('data_state')}")

    return {"code": code, "ok": not errors, "errors": errors, "endpoints": endpoints}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit every stock-detail HTTP dataset for a production cohort."
    )
    parser.add_argument("--base-url", default="https://secretnote.cloud")
    parser.add_argument("--codes", default=",".join(DEFAULT_CODES))
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--warm-timeout", type=float, default=30)
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument("--skip-ai", action="store_true")
    args = parser.parse_args()
    codes = [item.strip().upper() for item in args.codes.split(",") if item.strip()]
    client = ProductionClient(args.base_url, max(1, args.timeout), args.insecure)
    results = [
        audit_code(
            client,
            code,
            warm_timeout=max(0, args.warm_timeout),
            include_ai=not args.skip_ai,
        )
        for code in codes
    ]
    print(
        json.dumps(
            {
                "base_url": args.base_url,
                "codes": len(results),
                "passed": sum(1 for item in results if item["ok"]),
                "failed": sum(1 for item in results if not item["ok"]),
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )
    raise SystemExit(1 if any(not item["ok"] for item in results) else 0)


if __name__ == "__main__":
    main()
