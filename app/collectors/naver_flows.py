from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import InvestorFlow, StockMaster
from app.repository import finish_ingestion, start_ingestion, upsert_many

NAVER_FLOW_URL = "https://finance.naver.com/item/frgn.naver"
NAVER_HEADERS = {"User-Agent": "Mozilla/5.0"}
MARKET_SET = {"KOSPI", "KOSDAQ"}


def _to_int(value: object) -> Optional[int]:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").replace("+", "").strip()
    cleaned = re.sub(r"[^0-9.-]", "", cleaned)
    if cleaned in {"", "-", ".", "-."}:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def parse_naver_investor_flow_html(code: str, html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    flow_table = next(
        (
            table
            for table in soup.select("table.type2")
            if "기관" in table.get_text(" ", strip=True) and "외국인" in table.get_text(" ", strip=True)
        ),
        None,
    )
    if not flow_table:
        return []

    rows: list[dict[str, object]] = []
    for tr in flow_table.select("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in tr.find_all("td")]
        if len(cells) < 7 or not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
            continue
        trade_date = datetime.strptime(cells[0], "%Y.%m.%d").date()
        close = _to_int(cells[1])
        if close is None:
            continue

        for investor_type, net_buy_volume in (
            ("기관합계", _to_int(cells[5])),
            ("외국인", _to_int(cells[6])),
        ):
            if net_buy_volume is None:
                continue
            rows.append(
                {
                    "code": code,
                    "trade_date": trade_date,
                    "investor_type": investor_type,
                    "buy_volume": None,
                    "sell_volume": None,
                    "net_buy_volume": net_buy_volume,
                    "buy_value": None,
                    "sell_value": None,
                    "net_buy_value": net_buy_volume * close,
                }
            )
    return rows


def _fetch_rows_for_code(code: str, pages: int = 1) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for page in range(1, pages + 1):
        response = requests.get(
            NAVER_FLOW_URL,
            params={"code": code, "page": page},
            headers=NAVER_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        response.encoding = "euc-kr"
        rows.extend(parse_naver_investor_flow_html(code, response.text))
    return rows


def _market_codes(db: Session, markets: str, limit: Optional[int]) -> list[str]:
    market_values = [market.strip().upper() for market in markets.split(",") if market.strip()]
    if not market_values:
        market_values = sorted(MARKET_SET)
    statement = (
        select(StockMaster.code)
        .where(StockMaster.is_active.is_(True))
        .where(StockMaster.market.in_(market_values))
        .order_by(StockMaster.market, StockMaster.code)
    )
    if limit:
        statement = statement.limit(limit)
    return [code for (code,) in db.execute(statement).all() if code]


def collect_naver_investor_flows(
    db: Session,
    *,
    codes: Optional[Iterable[str]] = None,
    markets: str = "KOSPI,KOSDAQ",
    pages: int = 1,
    limit: Optional[int] = None,
    max_workers: int = 8,
    batch_size: int = 500,
) -> int:
    code_list = list(dict.fromkeys(codes or _market_codes(db, markets, limit)))
    run = start_ingestion(db, "naver", "investor_flow")
    rows_loaded = 0
    pending_rows: list[dict[str, object]] = []
    errors: dict[str, str] = {}
    try:
        with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
            futures = {executor.submit(_fetch_rows_for_code, code, pages): code for code in code_list}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    pending_rows.extend(future.result())
                except Exception as exc:
                    errors[code] = str(exc)
                    continue

                if len(pending_rows) >= batch_size:
                    rows_loaded += upsert_many(db, InvestorFlow, pending_rows)
                    db.commit()
                    pending_rows = []

        if pending_rows:
            rows_loaded += upsert_many(db, InvestorFlow, pending_rows)
            db.commit()

        message = None
        if errors:
            message = f"failed_codes={len(errors)}"
        if not rows_loaded and errors:
            finish_ingestion(db, run, "failed", 0, message)
            raise RuntimeError(message or "Naver investor flow collection failed")
        finish_ingestion(db, run, "success", rows_loaded, message)
        return rows_loaded
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", rows_loaded, str(exc))
        raise
