from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path
import re
from typing import Callable, Optional

import requests
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import StockLogo, StockMaster


ALPHASQUARE_KR_LOGO_BASE_URL = "https://file.alphasquare.co.kr/media/images/stock_logo/kr"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_LOGO_BYTES = 2 * 1024 * 1024
STOCK_CODE_PATTERN = re.compile(r"^[0-9A-Z]{6}$")
FALLBACK_STOCK_LOGO_PATH = Path(__file__).resolve().parents[1] / "static" / "stock-logo-fallback.png"
MANUAL_STOCK_LOGO_DIR = Path(__file__).resolve().parents[1] / "static" / "stock-logos"


@dataclass(frozen=True)
class StockLogoFetchResult:
    code: str
    source_url: str
    status: str
    content_type: Optional[str] = None
    image_data: Optional[bytes] = None


@lru_cache(maxsize=1)
def fallback_stock_logo_bytes() -> bytes:
    image_data = FALLBACK_STOCK_LOGO_PATH.read_bytes()
    if not image_data.startswith(PNG_SIGNATURE):
        raise RuntimeError("Fallback stock logo must be a PNG image")
    return image_data


def normalize_stock_logo_code(code: str) -> str:
    cleaned = re.sub(r"[^0-9A-Z]", "", str(code or "").upper())
    if len(cleaned) == 7 and cleaned.startswith("A") and cleaned[1:].isdigit():
        cleaned = cleaned[1:]
    if not STOCK_CODE_PATTERN.fullmatch(cleaned):
        raise ValueError("Korean stock logo code must be six letters or digits")
    return cleaned


def alphasquare_stock_logo_url(code: str) -> str:
    return f"{ALPHASQUARE_KR_LOGO_BASE_URL}/{normalize_stock_logo_code(code)}.png"


def fetch_stock_logo(
    code: str,
    *,
    timeout_seconds: int = 8,
    fetcher: Callable[..., requests.Response] = requests.get,
) -> StockLogoFetchResult:
    normalized = normalize_stock_logo_code(code)
    source_url = alphasquare_stock_logo_url(normalized)
    try:
        response = fetcher(
            source_url,
            headers={
                "Accept": "image/png,image/*;q=0.8",
                "User-Agent": "SecretNoteStockLogoCache/1.0",
            },
            timeout=max(1, timeout_seconds),
        )
    except requests.RequestException:
        return StockLogoFetchResult(normalized, source_url, "failed")
    except Exception:
        return StockLogoFetchResult(normalized, source_url, "failed")

    if response.status_code in {403, 404}:
        return StockLogoFetchResult(normalized, source_url, "missing")
    if response.status_code != 200:
        return StockLogoFetchResult(normalized, source_url, "failed")

    image_data = bytes(response.content or b"")
    content_type = str(response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    if (
        not image_data.startswith(PNG_SIGNATURE)
        or len(image_data) > MAX_LOGO_BYTES
        or (content_type and not content_type.startswith("image/"))
    ):
        return StockLogoFetchResult(normalized, source_url, "failed")
    return StockLogoFetchResult(
        normalized,
        source_url,
        "ready",
        content_type=content_type or "image/png",
        image_data=image_data,
    )


def store_stock_logo_result(db: Session, result: StockLogoFetchResult) -> StockLogo:
    now = datetime.utcnow()
    item = db.get(StockLogo, result.code)
    if item is None:
        item = StockLogo(stock_code=result.code, source_url=result.source_url)
    item.source_url = result.source_url
    item.status = result.status
    item.content_type = result.content_type
    item.image_data = result.image_data
    item.checked_at = now
    item.updated_at = now
    db.add(item)
    return item


def ensure_stock_logo(
    db: Session,
    code: str,
    *,
    timeout_seconds: int = 8,
    missing_retry_days: int = 7,
    fetcher: Callable[..., requests.Response] = requests.get,
) -> Optional[StockLogo]:
    normalized = normalize_stock_logo_code(code)
    item = db.get(StockLogo, normalized)
    if item and item.status == "ready" and item.image_data:
        return item
    retry_before = datetime.utcnow() - timedelta(days=max(1, missing_retry_days))
    if item and item.checked_at > retry_before:
        return None

    result = fetch_stock_logo(normalized, timeout_seconds=timeout_seconds, fetcher=fetcher)
    item = store_stock_logo_result(db, result)
    db.commit()
    if item.status == "ready" and item.image_data:
        return item
    return None


def sync_stock_logos(
    db: Session,
    *,
    markets: str = "KOSPI,KOSDAQ",
    timeout_seconds: int = 8,
    max_workers: int = 4,
    missing_retry_days: int = 7,
    limit: Optional[int] = None,
    fetcher: Callable[..., requests.Response] = requests.get,
) -> dict[str, int]:
    market_names = [item.strip().upper() for item in markets.split(",") if item.strip()]
    manual_codes = {
        path.stem.upper()
        for path in MANUAL_STOCK_LOGO_DIR.glob("*.png")
        if STOCK_CODE_PATTERN.fullmatch(path.stem.upper())
    }
    retry_before = datetime.utcnow() - timedelta(days=max(1, missing_retry_days))
    statement = (
        select(StockMaster.code)
        .outerjoin(StockLogo, StockLogo.stock_code == StockMaster.code)
        .where(
            StockMaster.is_active.is_(True),
            StockMaster.market.in_(market_names),
            or_(
                StockLogo.stock_code.is_(None),
                StockLogo.status != "ready",
                StockLogo.image_data.is_(None),
            ),
            or_(StockLogo.checked_at.is_(None), StockLogo.checked_at <= retry_before),
        )
        .order_by(StockMaster.listed_date.desc(), StockMaster.code)
    )
    if limit is not None:
        statement = statement.limit(max(0, limit))
    if manual_codes:
        statement = statement.where(StockMaster.code.not_in(manual_codes))
    codes = list(db.scalars(statement))
    summary = {"candidates": len(codes), "ready": 0, "missing": 0, "failed": 0}
    if not codes:
        return summary

    workers = min(max(1, max_workers), len(codes))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                fetch_stock_logo,
                code,
                timeout_seconds=timeout_seconds,
                fetcher=fetcher,
            ): code
            for code in codes
        }
        pending = 0
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception:
                code = futures[future]
                result = StockLogoFetchResult(code, alphasquare_stock_logo_url(code), "failed")
            store_stock_logo_result(db, result)
            summary[result.status] += 1
            pending += 1
            if pending >= 100:
                db.commit()
                pending = 0
    db.commit()
    return summary
