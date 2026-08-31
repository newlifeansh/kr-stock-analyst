from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

LOGIC_PATH = Path("app/static/staging/stock-change-copy-logic.js").resolve()


def _resolve(payload: dict[str, object]) -> dict[str, object]:
    script = f"""
const fs = require("fs");
const logic = require({json.dumps(str(LOGIC_PATH))});
const payload = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(logic.resolveChangeContext(payload)));
"""
    completed = subprocess.run(
        ["node", "-e", script],
        input=json.dumps(payload, ensure_ascii=False),
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    ("payload", "expected_label", "expected_mode", "expected_quote", "expected_reference"),
    [
        (
            {
                "currentDate": "2026-08-25",
                "quoteTradeDate": "2026-08-25",
                "tradeDates": ["2026-08-24", "2026-08-21"],
                "sessionStarted": True,
            },
            "어제보다",
            "current-session",
            "2026-08-25",
            "2026-08-24",
        ),
        (
            {
                "currentDate": "2026-08-31",
                "quoteTradeDate": "2026-08-31",
                "tradeDates": ["2026-08-28", "2026-08-27"],
                "sessionStarted": True,
            },
            "금요일보다",
            "current-session",
            "2026-08-31",
            "2026-08-28",
        ),
        (
            {
                "currentDate": "2026-08-30",
                "quoteTradeDate": "2026-08-28",
                "tradeDates": ["2026-08-28", "2026-08-27"],
                "sessionStarted": False,
            },
            "금요일 장에서",
            "completed-session",
            "2026-08-28",
            "",
        ),
        (
            {
                "currentDate": "2026-08-31",
                "quoteTradeDate": "2026-08-28",
                "tradeDates": ["2026-08-28", "2026-08-27"],
                "sessionStarted": False,
            },
            "금요일 장에서",
            "completed-session",
            "2026-08-28",
            "",
        ),
        (
            {
                "currentDate": "2026-09-01",
                "quoteTradeDate": "2026-08-31",
                "tradeDates": ["2026-08-31", "2026-08-28"],
                "sessionStarted": False,
            },
            "어제 장에서",
            "completed-session",
            "2026-08-31",
            "",
        ),
        (
            {
                "currentDate": "2026-08-18",
                "quoteTradeDate": "2026-08-18",
                "tradeDates": ["2026-08-14", "2026-08-13"],
                "sessionStarted": True,
            },
            "금요일보다",
            "current-session",
            "2026-08-18",
            "2026-08-14",
        ),
        (
            {
                "currentDate": "2026-08-31",
                "quoteTradeDate": "2026-08-31",
                "tradeDates": ["2026-08-28", "2026-08-27"],
                "sessionStarted": False,
            },
            "금요일 장에서",
            "completed-session",
            "2026-08-28",
            "",
        ),
    ],
)
def test_stock_change_copy_follows_real_session_dates(
    payload: dict[str, object],
    expected_label: str,
    expected_mode: str,
    expected_quote: str,
    expected_reference: str,
) -> None:
    result = _resolve(payload)

    assert result == {
        "label": expected_label,
        "mode": expected_mode,
        "quoteDate": expected_quote,
        "referenceDate": expected_reference,
    }


def test_stock_change_copy_falls_back_without_a_verified_session_date() -> None:
    assert _resolve(
        {
            "currentDate": "not-a-date",
            "quoteTradeDate": None,
            "tradeDates": [],
            "sessionStarted": False,
        }
    ) == {
        "label": "최근 장에서",
        "mode": "completed-session",
        "quoteDate": "",
        "referenceDate": "",
    }
