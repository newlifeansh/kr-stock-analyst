from __future__ import annotations

import asyncio
import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from typing import AsyncIterator, Optional
from zoneinfo import ZoneInfo

import requests
import websockets

from app.config import Settings
from app.services.stock_dashboard import _round_decimal


KIS_REALTIME_STOCK_TR_ID = "H0UNCNT0"
KIS_STOCK_TICK_MARKETS = {
    "H0STCNT0": "KRX",
    "H0NXCNT0": "NXT",
    "H0UNCNT0": "INTEGRATED",
}
KIS_MARKET_SESSIONS = {"1": "pre_market", "2": "regular", "3": "after_market", "5": "closing_price"}


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

    def invalidate_approval_key(self, approval_key: Optional[str] = None) -> bool:
        if approval_key is not None and self._approval_key != approval_key:
            return False
        self._approval_key = None
        self._approval_expires_at = None
        return True

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
                    "tr_id": KIS_REALTIME_STOCK_TR_ID,
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
    if len(parts) < 4 or parts[1] not in KIS_STOCK_TICK_MARKETS:
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
    # Official KIS ccnl_krx/ccnl_nxt/ccnl_total share these field positions.
    # MARKET_CLS_CODE was appended on 2026-09-14. Preserve older frames, but
    # never invent a regular-session classification when the field is absent.
    business_date = fields[33] if len(fields) > 33 else ""
    try:
        trade_date = datetime.strptime(business_date, "%Y%m%d").date() if len(business_date) == 8 else None
    except ValueError:
        trade_date = None
    market_class = fields[46].strip() if len(fields) > 46 else None
    return {
        "code": fields[0],
        "trade_time": fields[1],
        "price": price,
        "change_value": int(change_value) if change_value is not None else None,
        "change_rate": _round_decimal(change_rate),
        "trade_volume": _int(fields[12]),
        "volume": volume,
        "trading_value": trading_value,
        "market_venue": KIS_STOCK_TICK_MARKETS[parts[1]],
        "trade_date": trade_date,
        "trade_date_verified": trade_date is not None,
        "market_class_code": market_class,
        "source_market_session": KIS_MARKET_SESSIONS.get(market_class, "unknown"),
    }


def kis_tick_session_fields(tick: dict[str, object], now: datetime) -> dict[str, object]:
    """Classify an actual tick, not the wall-clock phase when it was received."""
    kst = ZoneInfo("Asia/Seoul")
    current = now.replace(tzinfo=kst) if now.tzinfo is None else now.astimezone(kst)
    venue = str(tick.get("market_venue") or "UNKNOWN")
    division = {"KRX": "J", "NXT": "NX", "INTEGRATED": "UN"}.get(venue)
    phase = KIS_MARKET_SESSIONS.get(str(tick.get("market_class_code") or ""), "unknown")
    stamp = None
    try:
        if tick.get("trade_date_verified") is True:
            stamp = datetime.strptime(f'{tick["trade_date"]} {tick["trade_time"]}', "%Y-%m-%d %H%M%S").replace(tzinfo=kst)
    except (KeyError, ValueError):
        pass
    fresh = bool(stamp and stamp.date() == current.date() and -5 <= (current - stamp).total_seconds() <= 180)
    windows = {"pre_market": (time(8), time(9)), "regular": (time(9), time(15, 30)), "after_market": (time(15, 40), time(20))}
    in_session = False
    if phase in windows and stamp is not None:
        start, end = windows[phase]
        if phase == "after_market" and venue == "KRX":
            start = time(16)
        in_session = start <= stamp.time() <= end and start <= current.time() <= end
    label = {"pre_market": "프리마켓", "regular": "정규장", "after_market": "애프터마켓", "closing_price": "종가매매", "unknown": "세션 확인 중"}[phase]
    venue_label = "통합" if venue == "INTEGRATED" else venue
    return {
        "market_venue": venue, "market_division": division,
        "market_class_code": tick.get("market_class_code"), "source_market_session": phase,
        "market_session": f"{venue.lower()}_{phase}",
        "market_session_label": f"{venue_label} {label}",
        "source_as_of": stamp,
        "price_timestamp_verified": stamp is not None,
        "is_live": bool(division and fresh and in_session),
        # The outer caller also checks the exchange session calendar. Even a
        # verified price is only an input; this flag is not an execution signal.
        "regular_session_price_verified": bool(venue == "KRX" and phase == "regular" and fresh and in_session),
    }
