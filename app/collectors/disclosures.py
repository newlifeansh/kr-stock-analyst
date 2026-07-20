from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.integrations.opendart import fetch_opendart_json
from app.models import DisclosureItem
from app.repository import finish_ingestion, latest_disclosures, start_ingestion, upsert_many

KST = ZoneInfo("Asia/Seoul")
DART_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_HOME_URL = "https://dart.fss.or.kr/"
CORP_CLASS_BY_MARKET = {
    "유가증권시장": "Y",
    "코스닥시장": "K",
    "코넥스시장": "N",
    "기타법인": "E",
}


@dataclass
class DisclosureListItem:
    source: str
    external_id: str
    disclosure_category: str
    company_name: str
    stock_code: Optional[str]
    corp_code: Optional[str]
    corp_class: Optional[str]
    report_name: str
    filer_name: Optional[str]
    remark: Optional[str]
    detail_url: Optional[str]
    published_at: Optional[datetime]
    raw: Optional[str] = None

    def as_row(self) -> dict[str, object]:
        return {
            "source": self.source,
            "external_id": self.external_id,
            "disclosure_category": self.disclosure_category,
            "company_name": self.company_name,
            "stock_code": self.stock_code,
            "corp_code": self.corp_code,
            "corp_class": self.corp_class,
            "report_name": self.report_name,
            "filer_name": self.filer_name,
            "remark": self.remark,
            "detail_url": self.detail_url,
            "published_at": self.published_at,
            "raw": self.raw,
        }


@dataclass
class DisclosureFetchResult:
    items: list[DisclosureListItem]
    requested_source: str
    resolved_source: str
    message: Optional[str] = None


@dataclass
class DisclosureCollectResult:
    rows_loaded: int
    requested_source: str
    resolved_source: str
    message: Optional[str] = None


def _parse_dart_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y%m%d")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST).replace(tzinfo=None)


def _parse_dart_web_datetime(date_text: str, time_text: str) -> Optional[datetime]:
    cleaned_date = date_text.replace("\xa0", " ").strip()
    cleaned_time = time_text.replace("\xa0", " ").strip()
    if not cleaned_date or not cleaned_time:
        return None
    try:
        parsed = datetime.strptime(f"{cleaned_date} {cleaned_time}", "%Y.%m.%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=KST).replace(tzinfo=None)


def _extract_corp_code(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    matched = re.search(r"openCorpInfoNew\('([^']+)'", value)
    return matched.group(1) if matched else None


def _extract_receipt_no(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    matched = re.search(r"rcpNo=(\d+)", value)
    return matched.group(1) if matched else None


def classify_disclosure_category(report_name: str) -> str:
    lowered = report_name.lower()

    if "기업설명회" in report_name or "(ir)" in lowered or "ir " in lowered or lowered.endswith(" ir"):
        return "ir"
    if "영업(잠정)실적" in report_name or "매출액또는손익구조" in report_name:
        return "earnings_flash"
    if "임원ㆍ주요주주" in report_name or "특정증권등소유상황보고서" in report_name:
        return "insider_trade"
    if "대량보유" in report_name:
        return "major_holder"
    if "소유주식변동" in report_name:
        return "major_holder"
    if "배당" in report_name:
        return "dividend"
    if "자기주식" in report_name:
        return "treasury_stock"
    if "주식소각" in report_name:
        return "treasury_stock"
    if "공급계약" in report_name or "단일판매ㆍ공급계약체결" in report_name:
        return "supply_contract"
    if "시설투자" in report_name or "유형자산취득결정" in report_name or "신규시설투자" in report_name:
        return "facility_investment"
    if "유상증자" in report_name or "유무상증자" in report_name:
        return "rights_offering"
    if "사업보고서" in report_name or "반기보고서" in report_name or "분기보고서" in report_name:
        return "business_report"
    return "filings"


def fetch_dart_web_disclosures() -> list[DisclosureListItem]:
    response = requests.get(DART_HOME_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tbody = soup.select_one("#today_all_list")
    if tbody is None:
        raise RuntimeError("DART 웹 메인에서 오늘의 공시 목록을 찾지 못했습니다.")

    items: list[DisclosureListItem] = []
    for row in tbody.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue

        date_text = cells[0].select_one(".webOnly")
        company_link = cells[2].find("a", href=True)
        report_link = cells[3].find("a", href=True)
        if company_link is None or report_link is None:
            continue

        market_label = cells[1].select_one(".webOnly")
        company_name = company_link.get_text(" ", strip=True) or "-"
        report_name = report_link.get_text(" ", strip=True) or "공시"
        corp_code = _extract_corp_code(company_link.get("href"))
        receipt_no = _extract_receipt_no(report_link.get("href"))
        published_at = _parse_dart_web_datetime(
            date_text.get_text(" ", strip=True) if date_text else "",
            cells[0].get_text(" ", strip=True).replace(date_text.get_text(" ", strip=True), "", 1) if date_text else "",
        )
        market_name = market_label.get_text(" ", strip=True) if market_label else cells[1].get_text(" ", strip=True)

        items.append(
            DisclosureListItem(
                source="dart_web",
                external_id=receipt_no or f"home:{company_name}:{report_name}:{cells[0].get_text(' ', strip=True)}",
                disclosure_category=classify_disclosure_category(report_name),
                company_name=company_name,
                stock_code=None,
                corp_code=corp_code,
                corp_class=CORP_CLASS_BY_MARKET.get(market_name.strip()),
                report_name=report_name,
                filer_name=company_name,
                remark=market_name.strip() if market_name else None,
                detail_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else None,
                published_at=published_at,
                raw=json.dumps(
                    {
                        "market_name": market_name.strip() if market_name else None,
                        "corp_code": corp_code,
                        "receipt_no": receipt_no,
                    },
                    ensure_ascii=False,
                ),
            )
        )
    return items


def fetch_dart_disclosures(
    settings: Settings,
    days_back: int,
    page_count: int,
    now: Optional[datetime] = None,
) -> DisclosureFetchResult:
    requested_source = "dart_api" if settings.dart_api_key else "dart_web"
    if not settings.dart_api_key:
        return DisclosureFetchResult(
            items=fetch_dart_web_disclosures(),
            requested_source=requested_source,
            resolved_source="dart_web",
        )

    now = now or datetime.now(KST)
    begin_date = (now - timedelta(days=days_back)).date()
    items: list[DisclosureListItem] = []

    for page_no in range(1, 6):
        payload = fetch_opendart_json(
            DART_LIST_URL,
            {
                "crtfc_key": settings.dart_api_key,
                "bgn_de": begin_date.strftime("%Y%m%d"),
                "end_de": now.strftime("%Y%m%d"),
                "sort": "date",
                "sort_mth": "desc",
                "page_no": page_no,
                "page_count": page_count,
            },
            timeout=30,
        )
        status = payload.get("status")
        if status == "013":
            break
        if status != "000":
            message = payload.get("message") or "DART disclosure request failed"
            return DisclosureFetchResult(
                items=fetch_dart_web_disclosures(),
                requested_source=requested_source,
                resolved_source="dart_web",
                message=message,
            )

        rows = payload.get("list", []) or []
        if not rows:
            break

        for row in rows:
            report_name = row.get("report_nm") or "공시"
            external_id = row.get("rcept_no") or ""
            items.append(
                DisclosureListItem(
                    source="dart_api",
                    external_id=external_id,
                    disclosure_category=classify_disclosure_category(report_name),
                    company_name=row.get("corp_name") or "-",
                    stock_code=row.get("stock_code") or None,
                    corp_code=row.get("corp_code") or None,
                    corp_class=row.get("corp_cls") or None,
                    report_name=report_name,
                    filer_name=row.get("flr_nm") or None,
                    remark=row.get("rm") or None,
                    detail_url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={external_id}" if external_id else None,
                    published_at=_parse_dart_datetime(row.get("rcept_dt")),
                    raw=json.dumps(row, ensure_ascii=False),
                )
            )

        if len(rows) < page_count:
            break

    return DisclosureFetchResult(
        items=items,
        requested_source=requested_source,
        resolved_source="dart_api",
    )


def collect_disclosures(
    db: Session,
    settings: Optional[Settings] = None,
    days_back: Optional[int] = None,
    page_count: Optional[int] = None,
) -> DisclosureCollectResult:
    settings = settings or get_settings()
    days_back = days_back or settings.disclosure_days_back
    page_count = page_count or settings.disclosure_page_count
    requested_source = "dart_api" if settings.dart_api_key else "dart_web"

    run = start_ingestion(db, "disclosure", requested_source)
    try:
        result = fetch_dart_disclosures(
            settings=settings,
            days_back=days_back,
            page_count=page_count,
        )
        if result.resolved_source == "dart_api":
            external_ids = [item.external_id for item in result.items if item.external_id]
            if external_ids:
                db.execute(
                    delete(DisclosureItem).where(
                        DisclosureItem.source.in_(["dart_web", "dart"]),
                        DisclosureItem.external_id.in_(external_ids),
                    )
                )
        count = upsert_many(db, DisclosureItem, [item.as_row() for item in result.items])
        db.commit()
        message_parts = [
            f"requested_source={result.requested_source}",
            f"resolved_source={result.resolved_source}",
            f"days_back={days_back}",
        ]
        if result.message:
            message_parts.append(f"detail={result.message}")
        finish_ingestion(
            db,
            run,
            "success",
            rows_loaded=count,
            message=", ".join(message_parts),
        )
        return DisclosureCollectResult(
            rows_loaded=count,
            requested_source=result.requested_source,
            resolved_source=result.resolved_source,
            message=result.message,
        )
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def latest_disclosure_events(db: Session, limit: int = 10) -> list[dict[str, object]]:
    items = latest_disclosures(db, limit=limit)
    return [
        {
            "event_type": "disclosure",
            "source": item.source,
            "title": item.report_name,
            "company_name": item.company_name,
            "stock_code": item.stock_code,
            "url": item.detail_url,
            "published_at": item.published_at,
            "raw": item.raw,
        }
        for item in items
    ]
