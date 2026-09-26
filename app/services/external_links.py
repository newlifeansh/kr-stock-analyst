from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

DART_REPORT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
NAVER_MOBILE_RESEARCH_URL = (
    "https://m.stock.naver.com/domestic/stock/{stock_code}/research/{report_id}"
)
STOCKHUB_STOCK_URL = "https://www.stockhub.kr/stock/{stock_code}"


def safe_external_http_url(value: object) -> Optional[str]:
    """Return a browser-safe public HTTP(S) URL or ``None``."""

    normalized = str(value or "").strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    return normalized


def naver_mobile_research_url(stock_code: object, external_id: object) -> Optional[str]:
    code = str(stock_code or "").strip()
    report_id = str(external_id or "").strip()
    if not re.fullmatch(r"\d{6}", code) or not re.fullmatch(r"\d+", report_id):
        return None
    return NAVER_MOBILE_RESEARCH_URL.format(stock_code=code, report_id=report_id)


def stockhub_stock_url(stock_code: object) -> Optional[str]:
    code = str(stock_code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return None
    return STOCKHUB_STOCK_URL.format(stock_code=code)


def preferred_research_url(
    stock_code: object,
    external_id: object,
    pdf_url: object,
    detail_url: object,
    *,
    source: object = None,
) -> Optional[str]:
    """Choose a stable, report-scoped URL for public research metadata.

    Naver report identifiers have a durable mobile detail route. Stockhub's
    embedded metadata sometimes exposes a broker's generic board URL instead
    of a report URL; several of those boards reject mobile requests with 400.
    A direct PDF remains preferable, otherwise the stable Stockhub stock page
    keeps the user on the selected company and report list.
    """

    normalized_source = str(source or "").strip()
    if normalized_source in {"", "naver_finance"}:
        mobile_url = naver_mobile_research_url(stock_code, external_id)
        if mobile_url:
            return mobile_url

    direct_pdf = safe_external_http_url(pdf_url)
    if direct_pdf:
        return direct_pdf

    if normalized_source == "stockhub":
        stable_stock_url = stockhub_stock_url(stock_code)
        if stable_stock_url:
            return stable_stock_url

    return safe_external_http_url(detail_url)


def preferred_disclosure_url(
    source: object,
    external_id: object,
    detail_url: object,
) -> Optional[str]:
    """Rebuild official DART receipt links instead of trusting stored URLs."""

    normalized_source = str(source or "").strip().lower()
    receipt_no = str(external_id or "").strip()
    if normalized_source in {"dart", "dart_api", "dart_web"} and re.fullmatch(
        r"\d{14}", receipt_no
    ):
        return DART_REPORT_URL.format(receipt_no=receipt_no)
    return safe_external_http_url(detail_url)
