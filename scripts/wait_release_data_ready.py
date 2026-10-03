#!/usr/bin/env python3
"""Wait until a staged or promoted surface has current critical datasets."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def dashboard_readiness(payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    datasets = payload.get("datasets") if isinstance(payload.get("datasets"), dict) else {}
    news = datasets.get("news") if isinstance(datasets.get("news"), dict) else {}
    stock_news = (
        datasets.get("stock_news")
        if isinstance(datasets.get("stock_news"), dict)
        else {}
    )
    summary = {
        "status": payload.get("status"),
        "as_of": payload.get("as_of"),
        "news_state": news.get("state"),
        "news_latest_published_at": news.get("latest_published_at"),
        "stock_news_state": stock_news.get("state"),
        "stock_news_covered": stock_news.get("covered"),
        "stock_news_total": stock_news.get("total"),
        "stock_news_last_success_at": (stock_news.get("api") or {}).get(
            "last_success_at"
        ),
    }
    ready = bool(
        payload.get("status") == "ready"
        and news.get("state") == "ready"
        and stock_news.get("state") == "ready"
        and int(stock_news.get("total") or 0) > 0
        and stock_news.get("covered") == stock_news.get("total")
    )
    return ready, summary


def us_readiness(
    quant_payload: dict[str, Any],
    recommendation_payload: dict[str, Any],
) -> tuple[bool, dict[str, Any]]:
    recommendations = recommendation_payload.get("items")
    recommendation_count = len(recommendations) if isinstance(recommendations, list) else 0
    summary = {
        "status": quant_payload.get("status"),
        "data_state": quant_payload.get("data_state"),
        "snapshot_id": quant_payload.get("snapshot_id"),
        "snapshot_generated_at": quant_payload.get("snapshot_generated_at"),
        "universe_as_of": quant_payload.get("universe_as_of"),
        "universe_count": quant_payload.get("universe_count"),
        "evaluated_count": quant_payload.get("evaluated_count"),
        "data_coverage_count": quant_payload.get("data_coverage_count"),
        "schema_upgrade_required": quant_payload.get("schema_upgrade_required"),
        "sector_classification_version": quant_payload.get(
            "sector_classification_version"
        ),
        "recommendation_status": recommendation_payload.get("status"),
        "recommendation_data_state": recommendation_payload.get("data_state"),
        "recommendation_count": recommendation_count,
    }
    ready = bool(
        quant_payload.get("status") == "ready"
        and quant_payload.get("data_state") == "ready"
        and quant_payload.get("schema_upgrade_required") is not True
        and quant_payload.get("universe_count") == 100
        and quant_payload.get("evaluated_count") == 100
        and quant_payload.get("data_coverage_count") == 100
        and bool(quant_payload.get("snapshot_id"))
        and recommendation_payload.get("status") == "ready"
        and recommendation_payload.get("data_state") == "ready"
        and recommendation_count > 0
    )
    return ready, summary


def _get_json(url: str, *, timeout: float = 20.0) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "secret-note-release-readiness/1.0",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected an object from {url}")
    return payload


def wait_for_readiness(
    *,
    surface: str,
    base_url: str,
    wait_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    normalized_base = base_url.rstrip("/")
    deadline = time.monotonic() + max(1, wait_seconds)
    attempt = 0
    last_summary: dict[str, Any] = {}
    last_error: str | None = None
    while True:
        attempt += 1
        try:
            if surface == "dashboard":
                payload = _get_json(f"{normalized_base}/meta/signal-data-quality")
                ready, last_summary = dashboard_readiness(payload)
            else:
                prefix = "/us-gateway" if surface == "us-gateway" else ""
                quant_payload = _get_json(
                    f"{normalized_base}{prefix}/us/market/quant-signals?limit=1"
                )
                recommendation_payload = _get_json(
                    f"{normalized_base}{prefix}/us/market/recommendations?limit=1"
                )
                ready, last_summary = us_readiness(
                    quant_payload,
                    recommendation_payload,
                )
            last_error = None
            print(
                json.dumps(
                    {"attempt": attempt, "ready": ready, **last_summary},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
            if ready:
                return {
                    "status": "ready",
                    "surface": surface,
                    "base_url": normalized_base,
                    "attempts": attempt,
                    "evidence": last_summary,
                }
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            print(
                json.dumps(
                    {"attempt": attempt, "ready": False, "error": last_error},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                flush=True,
            )
        if time.monotonic() >= deadline:
            return {
                "status": "timeout",
                "surface": surface,
                "base_url": normalized_base,
                "attempts": attempt,
                "error": last_error,
                "evidence": last_summary,
            }
        time.sleep(max(1, poll_seconds))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--surface",
        choices=("dashboard", "us", "us-gateway"),
        required=True,
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = wait_for_readiness(
        surface=args.surface,
        base_url=args.base_url,
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
