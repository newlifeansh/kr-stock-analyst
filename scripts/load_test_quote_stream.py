#!/usr/bin/env python3
"""Ramp concurrent browser-style quote streams and report connection health."""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from urllib.parse import urlparse, urlunparse

import websockets


DEFAULT_CODES = "005930,000660,035420,005380,105560"


@dataclass
class ClientResult:
    client_id: int
    connected: bool = False
    subscribed: bool = False
    quote_received: bool = False
    connect_ms: float | None = None
    messages: int = 0
    error: str | None = None


def websocket_url(value: str) -> str:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    scheme = "wss" if parsed.scheme in {"https", "wss"} else "ws"
    path = parsed.path.rstrip("/")
    if not path or path == "/":
        path = "/ws/quotes"
    elif path != "/ws/quotes":
        path = f"{path}/ws/quotes"
    return urlunparse((scheme, parsed.netloc, path, "", "", ""))


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(len(ordered) * fraction) - 1))
    return round(ordered[index], 2)


async def run_client(
    client_id: int,
    *,
    url: str,
    codes: list[str],
    codes_per_client: int,
    ramp_per_second: float,
    hold_seconds: float,
    open_timeout: float,
) -> ClientResult:
    result = ClientResult(client_id=client_id)
    if ramp_per_second > 0:
        await asyncio.sleep(client_id / ramp_per_second)
    started_at = time.monotonic()
    selected = [
        codes[(client_id + offset) % len(codes)]
        for offset in range(min(codes_per_client, len(codes)))
    ]
    try:
        async with websockets.connect(
            url,
            open_timeout=open_timeout,
            close_timeout=3,
            ping_interval=20,
            ping_timeout=20,
            max_queue=16,
        ) as socket:
            result.connected = True
            result.connect_ms = round((time.monotonic() - started_at) * 1000, 2)
            ready = json.loads(await asyncio.wait_for(socket.recv(), timeout=open_timeout))
            if ready.get("type") != "ready":
                raise RuntimeError(f"expected ready, received {ready.get('type')!r}")
            await socket.send(json.dumps({"type": "set", "codes": selected}))

            deadline = time.monotonic() + hold_seconds
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    raw = await asyncio.wait_for(socket.recv(), timeout=min(remaining, 10))
                except asyncio.TimeoutError:
                    continue
                message = json.loads(raw)
                result.messages += 1
                if message.get("type") == "subscribed":
                    result.subscribed = True
                elif message.get("type") == "quote":
                    result.quote_received = True
                elif message.get("type") == "error":
                    raise RuntimeError(str(message.get("message") or "stream error"))
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"[:300]
    return result


async def main_async(args: argparse.Namespace) -> int:
    codes = list(dict.fromkeys(code.strip() for code in args.codes.split(",") if code.strip()))
    if not codes:
        raise ValueError("At least one stock code is required")
    url = websocket_url(args.url)
    started_at = time.monotonic()
    results = await asyncio.gather(
        *(
            run_client(
                client_id,
                url=url,
                codes=codes,
                codes_per_client=max(1, args.codes_per_client),
                ramp_per_second=max(0, args.ramp_per_second),
                hold_seconds=max(1, args.hold_seconds),
                open_timeout=max(1, args.open_timeout),
            )
            for client_id in range(args.clients)
        )
    )
    elapsed = time.monotonic() - started_at
    healthy = [
        result
        for result in results
        if result.connected
        and result.subscribed
        and (result.quote_received or not args.require_quote)
        and result.error is None
    ]
    connection_times = [result.connect_ms for result in results if result.connect_ms is not None]
    failures = [asdict(result) for result in results if result not in healthy]
    report = {
        "target": url,
        "clients": args.clients,
        "codes": codes,
        "codes_per_client": min(max(1, args.codes_per_client), len(codes)),
        "elapsed_seconds": round(elapsed, 2),
        "healthy_clients": len(healthy),
        "success_ratio": round(len(healthy) / max(1, len(results)), 4),
        "quotes_received_clients": sum(result.quote_received for result in results),
        "messages": sum(result.messages for result in results),
        "connect_ms": {
            "p50": percentile(connection_times, 0.50),
            "p95": percentile(connection_times, 0.95),
            "max": round(max(connection_times), 2) if connection_times else None,
        },
        "failure_sample": failures[:10],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["success_ratio"] >= args.min_success_ratio else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Base URL or full /ws/quotes URL")
    parser.add_argument("--clients", type=int, default=300)
    parser.add_argument("--codes", default=DEFAULT_CODES)
    parser.add_argument("--codes-per-client", type=int, default=5)
    parser.add_argument("--ramp-per-second", type=float, default=50)
    parser.add_argument("--hold-seconds", type=float, default=20)
    parser.add_argument("--open-timeout", type=float, default=20)
    parser.add_argument("--min-success-ratio", type=float, default=0.99)
    parser.add_argument("--require-quote", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main_async(parse_args())))
    except KeyboardInterrupt:
        print("load test interrupted", file=sys.stderr)
        raise SystemExit(130)
