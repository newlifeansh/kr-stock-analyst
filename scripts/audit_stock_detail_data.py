from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.db import engine

ACTIVE_STOCKS = """
SELECT code, name, market
FROM stock_master
WHERE is_active IS TRUE
  AND market IN ('KOSPI', 'KOSDAQ')
"""


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _one(connection, statement: str, **params: Any) -> dict[str, Any]:
    row = connection.execute(text(statement), params).mappings().one()
    return dict(row)


def _many(connection, statement: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in connection.execute(text(statement), params).mappings()]


def _dataset_coverage(connection, table: str, code_column: str) -> dict[str, Any]:
    return _one(
        connection,
        f"""
        WITH active AS ({ACTIVE_STOCKS})
        SELECT
            COUNT(DISTINCT active.code) AS total,
            COUNT(DISTINCT source.{code_column}) AS covered,
            COUNT(DISTINCT active.code) - COUNT(DISTINCT source.{code_column}) AS missing
        FROM active
        LEFT JOIN {table} AS source ON source.{code_column} = active.code
        """,
    )


def audit(sample_limit: int = 50) -> dict[str, Any]:
    with engine.connect() as connection:
        target_date = connection.scalar(text("SELECT MAX(trade_date) FROM daily_price"))
        active = _one(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS})
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN market = 'KOSPI' THEN 1 ELSE 0 END) AS kospi,
                SUM(CASE WHEN market = 'KOSDAQ' THEN 1 ELSE 0 END) AS kosdaq
            FROM active
            """,
        )

        price = _one(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            stats AS (
                SELECT
                    active.code,
                    COUNT(price.id) AS row_count,
                    MAX(price.trade_date) AS latest_date
                FROM active
                LEFT JOIN daily_price AS price ON price.code = active.code
                GROUP BY active.code
            )
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN row_count > 0 THEN 1 ELSE 0 END) AS covered,
                SUM(CASE WHEN row_count = 0 THEN 1 ELSE 0 END) AS missing,
                SUM(CASE WHEN latest_date = :target_date THEN 1 ELSE 0 END) AS current,
                SUM(CASE WHEN latest_date IS NOT NULL AND latest_date < :target_date THEN 1 ELSE 0 END) AS stale,
                SUM(CASE WHEN row_count >= 22 THEN 1 ELSE 0 END) AS history_22,
                SUM(CASE WHEN row_count >= 64 THEN 1 ELSE 0 END) AS history_64,
                SUM(CASE WHEN row_count >= 125 THEN 1 ELSE 0 END) AS history_125,
                SUM(CASE WHEN row_count >= 250 THEN 1 ELSE 0 END) AS history_250,
                SUM(CASE WHEN row_count >= 760 THEN 1 ELSE 0 END) AS history_760
            FROM stats
            """,
            target_date=target_date,
        )
        price_quality = _one(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            latest AS (
                SELECT price.code, MAX(price.trade_date) AS latest_date
                FROM daily_price AS price
                JOIN active ON active.code = price.code
                GROUP BY price.code
            )
            SELECT
                COUNT(*) AS latest_rows,
                SUM(CASE WHEN
                    price.open IS NULL OR price.high IS NULL OR price.low IS NULL OR price.close IS NULL
                    OR price.open <= 0 OR price.high <= 0 OR price.low <= 0 OR price.close <= 0
                    OR price.high < price.open OR price.high < price.close
                    OR price.low > price.open OR price.low > price.close
                    OR price.high < price.low
                THEN 1 ELSE 0 END) AS invalid_latest_ohlc,
                SUM(CASE WHEN price.volume IS NULL OR price.volume < 0 THEN 1 ELSE 0 END) AS invalid_latest_volume,
                SUM(CASE WHEN price.trade_date > :target_date THEN 1 ELSE 0 END) AS future_dated
            FROM latest
            JOIN daily_price AS price
              ON price.code = latest.code AND price.trade_date = latest.latest_date
            """,
            target_date=target_date,
        )
        price_issues = _many(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            stats AS (
                SELECT
                    active.code,
                    active.name,
                    active.market,
                    COUNT(price.id) AS row_count,
                    MAX(price.trade_date) AS latest_date
                FROM active
                LEFT JOIN daily_price AS price ON price.code = active.code
                GROUP BY active.code, active.name, active.market
            )
            SELECT code, name, market, row_count, latest_date
            FROM stats
            WHERE row_count = 0 OR latest_date < :target_date OR row_count < 125
            ORDER BY latest_date NULLS FIRST, row_count, code
            LIMIT :sample_limit
            """,
            target_date=target_date,
            sample_limit=sample_limit,
        )

        flow = _one(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            stats AS (
                SELECT
                    active.code,
                    COUNT(DISTINCT flow.trade_date) AS day_count,
                    MAX(flow.trade_date) AS latest_date
                FROM active
                LEFT JOIN investor_flow AS flow ON flow.code = active.code
                GROUP BY active.code
            )
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN day_count > 0 THEN 1 ELSE 0 END) AS covered,
                SUM(CASE WHEN day_count = 0 THEN 1 ELSE 0 END) AS missing,
                SUM(CASE WHEN latest_date = :target_date THEN 1 ELSE 0 END) AS current,
                SUM(CASE WHEN latest_date IS NOT NULL AND latest_date < :target_date THEN 1 ELSE 0 END) AS stale,
                SUM(CASE WHEN day_count >= 20 THEN 1 ELSE 0 END) AS history_20,
                SUM(CASE WHEN day_count >= 60 THEN 1 ELSE 0 END) AS history_60,
                SUM(CASE WHEN day_count >= 120 THEN 1 ELSE 0 END) AS history_120,
                SUM(CASE WHEN day_count >= 240 THEN 1 ELSE 0 END) AS history_240
            FROM stats
            """,
            target_date=target_date,
        )
        flow_pairs = _one(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            latest AS (
                SELECT flow.code, MAX(flow.trade_date) AS latest_date
                FROM investor_flow AS flow
                JOIN active ON active.code = flow.code
                GROUP BY flow.code
            ),
            pairs AS (
                SELECT
                    latest.code,
                    latest.latest_date,
                    MAX(CASE WHEN flow.investor_type IN ('외국인', '외국인합계') THEN 1 ELSE 0 END) AS has_foreign,
                    MAX(CASE WHEN flow.investor_type = '기관합계' THEN 1 ELSE 0 END) AS has_institution
                FROM latest
                JOIN investor_flow AS flow
                  ON flow.code = latest.code AND flow.trade_date = latest.latest_date
                GROUP BY latest.code, latest.latest_date
            )
            SELECT
                COUNT(*) AS latest_codes,
                SUM(CASE WHEN has_foreign = 1 AND has_institution = 1 THEN 1 ELSE 0 END) AS complete_pairs,
                SUM(CASE WHEN has_foreign = 0 OR has_institution = 0 THEN 1 ELSE 0 END) AS incomplete_pairs,
                SUM(CASE WHEN latest_date > :target_date THEN 1 ELSE 0 END) AS future_dated
            FROM pairs
            """,
            target_date=target_date,
        )
        flow_issues = _many(
            connection,
            f"""
            WITH active AS ({ACTIVE_STOCKS}),
            stats AS (
                SELECT
                    active.code,
                    active.name,
                    active.market,
                    COUNT(DISTINCT flow.trade_date) AS day_count,
                    MAX(flow.trade_date) AS latest_date
                FROM active
                LEFT JOIN investor_flow AS flow ON flow.code = active.code
                GROUP BY active.code, active.name, active.market
            )
            SELECT code, name, market, day_count, latest_date
            FROM stats
            WHERE day_count = 0 OR latest_date < :target_date OR day_count < 20
            ORDER BY latest_date NULLS FIRST, day_count, code
            LIMIT :sample_limit
            """,
            target_date=target_date,
            sample_limit=sample_limit,
        )

        datasets = {
            "fundamental_snapshot": _dataset_coverage(
                connection, "stock_fundamental_snapshot", "stock_code"
            ),
            "stock_news_snapshot": _dataset_coverage(
                connection, "stock_news_snapshot", "stock_code"
            ),
            "company_snapshot": _dataset_coverage(
                connection, "stock_company_snapshot", "stock_code"
            ),
            "company_profile": _dataset_coverage(
                connection, "company_profile", "stock_code"
            ),
            "financials": _dataset_coverage(
                connection, "financial_statement_line", "stock_code"
            ),
            "research_reports": _dataset_coverage(
                connection, "research_report", "stock_code"
            ),
            "disclosures": _dataset_coverage(
                connection, "disclosure_item", "stock_code"
            ),
        }
        snapshots = _one(
            connection,
            """
            SELECT
                SUM(CASE WHEN snapshot_key LIKE 'stock-dashboard:v1:%' THEN 1 ELSE 0 END) AS dashboard_rows,
                SUM(CASE WHEN snapshot_key LIKE 'stock-home-context:v1:%' THEN 1 ELSE 0 END) AS home_context_rows,
                SUM(CASE WHEN snapshot_key LIKE 'stock-%' AND payload IS NULL THEN 1 ELSE 0 END) AS missing_payload,
                SUM(CASE WHEN snapshot_key LIKE 'stock-%' AND last_error IS NOT NULL THEN 1 ELSE 0 END) AS errored,
                SUM(CASE WHEN snapshot_key LIKE 'stock-%' AND failure_count > 0 THEN 1 ELSE 0 END) AS failed_once_or_more,
                SUM(CASE WHEN snapshot_key LIKE 'stock-%' AND refresh_requested_at IS NOT NULL THEN 1 ELSE 0 END) AS refresh_pending
            FROM complete_payload_snapshot
            """,
        )
        snapshot_issues = _many(
            connection,
            """
            SELECT snapshot_key, captured_at, fresh_until, failure_count, last_error, refresh_requested_at
            FROM complete_payload_snapshot
            WHERE snapshot_key LIKE 'stock-%'
              AND (payload IS NULL OR last_error IS NOT NULL OR failure_count > 0)
            ORDER BY failure_count DESC, updated_at DESC
            LIMIT :sample_limit
            """,
            sample_limit=sample_limit,
        )

    return {
        "audited_at": datetime.now(timezone.utc),
        "database": engine.dialect.name,
        "target_date": target_date,
        "active_stocks": active,
        "price": {**price, **price_quality, "issues": price_issues},
        "investor_flow": {**flow, **flow_pairs, "issues": flow_issues},
        "datasets": datasets,
        "complete_snapshots": {**snapshots, "issues": snapshot_issues},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only production coverage audit for every stock-detail dataset."
    )
    parser.add_argument("--sample-limit", type=int, default=50)
    args = parser.parse_args()
    payload = audit(sample_limit=max(1, min(args.sample_limit, 500)))
    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
            default=_json_default,
        )
    )


if __name__ == "__main__":
    main()
