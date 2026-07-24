from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.opendart import fetch_opendart_json
from app.models import CompanyProfile, DisclosureItem, FinancialStatementLine, StockMaster
from app.repository import finish_ingestion, start_ingestion, upsert_many
from app.services.company_profiles import dart_corp_code_map


REPORT_CODES = {
    "annual": "11011",
    "q1": "11013",
    "half": "11012",
    "q3": "11014",
}


@dataclass(frozen=True)
class FinancialStatementCompany:
    stock_code: str
    corp_code: str
    company_name: str


def latest_financial_report_target(today: Optional[date] = None) -> tuple[str, str]:
    current = today or date.today()
    if (current.month, current.day) >= (11, 16):
        return str(current.year), "q3"
    if (current.month, current.day) >= (8, 16):
        return str(current.year), "half"
    if (current.month, current.day) >= (5, 16):
        return str(current.year), "q1"
    return str(current.year - 1), "annual"


def _amount(value: Optional[str]) -> Optional[Decimal]:
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(value.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def _report_code(report: str) -> str:
    return REPORT_CODES.get(report, report)


def _financial_statement_rows(
    *,
    dart_api_key: str,
    corp_code: str,
    bsns_year: str,
    report: str,
    fs_div: str,
    stock_code: Optional[str] = None,
) -> list[dict[str, Any]]:
    reprt_code = _report_code(report)
    payload = fetch_opendart_json(
        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
        {
            "crtfc_key": dart_api_key,
            "corp_code": corp_code,
            "bsns_year": bsns_year,
            "reprt_code": reprt_code,
            "fs_div": fs_div,
        },
        timeout=30,
    )
    if payload.get("status") != "000":
        raise RuntimeError(f"DART error {payload.get('status')}: {payload.get('message')}")

    rows: list[dict[str, Any]] = []
    for item in payload.get("list", []):
        rows.append(
            {
                "corp_code": corp_code,
                "stock_code": item.get("stock_code") or stock_code,
                "bsns_year": bsns_year,
                "reprt_code": reprt_code,
                "fs_div": item.get("fs_div") or fs_div,
                "sj_div": item.get("sj_div"),
                "account_id": item.get("account_id"),
                "account_name": item.get("account_nm") or item.get("account_name") or "",
                "ord": int(item["ord"]) if str(item.get("ord", "")).isdigit() else None,
                "current_amount": _amount(item.get("thstrm_amount")),
                "previous_amount": _amount(item.get("frmtrm_amount")),
                "raw": json.dumps(item, ensure_ascii=False),
            }
        )
    deduped: dict[tuple[object, ...], dict[str, Any]] = {}
    for row in rows:
        key = (
            row.get("corp_code"),
            row.get("stock_code"),
            row.get("bsns_year"),
            row.get("reprt_code"),
            row.get("fs_div"),
            row.get("sj_div"),
            row.get("account_id"),
            row.get("account_name"),
            row.get("ord"),
        )
        deduped[key] = row
    return list(deduped.values())


def collect_financial_statement(
    db: Session,
    corp_code: str,
    bsns_year: str,
    report: str = "annual",
    fs_div: str = "CFS",
    stock_code: Optional[str] = None,
) -> int:
    settings = get_settings()
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY is missing in .env")

    reprt_code = _report_code(report)
    run = start_ingestion(db, "dart", f"financial_statement:{corp_code}:{bsns_year}:{reprt_code}")
    try:
        rows = _financial_statement_rows(
            dart_api_key=settings.dart_api_key,
            corp_code=corp_code,
            bsns_year=bsns_year,
            report=report,
            fs_div=fs_div,
            stock_code=stock_code,
        )
        count = upsert_many(db, FinancialStatementLine, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def _companies_from_disclosures(
    db: Session,
    *,
    stock_codes: Optional[list[str]] = None,
    limit: Optional[int] = None,
    settings=None,
) -> list[FinancialStatementCompany]:
    disclosure_statement = (
        select(DisclosureItem.stock_code, DisclosureItem.corp_code, DisclosureItem.company_name)
        .where(DisclosureItem.stock_code.is_not(None))
        .where(DisclosureItem.corp_code.is_not(None))
        .order_by(desc(DisclosureItem.published_at), DisclosureItem.stock_code)
    )
    if stock_codes:
        disclosure_statement = disclosure_statement.where(DisclosureItem.stock_code.in_(stock_codes))

    corp_by_code: dict[str, str] = {}
    name_by_code: dict[str, str] = {}
    for stock_code, corp_code, company_name in db.execute(disclosure_statement).all():
        code = str(stock_code)
        if code not in corp_by_code:
            corp_by_code[code] = str(corp_code)
            name_by_code[code] = str(company_name or code)

    profile_statement = select(CompanyProfile.stock_code, CompanyProfile.corp_code, CompanyProfile.corp_name)
    if stock_codes:
        profile_statement = profile_statement.where(CompanyProfile.stock_code.in_(stock_codes))
    for stock_code, corp_code, company_name in db.execute(profile_statement).all():
        code = str(stock_code)
        corp_by_code[code] = str(corp_code)
        name_by_code[code] = str(company_name or code)

    stock_statement = (
        select(StockMaster.code, StockMaster.name)
        .where(StockMaster.is_active.is_(True))
        .where(StockMaster.market.in_(["KOSPI", "KOSDAQ"]))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if stock_codes:
        stock_statement = stock_statement.where(StockMaster.code.in_(stock_codes))
    stocks = list(db.execute(stock_statement).all())
    official_mapping: dict[str, str] = {}
    if any(str(code) not in corp_by_code for code, _ in stocks):
        try:
            official_mapping = dart_corp_code_map(settings)
        except Exception:
            # Continue with corp codes already checkpointed from profiles and
            # disclosures. A later run can fill the remainder when DART recovers.
            official_mapping = {}
    companies: list[FinancialStatementCompany] = []
    seen_codes: set[str] = set()
    for code, stock_name in stocks:
        normalized_code = str(code)
        corp_code = corp_by_code.get(normalized_code) or official_mapping.get(normalized_code)
        if not corp_code:
            continue
        seen_codes.add(normalized_code)
        companies.append(
            FinancialStatementCompany(
                stock_code=normalized_code,
                corp_code=corp_code,
                company_name=name_by_code.get(normalized_code) or str(stock_name or normalized_code),
            )
        )
        if limit and len(companies) >= limit:
            break
    if not limit or len(companies) < limit:
        for normalized_code, corp_code in corp_by_code.items():
            if normalized_code in seen_codes:
                continue
            companies.append(
                FinancialStatementCompany(
                    stock_code=normalized_code,
                    corp_code=corp_code,
                    company_name=name_by_code.get(normalized_code) or normalized_code,
                )
            )
            if limit and len(companies) >= limit:
                break
    return companies


def _financial_statement_exists(
    db: Session,
    *,
    corp_code: str,
    bsns_year: str,
    report: str,
    fs_div: str,
) -> bool:
    return bool(
        db.scalar(
            select(func.count())
            .select_from(FinancialStatementLine)
            .where(FinancialStatementLine.corp_code == corp_code)
            .where(FinancialStatementLine.bsns_year == bsns_year)
            .where(FinancialStatementLine.reprt_code == _report_code(report))
            .where(FinancialStatementLine.fs_div == fs_div)
        )
    )


def collect_financial_statements_for_disclosure_companies(
    db: Session,
    *,
    bsns_year: Optional[str] = None,
    report: Optional[str] = None,
    fs_div: str = "CFS",
    stock_codes: Optional[list[str]] = None,
    limit: Optional[int] = None,
    skip_existing: bool = True,
    fallback_previous_annual: bool = True,
    batch_size: int = 1000,
) -> dict[str, object]:
    settings = get_settings()
    if not settings.dart_api_key:
        raise RuntimeError("DART_API_KEY is missing in .env")

    if not bsns_year or not report:
        default_year, default_report = latest_financial_report_target()
        bsns_year = bsns_year or default_year
        report = report or default_report
    reprt_code = _report_code(report)
    fallback_year = str(int(bsns_year) - 1) if fallback_previous_annual and report != "annual" else None
    companies = _companies_from_disclosures(
        db,
        stock_codes=stock_codes,
        limit=limit,
        settings=settings,
    )
    run = start_ingestion(db, "dart", f"financial_statement_bulk:{bsns_year}:{reprt_code}")
    rows_loaded = 0
    companies_loaded = 0
    fallback_loaded = 0
    standalone_loaded = 0
    skipped = 0
    errors: dict[str, str] = {}
    pending_rows: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal pending_rows, rows_loaded
        if not pending_rows:
            return
        rows_loaded += upsert_many(db, FinancialStatementLine, pending_rows)
        db.commit()
        pending_rows = []

    def existing_for_target(company: FinancialStatementCompany, year: str, target_report: str) -> bool:
        if _financial_statement_exists(
            db,
            corp_code=company.corp_code,
            bsns_year=year,
            report=target_report,
            fs_div=fs_div,
        ):
            return True
        return fs_div == "CFS" and _financial_statement_exists(
            db,
            corp_code=company.corp_code,
            bsns_year=year,
            report=target_report,
            fs_div="OFS",
        )

    def fetch_rows(company: FinancialStatementCompany, year: str, target_report: str) -> tuple[list[dict[str, Any]], bool]:
        try:
            rows = _financial_statement_rows(
                dart_api_key=settings.dart_api_key,
                corp_code=company.corp_code,
                bsns_year=year,
                report=target_report,
                fs_div=fs_div,
                stock_code=company.stock_code,
            )
            if rows or fs_div != "CFS":
                return rows, False
        except Exception:
            if fs_div != "CFS":
                raise
        rows = _financial_statement_rows(
            dart_api_key=settings.dart_api_key,
            corp_code=company.corp_code,
            bsns_year=year,
            report=target_report,
            fs_div="OFS",
            stock_code=company.stock_code,
        )
        return rows, bool(rows)

    try:
        for company in companies:
            if skip_existing and existing_for_target(company, bsns_year, report):
                skipped += 1
                continue

            try:
                rows, used_standalone = fetch_rows(company, bsns_year, report)
                if rows:
                    pending_rows.extend(rows)
                    companies_loaded += 1
                    standalone_loaded += int(used_standalone)
            except Exception as exc:
                if (
                    fallback_year
                    and not existing_for_target(company, fallback_year, "annual")
                ):
                    try:
                        rows, used_standalone = fetch_rows(company, fallback_year, "annual")
                        if rows:
                            pending_rows.extend(rows)
                            companies_loaded += 1
                            fallback_loaded += 1
                            standalone_loaded += int(used_standalone)
                        continue
                    except Exception as fallback_exc:
                        errors[company.stock_code] = str(fallback_exc)
                        continue
                errors[company.stock_code] = str(exc)
                continue

            if len(pending_rows) >= batch_size:
                flush()

        flush()
        message = (
            f"companies={companies_loaded}/{len(companies)} skipped={skipped} "
            f"fallback={fallback_loaded} standalone={standalone_loaded} "
            f"failed={len(errors)} report={bsns_year}:{reprt_code}"
        )
        finish_ingestion(db, run, "success", rows_loaded, message)
        return {
            "rows_loaded": rows_loaded,
            "companies": len(companies),
            "companies_loaded": companies_loaded,
            "skipped": skipped,
            "fallback_loaded": fallback_loaded,
            "standalone_loaded": standalone_loaded,
            "failed": len(errors),
            "errors": errors,
            "bsns_year": bsns_year,
            "report": report,
            "reprt_code": reprt_code,
            "message": message,
        }
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded, str(exc))
        raise
