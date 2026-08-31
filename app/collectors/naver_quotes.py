from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re
import time
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyPrice, StockMaster
from app.repository import finish_ingestion, start_ingestion, upsert_many
from app.services.stock_dashboard import _market_cap_from_korean, _to_int


NAVER_MAIN_URL = "https://finance.naver.com/item/main.naver"
NAVER_DAILY_URL = "https://finance.naver.com/item/sise_day.naver"
NAVER_KRX_CHART_URL = "https://api.stock.naver.com/chart/domestic/item/{code}"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _market_list(markets: str) -> list[str]:
    return [market.strip().upper() for market in markets.split(",") if market.strip()]


def _codes_for_markets(db: Session, markets: str, limit: Optional[int]) -> list[str]:
    market_names = _market_list(markets)
    statement = (
        select(StockMaster.code)
        .where(StockMaster.is_active.is_(True))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if market_names:
        statement = statement.where(StockMaster.market.in_(market_names))
    if limit:
        statement = statement.limit(limit)
    return [code for code in db.scalars(statement) if code]


def _get_soup(url: str, *, encoding: str, params: dict[str, object]) -> BeautifulSoup:
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=10)
            response.raise_for_status()
            response.encoding = encoding
            return BeautifulSoup(response.text, "html.parser")
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("request failed")


def _main_snapshot(code: str) -> dict[str, object]:
    soup = _get_soup(NAVER_MAIN_URL, encoding="utf-8", params={"code": code})
    snapshot: dict[str, object] = {}
    today_values = [_to_int(item.get_text(strip=True)) for item in soup.select("p.no_today .blind")]
    info_values = [_to_int(item.get_text(strip=True)) for item in soup.select("table.no_info .blind")]
    market_sum = soup.select_one("em#_market_sum")
    if today_values:
        snapshot["price"] = today_values[0]
    if len(info_values) >= 7:
        snapshot["volume"] = info_values[3]
        snapshot["trading_value"] = info_values[6] * 1_000_000 if info_values[6] is not None else None
    if market_sum:
        snapshot["market_cap"] = _market_cap_from_korean(market_sum.get_text(" ", strip=True))
    return snapshot


def _quote_row(code: str, trade_date) -> Optional[dict[str, Any]]:
    snapshot = _main_snapshot(code)
    price = snapshot.get("price")
    if price is None:
        return None
    return {
        "code": code,
        "trade_date": trade_date,
        "open": None,
        "high": None,
        "low": None,
        "close": int(price),
        "volume": snapshot.get("volume"),
        "trading_value": snapshot.get("trading_value"),
        "market_cap": snapshot.get("market_cap"),
        "listed_shares": None,
    }


def collect_naver_quotes(
    db: Session,
    yyyymmdd: str,
    markets: str = "KOSPI,KOSDAQ",
    limit: Optional[int] = None,
    max_workers: int = 8,
    batch_size: int = 200,
) -> int:
    trade_date = datetime.strptime(yyyymmdd, "%Y%m%d").date()
    codes = _codes_for_markets(db, markets, limit)
    run = start_ingestion(db, "naver_finance", f"quote:{markets}:{yyyymmdd}")
    try:
        rows: list[dict[str, Any]] = []
        total_count = 0
        failed_codes: dict[str, str] = {}
        worker_count = max(1, min(max_workers, len(codes) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(_quote_row, code, trade_date): code for code in codes}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    failed_codes[code] = str(exc)
                    continue
                if row:
                    rows.append(row)
                if len(rows) >= batch_size:
                    total_count += upsert_many(db, DailyPrice, rows)
                    db.commit()
                    rows = []

        if rows:
            total_count += upsert_many(db, DailyPrice, rows)
            db.commit()

        message = f"failed_codes={len(failed_codes)}" if failed_codes else None
        finish_ingestion(db, run, "success", total_count, message)
        return total_count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def _history_rows_for_page(code: str, page: int) -> list[dict[str, Any]]:
    soup = _get_soup(NAVER_DAILY_URL, encoding="euc-kr", params={"code": code, "page": page})
    rows: list[dict[str, Any]] = []
    for tr in soup.select("table.type2 tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all("td")]
        if len(cells) < 7 or not re.match(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
            continue
        trade_date = datetime.strptime(cells[0], "%Y.%m.%d").date()
        close = _to_int(cells[1])
        open_ = _to_int(cells[3])
        high = _to_int(cells[4])
        low = _to_int(cells[5])
        volume = _to_int(cells[6])
        rows.append(
            {
                "code": code,
                "trade_date": trade_date,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "trading_value": close * volume if close is not None and volume is not None else None,
                "market_cap": None,
                "listed_shares": None,
            }
        )
    return rows


def _krx_chart_price_row_from_payload(
    code: str,
    target_date,
    payload: object,
) -> Optional[dict[str, Any]]:
    if not isinstance(payload, dict) or payload.get("stockExchangeType") != "KRX":
        return None
    target_token = target_date.strftime("%Y%m%d")
    price_infos = payload.get("priceInfos")
    if not isinstance(price_infos, list):
        return None
    for item in reversed(price_infos):
        if not isinstance(item, dict) or str(item.get("localDate") or "") != target_token:
            continue
        try:
            open_price = int(float(item["openPrice"]))
            high = int(float(item["highPrice"]))
            low = int(float(item["lowPrice"]))
            close = int(float(item["closePrice"]))
            volume = int(float(item["accumulatedTradingVolume"]))
        except (KeyError, TypeError, ValueError):
            return None
        if (
            any(value <= 0 for value in (open_price, high, low, close))
            or high < max(open_price, close)
            or low > min(open_price, close)
            or high < low
        ):
            return None
        return {
            "code": code,
            "trade_date": target_date,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "trading_value": close * volume,
            "market_cap": None,
            "listed_shares": None,
        }
    return None


def _krx_chart_price_row(code: str, target_date) -> Optional[dict[str, Any]]:
    last_error: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = requests.get(
                NAVER_KRX_CHART_URL.format(code=code),
                params={
                    "periodType": "dayCandle",
                    "startTime": target_date.strftime("%Y%m%d"),
                    "endTime": target_date.strftime("%Y%m%d"),
                },
                headers=REQUEST_HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            return _krx_chart_price_row_from_payload(
                code,
                target_date,
                response.json(),
            )
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    return None


def collect_naver_krx_price_rows_for_codes(
    db: Session,
    codes: list[str],
    target_date,
    *,
    max_workers: int = 12,
) -> int:
    """Finalize one session from Naver's exchange-specific KRX chart feed."""

    normalized_codes = list(
        dict.fromkeys(
            normalized
            for code in codes
            if re.fullmatch(r"[0-9A-Z]{6}", normalized := str(code or "").strip().upper())
        )
    )
    if not normalized_codes:
        return 0
    run = start_ingestion(
        db,
        "naver_finance",
        f"krx_chart_finalize:codes={len(normalized_codes)}:date={target_date.isoformat()}",
    )
    try:
        rows: list[dict[str, Any]] = []
        failed_codes: dict[str, str] = {}
        worker_count = max(1, min(int(max_workers), 16, len(normalized_codes)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_krx_chart_price_row, code, target_date): code
                for code in normalized_codes
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    row = future.result()
                except Exception as exc:
                    failed_codes[code] = str(exc)
                    continue
                if row:
                    rows.append(row)
                else:
                    failed_codes[code] = "missing_target_krx_candle"
        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        message = f"failed_codes={len(failed_codes)}" if failed_codes else None
        finish_ingestion(db, run, "success", count, message)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_naver_price_history_for_code(
    db: Session,
    code: str,
    *,
    pages: int = 2,
) -> int:
    """Repair one stock's recent OHLC rows from Naver's daily-price table.

    This is intentionally separate from the universe history collector so a
    stock-detail request can repair a partial close-only row without launching
    thousands of network requests.
    """
    normalized_code = str(code or "").strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{6}", normalized_code):
        return 0

    page_count = max(1, min(int(pages), 10))
    run = start_ingestion(
        db,
        "naver_finance",
        f"daily_price_repair:{normalized_code}:pages={page_count}",
    )
    try:
        rows: list[dict[str, Any]] = []
        failed_pages: list[int] = []
        for page in range(1, page_count + 1):
            try:
                rows.extend(_history_rows_for_page(normalized_code, page))
            except Exception:
                failed_pages.append(page)

        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        message = f"failed_pages={failed_pages}" if failed_pages else None
        finish_ingestion(db, run, "success", count, message)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_naver_price_history_for_codes(
    db: Session,
    codes: list[str],
    *,
    pages: int = 3,
    max_workers: int = 12,
) -> int:
    """Repair recent OHLC candles for an explicit stock universe in parallel."""
    normalized_codes = list(
        dict.fromkeys(
            normalized
            for code in codes
            if re.fullmatch(r"[0-9A-Z]{6}", normalized := str(code or "").strip().upper())
        )
    )
    if not normalized_codes:
        return 0

    page_count = max(1, min(int(pages), 10))
    worker_count = max(1, min(int(max_workers), 16, len(normalized_codes) * page_count))
    run = start_ingestion(
        db,
        "naver_finance",
        f"daily_price_repair_batch:codes={len(normalized_codes)}:pages={page_count}",
    )
    try:
        rows: list[dict[str, Any]] = []
        failed_jobs: list[tuple[str, int]] = []
        jobs = [
            (code, page)
            for code in normalized_codes
            for page in range(1, page_count + 1)
        ]
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_history_rows_for_page, code, page): (code, page)
                for code, page in jobs
            }
            for future in as_completed(futures):
                code, page = futures[future]
                try:
                    rows.extend(future.result())
                except Exception:
                    failed_jobs.append((code, page))

        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        message = f"failed_jobs={len(failed_jobs)}" if failed_jobs else None
        finish_ingestion(db, run, "success", count, message)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_naver_price_history(
    db: Session,
    markets: str = "KOSPI,KOSDAQ",
    pages: int = 10,
    limit: Optional[int] = None,
    max_workers: int = 8,
) -> int:
    codes = _codes_for_markets(db, markets, limit)
    run = start_ingestion(db, "naver_finance", f"daily_price_history:{markets}:pages={pages}")
    try:
        rows: list[dict[str, Any]] = []
        total_count = 0
        failed_jobs: list[tuple[str, int, str]] = []
        jobs = [(code, page) for code in codes for page in range(1, pages + 1)]
        worker_count = max(1, min(max_workers, len(jobs) or 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(_history_rows_for_page, code, page): (code, page) for code, page in jobs}
            for future in as_completed(futures):
                code, page = futures[future]
                try:
                    rows.extend(future.result())
                except Exception as exc:
                    failed_jobs.append((code, page, str(exc)))
                    continue
                if len(rows) >= 2000:
                    total_count += upsert_many(db, DailyPrice, rows)
                    db.commit()
                    rows = []

        if rows:
            total_count += upsert_many(db, DailyPrice, rows)
            db.commit()

        message = f"failed_jobs={len(failed_jobs)}" if failed_jobs else None
        finish_ingestion(db, run, "success", total_count, message)
        return total_count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise
