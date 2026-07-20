from __future__ import annotations

import os
import re
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Optional

import certifi
import pandas as pd
from sqlalchemy.orm import Session

from app.models import DailyPrice, InvestorFlow, StockMaster
from app.repository import finish_ingestion, start_ingestion, upsert_many

PRICE_CODE_PATTERN = re.compile(r"^\d{6}$")


def _stock_module():
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="pkg_resources is deprecated.*")
            from pykrx import stock
    except ImportError as exc:
        raise RuntimeError(
            "pykrx import failed. Run `pip install -e .`; pykrx also requires setuptools<81."
        ) from exc
    return stock


def parse_yyyymmdd(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()


def _clean_int(value: Any) -> Optional[int]:
    if pd.isna(value):
        return None
    return int(value)


def _market_list(markets: str) -> list[str]:
    return [item.strip().upper() for item in markets.split(",") if item.strip()]


def is_supported_price_code(code: Optional[str]) -> bool:
    return bool(code and PRICE_CODE_PATTERN.fullmatch(code.strip()))


def _stock_rows_from_pykrx(yyyymmdd: str, markets: list[str], seen_date: date) -> list[dict[str, Any]]:
    stock = _stock_module()
    rows: list[dict[str, Any]] = []
    for market in markets:
        for code in stock.get_market_ticker_list(yyyymmdd, market=market):
            rows.append(
                {
                    "code": code,
                    "name": stock.get_market_ticker_name(code),
                    "market": market,
                    "last_seen_date": seen_date,
                }
            )
    return rows


def _stock_rows_from_fdr(markets: list[str], seen_date: date) -> list[dict[str, Any]]:
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    try:
        import FinanceDataReader as fdr
    except ImportError as exc:
        raise RuntimeError("FinanceDataReader is required. Run `pip install -e .`.") from exc

    frame = fdr.StockListing("KRX")
    if markets:
        frame = frame[frame["Market"].isin(markets)]
    return [
        {
            "code": row["Code"],
            "name": row["Name"],
            "market": row["Market"],
            "isin": row.get("ISU_CD"),
            "last_seen_date": seen_date,
        }
        for _, row in frame.iterrows()
    ]


def _price_rows_from_frame(code: str, frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return rows

    for idx, row in frame.iterrows():
        trade_date = idx.date() if hasattr(idx, "date") else idx
        rows.append(
            {
                "code": code,
                "trade_date": trade_date,
                "open": _clean_int(row.get("시가", row.get("Open"))),
                "high": _clean_int(row.get("고가", row.get("High"))),
                "low": _clean_int(row.get("저가", row.get("Low"))),
                "close": _clean_int(row.get("종가", row.get("Close"))),
                "volume": _clean_int(row.get("거래량", row.get("Volume"))),
                "trading_value": _clean_int(row.get("거래대금", row.get("Amount"))),
                "market_cap": _clean_int(row.get("시가총액", row.get("Marcap"))),
                "listed_shares": _clean_int(row.get("상장주식수", row.get("Stocks"))),
            }
        )
    return rows


def _price_rows_from_fdr(code: str, from_yyyymmdd: str, to_yyyymmdd: str) -> list[dict[str, Any]]:
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    try:
        import FinanceDataReader as fdr
    except ImportError as exc:
        raise RuntimeError("FinanceDataReader is required. Run `pip install -e .`.") from exc

    frame = fdr.DataReader(
        code,
        f"{from_yyyymmdd[:4]}-{from_yyyymmdd[4:6]}-{from_yyyymmdd[6:8]}",
        f"{to_yyyymmdd[:4]}-{to_yyyymmdd[4:6]}-{to_yyyymmdd[6:8]}",
    )
    return _price_rows_from_frame(code, frame)


def _price_rows_from_pykrx(code: str, from_yyyymmdd: str, to_yyyymmdd: str) -> list[dict[str, Any]]:
    stock = _stock_module()
    frame = stock.get_market_ohlcv_by_date(from_yyyymmdd, to_yyyymmdd, code)
    return _price_rows_from_frame(code, frame)


def _price_rows_for_code(code: str, from_yyyymmdd: str, to_yyyymmdd: str) -> list[dict[str, Any]]:
    try:
        return _price_rows_from_pykrx(code, from_yyyymmdd, to_yyyymmdd)
    except Exception:
        return _price_rows_from_fdr(code, from_yyyymmdd, to_yyyymmdd)


def collect_stocks(db: Session, yyyymmdd: str, markets: str) -> int:
    seen_date = parse_yyyymmdd(yyyymmdd)
    market_names = _market_list(markets)
    run = start_ingestion(db, "market_data", "stock_master")
    try:
        try:
            rows = _stock_rows_from_pykrx(yyyymmdd, market_names, seen_date)
        except Exception:
            rows = []
        if not rows:
            rows = _stock_rows_from_fdr(market_names, seen_date)
        count = upsert_many(db, StockMaster, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_market_prices(db: Session, yyyymmdd: str, market: str) -> int:
    stock = _stock_module()
    trade_date = parse_yyyymmdd(yyyymmdd)
    market = market.upper()
    run = start_ingestion(db, "krx", f"daily_price:{market}")
    try:
        ohlcv = stock.get_market_ohlcv_by_ticker(yyyymmdd, market=market)
        cap = stock.get_market_cap_by_ticker(yyyymmdd, market=market)
        frame = ohlcv.join(cap[["시가총액", "상장주식수"]], how="left")

        rows = [
            {
                "code": code,
                "trade_date": trade_date,
                "open": _clean_int(row.get("시가")),
                "high": _clean_int(row.get("고가")),
                "low": _clean_int(row.get("저가")),
                "close": _clean_int(row.get("종가")),
                "volume": _clean_int(row.get("거래량")),
                "trading_value": _clean_int(row.get("거래대금")),
                "market_cap": _clean_int(row.get("시가총액")),
                "listed_shares": _clean_int(row.get("상장주식수")),
            }
            for code, row in frame.iterrows()
        ]
        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_stock_prices(db: Session, code: str, from_yyyymmdd: str, to_yyyymmdd: str) -> int:
    if not is_supported_price_code(code):
        return 0

    run = start_ingestion(db, "krx", f"daily_price:{code}")
    try:
        rows = _price_rows_for_code(code, from_yyyymmdd, to_yyyymmdd)
        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_prices_for_codes(
    db: Session,
    codes: list[str],
    from_yyyymmdd: str,
    to_yyyymmdd: str,
    max_workers: int = 8,
) -> int:
    unique_codes: list[str] = []
    seen: set[str] = set()
    for raw_code in codes:
        code = (raw_code or "").strip()
        if not is_supported_price_code(code) or code in seen:
            continue
        unique_codes.append(code)
        seen.add(code)

    if not unique_codes:
        return 0

    run = start_ingestion(db, "market_data", f"daily_price_batch:{to_yyyymmdd}")
    try:
        rows: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        worker_count = max(1, min(max_workers, len(unique_codes)))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(_price_rows_for_code, code, from_yyyymmdd, to_yyyymmdd): code for code in unique_codes
            }
            for future in as_completed(futures):
                code = futures[future]
                try:
                    rows.extend(future.result())
                except Exception as exc:
                    errors[code] = str(exc)

        if not rows and errors:
            message = "; ".join(f"{code}: {error}" for code, error in list(errors.items())[:5])
            db.rollback()
            finish_ingestion(db, run, "failed", 0, message)
            raise RuntimeError(message)

        count = upsert_many(db, DailyPrice, rows)
        db.commit()
        message = None
        if errors:
            message = f"failed_codes={len(errors)}"
        finish_ingestion(db, run, "success", count, message)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise


def collect_investor_flows(db: Session, yyyymmdd: str, market: str) -> int:
    stock = _stock_module()
    trade_date = parse_yyyymmdd(yyyymmdd)
    market = market.upper()
    investors = ["개인", "외국인", "기관합계", "금융투자", "보험", "투신", "사모", "은행", "연기금"]
    run = start_ingestion(db, "krx", f"investor_flow:{market}")
    try:
        rows: list[dict[str, Any]] = []
        for investor in investors:
            if hasattr(stock, "get_market_net_purchases_of_equities_by_ticker"):
                frame = stock.get_market_net_purchases_of_equities_by_ticker(yyyymmdd, yyyymmdd, market, investor)
                column_map = {
                    "매수거래량": "volume_매수",
                    "매도거래량": "volume_매도",
                    "순매수거래량": "volume_순매수",
                    "매수거래대금": "value_매수",
                    "매도거래대금": "value_매도",
                    "순매수거래대금": "value_순매수",
                }
                frame = frame.rename(columns=column_map)
            elif hasattr(stock, "get_market_trading_value_and_volume_by_ticker"):
                frame = stock.get_market_trading_value_and_volume_by_ticker(yyyymmdd, yyyymmdd, market, investor)
                column_map = {
                    "매수거래량": "volume_매수",
                    "매도거래량": "volume_매도",
                    "순매수거래량": "volume_순매수",
                    "매수거래대금": "value_매수",
                    "매도거래대금": "value_매도",
                    "순매수거래대금": "value_순매수",
                }
                frame = frame.rename(columns=column_map)
            else:
                value_frame = stock.get_market_trading_value_by_ticker(yyyymmdd, market, investor)
                volume_frame = stock.get_market_trading_volume_by_ticker(yyyymmdd, market, investor)
                frame = value_frame.add_prefix("value_").join(volume_frame.add_prefix("volume_"), how="outer")
            for code, row in frame.iterrows():
                rows.append(
                    {
                        "code": code,
                        "trade_date": trade_date,
                        "investor_type": investor,
                        "buy_volume": _clean_int(row.get("volume_매수")),
                        "sell_volume": _clean_int(row.get("volume_매도")),
                        "net_buy_volume": _clean_int(row.get("volume_순매수")),
                        "buy_value": _clean_int(row.get("value_매수")),
                        "sell_value": _clean_int(row.get("value_매도")),
                        "net_buy_value": _clean_int(row.get("value_순매수")),
                    }
                )
        count = upsert_many(db, InvestorFlow, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise
