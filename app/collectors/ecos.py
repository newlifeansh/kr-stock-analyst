from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MacroObservation
from app.repository import finish_ingestion, start_ingestion, upsert_many


def _value(raw: Optional[str]) -> Optional[Decimal]:
    if raw in (None, "", "-"):
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def collect_ecos_series(
    db: Session,
    series_code: str,
    cycle: str,
    start_period: str,
    end_period: str,
    item_code: str = "?",
) -> int:
    settings = get_settings()
    if not settings.ecos_api_key:
        raise RuntimeError("ECOS_API_KEY is missing in .env")

    run = start_ingestion(db, "ecos", f"{series_code}:{item_code}:{cycle}")
    try:
        url = (
            "https://ecos.bok.or.kr/api/StatisticSearch/"
            f"{settings.ecos_api_key}/json/kr/1/10000/"
            f"{series_code}/{cycle}/{start_period}/{end_period}/{item_code}"
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("StatisticSearch", {})
        rows_payload = data.get("row", [])
        rows: list[dict[str, Any]] = [
            {
                "source": "ecos",
                "series_code": series_code,
                "item_code": item.get("ITEM_CODE1") or item_code,
                "period": item.get("TIME"),
                "value": _value(item.get("DATA_VALUE")),
                "unit": item.get("UNIT_NAME"),
                "name": item.get("ITEM_NAME1") or item.get("STAT_NAME"),
            }
            for item in rows_payload
            if item.get("TIME")
        ]
        count = upsert_many(db, MacroObservation, rows)
        db.commit()
        finish_ingestion(db, run, "success", count)
        return count
    except Exception as exc:
        db.rollback()
        finish_ingestion(db, run, "failed", 0, str(exc))
        raise
