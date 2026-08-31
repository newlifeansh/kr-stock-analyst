from __future__ import annotations

import json
import re
import warnings
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO
from typing import Optional
from zipfile import BadZipFile, ZipFile

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.integrations.opendart import fetch_opendart_bytes
from app.models import CompanyProfile, StockFundamentalSnapshot, StockMaster
from app.services.company_profiles import (
    DART_DOCUMENT_URL,
    _latest_business_report,
    ensure_company_profile,
)

DART_REPORT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
RECEIPT_NUMBER_RE = re.compile(r"rcpNo=(\d{14})")
YEAR_RE = re.compile(r"(?:CFY|PFY)(20\d{2})")
PREFERRED_DETAIL_WORDS = (
    "급여",
    "퇴직",
    "복리후생",
    "수수료",
    "용역",
    "서비스비",
    "광고",
    "판매촉진",
    "판촉",
    "감가상각",
    "무형자산상각",
    "운반",
    "물류",
    "연구개발",
    "경상개발",
    "소모품",
    "세금과공과",
)
TOTAL_LABELS = ("판매비와관리비", "판매비및관리비", "판매및관리비", "판매관리비", "판관비")
SUBTOTAL_WORDS = ("소계", "합계", "총계")

CATEGORY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("labor", "인건비", ("급여", "임금", "상여", "퇴직급여", "퇴직금", "종업원급여", "직원급여", "인건비")),
    ("benefits", "복리후생비", ("복리후생", "교육훈련", "여비교통")),
    ("fees", "지급·용역수수료", ("지급수수료", "판매수수료", "외주용역", "용역비", "서비스비", "수수료")),
    ("marketing", "광고·판매촉진비", ("광고", "선전", "판매촉진", "판촉", "판매장려")),
    ("depreciation", "감가·상각비", ("감가상각", "무형자산상각", "사용권자산상각", "상각비")),
    ("logistics", "물류·운반비", ("운반", "물류", "배송", "보관")),
    ("research", "연구개발비", ("연구", "개발")),
    ("facility", "세금·시설운영비", ("세금과공과", "세금", "공과", "임차", "수도", "광열", "전력", "수선", "보험료", "통신비")),
)


def _decimal(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    text = str(value).replace(",", "").replace(" ", "").strip()
    if not text or text in {"-", "—", "N/A"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()")
    try:
        parsed = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return -parsed if negative else parsed


def _normalized_label(value: object) -> str:
    return re.sub(r"[\sㆍ·:()\[\]-]+", "", str(value or "")).strip()


def _is_total_label(label: str) -> bool:
    normalized = _normalized_label(label)
    return any(
        normalized == candidate or normalized == f"{candidate}합계"
        for candidate in TOTAL_LABELS
    )


def _is_subtotal_label(label: str, account_code: str) -> bool:
    normalized = _normalized_label(label)
    lowered_code = account_code.lower()
    if "totalsellinggeneraladministrativeexpenses" in lowered_code:
        return True
    if _is_total_label(label) or any(word in normalized for word in SUBTOTAL_WORDS):
        return True
    if normalized in {"계", "판매비", "관리비", "일반관리비"}:
        return True
    if "판매비와관리비" in normalized and not normalized.startswith("기타"):
        return True
    return False


def _row_entries(table) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["te", "td", "th"], recursive=False)
        for index, cell in enumerate(cells):
            amount = _decimal(cell.get_text(" ", strip=True))
            context = str(cell.get("acontext") or "")
            account_code = str(cell.get("acode") or "")
            if amount is None or not (context or account_code or str(cell.get("align") or "").upper() == "RIGHT"):
                continue
            label = ""
            for previous in reversed(cells[:index]):
                candidate = previous.get_text(" ", strip=True)
                if candidate and _decimal(candidate) is None:
                    label = candidate
                    break
            if not label:
                continue
            entries.append(
                {
                    "label": label,
                    "amount": amount,
                    "context": context,
                    "account_code": account_code,
                    "decimal": str(cell.get("adecimal") or ""),
                }
            )
    return entries


def _table_unit(table, entries: list[dict[str, object]]) -> tuple[str, Decimal]:
    previous_unit = table.find_previous(
        string=lambda value: isinstance(value, str) and "단위" in value and any(unit in value for unit in ("백만원", "천원", "억원", "원"))
    )
    normalized = re.sub(r"\s+", "", str(previous_unit or ""))
    if "백만원" in normalized:
        return "백만원", Decimal("0.01")
    if "억원" in normalized:
        return "억원", Decimal("1")
    if "천원" in normalized:
        return "천원", Decimal("0.00001")
    if "원" in normalized:
        return "원", Decimal("0.00000001")
    decimals = {str(item.get("decimal") or "") for item in entries}
    if "-6" in decimals:
        return "백만원", Decimal("0.01")
    if "-3" in decimals:
        return "천원", Decimal("0.00001")
    return "원", Decimal("0.00000001")


def _main_document_xml(document: bytes) -> str:
    with ZipFile(BytesIO(document)) as archive:
        names = [item for item in archive.infolist() if not item.is_dir()]
        if not names:
            return ""
        selected = max(names, key=lambda item: item.file_size)
        raw = archive.read(selected.filename)
    for encoding in ("utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _candidate_sort_key(candidate: dict[str, object]) -> tuple[int, int, int, int]:
    return (
        1 if candidate.get("consolidated") else 0,
        1 if candidate.get("current") else 0,
        int(candidate.get("year") or 0),
        int(candidate.get("detail_count") or 0),
    )


def parse_sga_document(document: bytes, *, fallback_year: Optional[int] = None) -> Optional[dict[str, object]]:
    try:
        xml = _main_document_xml(document)
    except (BadZipFile, OSError):
        return None
    if not xml:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(xml, "html.parser")

    candidates: list[dict[str, object]] = []
    for table in soup.find_all("table"):
        entries = _row_entries(table)
        if len(entries) < 4:
            continue
        totals = [entry for entry in entries if _is_total_label(str(entry["label"]))]
        for total in totals:
            context = str(total.get("context") or "")
            context_entries = [entry for entry in entries if str(entry.get("context") or "") == context] if context else entries
            # A primary financial statement can contain one SGA total plus the
            # same benefit-related OCI line in several year columns. Counting
            # preferred words across the whole table made those duplicated
            # columns look like an SGA note and mixed revenue, cost, tax, and
            # EPS rows into the category total. Require at least two distinct
            # detail labels in the exact period/context being evaluated.
            detail_labels = {
                _normalized_label(entry["label"])
                for entry in context_entries
                if not _is_subtotal_label(
                    str(entry["label"]),
                    str(entry.get("account_code") or ""),
                )
                and any(
                    word in _normalized_label(entry["label"])
                    for word in PREFERRED_DETAIL_WORDS
                )
            }
            if len(detail_labels) < 2:
                continue
            year_match = YEAR_RE.search(context)
            year = int(year_match.group(1)) if year_match else int(fallback_year or 0)
            candidates.append(
                {
                    "table": table,
                    "entries": context_entries,
                    "context": context,
                    "total": total,
                    "year": year,
                    "current": "CFY" in context if context else True,
                    "consolidated": "_ConsolidatedMember" in context,
                    "detail_count": len(detail_labels),
                }
            )
    if not candidates:
        return None

    selected = max(candidates, key=_candidate_sort_key)
    entries = list(selected["entries"])
    total = Decimal(str(selected["total"]["amount"]))
    unit, multiplier = _table_unit(selected["table"], entries)

    ordinary_rnd_exists = any(
        "ordinarydevelopmentexpense" in str(entry.get("account_code") or "").lower()
        or "경상개발비" in _normalized_label(entry.get("label"))
        or "경상연구개발비" in _normalized_label(entry.get("label"))
        for entry in entries
    )
    raw_items: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        label = str(entry["label"]).strip()
        normalized = _normalized_label(label)
        account_code = str(entry.get("account_code") or "")
        lowered_code = account_code.lower()
        if _is_subtotal_label(label, account_code):
            continue
        if "developmentcostcapitalized" in lowered_code or "개발비자산화" in normalized:
            continue
        if ordinary_rnd_exists and "연구개발비총지출액" in normalized and "ordinarydevelopmentexpense" not in lowered_code and not normalized.startswith("경상"):
            continue
        identity = (normalized, account_code)
        if identity in seen:
            continue
        seen.add(identity)
        raw_items.append({"name": label, "amount": Decimal(str(entry["amount"])) * multiplier, "account_code": account_code})

    total_eok = total * multiplier
    item_sum = sum((Decimal(str(item["amount"])) for item in raw_items), Decimal("0"))
    residual = total_eok - item_sum
    tolerance = max(abs(total_eok) * Decimal("0.005"), Decimal("0.01"))
    if residual > tolerance:
        raw_items.append({"name": "그 밖의 공시 항목", "amount": residual, "account_code": "residual"})
        item_sum += residual

    grouped: dict[str, dict[str, object]] = {}
    for item in raw_items:
        normalized = _normalized_label(item["name"])
        category_key = "other"
        category_label = "기타판관비"
        for key, label, words in CATEGORY_RULES:
            if any(word in normalized for word in words):
                category_key, category_label = key, label
                break
        category = grouped.setdefault(
            category_key,
            {"key": category_key, "label": category_label, "amount": Decimal("0"), "details": []},
        )
        category["amount"] = Decimal(str(category["amount"])) + Decimal(str(item["amount"]))
        category["details"].append({"name": item["name"], "amount": item["amount"]})

    categories = sorted(grouped.values(), key=lambda item: (Decimal(str(item["amount"])), str(item["label"])), reverse=True)
    coverage_ratio = None
    if total_eok:
        coverage_ratio = (item_sum * Decimal("100") / total_eok).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return {
        "period": str(selected.get("year") or fallback_year or ""),
        "consolidated": bool(selected.get("consolidated")),
        "display_unit": unit,
        "total_amount": total_eok,
        "coverage_ratio": coverage_ratio,
        "categories": categories,
    }


def _latest_revenue(payload: str, year: str) -> Optional[Decimal]:
    try:
        parsed = json.loads(payload)
    except (TypeError, ValueError):
        return None
    annual = ((parsed.get("financial_series") or {}).get("annual") or [])
    matching: list[tuple[int, Decimal]] = []
    for point in annual:
        if not isinstance(point, dict) or point.get("estimated"):
            continue
        period_match = re.search(r"(20\d{2})", str(point.get("period") or ""))
        revenue = _decimal(point.get("revenue"))
        if not period_match or revenue is None:
            continue
        point_year = int(period_match.group(1))
        matching.append((point_year, revenue))
    if not matching:
        return None
    requested = int(year) if str(year).isdigit() else None
    exact = next((revenue for point_year, revenue in matching if point_year == requested), None)
    return exact if exact is not None else max(matching, key=lambda item: item[0])[1]


def _ratio(amount: Decimal, denominator: Optional[Decimal]) -> Optional[Decimal]:
    if denominator in (None, 0):
        return None
    return (amount * Decimal("100") / Decimal(str(denominator))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _empty_payload(stock: StockMaster, message: str, *, source_url: Optional[str] = None) -> dict[str, object]:
    return {
        "code": stock.code,
        "name": stock.name,
        "available": False,
        "detail_available": False,
        "period": None,
        "consolidated": None,
        "unit": "억원",
        "revenue": None,
        "total_amount": None,
        "sales_ratio": None,
        "coverage_ratio": None,
        "categories": [],
        "source": "DART 사업보고서 주석",
        "source_url": source_url,
        "message": message,
    }


def build_sga_analysis(
    db: Session,
    code: str,
    *,
    settings: Optional[Settings] = None,
) -> Optional[dict[str, object]]:
    stock = db.get(StockMaster, code)
    if not stock or not stock.is_active:
        return None
    resolved = settings or get_settings()
    if not resolved.dart_api_key:
        return _empty_payload(stock, "DART 인증키가 없어 판관비 세부 주석을 확인할 수 없습니다.")

    profile = db.get(CompanyProfile, code)
    if profile is None:
        try:
            profile = ensure_company_profile(
                db,
                stock,
                include_business_report=False,
                settings=resolved,
            )
        except Exception:
            db.rollback()
            profile = None
    if profile is None or not profile.corp_code:
        return _empty_payload(stock, "이 기업의 DART 법인 정보를 찾지 못했습니다.")

    receipt_no = None
    if profile.business_report_url:
        match = RECEIPT_NUMBER_RE.search(profile.business_report_url)
        receipt_no = match.group(1) if match else None
    report = None
    if not receipt_no:
        try:
            report = _latest_business_report(resolved.dart_api_key, profile.corp_code)
        except Exception:
            report = None
        receipt_no = str((report or {}).get("rcept_no") or "").strip() or None
    if not receipt_no:
        return _empty_payload(stock, "최신 사업보고서를 찾지 못했습니다.")

    source_url = DART_REPORT_URL.format(receipt_no=receipt_no)
    report_title = str((report or {}).get("report_nm") or profile.business_report_title or "")
    year_match = re.search(r"(20\d{2})", report_title)
    fallback_year = int(year_match.group(1)) if year_match else None
    try:
        document = fetch_opendart_bytes(
            DART_DOCUMENT_URL,
            {"crtfc_key": resolved.dart_api_key, "rcept_no": receipt_no},
            timeout=45,
        )
        parsed = parse_sga_document(document, fallback_year=fallback_year)
    except Exception:
        parsed = None
    if not parsed:
        return _empty_payload(
            stock,
            "사업보고서에 판관비 세부 주석 표가 없거나 자동 분류할 수 없는 형식입니다.",
            source_url=source_url,
        )

    period = str(parsed.get("period") or "")
    fundamental = db.get(StockFundamentalSnapshot, code)
    revenue = _latest_revenue(fundamental.payload, period) if fundamental else None
    total_amount = Decimal(str(parsed["total_amount"]))
    categories: list[dict[str, object]] = []
    for raw_category in parsed.get("categories", []):
        amount = Decimal(str(raw_category["amount"]))
        details = [
            {
                "name": detail["name"],
                "amount": detail["amount"],
                "sales_ratio": _ratio(Decimal(str(detail["amount"])), revenue),
            }
            for detail in raw_category.get("details", [])
        ]
        categories.append(
            {
                "key": raw_category["key"],
                "label": raw_category["label"],
                "amount": amount,
                "sales_ratio": _ratio(amount, revenue),
                "share_of_sga": _ratio(amount, total_amount),
                "details": details,
            }
        )

    return {
        "code": stock.code,
        "name": stock.name,
        "available": True,
        "detail_available": bool(categories),
        "period": period or None,
        "consolidated": bool(parsed.get("consolidated")),
        "unit": "억원",
        "revenue": revenue,
        "total_amount": total_amount,
        "sales_ratio": _ratio(total_amount, revenue),
        "coverage_ratio": parsed.get("coverage_ratio"),
        "categories": categories,
        "source": "DART 사업보고서 주석",
        "source_url": source_url,
        "message": "연결재무제표 주석 기준" if parsed.get("consolidated") else "별도재무제표 주석 기준",
    }
