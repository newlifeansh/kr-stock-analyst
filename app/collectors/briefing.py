from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Optional
from zoneinfo import ZoneInfo

import requests
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.collectors.disclosures import latest_disclosure_events
from app.collectors.news import latest_news_events
from app.integrations.opendart import fetch_opendart_json
from app.models import (
    BriefingEvent,
    BriefingMetric,
    BriefingMover,
    BriefingQuote,
    BriefingSnapshot,
    StockMaster,
)
from app.collectors.research import latest_report_events
from app.repository import finish_ingestion, start_ingestion, upsert_many

KST = ZoneInfo("Asia/Seoul")


@dataclass
class BriefingMetricPayload:
    metric_key: str
    label: str
    value_numeric: Optional[Decimal] = None
    value_text: Optional[str] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    unit: Optional[str] = None
    sort_order: int = 0


@dataclass
class BriefingQuotePayload:
    code: str
    name: str
    market: Optional[str]
    role: str
    price: Optional[Decimal] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None


@dataclass
class BriefingMoverPayload:
    list_type: str
    rank: int
    code: str
    name: str
    market: Optional[str]
    price: Optional[Decimal] = None
    change_value: Optional[Decimal] = None
    change_rate: Optional[Decimal] = None
    volume: Optional[int] = None
    trading_value: Optional[int] = None


@dataclass
class BriefingEventPayload:
    event_type: str
    source: str
    title: str
    company_name: Optional[str] = None
    stock_code: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    raw: Optional[str] = None


@dataclass
class BriefingBundle:
    briefing_kind: str
    source: str
    transport: str
    market_status: str
    is_live: bool
    as_of: datetime
    summary: Optional[str] = None
    metrics: list[BriefingMetricPayload] = field(default_factory=list)
    quotes: list[BriefingQuotePayload] = field(default_factory=list)
    movers: list[BriefingMoverPayload] = field(default_factory=list)
    events: list[BriefingEventPayload] = field(default_factory=list)


def _decimal(value: Any) -> Optional[Decimal]:
    if value in (None, "", "-", "--"):
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _int(value: Any) -> Optional[int]:
    decimal_value = _decimal(value)
    if decimal_value is None:
        return None
    return int(decimal_value)


def _parse_dart_datetime(rcept_dt: Optional[str]) -> Optional[datetime]:
    if not rcept_dt:
        return None
    try:
        parsed = datetime.strptime(rcept_dt, "%Y%m%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST)


def current_market_status(now: Optional[datetime] = None) -> str:
    now = now or datetime.now(KST)
    if now.tzinfo is None:
        now = now.replace(tzinfo=KST)
    local = now.astimezone(KST)

    if local.weekday() >= 5:
        return "closed"
    if local.time() < time(8, 30):
        return "closed"
    if local.time() < time(9, 0):
        return "pre_open"
    if local.time() < time(15, 30):
        return "open"
    if local.time() < time(18, 0):
        return "after_hours"
    return "closed"


class KisRestBriefingProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    @property
    def transport(self) -> str:
        return "polling"

    def is_configured(self) -> bool:
        return bool(self.settings.kis_app_key and self.settings.kis_app_secret)

    def fetch_quotes(
        self,
        codes: list[str],
        stock_lookup: dict[str, StockMaster],
    ) -> list[BriefingQuotePayload]:
        quotes: list[BriefingQuotePayload] = []
        for code in codes:
            try:
                row = self._request_current_price(code)
            except Exception:
                continue
            fallback = stock_lookup.get(code)
            quotes.append(
                BriefingQuotePayload(
                    code=code,
                    name=self._pick(row, "hts_kor_isnm") or (fallback.name if fallback else code),
                    market=fallback.market if fallback else None,
                    role="watchlist",
                    price=_decimal(self._pick(row, "stck_prpr")),
                    change_value=_decimal(self._pick(row, "prdy_vrss")),
                    change_rate=_decimal(self._pick(row, "prdy_ctrt")),
                    volume=_int(self._pick(row, "acml_vol")),
                    trading_value=_int(self._pick(row, "acml_tr_pbmn")),
                )
            )
        return quotes

    def fetch_movers(self, limit: int = 10) -> list[BriefingMoverPayload]:
        movers: list[BriefingMoverPayload] = []
        try:
            movers.extend(self._fetch_fluctuation(list_type="gainers", limit=limit, min_rate="0", max_rate="300"))
        except Exception:
            pass
        try:
            movers.extend(self._fetch_fluctuation(list_type="losers", limit=limit, min_rate="-300", max_rate="0"))
        except Exception:
            pass
        try:
            movers.extend(self._fetch_turnover(limit=limit))
        except Exception:
            pass
        return movers

    def _base_url(self) -> str:
        if self.settings.kis_env == "demo":
            return "https://openapivts.koreainvestment.com:29443"
        return "https://openapi.koreainvestment.com:9443"

    def _ensure_token(self) -> str:
        now = datetime.utcnow()
        if self._token and self._token_expires_at and self._token_expires_at > now + timedelta(minutes=1):
            return self._token

        response = requests.post(
            f"{self._base_url()}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            },
            headers={"content-type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        self._token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 86400))
        self._token_expires_at = now + timedelta(seconds=expires_in)
        return self._token

    def _headers(self, tr_id: str) -> dict[str, str]:
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {self._ensure_token()}",
            "appkey": self.settings.kis_app_key or "",
            "appsecret": self.settings.kis_app_secret or "",
            "tr_id": tr_id,
            "custtype": "P",
        }

    def _get(self, path: str, tr_id: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(
            f"{self._base_url()}{path}",
            headers=self._headers(tr_id),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("rt_cd") not in (None, "0"):
            raise RuntimeError(payload.get("msg1") or payload.get("msg_cd") or "KIS request failed")
        return payload

    def _request_current_price(self, code: str) -> dict[str, Any]:
        payload = self._get(
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            "FHKST01010100",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": code,
            },
        )
        return payload.get("output", {})

    def fetch_intraday_chart(self, code: str, *, max_points: int = 390) -> list[dict[str, object]]:
        """Fetch today's one-minute chart without retaining a quote cache."""
        now = datetime.now(KST)
        if now.time() < time(9, 0):
            cursor = "153000"
        elif now.time() > time(15, 30):
            cursor = "153000"
        else:
            cursor = now.strftime("%H%M%S")

        points: dict[tuple[str, str], dict[str, object]] = {}
        latest_trade_date: Optional[str] = None
        previous_cursor = ""
        max_chunks = max(1, min(14, (max_points + 29) // 30))
        for _ in range(max_chunks):
            payload = self._get(
                "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                "FHKST03010200",
                {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": code,
                    "FID_INPUT_HOUR_1": cursor,
                    "FID_PW_DATA_INCU_YN": "Y",
                    "FID_ETC_CLS_CODE": "",
                },
            )
            rows = payload.get("output2", []) or []
            if not rows:
                break

            valid_times: list[str] = []
            for row in rows:
                trade_date = str(row.get("stck_bsop_date") or "").strip()
                trade_time = str(row.get("stck_cntg_hour") or "").strip().zfill(6)
                if not trade_date or not trade_time:
                    continue
                latest_trade_date = latest_trade_date or trade_date
                if trade_date != latest_trade_date:
                    continue
                price = _int(row.get("stck_prpr"))
                if price is None:
                    continue
                valid_times.append(trade_time)
                points[(trade_date, trade_time)] = {
                    "trade_date": trade_date,
                    "trade_time": trade_time,
                    "price": price,
                    "open": _int(row.get("stck_oprc")),
                    "high": _int(row.get("stck_hgpr")),
                    "low": _int(row.get("stck_lwpr")),
                    "volume": _int(row.get("cntg_vol")),
                    "trading_value": _int(row.get("acml_tr_pbmn")),
                }
            if not valid_times:
                break
            earliest = min(valid_times)
            if earliest <= "090000" or len(points) >= max_points:
                break
            cursor_time = datetime.strptime(earliest, "%H%M%S") - timedelta(minutes=1)
            next_cursor = cursor_time.strftime("%H%M%S")
            if next_cursor == cursor or next_cursor == previous_cursor:
                break
            previous_cursor, cursor = cursor, next_cursor

        return sorted(points.values(), key=lambda row: (str(row["trade_date"]), str(row["trade_time"])))[:max_points]

    def _fetch_fluctuation(self, list_type: str, limit: int, min_rate: str, max_rate: str) -> list[BriefingMoverPayload]:
        payload = self._get(
            "/uapi/domestic-stock/v1/ranking/fluctuation",
            "FHPST01700000",
            {
                "fid_cond_mrkt_div_code": "J",
                "fid_cond_scr_div_code": "20170",
                "fid_input_iscd": "0000",
                "fid_rank_sort_cls_code": "0000",
                "fid_input_cnt_1": str(limit),
                "fid_prc_cls_code": "0",
                "fid_input_price_1": "0",
                "fid_input_price_2": "9999999",
                "fid_vol_cnt": "0",
                "fid_trgt_cls_code": "0",
                "fid_trgt_exls_cls_code": "0",
                "fid_div_cls_code": "0",
                "fid_rsfl_rate1": min_rate,
                "fid_rsfl_rate2": max_rate,
            },
        )
        output = payload.get("output", []) or []
        rows: list[BriefingMoverPayload] = []
        for rank, row in enumerate(output[:limit], start=1):
            rows.append(
                BriefingMoverPayload(
                    list_type=list_type,
                    rank=rank,
                    code=self._pick(row, "mksc_shrn_iscd", "stck_shrn_iscd", "stck_cd") or "",
                    name=self._pick(row, "hts_kor_isnm", "stck_shrn_iscd") or "",
                    market=self._pick(row, "stck_avls", "bstp_kor_isnm"),
                    price=_decimal(self._pick(row, "stck_prpr")),
                    change_value=_decimal(self._pick(row, "prdy_vrss")),
                    change_rate=_decimal(self._pick(row, "prdy_ctrt")),
                    volume=_int(self._pick(row, "acml_vol", "cntg_vol")),
                    trading_value=_int(self._pick(row, "acml_tr_pbmn")),
                )
            )
        return [row for row in rows if row.code]

    def _fetch_turnover(self, limit: int) -> list[BriefingMoverPayload]:
        payload = self._get(
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            "FHPST01710000",
            {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_COND_SCR_DIV_CODE": "20171",
                "FID_INPUT_ISCD": "0000",
                "FID_DIV_CLS_CODE": "0",
                "FID_BLNG_CLS_CODE": "3",
                "FID_TRGT_CLS_CODE": "111111",
                "FID_TRGT_EXLS_CLS_CODE": "0000000000",
                "FID_INPUT_PRICE_1": "",
                "FID_INPUT_PRICE_2": "",
                "FID_VOL_CNT": "",
                "FID_INPUT_DATE_1": "",
            },
        )
        output = payload.get("output", []) or []
        rows: list[BriefingMoverPayload] = []
        for rank, row in enumerate(output[:limit], start=1):
            rows.append(
                BriefingMoverPayload(
                    list_type="turnover",
                    rank=rank,
                    code=self._pick(row, "mksc_shrn_iscd", "stck_shrn_iscd", "stck_cd") or "",
                    name=self._pick(row, "hts_kor_isnm", "stck_shrn_iscd") or "",
                    market=self._pick(row, "bstp_kor_isnm"),
                    price=_decimal(self._pick(row, "stck_prpr")),
                    change_value=_decimal(self._pick(row, "prdy_vrss")),
                    change_rate=_decimal(self._pick(row, "prdy_ctrt")),
                    volume=_int(self._pick(row, "acml_vol", "cntg_vol")),
                    trading_value=_int(self._pick(row, "acml_tr_pbmn")),
                )
            )
        return [row for row in rows if row.code]

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] not in (None, ""):
                return row[key]
        return None


class DartDisclosureProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def is_configured(self) -> bool:
        return bool(self.settings.dart_api_key)

    def fetch_events(self, limit: int = 20) -> list[BriefingEventPayload]:
        today = datetime.now(KST).date()
        begin_date = today - timedelta(days=3)
        payload = fetch_opendart_json(
            "https://opendart.fss.or.kr/api/list.json",
            {
                "crtfc_key": self.settings.dart_api_key,
                "bgn_de": begin_date.strftime("%Y%m%d"),
                "end_de": today.strftime("%Y%m%d"),
                "corp_cls": "Y",
                "sort": "date",
                "sort_mth": "desc",
                "page_no": 1,
                "page_count": limit,
            },
            timeout=30,
        )
        if payload.get("status") != "000":
            raise RuntimeError(payload.get("message") or "DART request failed")
        rows = payload.get("list", []) or []
        return [
            BriefingEventPayload(
                event_type="disclosure",
                source="dart_api",
                title=item.get("report_nm") or "공시",
                company_name=item.get("corp_name"),
                stock_code=item.get("stock_code") or None,
                url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={item.get('rcept_no')}"
                if item.get("rcept_no")
                else None,
                published_at=_parse_dart_datetime(item.get("rcept_dt")),
                raw=json.dumps(item, ensure_ascii=False),
            )
            for item in rows[:limit]
        ]


def build_home_briefing_bundle(
    db: Session,
    settings: Optional[Settings] = None,
    market_provider: Optional[KisRestBriefingProvider] = None,
    disclosure_provider: Optional[DartDisclosureProvider] = None,
    now: Optional[datetime] = None,
) -> BriefingBundle:
    settings = settings or get_settings()
    now = now or datetime.now(KST)

    stock_lookup = {
        stock.code: stock
        for stock in db.query(StockMaster).filter(StockMaster.code.in_(settings.briefing_watch_code_list())).all()
    }

    market_provider = market_provider or KisRestBriefingProvider(settings)
    disclosure_provider = disclosure_provider or DartDisclosureProvider(settings)

    quotes: list[BriefingQuotePayload] = []
    movers: list[BriefingMoverPayload] = []
    events: list[BriefingEventPayload] = []
    errors: list[str] = []
    metrics: list[BriefingMetricPayload] = [
        BriefingMetricPayload(
            metric_key="market_status",
            label="장 상태",
            value_text=current_market_status(now),
            sort_order=0,
        ),
        BriefingMetricPayload(
            metric_key="watchlist_count",
            label="브리핑 대상 종목 수",
            value_numeric=Decimal(len(settings.briefing_watch_code_list())),
            unit="count",
            sort_order=1,
        ),
    ]
    source_parts: list[str] = []

    if market_provider.is_configured():
        try:
            quotes = market_provider.fetch_quotes(settings.briefing_watch_code_list(), stock_lookup)
            movers = market_provider.fetch_movers()
            source_parts.append("kis")
        except Exception as exc:
            errors.append(f"kis={exc}")

    disclosure_events = latest_disclosure_events(db, limit=settings.briefing_disclosure_limit)
    report_events = latest_report_events(db, limit=settings.briefing_report_limit)
    news_events = latest_news_events(db, limit=settings.briefing_news_limit)

    events.extend(
        [
            BriefingEventPayload(
                event_type=event["event_type"],
                source=str(event["source"]),
                title=str(event["title"]),
                company_name=event.get("company_name"),
                stock_code=event.get("stock_code"),
                url=event.get("url"),
                published_at=event.get("published_at"),
                raw=event.get("raw"),
            )
            for event in disclosure_events + report_events + news_events
        ]
    )
    if disclosure_events:
        source_parts.append("dart")
    if report_events:
        source_parts.append("research")
    if news_events:
        source_parts.append("news")

    summary_parts = [
        f"watchlist={len(quotes)}",
        f"movers={len(movers)}",
        f"disclosures={len(disclosure_events)}",
        f"reports={len(report_events)}",
        f"news={len(news_events)}",
    ]
    if errors:
        summary_parts.append("errors=" + "; ".join(errors))
    if not source_parts and not errors:
        summary_parts.append("No live briefing source configured")

    return BriefingBundle(
        briefing_kind="home",
        source="+".join(source_parts) if source_parts else "none",
        transport=market_provider.transport if market_provider.is_configured() else "polling",
        market_status=current_market_status(now),
        is_live=bool(quotes or movers),
        as_of=now.astimezone(KST).replace(tzinfo=None),
        summary=" ".join(summary_parts),
        metrics=metrics,
        quotes=quotes,
        movers=movers,
        events=events,
    )


def prune_briefing_snapshots(db: Session, briefing_kind: str, retain_count: int) -> int:
    retain_count = max(int(retain_count), 1)
    stale_snapshot_ids = select(BriefingSnapshot.id).where(
        BriefingSnapshot.briefing_kind == briefing_kind
    ).order_by(
        BriefingSnapshot.as_of.desc(),
        BriefingSnapshot.id.desc(),
    ).offset(retain_count)
    stale_ids = list(db.scalars(stale_snapshot_ids))
    if not stale_ids:
        return 0

    for model in (BriefingEvent, BriefingMover, BriefingQuote, BriefingMetric):
        db.execute(delete(model).where(model.snapshot_id.in_(stale_ids)))
    db.execute(delete(BriefingSnapshot).where(BriefingSnapshot.id.in_(stale_ids)))
    return len(stale_ids)


def persist_briefing_bundle(
    db: Session,
    bundle: BriefingBundle,
    retention_limit: int = 288,
) -> BriefingSnapshot:
    snapshot = BriefingSnapshot(
        briefing_kind=bundle.briefing_kind,
        source=bundle.source,
        transport=bundle.transport,
        market_status=bundle.market_status,
        is_live=bundle.is_live,
        as_of=bundle.as_of,
        summary=bundle.summary,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    metric_rows = [
        {
            "snapshot_id": snapshot.id,
            "metric_key": item.metric_key,
            "label": item.label,
            "value_numeric": item.value_numeric,
            "value_text": item.value_text,
            "change_value": item.change_value,
            "change_rate": item.change_rate,
            "unit": item.unit,
            "sort_order": item.sort_order,
        }
        for item in bundle.metrics
    ]
    quote_rows = [
        {
            "snapshot_id": snapshot.id,
            "code": item.code,
            "name": item.name,
            "market": item.market,
            "role": item.role,
            "price": item.price,
            "change_value": item.change_value,
            "change_rate": item.change_rate,
            "volume": item.volume,
            "trading_value": item.trading_value,
        }
        for item in bundle.quotes
    ]
    mover_rows = [
        {
            "snapshot_id": snapshot.id,
            "list_type": item.list_type,
            "rank": item.rank,
            "code": item.code,
            "name": item.name,
            "market": item.market,
            "price": item.price,
            "change_value": item.change_value,
            "change_rate": item.change_rate,
            "volume": item.volume,
            "trading_value": item.trading_value,
        }
        for item in bundle.movers
    ]
    event_rows = [
        {
            "snapshot_id": snapshot.id,
            "event_type": item.event_type,
            "source": item.source,
            "title": item.title,
            "company_name": item.company_name,
            "stock_code": item.stock_code,
            "url": item.url,
            "published_at": item.published_at.astimezone(KST).replace(tzinfo=None)
            if item.published_at and item.published_at.tzinfo
            else item.published_at,
            "raw": item.raw,
        }
        for item in bundle.events
    ]

    upsert_many(db, BriefingMetric, metric_rows)
    upsert_many(db, BriefingQuote, quote_rows)
    upsert_many(db, BriefingMover, mover_rows)
    if event_rows:
        db.bulk_insert_mappings(BriefingEvent, event_rows)
    prune_briefing_snapshots(db, bundle.briefing_kind, retention_limit)
    db.commit()
    return snapshot


def collect_home_briefing(
    db: Session,
    settings: Optional[Settings] = None,
    market_provider: Optional[KisRestBriefingProvider] = None,
    disclosure_provider: Optional[DartDisclosureProvider] = None,
    now: Optional[datetime] = None,
) -> BriefingSnapshot:
    settings = settings or get_settings()
    run = start_ingestion(db, "briefing", "home")
    try:
        bundle = build_home_briefing_bundle(
            db,
            settings=settings,
            market_provider=market_provider,
            disclosure_provider=disclosure_provider,
            now=now,
        )
        snapshot = persist_briefing_bundle(
            db,
            bundle,
            retention_limit=settings.briefing_retention_snapshots,
        )
        rows_loaded = len(bundle.metrics) + len(bundle.quotes) + len(bundle.movers) + len(bundle.events) + 1
        finish_ingestion(db, run, "success", rows_loaded=rows_loaded, message=bundle.summary)
        return snapshot
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise
