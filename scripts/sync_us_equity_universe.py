from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO
from pathlib import Path
from time import strptime
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "app" / "services" / "us_equity_universe.json"
NASDAQ_100_URL = "https://api.nasdaq.com/api/quote/list-type/nasdaq100"
NASDAQ_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableonly=true&limit=5000&offset=0&download=true"
)
SPY_HOLDINGS_URL = (
    "https://www.ssga.com/library-content/products/fund-data/etfs/us/"
    "holdings-daily-us-en-spy.xlsx"
)
HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "SecretNoteUSUniverseSync/1.0",
}
TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z])?$")
XML_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SECTOR_LABELS = {
    "Basic Materials": "소재",
    "Consumer Discretionary": "경기소비재",
    "Consumer Staples": "필수소비재",
    "Energy": "에너지",
    "Finance": "금융",
    "Health Care": "헬스케어",
    "Industrials": "산업재",
    "Miscellaneous": "기타",
    "Real Estate": "부동산",
    "Technology": "기술",
    "Telecommunications": "통신",
    "Utilities": "유틸리티",
}
SPECIAL_COMPANY_METADATA = {
    "BF.B": {"sector": "Consumer Staples", "industry": "Beverages"},
    "BRK.B": {"sector": "Finance", "industry": "Diversified Financial Services"},
    "FERG": {"sector": "Industrials", "industry": "Industrial Distribution"},
}


def normalize_ticker(value: object) -> str:
    return str(value or "").strip().upper().replace("/", ".")


def storage_code(symbol: str) -> str:
    return re.sub(r"[^0-9A-Z]", "", normalize_ticker(symbol))


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    if cell.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//m:t", XML_NS))
    value = cell.find("m:v", XML_NS)
    if value is None or value.text is None:
        return ""
    if cell.get("t") == "s":
        return shared_strings[int(value.text)]
    return value.text


def parse_spy_holdings(workbook: bytes) -> tuple[str, list[dict[str, str]]]:
    with zipfile.ZipFile(BytesIO(workbook)) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        shared_strings = [
            "".join(node.text or "" for node in item.findall(".//m:t", XML_NS))
            for item in shared_root.findall("m:si", XML_NS)
        ]
        sheet_root = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[dict[str, str]] = []
    as_of = ""
    for row in sheet_root.findall(".//m:sheetData/m:row", XML_NS):
        values = {
            re.sub(r"\d+", "", cell.get("r") or ""): _cell_text(cell, shared_strings)
            for cell in row.findall("m:c", XML_NS)
        }
        if values.get("A") == "Holdings:":
            match = re.search(r"As of\s+(.+)", values.get("B", ""), flags=re.IGNORECASE)
            if match:
                parsed = strptime(match.group(1), "%d-%b-%Y")
                as_of = date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
        ticker = normalize_ticker(values.get("B"))
        if (
            values.get("H") == "USD"
            and TICKER_PATTERN.fullmatch(ticker)
            and values.get("A")
            and values.get("C")
        ):
            rows.append(
                {
                    "code": ticker,
                    "name": values["A"].strip(),
                    "identifier": values["C"].strip(),
                }
            )
    if not as_of:
        raise ValueError("SPY holdings as-of date was not found")
    return as_of, rows


def parse_nasdaq_100(payload: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    data = payload.get("data") or {}
    rows = ((data.get("data") or {}).get("rows") or [])
    parsed_date = strptime(str(data.get("date")), "%b %d, %Y")
    as_of = date(parsed_date.tm_year, parsed_date.tm_mon, parsed_date.tm_mday).isoformat()
    parsed = []
    for row in rows:
        ticker = normalize_ticker(row.get("symbol"))
        if TICKER_PATTERN.fullmatch(ticker):
            parsed.append(
                {
                    "code": ticker,
                    "name": str(row.get("companyName") or ticker).strip(),
                }
            )
    return as_of, parsed


def _clean_company_name(value: str) -> str:
    name = re.sub(r"\s+", " ", value).strip()
    name = re.sub(r"\s+Common Stock$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s+Ordinary Shares$", "", name, flags=re.IGNORECASE)
    return name or value


def build_universe(
    nasdaq_payload: dict[str, Any],
    screener_payload: dict[str, Any],
    spy_workbook: bytes,
) -> dict[str, Any]:
    nasdaq_as_of, nasdaq_rows = parse_nasdaq_100(nasdaq_payload)
    spy_as_of, sp500_rows = parse_spy_holdings(spy_workbook)
    screener_rows = ((screener_payload.get("data") or {}).get("rows") or [])
    metadata = {
        normalize_ticker(row.get("symbol")): row
        for row in screener_rows
        if TICKER_PATTERN.fullmatch(normalize_ticker(row.get("symbol")))
    }
    nasdaq_by_code = {row["code"]: row for row in nasdaq_rows}
    sp500_by_code = {row["code"]: row for row in sp500_rows}
    all_codes = sorted(set(nasdaq_by_code) | set(sp500_by_code))
    items: list[dict[str, Any]] = []
    storage_codes: set[str] = set()
    for code in all_codes:
        memberships = [
            market
            for market, members in (("NASDAQ", nasdaq_by_code), ("SP500", sp500_by_code))
            if code in members
        ]
        meta = metadata.get(code) or {}
        base = nasdaq_by_code.get(code) or sp500_by_code[code]
        storage = storage_code(code)
        if storage in storage_codes:
            raise ValueError(f"duplicate logo storage code: {code} -> {storage}")
        storage_codes.add(storage)
        special = SPECIAL_COMPANY_METADATA.get(code) or {}
        raw_sector = str(special.get("sector") or meta.get("sector") or "").strip()
        items.append(
            {
                "code": code,
                "name": _clean_company_name(str(meta.get("name") or base["name"])),
                "sector": SECTOR_LABELS.get(raw_sector, "기타"),
                "industry": str(special.get("industry") or meta.get("industry") or "").strip()
                or None,
                "market": memberships[0],
                "markets": memberships,
            }
        )

    nasdaq_count = len(nasdaq_by_code)
    sp500_count = len(sp500_by_code)
    overlap_count = len(set(nasdaq_by_code) & set(sp500_by_code))
    if not 95 <= nasdaq_count <= 110:
        raise ValueError(f"unexpected Nasdaq-100 security count: {nasdaq_count}")
    if not 495 <= sp500_count <= 510:
        raise ValueError(f"unexpected S&P 500 security count: {sp500_count}")
    if len(items) != nasdaq_count + sp500_count - overlap_count:
        raise ValueError("union count does not match membership counts")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),  # noqa: UP017
        "sources": {
            "nasdaq_100": {"url": NASDAQ_100_URL, "as_of": nasdaq_as_of},
            "nasdaq_screener": {
                "url": NASDAQ_SCREENER_URL,
                "as_of": str((screener_payload.get("data") or {}).get("asOf") or ""),
            },
            "sp500": {"url": SPY_HOLDINGS_URL, "as_of": spy_as_of},
        },
        "counts": {
            "nasdaq_100": nasdaq_count,
            "sp500": sp500_count,
            "overlap": overlap_count,
            "union": len(items),
        },
        "items": items,
    }


def _get(url: str, timeout_seconds: int) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=max(5, timeout_seconds))
    response.raise_for_status()
    return response


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync the complete Nasdaq-100 and S&P 500 constituent universe."
    )
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    nasdaq_payload = _get(NASDAQ_100_URL, args.timeout_seconds).json()
    screener_payload = _get(NASDAQ_SCREENER_URL, args.timeout_seconds).json()
    spy_workbook = _get(SPY_HOLDINGS_URL, args.timeout_seconds).content
    universe = build_universe(nasdaq_payload, screener_payload, spy_workbook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(universe, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(universe["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
