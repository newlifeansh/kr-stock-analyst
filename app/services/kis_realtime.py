from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncIterator, Optional

import requests
import websockets

from app.config import Settings
from app.services.stock_dashboard import _round_decimal


class KisRealtimeError(RuntimeError):
    pass


class KisRealtimeQuoteProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._approval_key: Optional[str] = None
        self._approval_expires_at: Optional[datetime] = None

    def is_configured(self) -> bool:
        return bool(self.settings.kis_realtime_enabled and self.settings.kis_app_key and self.settings.kis_app_secret)

    def _rest_base_url(self) -> str:
        if self.settings.kis_env == "demo":
            return "https://openapivts.koreainvestment.com:29443"
        return "https://openapi.koreainvestment.com:9443"

    def _websocket_url(self) -> str:
        if self.settings.kis_env == "demo":
            return "ws://ops.koreainvestment.com:31000"
        return "ws://ops.koreainvestment.com:21000"

    def _fetch_approval_key_sync(self) -> str:
        now = datetime.utcnow()
        if self._approval_key and self._approval_expires_at and self._approval_expires_at > now + timedelta(minutes=5):
            return self._approval_key
        response = requests.post(
            f"{self._rest_base_url()}/oauth2/Approval",
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key,
                "secretkey": self.settings.kis_app_secret,
            },
            headers={"content-type": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        approval_key = payload.get("approval_key")
        if not approval_key:
            raise KisRealtimeError(payload.get("msg1") or "KIS approval_key 발급 실패")
        self._approval_key = approval_key
        self._approval_expires_at = now + timedelta(hours=20)
        return approval_key

    async def approval_key(self) -> str:
        return await asyncio.to_thread(self._fetch_approval_key_sync)

    async def quote_stream(self, code: str) -> AsyncIterator[dict[str, object]]:
        if not self.is_configured():
            raise KisRealtimeError("KIS realtime is not configured")
        approval_key = await self.approval_key()
        subscribe = {
            "header": {
                "approval_key": approval_key,
                "custtype": "P",
                "tr_type": "1",
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": "H0STCNT0",
                    "tr_key": code,
                }
            },
        }
        async with websockets.connect(self._websocket_url(), ping_interval=20, ping_timeout=20, close_timeout=5) as websocket:
            await websocket.send(json.dumps(subscribe, ensure_ascii=False))
            async for raw in websocket:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="ignore")
                if not raw:
                    continue
                if raw.startswith("{"):
                    message = json.loads(raw)
                    if message.get("header", {}).get("tr_id") == "PINGPONG":
                        await websocket.send(raw)
                        continue
                    body = message.get("body") or {}
                    if body.get("rt_cd") not in (None, "0"):
                        raise KisRealtimeError(body.get("msg1") or body.get("msg_cd") or "KIS realtime request failed")
                    continue
                quote = parse_kis_stock_tick(raw)
                if quote and quote.get("code") == code:
                    yield quote


def _decimal(value: str) -> Optional[Decimal]:
    if value in ("", None):
        return None
    try:
        return Decimal(str(value).strip())
    except Exception:
        return None


def _signed_decimal(sign: str, value: str) -> Optional[Decimal]:
    number = _decimal(value)
    if number is None:
        return None
    if sign in {"4", "5"}:
        return -abs(number)
    if sign == "3":
        return Decimal("0")
    return abs(number)


def _int(value: str) -> Optional[int]:
    number = _decimal(value)
    return int(number) if number is not None else None


def parse_kis_stock_tick(raw: str) -> Optional[dict[str, object]]:
    parts = raw.split("|", 3)
    if len(parts) < 4 or parts[1] != "H0STCNT0":
        return None
    fields = parts[3].split("^")
    if len(fields) < 15:
        return None
    sign = fields[3]
    price = _int(fields[2])
    change_value = _signed_decimal(sign, fields[4])
    change_rate = _signed_decimal(sign, fields[5])
    volume = _int(fields[13])
    trading_value = _int(fields[14])
    return {
        "code": fields[0],
        "trade_time": fields[1],
        "price": price,
        "change_value": int(change_value) if change_value is not None else None,
        "change_rate": _round_decimal(change_rate),
        "volume": volume,
        "trading_value": trading_value,
    }
