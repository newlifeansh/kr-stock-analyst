"""Read-only counts for the current domestic signal evidence gap."""
from __future__ import annotations

import json
import os

try:
    import psycopg
except ImportError:
    print(json.dumps({"status": "missing_driver"}))
    raise SystemExit(0)


def main() -> None:
    url = os.getenv("DATABASE_PUBLIC_URL") or os.getenv("DATABASE_URL")
    if not url:
        print(json.dumps({"status": "database_url_unavailable"}))
        return
    try:
        with psycopg.connect(url, connect_timeout=8) as db:
            with db.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """
                    WITH ranked AS (
                      SELECT dp.code, ROW_NUMBER() OVER (
                        ORDER BY dp.market_cap DESC, dp.code
                      ) AS rank
                      FROM daily_price dp
                      JOIN stock_master sm ON sm.code = dp.code
                      WHERE dp.trade_date = (
                        SELECT MAX(trade_date) FROM daily_price
                        WHERE market_cap > 0
                      )
                      AND dp.market_cap > 0 AND sm.is_active
                      AND sm.market IN ('KOSPI', 'KOSDAQ')
                    )
                    SELECT r.code, r.rank
                    FROM ranked r
                    LEFT JOIN quant_signal_evidence_snapshot e
                      ON e.stock_code = r.code
                      AND e.signal_date = CURRENT_DATE
                      AND e.strategy_version = 'position-lifecycle-v8.1'
                    WHERE r.rank <= 100 AND e.id IS NULL
                    ORDER BY r.rank
                    """
                )
                missing = [{"code": code, "rank": rank} for code, rank in cur.fetchall()]
        print(json.dumps({"status": "ok", "missing": missing}))
    except Exception as exc:
        print(json.dumps({"status": "query_failed", "error_type": type(exc).__name__}))


if __name__ == "__main__":
    main()
