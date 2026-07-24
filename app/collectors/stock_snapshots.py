from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StockCompanySnapshot, StockFundamentalSnapshot, StockMaster, StockNewsSnapshot
from app.repository import finish_ingestion, start_ingestion, upsert_many
from app.services.stock_dashboard import (
    _fetch_naver_item_news,
    _fetch_naver_company_snapshot,
    _fetch_naver_snapshot,
    _json_default,
    fundamental_snapshot_payload,
)


NON_OPERATING_INSTRUMENT_WORDS = ("리츠", "인프라", "리얼티", "코크렙")


def _not_applicable_payload(name: str) -> Optional[dict[str, object]]:
    if not any(word in name for word in NON_OPERATING_INSTRUMENT_WORDS):
        return None
    return {
        "data_status": "not_applicable",
        "instrument_type": "reit_or_infrastructure_fund",
        "unavailable_reason": "리츠·인프라 종목은 일반 상장기업용 재무·밸류에이션 표가 제공되지 않습니다.",
    }


def collect_stock_fundamental_snapshots(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    limit: Optional[int] = None,
    max_workers: int = 8,
    refresh_days: int = 7,
    batch_size: int = 200,
) -> dict[str, object]:
    market_values = [value.strip().upper() for value in markets.split(",") if value.strip()]
    statement = (
        select(StockMaster.code, StockMaster.name)
        .where(StockMaster.is_active.is_(True))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if market_values:
        statement = statement.where(StockMaster.market.in_(market_values))
    if limit:
        statement = statement.limit(limit)
    stocks = list(db.execute(statement).all())
    codes = [code for code, _name in stocks]
    names_by_code = {code: name for code, name in stocks}

    cutoff = datetime.utcnow() - timedelta(days=max(0, refresh_days))
    fresh_codes = set(
        db.scalars(
            select(StockFundamentalSnapshot.stock_code).where(
                StockFundamentalSnapshot.stock_code.in_(codes),
                StockFundamentalSnapshot.fetched_at >= cutoff,
            )
        )
    ) if codes and refresh_days > 0 else set()
    pending_codes = [code for code in codes if code not in fresh_codes]
    run = start_ingestion(db, "naver_finance", "stock_fundamental_snapshot")
    rows_loaded = 0
    failures: dict[str, str] = {}
    pending_rows: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal pending_rows, rows_loaded
        if not pending_rows:
            return
        rows_loaded += upsert_many(db, StockFundamentalSnapshot, pending_rows)
        db.commit()
        pending_rows = []

    try:
        worker_count = max(1, min(max_workers, len(pending_codes) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(_fetch_naver_snapshot, code): code for code in pending_codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    payload = fundamental_snapshot_payload(future.result())
                    if not payload:
                        payload = _not_applicable_payload(names_by_code.get(code, ""))
                    if not payload:
                        failures[code] = "fundamental data unavailable"
                        continue
                    now = datetime.utcnow()
                    pending_rows.append(
                        {
                            "stock_code": code,
                            "source": "naver_finance",
                            "payload": json.dumps(payload, ensure_ascii=False, default=_json_default),
                            "fetched_at": now,
                            "updated_at": now,
                        }
                    )
                except Exception as exc:
                    failures[code] = str(exc)
                    continue
                if len(pending_rows) >= batch_size:
                    flush()
        flush()
        message = (
            f"target={len(codes)} refreshed={rows_loaded} skipped={len(fresh_codes)} "
            f"unavailable={len(failures)}"
        )
        finish_ingestion(db, run, "success", rows_loaded, message)
        return {
            "target": len(codes),
            "rows_loaded": rows_loaded,
            "skipped": len(fresh_codes),
            "failed": len(failures),
            "errors": failures,
            "message": message,
        }
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded, str(exc))
        raise


def collect_stock_news_snapshots(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    limit: Optional[int] = None,
    max_workers: int = 8,
    refresh_hours: int = 6,
    batch_size: int = 200,
) -> dict[str, object]:
    market_values = [value.strip().upper() for value in markets.split(",") if value.strip()]
    statement = (
        select(StockMaster.code)
        .where(StockMaster.is_active.is_(True))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if market_values:
        statement = statement.where(StockMaster.market.in_(market_values))
    if limit:
        statement = statement.limit(limit)
    codes = list(db.scalars(statement))

    cutoff = datetime.utcnow() - timedelta(hours=max(0, refresh_hours))
    fresh_codes = (
        set(
            db.scalars(
                select(StockNewsSnapshot.stock_code).where(
                    StockNewsSnapshot.stock_code.in_(codes),
                    StockNewsSnapshot.fetched_at >= cutoff,
                )
            )
        )
        if codes and refresh_hours > 0
        else set()
    )
    pending_codes = [code for code in codes if code not in fresh_codes]
    run = start_ingestion(db, "naver_finance", "stock_news_snapshot")
    rows_loaded = 0
    news_items = 0
    empty_snapshots = 0
    failures: dict[str, str] = {}
    pending_rows: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal pending_rows, rows_loaded
        if not pending_rows:
            return
        rows_loaded += upsert_many(db, StockNewsSnapshot, pending_rows)
        db.commit()
        pending_rows = []

    try:
        worker_count = max(1, min(max_workers, len(pending_codes) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_fetch_naver_item_news, code, strict=True): code
                for code in pending_codes
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    items = future.result()
                    news_items += len(items)
                    if not items:
                        empty_snapshots += 1
                    now = datetime.utcnow()
                    pending_rows.append(
                        {
                            "stock_code": code,
                            "source": "naver_finance",
                            "payload": json.dumps(items, ensure_ascii=False, default=_json_default),
                            "fetched_at": now,
                            "updated_at": now,
                        }
                    )
                except Exception as exc:
                    failures[code] = str(exc)
                    continue
                if len(pending_rows) >= batch_size:
                    flush()
        flush()
        message = (
            f"target={len(codes)} refreshed={rows_loaded} skipped={len(fresh_codes)} "
            f"items={news_items} empty={empty_snapshots} failed={len(failures)}"
        )
        finish_ingestion(db, run, "success", rows_loaded, message)
        return {
            "target": len(codes),
            "rows_loaded": rows_loaded,
            "skipped": len(fresh_codes),
            "news_items": news_items,
            "empty": empty_snapshots,
            "failed": len(failures),
            "errors": failures,
            "message": message,
        }
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded, str(exc))
        raise


def collect_stock_company_snapshots(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    limit: Optional[int] = None,
    max_workers: int = 8,
    refresh_days: int = 30,
    batch_size: int = 200,
) -> dict[str, object]:
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
    stock_by_code = {stock.code: stock for stock in stocks}
    codes = list(stock_by_code)

    cutoff = datetime.utcnow() - timedelta(days=max(0, refresh_days))
    fresh_codes = (
        set(
            db.scalars(
                select(StockCompanySnapshot.stock_code).where(
                    StockCompanySnapshot.stock_code.in_(codes),
                    StockCompanySnapshot.fetched_at >= cutoff,
                )
            )
        )
        if codes and refresh_days > 0
        else set()
    )
    pending_codes = [code for code in codes if code not in fresh_codes]
    if fresh_codes:
        existing_classifications = db.execute(
            select(
                StockCompanySnapshot.stock_code,
                StockCompanySnapshot.sector,
                StockCompanySnapshot.industry,
            ).where(StockCompanySnapshot.stock_code.in_(fresh_codes))
        ).all()
        for code, sector, industry in existing_classifications:
            stock = stock_by_code.get(code)
            if stock is None:
                continue
            if sector and not stock.sector:
                stock.sector = sector
            if industry and not stock.industry:
                stock.industry = industry
    run = start_ingestion(db, "naver_wisereport", "stock_company_snapshot")
    rows_loaded = 0
    summary_missing = 0
    failures: dict[str, str] = {}
    pending_rows: list[dict[str, object]] = []

    def flush() -> None:
        nonlocal pending_rows, rows_loaded
        if not pending_rows:
            return
        rows_loaded += upsert_many(db, StockCompanySnapshot, pending_rows)
        db.commit()
        pending_rows = []

    try:
        worker_count = max(1, min(max_workers, len(pending_codes) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_fetch_naver_company_snapshot, code, strict=True): code
                for code in pending_codes
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    payload = future.result()
                    if not payload.get("summary"):
                        summary_missing += 1
                    stock = stock_by_code[code]
                    if payload.get("sector"):
                        stock.sector = str(payload["sector"])
                    if payload.get("industry"):
                        stock.industry = str(payload["industry"])
                    now = datetime.utcnow()
                    pending_rows.append(
                        {
                            "stock_code": code,
                            "source": "naver_wisereport",
                            "summary": payload.get("summary"),
                            "sector": payload.get("sector"),
                            "industry": payload.get("industry"),
                            "source_url": payload.get("source_url"),
                            "fetched_at": now,
                            "updated_at": now,
                        }
                    )
                except Exception as exc:
                    failures[code] = str(exc)
                    continue
                if len(pending_rows) >= batch_size:
                    flush()
        flush()
        message = (
            f"target={len(codes)} refreshed={rows_loaded} skipped={len(fresh_codes)} "
            f"summary_missing={summary_missing} failed={len(failures)}"
        )
        finish_ingestion(db, run, "success", rows_loaded, message)
        return {
            "target": len(codes),
            "rows_loaded": rows_loaded,
            "skipped": len(fresh_codes),
            "summary_missing": summary_missing,
            "failed": len(failures),
            "errors": failures,
            "message": message,
        }
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded, str(exc))
        raise
