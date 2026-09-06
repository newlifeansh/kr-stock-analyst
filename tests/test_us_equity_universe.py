from __future__ import annotations

import importlib.util
import json
import zipfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from app.services import us_market

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_PATH = ROOT / "app" / "services" / "us_equity_universe.json"
SYNC_SCRIPT_PATH = ROOT / "scripts" / "sync_us_equity_universe.py"
SYNC_SCRIPT_SPEC = importlib.util.spec_from_file_location("sync_us_equity_universe", SYNC_SCRIPT_PATH)
assert SYNC_SCRIPT_SPEC and SYNC_SCRIPT_SPEC.loader
SYNC_SCRIPT = importlib.util.module_from_spec(SYNC_SCRIPT_SPEC)
SYNC_SCRIPT_SPEC.loader.exec_module(SYNC_SCRIPT)
parse_nasdaq_100 = SYNC_SCRIPT.parse_nasdaq_100
parse_spy_holdings = SYNC_SCRIPT.parse_spy_holdings


def _spy_fixture() -> bytes:
    shared = [
        "Holdings:",
        "As of 03-Sep-2026",
        "Name",
        "Ticker",
        "Identifier",
        "SEDOL",
        "Weight",
        "Sector",
        "Shares Held",
        "Local Currency",
        "BERKSHIRE HATHAWAY INC-CL B",
        "BRK.B",
        "084670702",
        "USD",
        "Cash Collateral USD",
        "USD",
    ]
    shared_xml = "".join(f"<si><t>{value}</t></si>" for value in shared)
    sheet_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
      <row r="3"><c r="A3" t="s"><v>0</v></c><c r="B3" t="s"><v>1</v></c></row>
      <row r="5"><c r="A5" t="s"><v>2</v></c><c r="B5" t="s"><v>3</v></c></row>
      <row r="6"><c r="A6" t="s"><v>10</v></c><c r="B6" t="s"><v>11</v></c><c r="C6" t="s"><v>12</v></c><c r="H6" t="s"><v>13</v></c></row>
      <row r="7"><c r="A7" t="s"><v>14</v></c><c r="B7" t="s"><v>15</v></c><c r="H7" t="s"><v>13</v></c></row>
    </sheetData></worksheet>"""
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
            "<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">"
            f"{shared_xml}</sst>",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def test_checked_in_universe_contains_complete_current_index_memberships() -> None:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    items = payload["items"]
    by_code = {item["code"]: item for item in items}

    assert payload["counts"] == {
        "nasdaq_100": 102,
        "sp500": 503,
        "overlap": 87,
        "union": 518,
    }
    assert len(items) == len(by_code) == 518
    assert by_code["NVDA"]["markets"] == ["NASDAQ", "SP500"]
    assert by_code["RKLB"]["markets"] == ["NASDAQ"]
    assert by_code["BRK.B"]["markets"] == ["SP500"]
    assert len(us_market.NASDAQ_UNIVERSE) == 102
    assert len(us_market.SP500_UNIVERSE) == 503
    assert len(us_market.US_EQUITY_UNIVERSE) == 518


def test_market_filters_include_overlap_without_duplicating_union() -> None:
    nasdaq_codes = {str(item["code"]) for item in us_market._us_universe_for_market("NASDAQ")}
    sp500_codes = {str(item["code"]) for item in us_market._us_universe_for_market("SP500")}
    all_codes = [str(item["code"]) for item in us_market._us_universe_for_market("ALL")]

    assert "NVDA" in nasdaq_codes & sp500_codes
    assert "RKLB" in nasdaq_codes - sp500_codes
    assert "BRK.B" in sp500_codes - nasdaq_codes
    assert len(all_codes) == len(set(all_codes)) == 518


def test_new_full_universe_members_are_searchable_and_resolvable(monkeypatch) -> None:
    monkeypatch.setattr(us_market, "_search_yahoo", lambda *args, **kwargs: {"quotes": []})

    rocket_lab = us_market.search_us_stocks("Rocket Lab", limit=5)
    vivmark = us_market.resolve_us_stock("VMRK")

    assert rocket_lab[0]["code"] == "RKLB"
    assert rocket_lab[0]["markets"] == ["NASDAQ"]
    assert vivmark["code"] == "VMRK"
    assert vivmark["markets"] == ["SP500"]


def test_nasdaq_parser_keeps_all_security_rows_and_as_of_date() -> None:
    payload = {
        "data": {
            "date": "Sep 3, 2026",
            "data": {
                "rows": [
                    {"symbol": "GOOG", "companyName": "Alphabet Class C"},
                    {"symbol": "GOOGL", "companyName": "Alphabet Class A"},
                ]
            },
        }
    }

    as_of, rows = parse_nasdaq_100(payload)

    assert as_of == "2026-09-03"
    assert [row["code"] for row in rows] == ["GOOG", "GOOGL"]


def test_spy_workbook_parser_keeps_dotted_equity_and_excludes_cash_row() -> None:
    as_of, rows = parse_spy_holdings(_spy_fixture())

    assert as_of == "2026-09-03"
    assert rows == [
        {
            "code": "BRK.B",
            "name": "BERKSHIRE HATHAWAY INC-CL B",
            "identifier": "084670702",
        }
    ]


def test_quote_batch_maps_yahoo_dashed_symbols_back_to_index_tickers(monkeypatch) -> None:
    monkeypatch.setattr(
        us_market,
        "_fetch_yahoo_quote_batch_once",
        lambda symbols: [
            {"symbol": "BRK-B", "regularMarketPrice": 500},
            {"symbol": "AAPL", "regularMarketPrice": 300},
        ],
    )

    rows = us_market.fetch_us_quote_batch(["BRK.B", "AAPL"], refresh=True)

    assert set(rows) == {"BRK.B", "AAPL"}
    assert rows["BRK.B"]["regularMarketPrice"] == 500


def test_industry_valuation_uses_one_bulk_quote_snapshot(monkeypatch) -> None:
    universe = [
        {"code": "AAA", "name": "Alpha", "sector": "기술", "market": "NASDAQ"},
        {"code": "BBB", "name": "Beta", "sector": "기술", "market": "NASDAQ"},
    ]
    calls: list[list[str]] = []

    def fake_quote_batch(symbols: list[str]) -> dict[str, dict[str, object]]:
        calls.append(symbols)
        return {
            "AAA": {"trailingPE": 10, "priceToBook": 2},
            "BBB": {"trailingPE": 30, "priceToBook": 4},
        }

    us_market.US_CACHE.clear()
    monkeypatch.setattr(us_market, "US_EQUITY_UNIVERSE", universe)
    monkeypatch.setattr(us_market, "fetch_us_quote_batch", fake_quote_batch)

    result = us_market._industry_valuation_stats("technology")

    assert calls == [["AAA", "BBB"]]
    assert result["industry_per"] == Decimal("20.00")
    assert result["industry_pbr"] == Decimal("3.00")
