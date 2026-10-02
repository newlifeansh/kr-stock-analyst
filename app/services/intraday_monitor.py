"""Collector-owned Top100 polling; independent of browser/push subscriptions."""
from __future__ import annotations

import asyncio
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import json
import logging
import threading
from zoneinfo import ZoneInfo

from sqlalchemy import select, desc, text

from app.db import SessionLocal
from app.models import DailyPrice, StockMaster, PushSubscription
from app.services.intraday_signals import (
    VERSION, IntradayState, IntradayEvent, IntradayMinute, Minute, encode, record,
)

logger = logging.getLogger(__name__)
UTC = timezone.utc
KST = ZoneInfo("Asia/Seoul")
NY = ZoneInfo("America/New_York")


def session_bounds(market, now):
    if market == "us":
        from app.services.us_market_calendar import us_market_session, latest_completed_us_market_session
        session = us_market_session(now.astimezone(NY).date())
        previous = latest_completed_us_market_session(now).session_date
        if session and session.open_at <= now < session.close_at:
            return session.open_at, session.close_at, previous
        return None
    from app.services.market_calendar import (
        is_korea_regular_market_session, latest_completed_korea_market_session_date,
    )
    local = now.astimezone(KST)
    if not is_korea_regular_market_session(local):
        return None
    previous = latest_completed_korea_market_session_date(local)
    if previous is None:
        return None
    return (local.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(UTC),
            local.replace(hour=15, minute=30, second=0, microsecond=0).astimezone(UTC), previous)


def universe(db, market, previous):
    if market == "us":
        from app.services.us_signal_universe import load_us_signal_universe_snapshot_for_date
        payload = load_us_signal_universe_snapshot_for_date(db, previous)
        items = list((payload or {}).get("items") or [])
    else:
        rows = db.execute(select(StockMaster, DailyPrice.market_cap).join(
            DailyPrice, DailyPrice.code == StockMaster.code
        ).where(DailyPrice.trade_date == previous, DailyPrice.market_cap > 0,
                StockMaster.is_active.is_(True),
                StockMaster.market.in_(("KOSPI", "KOSDAQ")))
            .order_by(desc(DailyPrice.market_cap), StockMaster.code).limit(100)).all()
        items = [dict(code=s.code, name=s.name, exchange=s.market) for s, _ in rows]
    if len(items) != 100 or len({x["code"] for x in items}) != 100:
        raise ValueError("top100_incomplete")
    return items


def normalize_bars(rows, market):
    output = []
    for r in rows:
        if market == "kr":
            stamp = datetime.strptime(r["stck_bsop_date"] + r["stck_cntg_hour"], "%Y%m%d%H%M%S").replace(tzinfo=KST)
            values = [r[k] for k in ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_prpr", "cntg_vol")]
        else:
            stamp = datetime.strptime(r["xymd"] + r["xhms"], "%Y%m%d%H%M%S").replace(tzinfo=NY)
            values = [r[k] for k in ("open", "high", "low", "last", "evol")]
        row = Minute(stamp.astimezone(UTC), *(float(v) for v in values))
        if not row.valid():
            raise ValueError("invalid_bars")
        output.append(row)
    return output


class IntradayMonitor:
    def __init__(self, settings, provider, push_runtime):
        self.settings, self.provider, self.push = settings, provider, push_runtime
        self.task = None
        self.contexts = {}
        self.histories = {}
        self.cache_session = None
        self.cycle_lock = threading.Lock()

    async def start(self):
        if self.settings.intraday_signal_mode != "off" and self.task is None:
            self.task = asyncio.create_task(self.loop())

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def loop(self):
        while True:
            try:
                await asyncio.to_thread(self.run_once)
            except Exception:
                # Source exceptions can contain credentials/URLs: no raw trace.
                logger.warning("Intraday cycle failed; no confirmed readiness")
            await asyncio.sleep(max(10, self.settings.intraday_signal_poll_seconds))

    def bars(self, market, item, now):
        if market == "kr":
            data = self.provider._get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice", "FHKST03010200",
                {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": item["code"],
                 "FID_INPUT_HOUR_1": now.astimezone(KST).strftime("%H%M%S"),
                 "FID_PW_DATA_INCU_YN": "N", "FID_ETC_CLS_CODE": ""})
        else:
            exchange = {"NASDAQ": "NAS", "NYSE": "NYS", "NAS": "NAS", "NYS": "NYS"}.get(str(item.get("exchange", "")).upper())
            if not exchange:
                raise ValueError("unknown_exchange")
            symbol = item["code"].replace(".", "/")
            data = self.provider._get(
                "/uapi/overseas-price/v1/quotations/inquire-time-itemchartprice", "HHDFS76950200",
                {"AUTH": "", "EXCD": exchange, "SYMB": symbol, "NMIN": "1",
                 "PINC": "0", "NEXT": "", "NREC": "30", "FILL": "", "KEYB": ""})
            identity = str((data.get("output1") or {}).get("rsym") or "")
            if identity not in {exchange + symbol, "D" + exchange + symbol, "R" + exchange + symbol}:
                raise ValueError("source_identity_mismatch")
        return normalize_bars(data.get("output2") or [], market)

    def context(self, market, item, bounds):
        opened, closed, previous = bounds
        cache_key = (market, item["code"], opened.isoformat())
        if cache_key in self.contexts:
            return self.contexts[cache_key]
        from app.services import quant_signals as qs
        with SessionLocal() as db:
            if market == "kr":
                prices = list(db.scalars(select(DailyPrice).where(
                    DailyPrice.code == item["code"], DailyPrice.trade_date <= previous
                ).order_by(DailyPrice.trade_date.desc()).limit(260)))[::-1]
                bars = qs._normalize_prices(prices)
                if len(bars) < 125 or bars[-1].trade_date != previous:
                    return {"ready": False}
                technical = qs._indicator_rows(bars)[-1]
                from app.services.signal_entry_evidence import load_entry_evidence_timeline, entry_confirmation_decision
                evidence = load_entry_evidence_timeline(db, item["code"]).get(previous)
                allowed = entry_confirmation_decision(evidence, "trend_continuation", signal_date=previous)["allowed"]
            else:
                from app.services.us_position_lifecycle import (
                    _history_loader, _sector_etf, evaluate_us_entry_candidate, us_price_bars,
                )
                def history(code):
                    key = (code, previous)
                    if key not in self.histories:
                        self.histories[key] = us_price_bars(
                            [r for r in _history_loader(code) if r.trade_date <= previous],
                            now=opened, market_session="regular")
                    return self.histories[key]
                bars = history(item["code"])
                if not bars or bars[-1].trade_date != previous:
                    return {"ready": False}
                result = evaluate_us_entry_candidate(
                    bars, history("SPY"), history("QQQ"), history(_sector_etf(item)))
                technical = result.get("technical") or {}
                allowed = bool((result.get("confirmation") or {}).get("allowed"))
        result = dict(technical, ready=bool(technical), evidence_allowed=allowed,
                      previous_close=bars[-1].close, session_open=opened.isoformat(),
                      evidence_as_of=previous.isoformat())
        self.contexts[cache_key] = result
        return result

    def status(self, market, payload):
        with SessionLocal() as db:
            key = f"monitor:{market}"
            row = db.get(IntradayState, key)
            if row is None:
                row = IntradayState(key=key, payload="{}", updated_at=datetime.utcnow())
                db.add(row)
            row.payload = encode(dict(payload, strategy_version=VERSION,
                mode=self.settings.intraday_signal_mode,
                provider_ready=bool(self.provider.is_configured()),
                push_ready=bool(self.push.configured),
                observed_at=datetime.now(UTC).isoformat()))
            row.updated_at = datetime.utcnow()
            db.commit()

    def run_once(self, now=None):
        if self.settings.intraday_signal_mode == "off":
            return
        if not self.cycle_lock.acquire(blocking=False):
            return
        # Cross-replica ownership for the production PostgreSQL collectors.
        # Keep the physical connection until unlock; returning a locked pooled
        # connection would leave an invisible lease after a failed cycle.
        connection = None
        acquired = False
        try:
            from app.db import engine
            if engine.dialect.name == "postgresql":
                connection = engine.connect()
                acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(73100421)")))
                if not acquired:
                    return
            return self._run_once(now)
        finally:
            if connection is not None:
                try:
                    if acquired:
                        connection.execute(text("SELECT pg_advisory_unlock(73100421)"))
                finally:
                    connection.close()
            self.cycle_lock.release()

    def _run_once(self, now=None):
        fixed_clock = now is not None
        now = now or datetime.now(UTC)
        mode = self.settings.intraday_signal_mode
        if mode == "off":
            return
        # Independent deployments own one market each; never scan another
        # market's DB or infer its collector is running from gateway health.
        market = "us" if self.settings.us_market_enabled else "kr"
        try:
            bounds = session_bounds(market, now)
        except Exception:
            self.status(market, {"state": "unavailable", "reason": "calendar_unavailable"})
            return
        if bounds is None:
            self.status(market, {"state": "closed", "evaluated": 0})
            return
        if self.cache_session != bounds[0]:
            self.contexts.clear()
            self.histories.clear()
            self.cache_session = bounds[0]
        if not self.provider.is_configured():
            self.status(market, {"state": "unavailable", "reason": "provider_not_configured"})
            return
        with SessionLocal() as db:
            try:
                items = universe(db, market, bounds[2])
                universe_ready = True
            except Exception:
                items, universe_ready = [], False
            # Open positions remain monitored after dropping out of Top100 or
            # during a universe refresh outage. New buys then fail closed.
            states = db.scalars(select(IntradayState).where(
                IntradayState.key.like(f"{VERSION}:{mode}:{market}:%")))
            retained = [json.loads(r.payload).get("member") for r in states
                        if json.loads(r.payload).get("remaining", 0) > 0]
        codes = {item["code"] for item in items}
        scan = {item["code"]: item for item in [*items, *[r for r in retained if r]]}
        held_codes = {item["code"] for item in retained if item}
        counts = Counter()
        started = datetime.now(UTC)
        # Rate limiting remains centralized in the existing KIS provider.
        with ThreadPoolExecutor(max_workers=4) as executor:
            ordered = sorted(scan.values(), key=lambda item: (item["code"] not in held_codes, item["code"]))
            jobs = {executor.submit(self.bars, market, item, now): item for item in ordered}
            for job in as_completed(jobs):
                item = jobs[job]
                try:
                    minutes = job.result()
                    with SessionLocal() as db:
                        existing = db.get(IntradayState, f"{VERSION}:{mode}:{market}:{item['code']}")
                        held = bool(existing and json.loads(existing.payload).get("remaining", 0) > 0)
                    context = self.context(market, item, bounds) if item["code"] in codes and not held else {}
                    observed_now = now if fixed_clock else datetime.now(UTC)
                    with SessionLocal() as db:
                        # Persist only completed minutes. Never rewrite an
                        # archived observation after a vendor revision.
                        completed = {
                            f"{market}:{item['code']}:{bar.start.isoformat()}": bar
                            for bar in minutes if bounds[0] <= bar.start < bounds[1]
                            and bar.start + timedelta(minutes=1) <= observed_now
                        }
                        archived = set(db.scalars(select(IntradayMinute.key).where(
                            IntradayMinute.key.in_(list(completed)))))
                        for key, bar in completed.items():
                            if key not in archived:
                                db.add(IntradayMinute(key=key, market=market, code=item["code"],
                                    start_at=bar.start.replace(tzinfo=None), payload=encode(bar.__dict__)))
                        db.commit()
                        status = record(db, market=market, code=item["code"], mode=mode, member=item,
                            name=item.get("name", item["code"]), minutes=minutes, context=context,
                            now=observed_now, session_open=bounds[0], session_close=bounds[1],
                            in_universe=universe_ready and item["code"] in codes,
                            max_age=self.settings.intraday_signal_max_age_seconds)
                    counts[status] += 1
                except Exception:
                    counts["source_or_context_error"] += 1
        failures = sum(counts[k] for k in ("stale", "future_bars", "invalid_bars",
            "source_or_context_error", "wrong_session", "conflicting_bars", "out_of_order"))
        self.status(market, {"state": "monitoring" if universe_ready and not failures else "degraded",
            "universe_count": len(codes), "evaluated": sum(counts.values()),
            "decisions": dict(counts), "cycle_seconds": (datetime.now(UTC)-started).total_seconds(),
            "session_open": bounds[0].isoformat(), "session_close": bounds[1].isoformat(),
            "push_ready": bool(self.push.configured), "universe_as_of": str(bounds[2])})
        if mode == "alerts":
            self.deliver(market)

    def deliver(self, market):
        if self.settings.intraday_signal_mode != "alerts" or not self.push.configured:
            return
        from app.services.web_push import NotificationCandidate, subscription_conditions
        cutoff = datetime.utcnow() - timedelta(minutes=3)
        with SessionLocal() as db:
            events = list(db.scalars(select(IntradayEvent).where(
                IntradayEvent.market == market, IntradayEvent.mode == "alerts",
                IntradayEvent.occurred_at >= cutoff).order_by(IntradayEvent.occurred_at)))
            subscriptions = list(db.scalars(select(PushSubscription).where(PushSubscription.enabled.is_(True))))
            for row in events:
                event = json.loads(row.payload)
                event_date = row.occurred_at.replace(tzinfo=UTC).astimezone(NY if market == "us" else KST).date()
                label = {"buy": "장중 매수 확정", "partial_sell": "장중 1차 수익확정", "sell": "장중 전량 매도"}[event["side"]]
                for sub in subscriptions:
                    if market == "kr" and sub.share_id.startswith("us."):
                        continue
                    if "market_ai_signal" not in subscription_conditions(sub):
                        continue
                    if row.occurred_at <= max(sub.created_at, sub.updated_at):
                        continue
                    candidate = NotificationCandidate(
                        event_key=f"intraday:{market}:{event['code']}:{event['side']}:{row.event_id}:{event_date}", kind="market_ai_signal",
                        title=f"[{label}] {event['name']}",
                        body=f"관측 기준가 {event['reference_price']:,.2f} {event['currency']} · 전략 신호이며 주문 체결이 아닙니다.",
                        url=f"/{'us/' if market == 'us' else ''}intraday-alerts?event={row.event_id}",
                        tag=f"intraday-{row.event_id}", occurred_at=row.occurred_at,
                        stock_codes=(event["code"],), ttl_seconds=180,
                        **({"market_scope": market} if "market_scope" in NotificationCandidate.__dataclass_fields__ else {}))
                    self.push._send(db, sub, candidate)
            db.commit()
