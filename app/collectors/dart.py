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
from app.models import DisclosureItem, FinancialStatementLine
from app.repository import finish_ingestion, start_ingestion, upsert_many


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
    return rows


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
) -> list[FinancialStatementCompany]:
    statement = (
        select(DisclosureItem.stock_code, DisclosureItem.corp_code, DisclosureItem.company_name)
        .where(DisclosureItem.stock_code.is_not(None))
        .where(DisclosureItem.corp_code.is_not(None))
        .order_by(desc(DisclosureItem.published_at), DisclosureItem.stock_code)
    )
    if stock_codes:
        statement = statement.where(DisclosureItem.stock_code.in_(stock_codes))

    companies: list[FinancialStatementCompany] = []
    seen: set[tuple[str, str]] = set()
    for stock_code, corp_code, company_name in db.execute(statement).all():
        key = (str(stock_code), str(corp_code))
        if key in seen:
            continue
        seen.add(key)
        companies.append(
            FinancialStatementCompany(
                stock_code=str(stock_code),
                corp_code=str(corp_code),
                company_name=str(company_name or stock_code),
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
    companies = _companies_from_disclosures(db, stock_codes=stock_codes, limit=limit)
    run = start_ingestion(db, "dart", f"financial_statement_bulk:{bsns_year}:{reprt_code}")
    rows_loaded = 0
    companies_loaded = 0
    fallback_loaded = 0
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

    try:
        for company in companies:
            if skip_existing and _financial_statement_exists(
                db,
                corp_code=company.corp_code,
                bsns_year=bsns_year,
                report=report,
                fs_div=fs_div,
            ):
                skipped += 1
                continue

            try:
                rows = _financial_statement_rows(
                    dart_api_key=settings.dart_api_key,
                    corp_code=company.corp_code,
                    bsns_year=bsns_year,
                    report=report,
                    fs_div=fs_div,
                    stock_code=company.stock_code,
                )
                if rows:
                    pending_rows.extend(rows)
                    companies_loaded += 1
            except Exception as exc:
                if (
                    fallback_year
                    and not _financial_statement_exists(
                        db,
                        corp_code=company.corp_code,
                        bsns_year=fallback_year,
                        report="annual",
                        fs_div=fs_div,
                    )
                ):
                    try:
                        rows = _financial_statement_rows(
                            dart_api_key=settings.dart_api_key,
                            corp_code=company.corp_code,
                            bsns_year=fallback_year,
                            report="annual",
                            fs_div=fs_div,
                            stock_code=company.stock_code,
                        )
                        if rows:
                            pending_rows.extend(rows)
                            companies_loaded += 1
                            fallback_loaded += 1
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
            f"fallback={fallback_loaded} failed={len(errors)} report={bsns_year}:{reprt_code}"
        )
        finish_ingestion(db, run, "success", rows_loaded, message)
        return {
            "rows_loaded": rows_loaded,
            "companies": len(companies),
            "companies_loaded": companies_loaded,
            "skipped": skipped,
            "fallback_loaded": fallback_loaded,
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
