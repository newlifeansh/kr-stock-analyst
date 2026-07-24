from __future__ import annotations

from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from io import BytesIO
import json
import re
import time
from typing import Optional
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.integrations.opendart import fetch_opendart_bytes, fetch_opendart_json
from app.models import CompanyProfile, DisclosureItem, StockCompanySnapshot, StockMaster
from app.repository import finish_ingestion, start_ingestion, upsert_many


DART_COMPANY_URL = "https://opendart.fss.or.kr/api/company.json"
DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_DISCLOSURE_LIST_URL = "https://opendart.fss.or.kr/api/list.json"
DART_DOCUMENT_URL = "https://opendart.fss.or.kr/api/document.xml"
DART_REPORT_URL = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"
DART_COMPANY_PAGE_URL = "https://dart.fss.or.kr/dsae001/selectPopup.ax?selectKey={corp_code}"
PROFILE_REFRESH_DAYS = 30


def _parse_date(value: object, fmt: str = "%Y%m%d") -> Optional[date]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, fmt).date()
    except ValueError:
        return None


def _parse_datetime(value: object) -> Optional[datetime]:
    parsed = _parse_date(value)
    return datetime.combine(parsed, datetime.min.time()) if parsed else None


def _normalized_url(value: object) -> Optional[str]:
    raw = str(value or "").strip()
    if not raw:
        return None
    if raw.startswith(("http://", "https://")):
        return raw
    return f"https://{raw.lstrip('/')}"


@lru_cache(maxsize=4)
def _dart_corp_code_map(api_key: str) -> dict[str, str]:
    payload = fetch_opendart_bytes(
        DART_CORP_CODE_URL,
        {"crtfc_key": api_key},
        timeout=45,
    )
    try:
        with ZipFile(BytesIO(payload)) as archive:
            xml_name = next((name for name in archive.namelist() if name.lower().endswith(".xml")), None)
            if not xml_name:
                return {}
            root = ET.fromstring(archive.read(xml_name))
    except (BadZipFile, ET.ParseError):
        return {}
    mapping: dict[str, str] = {}
    for item in root.findall(".//list"):
        stock_code = str(item.findtext("stock_code") or "").strip()
        corp_code = str(item.findtext("corp_code") or "").strip()
        if stock_code and corp_code:
            mapping[stock_code] = corp_code
    return mapping


def dart_corp_code_map(settings: Optional[Settings] = None) -> dict[str, str]:
    resolved = settings or get_settings()
    if not resolved.dart_api_key:
        return {}
    return dict(_dart_corp_code_map(resolved.dart_api_key))


def _corp_code_for_stock(db: Session, stock_code: str, api_key: str) -> Optional[str]:
    existing = db.get(CompanyProfile, stock_code)
    if existing and existing.corp_code:
        return existing.corp_code
    corp_code = db.scalar(
        select(DisclosureItem.corp_code)
        .where(DisclosureItem.stock_code == stock_code)
        .where(DisclosureItem.corp_code.is_not(None))
        .order_by(desc(DisclosureItem.published_at), desc(DisclosureItem.id))
        .limit(1)
    )
    if corp_code:
        return str(corp_code)
    return _dart_corp_code_map(api_key).get(stock_code)


def _latest_business_report(api_key: str, corp_code: str) -> Optional[dict[str, object]]:
    today = date.today()
    payload = fetch_opendart_json(
        DART_DISCLOSURE_LIST_URL,
        {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bgn_de": f"{today.year - 3}0101",
            "end_de": today.strftime("%Y%m%d"),
            "pblntf_ty": "A",
            "page_count": 100,
        },
        timeout=25,
    )
    if payload.get("status") != "000":
        return None
    reports = [
        item
        for item in payload.get("list", [])
        if "사업보고서" in str(item.get("report_nm") or "")
    ]
    if not reports:
        return None
    reports.sort(key=lambda item: str(item.get("rcept_dt") or ""), reverse=True)
    return reports[0]


def _document_text(payload: bytes) -> str:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            chunks: list[str] = []
            for name in archive.namelist():
                if not name.lower().endswith((".xml", ".html", ".htm")):
                    continue
                raw = archive.read(name)
                decoded = raw.decode("utf-8", errors="ignore")
                if not decoded.strip():
                    decoded = raw.decode("euc-kr", errors="ignore")
                chunks.append(BeautifulSoup(decoded, "xml").get_text("\n", strip=True))
            return "\n".join(chunks)
    except BadZipFile:
        return ""


def extract_business_summary(payload: bytes, max_characters: int = 480) -> Optional[str]:
    text = _document_text(payload)
    if not text:
        return None
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    compact = [re.sub(r"[\s·ㆍⅠⅡⅢIVX.0-9-]", "", line) for line in lines]
    overview_starts = [
        index
        for index, line in enumerate(lines)
        if compact[index] == "사업의개요" and len(line) < 80
    ]
    overview_candidates: list[list[str]] = []
    for start in overview_starts:
        paragraphs: list[str] = []
        for index in range(start + 1, min(len(lines), start + 80)):
            line = lines[index]
            normalized = compact[index]
            if normalized in {
                "주요제품및서비스",
                "원재료및생산설비",
                "매출및수주상황",
                "위험관리및파생거래",
                "주요계약및연구개발활동",
                "기타참고사항",
                "재무에관한사항",
            }:
                break
            if len(line) < 38 or len(line) > 900 or not re.search(r"[가-힣]", line):
                continue
            if sum(character.isdigit() for character in line) / max(len(line), 1) > 0.24:
                continue
            paragraphs.append(line)
            if len(paragraphs) >= 3:
                break
        if paragraphs:
            overview_candidates.append(paragraphs)
    if overview_candidates:
        paragraphs = max(overview_candidates, key=lambda group: sum(len(line) for line in group))
        sentences: list[str] = []
        for paragraph in paragraphs:
            normalized_paragraph = re.sub(r"(?<=[.!?])(?=[가-힣A-Za-z])", " ", paragraph)
            sentences.extend(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", normalized_paragraph)
                if sentence.strip()
            )
        selected: list[str] = []
        total = 0
        for line in sentences:
            sentence = line if line.endswith((".", "다", "요")) else f"{line}."
            remaining = max_characters - total
            if remaining <= 0:
                break
            if len(sentence) > remaining:
                sentence = sentence[:remaining].rsplit(".", 1)[0].strip()
                if sentence:
                    sentence = f"{sentence}."
            if sentence:
                selected.append(sentence)
                total += len(sentence) + 1
            if len(selected) >= 2:
                break
        if selected:
            return " ".join(selected)

    starts = [
        index
        for index, line in enumerate(lines)
        if compact[index] == "사업의내용" and len(line) < 80
    ]
    if not starts:
        return None
    keywords = ("회사", "당사", "사업", "제품", "서비스", "생산", "판매", "개발", "시장", "고객")
    rejected = ("단위", "주1", "주 1", "연결재무", "감사보고서", "목 차", "표준산업분류")
    candidate_groups: list[list[tuple[int, str]]] = []
    for start in starts:
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if compact[index] == "재무에관한사항" and len(lines[index]) < 80
            ),
            min(len(lines), start + 1200),
        )
        candidates: list[tuple[int, str]] = []
        seen: set[str] = set()
        for line in lines[start + 1 : end]:
            if len(line) < 38 or len(line) > 420 or not re.search(r"[가-힣]", line):
                continue
            if any(word in line for word in rejected):
                continue
            digit_ratio = sum(character.isdigit() for character in line) / max(len(line), 1)
            if digit_ratio > 0.22:
                continue
            score = sum(1 for word in keywords if word in line)
            if score < 2:
                continue
            normalized = re.sub(r"[^가-힣A-Za-z0-9]", "", line)
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append((score, line))
        candidate_groups.append(candidates)
    candidates = max(
        candidate_groups,
        key=lambda group: (sum(score for score, _ in group), sum(len(line) for _, line in group)),
        default=[],
    )
    candidates.sort(key=lambda item: item[0], reverse=True)
    selected: list[str] = []
    total = 0
    for _, line in candidates:
        sentence = line if line.endswith((".", "다", "요")) else f"{line}."
        if total + len(sentence) > max_characters and selected:
            continue
        selected.append(sentence)
        total += len(sentence) + 1
        if len(selected) >= 3 or total >= max_characters * 0.8:
            break
    return " ".join(selected) or None


def _fallback_summary(stock: StockMaster, corp_name: Optional[str] = None) -> str:
    name = corp_name or stock.name
    industry = stock.industry or stock.sector
    if industry:
        return f"{name}은 {stock.market}에 상장된 기업으로, 주요 업종은 {industry}입니다."
    return f"{name}은 {stock.market}에 상장된 기업입니다. 사업 설명은 최신 DART 보고서 확인이 필요합니다."


def _topic_particle(word: str) -> str:
    if not word:
        return "는"
    code = ord(word[-1])
    has_batchim = 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0
    return "은" if has_batchim else "는"


def _company_named_summary(summary: Optional[str], stock_name: str) -> Optional[str]:
    if not summary:
        return None
    named = summary
    if named.startswith("당사는"):
        named = f"{stock_name}{_topic_particle(stock_name)}{named[len('당사는'):]}"
    named = named.replace("당사 및 당사의 종속기업", f"{stock_name}와 종속기업", 1)
    return named


def _short_company_summary(summary: Optional[str], stock_name: str) -> Optional[str]:
    if not summary:
        return None
    normalized = re.sub(r"\s+", " ", summary).strip()
    normalized = re.sub(
        rf"^{re.escape(stock_name)}[은는]",
        f"{stock_name}{_topic_particle(stock_name)}",
        normalized,
        count=1,
    )
    product_match = re.search(
        r"(?:주력|주요) (?:제품|사업)은\s*(.+?)(?:이며|이고|입니다)",
        normalized,
    )
    if product_match:
        main_business = product_match.group(1).strip(" ,.")
        main_business = main_business.replace(" 및 ", "·").replace("를 중심으로 하는", " 중심의")
        secondary_match = re.search(
            r"([A-Za-z가-힣0-9·]+(?:\s+[A-Za-z가-힣0-9·]+){0,3}\s+사업)도 병행",
            normalized,
        )
        secondary = secondary_match.group(1).strip() if secondary_match else ""
        if secondary and secondary not in main_business:
            return f"{main_business}가 주력이며, {secondary}도 병행합니다."
        return f"주력 분야는 {main_business}입니다."
    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
    return first_sentence if first_sentence.endswith((".", "!", "?")) else f"{first_sentence}."


def ensure_company_profile(
    db: Session,
    stock: StockMaster,
    *,
    refresh: bool = False,
    include_business_report: bool = True,
    settings: Optional[Settings] = None,
) -> Optional[CompanyProfile]:
    settings = settings or get_settings()
    existing = db.get(CompanyProfile, stock.code)
    if existing and not refresh and existing.updated_at >= datetime.utcnow() - timedelta(days=PROFILE_REFRESH_DAYS):
        if not include_business_report or existing.business_report_url:
            return existing
    if not settings.dart_api_key:
        return existing
    corp_code = _corp_code_for_stock(db, stock.code, settings.dart_api_key)
    if not corp_code:
        return existing
    company = fetch_opendart_json(
        DART_COMPANY_URL,
        {"crtfc_key": settings.dart_api_key, "corp_code": corp_code},
        timeout=20,
    )
    if company.get("status") != "000":
        return existing

    report = None
    summary = None
    if include_business_report:
        try:
            report = _latest_business_report(settings.dart_api_key, corp_code)
            receipt_no = str((report or {}).get("rcept_no") or "").strip()
            if receipt_no:
                document = fetch_opendart_bytes(
                    DART_DOCUMENT_URL,
                    {"crtfc_key": settings.dart_api_key, "rcept_no": receipt_no},
                    timeout=45,
                )
                summary = _company_named_summary(extract_business_summary(document), stock.name)
        except Exception:
            summary = None

    profile = existing or CompanyProfile(
        stock_code=stock.code,
        corp_code=corp_code,
        corp_name=str(company.get("corp_name") or stock.name),
    )
    profile.corp_code = corp_code
    profile.corp_name = str(company.get("corp_name") or stock.name)
    profile.corp_name_eng = str(company.get("corp_name_eng") or "").strip() or None
    profile.ceo_name = str(company.get("ceo_nm") or "").strip() or None
    profile.corp_class = str(company.get("corp_cls") or "").strip() or None
    profile.address = str(company.get("adres") or "").strip() or None
    profile.homepage_url = _normalized_url(company.get("hm_url"))
    profile.ir_url = _normalized_url(company.get("ir_url"))
    profile.phone = str(company.get("phn_no") or "").strip() or None
    profile.industry_code = str(company.get("induty_code") or "").strip() or None
    profile.established_date = _parse_date(company.get("est_dt"))
    profile.fiscal_month = str(company.get("acc_mt") or "").strip() or None
    profile.business_summary = summary or _fallback_summary(stock, profile.corp_name)
    profile.summary_source = "dart_business_report" if summary else "dart_company_profile"
    profile.source_modified_date = _parse_date(company.get("modify_date"))
    profile.raw = json.dumps(company, ensure_ascii=False)
    if report:
        receipt_no = str(report.get("rcept_no") or "").strip()
        profile.business_report_title = str(report.get("report_nm") or "").strip() or None
        profile.business_report_url = DART_REPORT_URL.format(receipt_no=receipt_no) if receipt_no else None
        profile.business_report_published_at = _parse_datetime(report.get("rcept_dt"))
    if existing is None:
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def collect_company_profiles(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    limit: Optional[int] = None,
    refresh: bool = False,
    include_business_reports: bool = False,
    max_workers: int = 2,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY is missing in .env")
    market_values = [value.strip().upper() for value in markets.split(",") if value.strip()]
    statement = (
        select(StockMaster)
        .where(StockMaster.is_active.is_(True))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if market_values:
        statement = statement.where(StockMaster.market.in_(market_values))
    if limit:
        statement = statement.limit(limit)
    stocks = list(db.scalars(statement))
    run = start_ingestion(db, "dart", "company_profiles")
    loaded = 0
    errors: dict[str, str] = {}
    try:
        if not include_business_reports:
            fresh_cutoff = datetime.utcnow() - timedelta(days=PROFILE_REFRESH_DAYS)
            existing_by_code = {
                profile.stock_code: profile
                for profile in db.scalars(
                    select(CompanyProfile).where(CompanyProfile.stock_code.in_([stock.code for stock in stocks]))
                )
            }
            targets = [
                stock
                for stock in stocks
                if refresh
                or stock.code not in existing_by_code
                or existing_by_code[stock.code].updated_at < fresh_cutoff
            ]
            corp_mapping = {
                stock_code: corp_code
                for stock_code, corp_code in db.execute(
                    select(DisclosureItem.stock_code, DisclosureItem.corp_code)
                    .where(DisclosureItem.stock_code.is_not(None))
                    .where(DisclosureItem.corp_code.is_not(None))
                    .distinct()
                )
                if stock_code and corp_code
            }
            corp_mapping.update(
                {
                    profile.stock_code: profile.corp_code
                    for profile in existing_by_code.values()
                    if profile.corp_code
                }
            )
            try:
                corp_mapping.update(dart_corp_code_map(settings))
            except Exception:
                # Existing disclosures retain enough corp-code coverage to resume
                # a partially completed backfill while DART is throttling the ZIP endpoint.
                pass

            def fetch_overview(stock: StockMaster):
                corp_code = corp_mapping.get(stock.code)
                if not corp_code:
                    return stock, None, None
                last_error: Optional[Exception] = None
                for attempt in range(4):
                    try:
                        company = fetch_opendart_json(
                            DART_COMPANY_URL,
                            {"crtfc_key": settings.dart_api_key, "corp_code": corp_code},
                            timeout=20,
                        )
                        if company.get("status") == "000":
                            return stock, corp_code, company
                        if company.get("status") not in {"020", "800", "900"}:
                            return stock, corp_code, company
                    except Exception as exc:
                        last_error = exc
                    if attempt < 3:
                        time.sleep(0.35 * (2**attempt))
                if last_error:
                    raise last_error
                return stock, corp_code, company

            rows: list[dict[str, object]] = []
            worker_count = max(1, min(max_workers, len(targets) or 1))
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = {executor.submit(fetch_overview, stock): stock for stock in targets}
                for future in as_completed(futures):
                    stock = futures[future]
                    try:
                        stock, corp_code, company = future.result()
                        if not corp_code:
                            errors[stock.code] = "DART corp code unavailable"
                            continue
                        if not company or company.get("status") != "000":
                            status = str((company or {}).get("status") or "unknown")
                            message = str((company or {}).get("message") or "company profile unavailable")
                            errors[stock.code] = f"DART {status}: {message}"
                            continue
                        existing = existing_by_code.get(stock.code)
                        rows.append(
                            {
                                "stock_code": stock.code,
                                "corp_code": corp_code,
                                "corp_name": str(company.get("corp_name") or stock.name),
                                "corp_name_eng": str(company.get("corp_name_eng") or "").strip() or None,
                                "ceo_name": str(company.get("ceo_nm") or "").strip() or None,
                                "corp_class": str(company.get("corp_cls") or "").strip() or None,
                                "address": str(company.get("adres") or "").strip() or None,
                                "homepage_url": _normalized_url(company.get("hm_url")),
                                "ir_url": _normalized_url(company.get("ir_url")),
                                "phone": str(company.get("phn_no") or "").strip() or None,
                                "industry_code": str(company.get("induty_code") or "").strip() or None,
                                "established_date": _parse_date(company.get("est_dt")),
                                "fiscal_month": str(company.get("acc_mt") or "").strip() or None,
                                "business_summary": (
                                    existing.business_summary
                                    if existing and existing.business_summary
                                    else _fallback_summary(stock, str(company.get("corp_name") or stock.name))
                                ),
                                "summary_source": existing.summary_source if existing else "dart_company_profile",
                                "business_report_title": existing.business_report_title if existing else None,
                                "business_report_url": existing.business_report_url if existing else None,
                                "business_report_published_at": (
                                    existing.business_report_published_at if existing else None
                                ),
                                "source_modified_date": _parse_date(company.get("modify_date")),
                                "raw": json.dumps(company, ensure_ascii=False),
                                "updated_at": datetime.utcnow(),
                            }
                        )
                    except Exception as exc:
                        errors[stock.code] = str(exc)
            if rows:
                loaded = upsert_many(db, CompanyProfile, rows)
                db.commit()
            loaded += len(stocks) - len(targets)
            message = (
                f"target={len(stocks)} loaded={loaded} refreshed={len(rows)} "
                f"skipped={len(stocks) - len(targets)} failed={len(errors)}"
            )
            finish_ingestion(db, run, "success", loaded, message)
            return {
                "target": len(stocks),
                "rows_loaded": loaded,
                "failed": len(errors),
                "errors": errors,
                "message": message,
            }

        for stock in stocks:
            try:
                profile = ensure_company_profile(
                    db,
                    stock,
                    refresh=refresh,
                    include_business_report=include_business_reports,
                    settings=settings,
                )
                if profile:
                    loaded += 1
                else:
                    errors[stock.code] = "DART company profile unavailable"
            except Exception as exc:
                db.rollback()
                errors[stock.code] = str(exc)
        message = f"target={len(stocks)} loaded={loaded} failed={len(errors)}"
        finish_ingestion(db, run, "success", loaded, message)
        return {
            "target": len(stocks),
            "rows_loaded": loaded,
            "failed": len(errors),
            "errors": errors,
            "message": message,
        }
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", loaded, str(exc))
        raise


def company_profile_payload(db: Session, stock: StockMaster) -> dict[str, object]:
    try:
        profile = db.get(CompanyProfile, stock.code)
        company_snapshot = db.get(StockCompanySnapshot, stock.code)
    except SQLAlchemyError:
        db.rollback()
        profile = None
        company_snapshot = None
    if profile is None:
        summary = (
            company_snapshot.summary
            if company_snapshot and company_snapshot.summary
            else _fallback_summary(stock)
        )
        return {
            "summary": summary,
            "short_summary": _short_company_summary(summary, stock.name),
            "summary_source": company_snapshot.source if company_snapshot else "stock_master",
            "industry": (
                company_snapshot.industry
                if company_snapshot and company_snapshot.industry
                else stock.industry or stock.sector
            ),
            "sector": company_snapshot.sector if company_snapshot else stock.sector,
            "source_label": "네이버 금융 기업현황" if company_snapshot else "상장 종목 기본정보",
            "source_url": company_snapshot.source_url if company_snapshot else None,
            "updated_at": company_snapshot.updated_at if company_snapshot else stock.updated_at,
        }
    source_url = profile.business_report_url or DART_COMPANY_PAGE_URL.format(corp_code=profile.corp_code)
    summary = profile.business_summary or _fallback_summary(stock, profile.corp_name)
    summary_source = profile.summary_source
    source_label = "DART 사업보고서" if profile.summary_source == "dart_business_report" else "DART 기업개황"
    if profile.summary_source != "dart_business_report" and company_snapshot and company_snapshot.summary:
        summary = company_snapshot.summary
        summary_source = company_snapshot.source
        source_label = "네이버 금융 기업현황"
        source_url = company_snapshot.source_url or source_url
    return {
        "corp_name": profile.corp_name,
        "corp_name_eng": profile.corp_name_eng,
        "summary": summary,
        "short_summary": _short_company_summary(summary, stock.name),
        "summary_source": summary_source,
        "industry": (
            company_snapshot.industry
            if company_snapshot and company_snapshot.industry
            else stock.industry or stock.sector
        ),
        "sector": company_snapshot.sector if company_snapshot and company_snapshot.sector else stock.sector,
        "ceo_name": profile.ceo_name,
        "address": profile.address,
        "homepage_url": profile.homepage_url,
        "ir_url": profile.ir_url,
        "established_date": profile.established_date,
        "fiscal_month": profile.fiscal_month,
        "business_report_title": profile.business_report_title,
        "business_report_url": profile.business_report_url,
        "business_report_published_at": profile.business_report_published_at,
        "source_label": source_label,
        "source_url": source_url,
        "updated_at": (
            company_snapshot.updated_at
            if summary_source == "naver_wisereport" and company_snapshot
            else profile.updated_at
        ),
    }
