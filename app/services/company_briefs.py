from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DisclosureItem, NewsItem, ResearchReport, StockMaster
from app.repository import latest_prices_by_codes


def _normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", "", value).strip()


@dataclass(frozen=True)
class StockLookup:
    code: str
    name: str
    market: Optional[str]
    normalized_name: str


@dataclass
class CompanyBriefAccumulator:
    company_name: str
    stock_code: Optional[str] = None
    market: Optional[str] = None
    report_count: int = 0
    disclosure_count: int = 0
    news_count: int = 0
    latest_published_at: Optional[datetime] = None
    latest_report_title: Optional[str] = None
    latest_report_url: Optional[str] = None
    latest_report_at: Optional[datetime] = None
    latest_report_broker: Optional[str] = None
    latest_disclosure_title: Optional[str] = None
    latest_disclosure_url: Optional[str] = None
    latest_disclosure_at: Optional[datetime] = None
    latest_disclosure_category: Optional[str] = None
    latest_news_title: Optional[str] = None
    latest_news_url: Optional[str] = None
    latest_news_at: Optional[datetime] = None
    latest_news_press: Optional[str] = None

    def touch(self, published_at: Optional[datetime]) -> None:
        if published_at and (self.latest_published_at is None or published_at > self.latest_published_at):
            self.latest_published_at = published_at

    def as_payload(self, latest_close: Optional[int] = None, latest_trade_date: Optional[object] = None) -> dict[str, object]:
        return {
            "company_name": self.company_name,
            "stock_code": self.stock_code,
            "market": self.market,
            "latest_close": latest_close,
            "latest_trade_date": latest_trade_date,
            "report_count": self.report_count,
            "disclosure_count": self.disclosure_count,
            "news_count": self.news_count,
            "total_count": self.report_count + self.disclosure_count + self.news_count,
            "latest_published_at": self.latest_published_at,
            "latest_report_title": self.latest_report_title,
            "latest_report_url": self.latest_report_url,
            "latest_report_at": self.latest_report_at,
            "latest_report_broker": self.latest_report_broker,
            "latest_disclosure_title": self.latest_disclosure_title,
            "latest_disclosure_url": self.latest_disclosure_url,
            "latest_disclosure_at": self.latest_disclosure_at,
            "latest_disclosure_category": self.latest_disclosure_category,
            "latest_news_title": self.latest_news_title,
            "latest_news_url": self.latest_news_url,
            "latest_news_at": self.latest_news_at,
            "latest_news_press": self.latest_news_press,
        }


def _load_stock_lookups(db: Session) -> tuple[dict[str, StockLookup], dict[str, StockLookup], list[StockLookup]]:
    rows = db.execute(select(StockMaster.code, StockMaster.name, StockMaster.market)).all()
    by_code: dict[str, StockLookup] = {}
    by_name: dict[str, StockLookup] = {}
    candidates: list[StockLookup] = []

    for code, name, market in rows:
        normalized = _normalize_name(name)
        if not normalized:
            continue
        lookup = StockLookup(code=code, name=name, market=market, normalized_name=normalized)
        by_code[code] = lookup
        by_name[normalized] = lookup
        if len(normalized) >= 2:
            candidates.append(lookup)

    candidates.sort(key=lambda item: len(item.normalized_name), reverse=True)
    return by_code, by_name, candidates


def _match_stock_from_news(
    item: NewsItem,
    candidates: list[StockLookup],
) -> Optional[StockLookup]:
    haystack = _normalize_name(" ".join(part for part in [item.title, item.summary] if part))
    if not haystack:
        return None
    for candidate in candidates:
        if candidate.normalized_name in haystack:
            return candidate
    return None


def _resolve_identity(
    company_name: Optional[str],
    stock_code: Optional[str],
    by_code: dict[str, StockLookup],
    by_name: dict[str, StockLookup],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    lookup = None
    if stock_code:
        lookup = by_code.get(stock_code)
    if lookup is None and company_name:
        lookup = by_name.get(_normalize_name(company_name))

    resolved_name = company_name or (lookup.name if lookup else None)
    resolved_code = stock_code or (lookup.code if lookup else None)
    resolved_market = lookup.market if lookup else None
    return resolved_name, resolved_code, resolved_market


def build_company_briefs(
    db: Session,
    research_items: list[ResearchReport],
    disclosure_items: list[DisclosureItem],
    news_items: list[NewsItem],
    limit: int = 60,
) -> list[dict[str, object]]:
    by_code, by_name, stock_candidates = _load_stock_lookups(db)
    grouped: dict[str, CompanyBriefAccumulator] = {}

    def get_group(company_name: Optional[str], stock_code: Optional[str], market: Optional[str]) -> Optional[CompanyBriefAccumulator]:
        resolved_name, resolved_code, resolved_market = _resolve_identity(company_name, stock_code, by_code, by_name)
        if not resolved_name and not resolved_code:
            return None
        key = resolved_code or _normalize_name(resolved_name)
        if not key:
            return None
        entry = grouped.get(key)
        if entry is None:
            entry = CompanyBriefAccumulator(
                company_name=resolved_name or resolved_code or "-",
                stock_code=resolved_code,
                market=resolved_market or market,
            )
            grouped[key] = entry
            return entry
        if entry.stock_code is None and resolved_code:
            entry.stock_code = resolved_code
        if entry.market is None and (resolved_market or market):
            entry.market = resolved_market or market
        if entry.company_name in {"-", ""} and resolved_name:
            entry.company_name = resolved_name
        return entry

    for item in research_items:
        if not item.company_name and not item.stock_code:
            continue
        entry = get_group(item.company_name, item.stock_code, None)
        if entry is None:
            continue
        entry.report_count += 1
        entry.touch(item.published_at)
        if item.published_at and (entry.latest_report_at is None or item.published_at > entry.latest_report_at):
            entry.latest_report_title = item.title
            entry.latest_report_url = item.detail_url or item.pdf_url
            entry.latest_report_at = item.published_at
            entry.latest_report_broker = item.broker_name

    for item in disclosure_items:
        entry = get_group(item.company_name, item.stock_code, item.remark)
        if entry is None:
            continue
        entry.disclosure_count += 1
        entry.touch(item.published_at)
        if item.published_at and (entry.latest_disclosure_at is None or item.published_at > entry.latest_disclosure_at):
            entry.latest_disclosure_title = item.report_name
            entry.latest_disclosure_url = item.detail_url
            entry.latest_disclosure_at = item.published_at
            entry.latest_disclosure_category = item.disclosure_category

    for item in news_items:
        matched = _match_stock_from_news(item, stock_candidates)
        if matched is None:
            continue
        entry = get_group(matched.name, matched.code, matched.market)
        if entry is None:
            continue
        entry.news_count += 1
        entry.touch(item.published_at)
        if item.published_at and (entry.latest_news_at is None or item.published_at > entry.latest_news_at):
            entry.latest_news_title = item.title
            entry.latest_news_url = item.detail_url
            entry.latest_news_at = item.published_at
            entry.latest_news_press = item.press_name

    if not grouped:
        return []

    price_map = latest_prices_by_codes(
        db,
        [item.stock_code for item in grouped.values() if item.stock_code],
    )
    items = [
        item.as_payload(
            latest_close=price_map[item.stock_code].close if item.stock_code in price_map else None,
            latest_trade_date=price_map[item.stock_code].trade_date if item.stock_code in price_map else None,
        )
        for item in grouped.values()
    ]
    items.sort(
        key=lambda item: (
            item["total_count"] or 0,
            item["latest_published_at"] or datetime.min,
            item["company_name"] or "",
        ),
        reverse=True,
    )
    return items[:limit]
