import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests
import typer
from dotenv import dotenv_values
from sqlalchemy import select, text

from app.bootstrap import bootstrap_runtime_data
from app.collectors.briefing import collect_home_briefing
from app.collectors.dart import (
    collect_financial_statement,
    collect_financial_statements_for_disclosure_companies,
)
from app.collectors.disclosures import collect_disclosures
from app.collectors.ecos import collect_ecos_series
from app.collectors.krx import (
    collect_investor_flows,
    collect_market_prices,
    collect_prices_for_codes,
    collect_stock_prices,
    collect_stocks,
)
from app.collectors.macro import collect_yahoo_macro_observations
from app.collectors.naver_flows import collect_naver_investor_flows
from app.collectors.naver_quotes import (
    collect_naver_price_history,
    collect_naver_quotes,
)
from app.collectors.news import collect_news_items
from app.collectors.research import collect_research_reports
from app.collectors.stock_snapshots import (
    collect_stock_company_snapshots,
    collect_stock_fundamental_snapshots,
    collect_stock_news_snapshots,
)
from app.config import get_settings
from app.db import SessionLocal, engine, init_db
from app.models import StockMaster
from app.qa.catalog import write_qa_catalog_markdown
from app.qa.release_parity import verify_release_parity, write_release_parity_report
from app.qa.runner import run_data_signal_qa, write_qa_report
from app.services.company_profiles import collect_company_profiles
from app.services.stock_logos import sync_stock_logos

app = typer.Typer(no_args_is_help=True)
qa_app = typer.Typer(no_args_is_help=True, help="Data-integration and signal-decision QA.")
app.add_typer(qa_app, name="qa")


@qa_app.command("data-signal")
def qa_data_signal_command(
    mode: str = typer.Option(
        "gate",
        "--mode",
        help="QA mode: gate, live, or e2e.",
    ),
    base_url: str = typer.Option(
        "https://dark-theme-preview-staging.up.railway.app",
        "--base-url",
        help="Read-only API and browser target.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        help="Optional JSON report path.",
    ),
    artifact_dir: Path = typer.Option(
        Path("artifacts/qa-data-signal/e2e"),
        "--artifact-dir",
        help="E2E failure screenshot directory.",
    ),
    timeout: float = typer.Option(
        20.0,
        "--timeout",
        min=1.0,
        help="Per-request/browser timeout in seconds.",
    ),
    direct_kis: bool = typer.Option(
        False,
        "--direct-kis/--no-direct-kis",
        help="Also call the configured KIS source directly in live mode.",
    ),
    pytest_junit: Optional[Path] = typer.Option(
        None,
        "--pytest-junit",
        help="JUnit XML evidence from the deterministic pytest gate.",
    ),
) -> None:
    normalized_mode = mode.strip().lower()
    if normalized_mode not in {"gate", "live", "e2e"}:
        raise typer.BadParameter("mode must be gate, live, or e2e", param_hint="--mode")
    report = run_data_signal_qa(
        mode=normalized_mode,  # type: ignore[arg-type]
        base_url=base_url,
        timeout=timeout,
        artifact_dir=artifact_dir,
        direct_kis=direct_kis,
        pytest_junit=pytest_junit,
    )
    if output is not None:
        write_qa_report(report, output)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if report["deployment_blocked"]:
        raise typer.Exit(code=1)


@qa_app.command("render-catalog")
def qa_render_catalog_command(
    output: Path = typer.Option(
        Path("docs/qa/data-signal-qa-matrix.md"),
        "--output",
        help="Generated Markdown QA catalog path.",
    ),
) -> None:
    destination = write_qa_catalog_markdown(output)
    typer.echo(str(destination))


@qa_app.command("release-parity")
def qa_release_parity_command(
    staging_url: str = typer.Option(..., "--staging-url"),
    production_url: Optional[str] = typer.Option(None, "--production-url"),
    source_sha: Optional[str] = typer.Option(None, "--source-sha"),
    output: Path = typer.Option(
        Path("artifacts/qa-data-signal/release-parity.json"),
        "--output",
    ),
    timeout: float = typer.Option(20.0, "--timeout", min=1.0),
    wait_seconds: float = typer.Option(0.0, "--wait-seconds", min=0.0),
) -> None:
    report = verify_release_parity(
        staging_url=staging_url,
        production_url=production_url,
        source_sha=source_sha,
        timeout=timeout,
        wait_seconds=wait_seconds,
    )
    write_release_parity_report(report, output)
    typer.echo(json.dumps(report, ensure_ascii=False, indent=2))
    if report["deployment_blocked"]:
        raise typer.Exit(code=1)


PERFORMANCE_INDEX_DEFINITIONS = (
    (
        "ix_investor_flow_code_trade_date_desc_type",
        "investor_flow",
        '"code", "trade_date" DESC, "investor_type"',
    ),
    (
        "ix_research_report_stock_published_id_desc",
        "research_report",
        '"stock_code", "published_at" DESC, "id" DESC',
    ),
    (
        "ix_disclosure_item_stock_published_external_id_desc",
        "disclosure_item",
        '"stock_code", "published_at" DESC, "external_id" DESC, "id" DESC',
    ),
    (
        "ix_market_ranking_snapshot_category_captured_desc",
        "market_ranking_snapshot",
        '"category", "captured_at" DESC',
    ),
)


def performance_index_statements(dialect_name: str) -> list[str]:
    normalized = str(dialect_name or "").strip().lower()
    if normalized not in {"postgresql", "sqlite"}:
        raise ValueError(
            "Performance index migration supports only PostgreSQL and SQLite"
        )
    concurrently = " CONCURRENTLY" if normalized == "postgresql" else ""
    return [
        (f'CREATE INDEX{concurrently} "{index_name}" ON "{table_name}" ({columns})')
        for index_name, table_name, columns in PERFORMANCE_INDEX_DEFINITIONS
    ]


POSTGRESQL_INDEX_STATE_SQL = """
WITH target_table AS (
    SELECT
        target.oid AS table_oid,
        target.relnamespace AS schema_oid,
        target.relname AS table_name,
        target_schema.nspname AS schema_name
    FROM pg_catalog.pg_class AS target
    JOIN pg_catalog.pg_namespace AS target_schema
      ON target_schema.oid = target.relnamespace
    WHERE target.oid = pg_catalog.to_regclass(:table_name)
      AND target.relkind IN ('r', 'p')
)
SELECT
    target_table.schema_name AS target_schema_name,
    target_table.table_name AS target_table_name,
    existing_index.relname AS index_name,
    existing_index.relkind AS relation_kind,
    indexed_schema.nspname AS indexed_table_schema_name,
    indexed_table.relname AS indexed_table_name,
    index_metadata.indisvalid AS is_valid,
    index_metadata.indisready AS is_ready,
    index_metadata.indisunique AS is_unique,
    index_method.amname AS access_method,
    (index_metadata.indpred IS NOT NULL) AS is_partial,
    (index_metadata.indexprs IS NOT NULL) AS has_expressions,
    index_metadata.indnkeyatts AS key_column_count,
    index_metadata.indnatts AS total_column_count,
    ARRAY(
        SELECT indexed_attribute.attname
        FROM generate_series(0, index_metadata.indnkeyatts - 1) AS key_position(position)
        LEFT JOIN pg_catalog.pg_attribute AS indexed_attribute
          ON indexed_attribute.attrelid = index_metadata.indrelid
         AND indexed_attribute.attnum = index_metadata.indkey[key_position.position]
        ORDER BY key_position.position
    ) AS column_names,
    ARRAY(
        SELECT CASE
            WHEN (index_metadata.indoption[key_position.position] & 1) = 1 THEN 'DESC'
            ELSE 'ASC'
        END
        FROM generate_series(0, index_metadata.indnkeyatts - 1) AS key_position(position)
        ORDER BY key_position.position
    ) AS sort_directions,
    CASE
        WHEN existing_index.relkind IN ('i', 'I')
        THEN pg_catalog.pg_get_indexdef(existing_index.oid)
        ELSE NULL
    END AS index_definition
FROM target_table
LEFT JOIN pg_catalog.pg_class AS existing_index
  ON existing_index.relnamespace = target_table.schema_oid
 AND existing_index.relname = :index_name
LEFT JOIN pg_catalog.pg_index AS index_metadata
  ON index_metadata.indexrelid = existing_index.oid
LEFT JOIN pg_catalog.pg_class AS indexed_table
  ON indexed_table.oid = index_metadata.indrelid
LEFT JOIN pg_catalog.pg_namespace AS indexed_schema
  ON indexed_schema.oid = indexed_table.relnamespace
LEFT JOIN pg_catalog.pg_am AS index_method
  ON index_method.oid = existing_index.relam
"""


def _quote_identifier(value: str) -> str:
    return f'"{str(value).replace(chr(34), chr(34) * 2)}"'


def _expected_index_columns(columns_sql: str) -> tuple[list[str], list[str]]:
    column_names: list[str] = []
    sort_directions: list[str] = []
    for raw_column in columns_sql.split(","):
        match = re.fullmatch(
            r'\s*"((?:[^"]|"")+)"(?:\s+(ASC|DESC))?\s*',
            raw_column,
            flags=re.IGNORECASE,
        )
        if match is None:
            raise ValueError(f"Unsupported performance index column: {raw_column}")
        column_names.append(match.group(1).replace('""', '"'))
        sort_directions.append((match.group(2) or "ASC").upper())
    return column_names, sort_directions


def _normalize_catalog_sequence(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        # psycopg normally returns PostgreSQL arrays as lists. Keep this small
        # fallback for alternate drivers and test doubles.
        normalized = value.strip()
        if normalized.startswith("{") and normalized.endswith("}"):
            normalized = normalized[1:-1]
            if not normalized:
                return []
            return [part.strip().strip('"') for part in normalized.split(",")]
        return [normalized]
    return [str(item) for item in value]


def _index_state_errors(
    state: dict[str, object],
    *,
    table_name: str,
    columns_sql: str,
) -> list[str]:
    if state.get("index_name") is None:
        return ["index is missing"]
    if state.get("relation_kind") not in {"i", "I", "index"}:
        return [
            f"name is occupied by a non-index relation ({state.get('relation_kind')})"
        ]

    expected_columns, expected_directions = _expected_index_columns(columns_sql)
    errors: list[str] = []
    if state.get("indexed_table_name") != table_name:
        errors.append(
            f"indexes table {state.get('indexed_table_name')!r}, expected {table_name!r}"
        )
    target_schema = state.get("target_schema_name")
    indexed_schema = state.get("indexed_table_schema_name")
    if target_schema and indexed_schema != target_schema:
        errors.append(f"indexes schema {indexed_schema!r}, expected {target_schema!r}")
    if state.get("is_valid") is not True:
        errors.append("index is not valid")
    if state.get("is_ready") is not True:
        errors.append("index is not ready")
    if state.get("is_unique") is not False:
        errors.append("index uniqueness metadata is not the expected non-unique value")
    if state.get("access_method") != "btree":
        errors.append(
            f"uses access method {state.get('access_method')!r}, expected btree"
        )
    if state.get("is_partial") is not False:
        errors.append("index predicate metadata is not the expected non-partial value")
    if state.get("has_expressions") is not False:
        errors.append(
            "index expression metadata is not the expected simple-column value"
        )

    actual_columns = _normalize_catalog_sequence(state.get("column_names"))
    actual_directions = [
        direction.upper()
        for direction in _normalize_catalog_sequence(state.get("sort_directions"))
    ]
    if actual_columns != expected_columns:
        errors.append(f"columns are {actual_columns!r}, expected {expected_columns!r}")
    if actual_directions != expected_directions:
        errors.append(
            f"directions are {actual_directions!r}, expected {expected_directions!r}"
        )
    key_column_count = state.get("key_column_count")
    if key_column_count is None or int(key_column_count) != len(expected_columns):
        errors.append(
            f"has {key_column_count} key columns, expected {len(expected_columns)}"
        )
    total_column_count = state.get("total_column_count")
    if total_column_count is None or int(total_column_count) != len(expected_columns):
        errors.append("index contains unexpected included columns")
    return errors


def _read_postgresql_index_state(
    connection,
    *,
    index_name: str,
    table_name: str,
) -> dict[str, object]:
    row = (
        connection.execute(
            text(POSTGRESQL_INDEX_STATE_SQL),
            {"index_name": index_name, "table_name": table_name},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise RuntimeError(f'PostgreSQL target table "{table_name}" does not exist')
    return dict(row)


def _read_sqlite_index_state(
    connection,
    *,
    index_name: str,
    table_name: str,
) -> dict[str, object]:
    table_exists = connection.execute(
        text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = :table_name"),
        {"table_name": table_name},
    ).first()
    if table_exists is None:
        raise RuntimeError(f'SQLite target table "{table_name}" does not exist')

    relation = (
        connection.execute(
            text(
                "SELECT type, name AS index_name, tbl_name AS table_name, sql "
                "FROM sqlite_master WHERE name = :index_name"
            ),
            {"index_name": index_name},
        )
        .mappings()
        .one_or_none()
    )
    if relation is None:
        return {
            "target_schema_name": "main",
            "target_table_name": table_name,
            "index_name": None,
        }
    state = dict(relation)
    state.update(
        {
            "target_schema_name": "main",
            "target_table_name": table_name,
            "relation_kind": "index"
            if relation["type"] == "index"
            else relation["type"],
            "indexed_table_name": relation["table_name"],
            "indexed_table_schema_name": "main",
            "is_valid": relation["type"] == "index",
            "is_ready": relation["type"] == "index",
            "access_method": "btree",
        }
    )
    if relation["type"] != "index":
        return state

    quoted_table = _quote_identifier(str(relation["table_name"]))
    index_list = (
        connection.execute(text(f"PRAGMA index_list({quoted_table})")).mappings().all()
    )
    index_list_row = next(
        (item for item in index_list if item.get("name") == index_name),
        None,
    )
    quoted_index = _quote_identifier(index_name)
    index_columns = (
        connection.execute(text(f"PRAGMA index_xinfo({quoted_index})")).mappings().all()
    )
    key_columns = [item for item in index_columns if int(item.get("key", 1)) == 1]
    state.update(
        {
            "is_unique": bool(index_list_row and index_list_row.get("unique")),
            "is_partial": bool(index_list_row and index_list_row.get("partial")),
            "has_expressions": any(
                item.get("name") is None or int(item.get("cid", -2)) < 0
                for item in key_columns
            ),
            "column_names": [item.get("name") for item in key_columns],
            "sort_directions": [
                "DESC" if bool(item.get("desc")) else "ASC" for item in key_columns
            ],
            "key_column_count": len(key_columns),
            "total_column_count": len(key_columns),
        }
    )
    return state


def _create_index_statement(
    *,
    dialect_name: str,
    index_name: str,
    table_name: str,
    columns_sql: str,
    schema_name: Optional[str] = None,
) -> str:
    concurrently = " CONCURRENTLY" if dialect_name == "postgresql" else ""
    qualified_table = _quote_identifier(table_name)
    if schema_name:
        qualified_table = f"{_quote_identifier(schema_name)}.{qualified_table}"
    return (
        f"CREATE INDEX{concurrently} {_quote_identifier(index_name)} "
        f"ON {qualified_table} ({columns_sql})"
    )


def _ensure_postgresql_performance_indexes(database_engine) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    with database_engine.connect() as connection:
        # CREATE/DROP INDEX CONCURRENTLY are both forbidden in a transaction.
        autocommit_connection = connection.execution_options(
            isolation_level="AUTOCOMMIT"
        )
        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS:
            state = _read_postgresql_index_state(
                autocommit_connection,
                index_name=index_name,
                table_name=table_name,
            )
            errors = _index_state_errors(
                state,
                table_name=table_name,
                columns_sql=columns_sql,
            )
            statements: list[str] = []
            if errors != ["index is missing"] and state.get("relation_kind") not in {
                "i",
                "I",
            }:
                raise RuntimeError(
                    f'Cannot repair performance index "{index_name}": {"; ".join(errors)}'
                )
            if errors:
                if state.get("index_name") is not None:
                    schema_name = str(state["target_schema_name"])
                    drop_statement = (
                        "DROP INDEX CONCURRENTLY IF EXISTS "
                        f"{_quote_identifier(schema_name)}.{_quote_identifier(index_name)}"
                    )
                    autocommit_connection.execute(text(drop_statement))
                    statements.append(drop_statement)
                create_statement = _create_index_statement(
                    dialect_name="postgresql",
                    index_name=index_name,
                    table_name=table_name,
                    columns_sql=columns_sql,
                    schema_name=str(state["target_schema_name"]),
                )
                autocommit_connection.execute(text(create_statement))
                statements.append(create_statement)
            actions.append(
                {
                    "index": index_name,
                    "action": (
                        "verified"
                        if not errors
                        else "created"
                        if errors == ["index is missing"]
                        else "recreated"
                    ),
                    "preflight_errors": errors,
                    "statements": statements,
                }
            )

        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS:
            state = _read_postgresql_index_state(
                autocommit_connection,
                index_name=index_name,
                table_name=table_name,
            )
            errors = _index_state_errors(
                state,
                table_name=table_name,
                columns_sql=columns_sql,
            )
            if errors:
                raise RuntimeError(
                    f'Postflight verification failed for "{index_name}": '
                    f"{'; '.join(errors)}"
                )
    return actions


def _ensure_sqlite_performance_indexes(database_engine) -> list[dict[str, object]]:
    actions: list[dict[str, object]] = []
    # SQLite has no concurrent index build; keep inspection and all repairs atomic.
    with database_engine.begin() as connection:
        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS:
            state = _read_sqlite_index_state(
                connection,
                index_name=index_name,
                table_name=table_name,
            )
            errors = _index_state_errors(
                state,
                table_name=table_name,
                columns_sql=columns_sql,
            )
            statements: list[str] = []
            if errors != ["index is missing"] and state.get("relation_kind") != "index":
                raise RuntimeError(
                    f'Cannot repair performance index "{index_name}": {"; ".join(errors)}'
                )
            if errors:
                if state.get("index_name") is not None:
                    drop_statement = (
                        f"DROP INDEX IF EXISTS {_quote_identifier(index_name)}"
                    )
                    connection.execute(text(drop_statement))
                    statements.append(drop_statement)
                create_statement = _create_index_statement(
                    dialect_name="sqlite",
                    index_name=index_name,
                    table_name=table_name,
                    columns_sql=columns_sql,
                )
                connection.execute(text(create_statement))
                statements.append(create_statement)
            actions.append(
                {
                    "index": index_name,
                    "action": (
                        "verified"
                        if not errors
                        else "created"
                        if errors == ["index is missing"]
                        else "recreated"
                    ),
                    "preflight_errors": errors,
                    "statements": statements,
                }
            )

        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS:
            state = _read_sqlite_index_state(
                connection,
                index_name=index_name,
                table_name=table_name,
            )
            errors = _index_state_errors(
                state,
                table_name=table_name,
                columns_sql=columns_sql,
            )
            if errors:
                raise RuntimeError(
                    f'Postflight verification failed for "{index_name}": '
                    f"{'; '.join(errors)}"
                )
    return actions


def ensure_performance_indexes(
    database_engine, *, dry_run: bool = False
) -> dict[str, object]:
    """Validate and idempotently repair query-order indexes."""

    dialect_name = str(database_engine.dialect.name).strip().lower()
    statements = performance_index_statements(dialect_name)
    actions: list[dict[str, object]] = []
    if not dry_run and dialect_name == "postgresql":
        actions = _ensure_postgresql_performance_indexes(database_engine)
    elif not dry_run:
        actions = _ensure_sqlite_performance_indexes(database_engine)
    return {
        "dialect": dialect_name,
        "dry_run": dry_run,
        "indexes": [definition[0] for definition in PERFORMANCE_INDEX_DEFINITIONS],
        "statements": statements,
        "actions": actions,
    }


def verify_mcp_endpoint_payload(
    url: str,
    *,
    query: str = "삼성전자",
    timeout: int = 30,
    limit: int = 3,
) -> dict[str, object]:
    endpoint = url.strip()
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }

    def rpc(
        method: str, params: dict[str, object], request_id: int
    ) -> dict[str, object]:
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"{method} failed: {payload['error']}")
        return payload["result"]

    initialize = rpc(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "kr-stock-analyst-cli", "version": "0.1.0"},
        },
        1,
    )
    tools = rpc("tools/list", {}, 2).get("tools", [])
    search = rpc(
        "tools/call",
        {
            "name": "search_korea_stocks",
            "arguments": {"query": query, "limit": max(1, min(limit, 10))},
        },
        3,
    )
    pipeline = rpc(
        "tools/call",
        {
            "name": "get_data_pipeline_status",
            "arguments": {},
        },
        4,
    )

    return {
        "ok": True,
        "endpoint": endpoint,
        "server_name": initialize.get("serverInfo", {}).get("name"),
        "protocol_version": initialize.get("protocolVersion"),
        "tool_count": len(tools),
        "tool_names": [tool.get("name") for tool in tools],
        "search_query": query,
        "search_count": search.get("structuredContent", {}).get("count"),
        "search_preview": search.get("structuredContent", {}).get("stocks", [])[
            : max(1, min(limit, 5))
        ],
        "pipeline_status": pipeline.get("structuredContent"),
    }


RAILWAY_ENV_KEYS = [
    "APP_NAME",
    "PROCESS_ROLE",
    "DATABASE_URL",
    "DART_API_KEY",
    "ECOS_API_KEY",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
    "KIS_ENV",
    "BRIEFING_REALTIME_ENABLED",
    "BRIEFING_POLL_SECONDS",
    "BRIEFING_WATCH_CODES",
    "BRIEFING_DISCLOSURE_LIMIT",
    "BRIEFING_REPORT_LIMIT",
    "BRIEFING_NEWS_LIMIT",
    "RESEARCH_ENABLED",
    "RESEARCH_POLL_SECONDS",
    "RESEARCH_CATEGORIES",
    "RESEARCH_MAX_PAGES",
    "RESEARCH_DAYS_BACK",
    "RESEARCH_INCLUDE_DETAIL",
    "DISCLOSURE_ENABLED",
    "DISCLOSURE_POLL_SECONDS",
    "DISCLOSURE_DAYS_BACK",
    "DISCLOSURE_PAGE_COUNT",
    "NEWS_ENABLED",
    "NEWS_POLL_SECONDS",
    "NEWS_CATEGORIES",
    "NEWS_MAX_PAGES",
    "NEWS_DAYS_BACK",
    "PRICE_ENABLED",
    "PRICE_POLL_SECONDS",
    "PRICE_DAYS_BACK",
    "PRICE_CODE_LIMIT",
    "PRICE_MAX_WORKERS",
    "STOCK_UNIVERSE_ENABLED",
    "STOCK_UNIVERSE_POLL_SECONDS",
    "STOCK_UNIVERSE_MARKETS",
    "STOCK_LOGO_ENABLED",
    "STOCK_LOGO_POLL_SECONDS",
    "STOCK_LOGO_INITIAL_DELAY_SECONDS",
    "STOCK_LOGO_TIMEOUT_SECONDS",
    "STOCK_LOGO_MAX_WORKERS",
    "STOCK_LOGO_MISSING_RETRY_DAYS",
    "INVESTOR_FLOW_ENABLED",
    "INVESTOR_FLOW_POLL_SECONDS",
    "INVESTOR_FLOW_PAGES",
    "INVESTOR_FLOW_CODE_LIMIT",
    "INVESTOR_FLOW_MAX_WORKERS",
    "FINANCIALS_ENABLED",
    "FINANCIALS_POLL_SECONDS",
    "FINANCIALS_YEAR",
    "FINANCIALS_REPORT",
    "FINANCIALS_FS_DIV",
    "FINANCIALS_COMPANY_LIMIT",
    "FUNDAMENTAL_SNAPSHOT_ENABLED",
    "FUNDAMENTAL_SNAPSHOT_POLL_SECONDS",
    "FUNDAMENTAL_SNAPSHOT_REFRESH_DAYS",
    "FUNDAMENTAL_SNAPSHOT_MAX_WORKERS",
    "STOCK_NEWS_SNAPSHOT_ENABLED",
    "STOCK_NEWS_SNAPSHOT_POLL_SECONDS",
    "STOCK_NEWS_SNAPSHOT_REFRESH_HOURS",
    "STOCK_NEWS_SNAPSHOT_MAX_WORKERS",
    "STOCK_COMPANY_SNAPSHOT_ENABLED",
    "STOCK_COMPANY_SNAPSHOT_POLL_SECONDS",
    "STOCK_COMPANY_SNAPSHOT_REFRESH_DAYS",
    "STOCK_COMPANY_SNAPSHOT_MAX_WORKERS",
    "MACRO_ENABLED",
    "MACRO_POLL_SECONDS",
    "MACRO_RANGE",
    "BOOTSTRAP_ON_START",
    "BOOTSTRAP_FORCE_REFRESH",
    "MCP_ENABLED",
    "MCP_SERVER_NAME",
    "MCP_PUBLIC_BASE_URL",
    "MCP_ALLOWED_HOSTS",
    "MCP_ALLOWED_ORIGINS",
    "MCP_LOG_LEVEL",
]

RAILWAY_SECRET_KEYS = {
    "DART_API_KEY",
    "ECOS_API_KEY",
    "KIS_APP_KEY",
    "KIS_APP_SECRET",
}


def _stringify_env_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _normalized_public_base_url(value: str) -> tuple[str, str]:
    raw = value.strip()
    if not raw:
        raise ValueError("public base URL is required")
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"invalid public base URL: {value}")
    return raw.rstrip("/"), parsed.netloc


def export_railway_env_payload(
    public_base_url: str,
    *,
    source_env_path: str = ".env",
    database_mode: str = "postgres-ref",
    redact_secrets: bool = False,
) -> str:
    normalized_url, host = _normalized_public_base_url(public_base_url)
    env_path = Path(source_env_path)
    source_values = dotenv_values(env_path) if env_path.exists() else {}
    settings = get_settings()

    output: dict[str, str] = {"APP_MODULE": "app.mcp_app:app"}
    if database_mode == "postgres-ref":
        output["DATABASE_URL"] = "${{Postgres.DATABASE_URL}}"
    elif database_mode == "sqlite-volume":
        output["DATABASE_URL"] = "sqlite:////data/analyst.db"
    else:
        raise ValueError("database_mode must be one of: postgres-ref, sqlite-volume")

    for key in RAILWAY_ENV_KEYS:
        if key in output:
            continue
        value = source_values.get(key)
        if value is None:
            value = getattr(settings, key.lower(), None)
        output[key] = _stringify_env_value(value)

    output["MCP_PUBLIC_BASE_URL"] = normalized_url
    output["MCP_ALLOWED_HOSTS"] = f"{host},healthcheck.railway.app"
    output["MCP_ALLOWED_ORIGINS"] = "https://playmcp.kakao.com"
    output["MCP_ENABLED"] = "true"
    output["BOOTSTRAP_ON_START"] = output.get("BOOTSTRAP_ON_START") or "true"

    if redact_secrets:
        for key in RAILWAY_SECRET_KEYS:
            if output.get(key):
                output[key] = "***REDACTED***"

    ordered_keys = ["APP_MODULE"] + RAILWAY_ENV_KEYS
    return "\n".join(f"{key}={output[key]}" for key in ordered_keys) + "\n"


def _command_status(
    command: list[str], *, cwd: Optional[str] = None
) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except FileNotFoundError:
        return {"ok": False, "code": None, "stdout": "", "stderr": "command not found"}
    except Exception as exc:
        return {"ok": False, "code": None, "stdout": "", "stderr": str(exc)}

    return {
        "ok": completed.returncode == 0,
        "code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def railway_readiness_payload(
    public_base_url: str,
    *,
    workdir: str = ".",
    source_env_path: str = ".env",
    check_endpoint: bool = True,
) -> dict[str, object]:
    normalized_url, host = _normalized_public_base_url(public_base_url)
    repo_root = Path(workdir).resolve()
    git_dir = repo_root / ".git"
    railway_json = repo_root / "railway.json"
    dockerfile = repo_root / "Dockerfile"
    dockerignore = repo_root / ".dockerignore"

    git_remote = _command_status(["git", "remote", "-v"], cwd=str(repo_root))
    gh_auth = _command_status(["gh", "auth", "status"], cwd=str(repo_root))
    railway_version = _command_status(
        ["npx", "-y", "@railway/cli", "--version"], cwd=str(repo_root)
    )
    railway_auth = _command_status(
        ["npx", "-y", "@railway/cli", "whoami"], cwd=str(repo_root)
    )

    payload: dict[str, object] = {
        "ok": True,
        "public_base_url": normalized_url,
        "public_host": host,
        "paths": {
            "workdir": str(repo_root),
            "railway_json": railway_json.exists(),
            "dockerfile": dockerfile.exists(),
            "dockerignore": dockerignore.exists(),
            "env_file": (repo_root / source_env_path).exists()
            if not Path(source_env_path).is_absolute()
            else Path(source_env_path).exists(),
        },
        "git": {
            "initialized": git_dir.exists(),
            "remote_configured": bool(git_remote.get("stdout")),
            "remote_preview": (git_remote.get("stdout") or "").splitlines()[:2],
        },
        "github_cli": {
            "authenticated": gh_auth["ok"],
            "stderr": gh_auth["stderr"],
        },
        "railway_cli": {
            "available": railway_version["ok"],
            "version": railway_version["stdout"] or railway_version["stderr"],
            "authenticated": railway_auth["ok"],
            "whoami": railway_auth["stdout"] or railway_auth["stderr"],
        },
        "railway_env_preview": export_railway_env_payload(
            normalized_url,
            source_env_path=source_env_path,
            database_mode="postgres-ref",
            redact_secrets=True,
        ).splitlines()[:12],
        "notes": [],
        "next_actions": [],
    }

    if check_endpoint:
        try:
            endpoint = verify_mcp_endpoint_payload(normalized_url + "/", limit=1)
            payload["endpoint_check"] = {
                "ok": True,
                "tool_count": endpoint["tool_count"],
                "search_count": endpoint["search_count"],
                "server_name": endpoint["server_name"],
            }
        except Exception as exc:
            payload["endpoint_check"] = {"ok": False, "error": str(exc)}

    notes: list[str] = []
    next_actions: list[str] = []
    if not payload["git"]["remote_configured"]:
        notes.append(
            "Git remote is not configured, but `railway up` can still deploy local source code."
        )
    if not payload["railway_cli"]["authenticated"]:
        next_actions.append("Run `railway login` before deploying.")
    if not payload["github_cli"]["authenticated"]:
        next_actions.append(
            "Authenticate GitHub CLI or connect the repo manually in Railway."
        )
    if check_endpoint and not payload.get("endpoint_check", {}).get("ok", False):
        next_actions.append("Fix the public MCP endpoint before final registration.")
    payload["notes"] = notes
    payload["next_actions"] = next_actions
    payload["ok"] = not next_actions
    return payload


@app.command("export-railway-env")
def export_railway_env_command(
    public_base_url: str = typer.Option(
        ...,
        "--public-base-url",
        help="Public service URL or host, e.g. https://your-mcp-domain or your-mcp-domain",
    ),
    source_env: str = typer.Option(
        ".env", "--source-env", help="Source dotenv file to read secrets/defaults from"
    ),
    database_mode: str = typer.Option(
        "postgres-ref", "--database-mode", help="postgres-ref or sqlite-volume"
    ),
    redact_secrets: bool = typer.Option(
        False, "--redact-secrets", help="Redact secret values for safe preview"
    ),
    output: Optional[str] = typer.Option(
        None, "--output", help="Optional file path to save the generated env block"
    ),
) -> None:
    try:
        payload = export_railway_env_payload(
            public_base_url,
            source_env_path=source_env,
            database_mode=database_mode,
            redact_secrets=redact_secrets,
        )
    except Exception as exc:
        typer.echo(f"Railway env export failed: {exc}")
        raise typer.Exit(code=1) from exc

    if output:
        Path(output).write_text(payload, encoding="utf-8")
        typer.echo(f"Saved Railway env to {output}")
        return
    typer.echo(payload.rstrip())


@app.command("check-railway-readiness")
def check_railway_readiness_command(
    public_base_url: str = typer.Option(
        ...,
        "--public-base-url",
        help="Public service URL or host, e.g. https://your-mcp-domain or your-mcp-domain",
    ),
    source_env: str = typer.Option(
        ".env", "--source-env", help="Source dotenv file to read secrets/defaults from"
    ),
    check_endpoint: bool = typer.Option(
        True,
        "--check-endpoint/--no-check-endpoint",
        help="Verify the current public MCP endpoint too",
    ),
) -> None:
    payload = railway_readiness_payload(
        public_base_url,
        workdir=".",
        source_env_path=source_env,
        check_endpoint=check_endpoint,
    )
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("init-db")
def init_database() -> None:
    init_db()
    typer.echo("Database initialized.")


@app.command("migrate-performance-indexes")
def migrate_performance_indexes_command(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the canonical index DDL without changing the database",
    ),
) -> None:
    """Validate and repair dashboard indexes as a maintenance operation."""

    try:
        payload = ensure_performance_indexes(engine, dry_run=dry_run)
    except Exception as exc:
        typer.echo(f"Performance index migration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("collect-stocks")
def collect_stocks_command(
    date: str = typer.Option(..., "--date", help="YYYYMMDD"),
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_stocks(db, date, markets)
    typer.echo(f"Loaded {count} stock rows.")


@app.command("sync-stock-logos")
def sync_stock_logos_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(
        None, "--limit", help="Optional missing-logo limit"
    ),
    max_workers: int = typer.Option(4, "--max-workers", help="Concurrent workers"),
) -> None:
    settings = get_settings()
    init_db()
    with SessionLocal() as db:
        result = sync_stock_logos(
            db,
            markets=markets,
            timeout_seconds=settings.stock_logo_timeout_seconds,
            max_workers=max_workers,
            missing_retry_days=settings.stock_logo_missing_retry_days,
            limit=limit,
        )
    typer.echo(json.dumps(result, ensure_ascii=False))


@app.command("collect-prices")
def collect_prices_command(
    date: str = typer.Option(..., "--date", help="YYYYMMDD"),
    market: str = typer.Option("KOSPI", "--market", help="KOSPI, KOSDAQ, or KONEX"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_market_prices(db, date, market)
    typer.echo(f"Loaded {count} daily price rows.")


@app.command("collect-naver-quotes")
def collect_naver_quotes_command(
    date: str = typer.Option(..., "--date", help="YYYYMMDD"),
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_naver_quotes(
            db, date, markets=markets, limit=limit, max_workers=max_workers
        )
    typer.echo(f"Loaded {count} Naver quote rows.")


@app.command("collect-naver-price-history")
def collect_naver_price_history_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    pages: int = typer.Option(
        10, "--pages", help="Naver daily-price pages per code; 10 rows per page"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_naver_price_history(
            db, markets=markets, pages=pages, limit=limit, max_workers=max_workers
        )
    typer.echo(f"Loaded {count} Naver daily price history rows.")


@app.command("collect-stock-fundamentals")
def collect_stock_fundamentals_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
    refresh_days: int = typer.Option(
        7, "--refresh-days", help="Skip snapshots newer than N days; 0 refreshes all"
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        result = collect_stock_fundamental_snapshots(
            db,
            markets=markets,
            limit=limit,
            max_workers=max_workers,
            refresh_days=refresh_days,
        )
    typer.echo(result["message"])


@app.command("collect-company-profiles")
def collect_company_profiles_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional company limit"),
    refresh: bool = typer.Option(
        False, "--refresh/--skip-fresh", help="Refresh profiles already stored"
    ),
    include_business_reports: bool = typer.Option(
        False,
        "--include-business-reports/--company-overview-only",
        help="Download business reports too; overview-only is recommended for the first full backfill",
    ),
    max_workers: int = typer.Option(
        2, "--max-workers", help="Concurrent DART overview requests"
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        result = collect_company_profiles(
            db,
            markets=markets,
            limit=limit,
            refresh=refresh,
            include_business_reports=include_business_reports,
            max_workers=max_workers,
        )
    typer.echo(result["message"])


@app.command("collect-stock-news")
def collect_stock_news_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
    refresh_hours: int = typer.Option(
        6,
        "--refresh-hours",
        help="Skip snapshots newer than N hours; 0 refreshes all",
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        result = collect_stock_news_snapshots(
            db,
            markets=markets,
            limit=limit,
            max_workers=max_workers,
            refresh_hours=refresh_hours,
        )
    typer.echo(result["message"])


@app.command("collect-stock-company-info")
def collect_stock_company_info_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
    refresh_days: int = typer.Option(
        30,
        "--refresh-days",
        help="Skip snapshots newer than N days; 0 refreshes all",
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        result = collect_stock_company_snapshots(
            db,
            markets=markets,
            limit=limit,
            max_workers=max_workers,
            refresh_days=refresh_days,
        )
    typer.echo(result["message"])


@app.command("collect-market-universe")
def collect_market_universe_command(
    date: str = typer.Option(..., "--date", help="YYYYMMDD"),
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    max_workers: int = typer.Option(
        8, "--max-workers", help="Naver fallback concurrent workers"
    ),
) -> None:
    init_db()
    market_list = [
        market.strip().upper() for market in markets.split(",") if market.strip()
    ]
    with SessionLocal() as db:
        stock_count = collect_stocks(db, date, markets)
    typer.echo(f"Loaded {stock_count} stock rows.")

    for market in market_list:
        try:
            with SessionLocal() as db:
                count = collect_market_prices(db, date, market)
            typer.echo(f"Loaded {count} KRX price rows for {market}.")
        except Exception as exc:
            typer.echo(f"KRX price collection failed for {market}: {exc}")

    with SessionLocal() as db:
        naver_count = collect_naver_quotes(
            db, date, markets=markets, max_workers=max_workers
        )
    typer.echo(f"Loaded {naver_count} Naver fallback quote rows.")


@app.command("collect-stock-prices")
def collect_stock_prices_command(
    code: str = typer.Option(..., "--code", help="Stock code, e.g. 005930"),
    from_date: str = typer.Option(..., "--from-date", help="YYYYMMDD"),
    to_date: str = typer.Option(..., "--to-date", help="YYYYMMDD"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_stock_prices(db, code, from_date, to_date)
    typer.echo(f"Loaded {count} price rows for {code}.")


@app.command("collect-stock-history-universe")
def collect_stock_history_universe_command(
    from_date: str = typer.Option(
        (datetime.utcnow() - timedelta(days=1200)).strftime("%Y%m%d"),
        "--from-date",
        help="YYYYMMDD; defaults to about 3 years ago",
    ),
    to_date: str = typer.Option(
        datetime.utcnow().strftime("%Y%m%d"),
        "--to-date",
        help="YYYYMMDD",
    ),
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
) -> None:
    init_db()
    market_values = [
        value.strip().upper() for value in markets.split(",") if value.strip()
    ]
    with SessionLocal() as db:
        statement = (
            select(StockMaster.code)
            .where(StockMaster.is_active.is_(True))
            .order_by(StockMaster.market, StockMaster.code)
        )
        if market_values:
            statement = statement.where(StockMaster.market.in_(market_values))
        if limit:
            statement = statement.limit(limit)
        codes = list(db.scalars(statement))
        count = collect_prices_for_codes(
            db,
            codes,
            from_yyyymmdd=from_date,
            to_yyyymmdd=to_date,
            max_workers=max_workers,
            prefer_fdr=True,
        )
    typer.echo(f"Loaded {count} daily price rows for {len(codes)} active stocks.")


@app.command("collect-investor-flows")
def collect_investor_flows_command(
    date: str = typer.Option(..., "--date", help="YYYYMMDD"),
    market: str = typer.Option("KOSPI", "--market", help="KOSPI, KOSDAQ, or KONEX"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_investor_flows(db, date, market)
    typer.echo(f"Loaded {count} investor flow rows.")


@app.command("collect-naver-investor-flows")
def collect_naver_investor_flows_command(
    markets: str = typer.Option(
        "KOSPI,KOSDAQ", "--markets", help="Comma-separated markets"
    ),
    pages: int = typer.Option(
        1, "--pages", help="Naver investor-flow pages per code; 20 rows per page"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional code limit"),
    max_workers: int = typer.Option(8, "--max-workers", help="Concurrent workers"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_naver_investor_flows(
            db,
            markets=markets,
            pages=pages,
            limit=limit,
            max_workers=max_workers,
        )
    typer.echo(f"Loaded {count} Naver investor flow rows.")


@app.command("collect-dart-financials")
def collect_dart_financials_command(
    corp_code: str = typer.Option(..., "--corp-code", help="DART corp code"),
    year: str = typer.Option(..., "--year", help="Business year, e.g. 2025"),
    report: str = typer.Option(
        "annual", "--report", help="annual, q1, half, q3, or DART report code"
    ),
    fs_div: str = typer.Option("CFS", "--fs-div", help="CFS or OFS"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_financial_statement(db, corp_code, year, report, fs_div)
    typer.echo(f"Loaded {count} DART financial rows.")


@app.command("collect-dart-financials-bulk")
def collect_dart_financials_bulk_command(
    year: Optional[str] = typer.Option(
        None, "--year", help="Business year. Defaults to latest available report year."
    ),
    report: Optional[str] = typer.Option(
        None, "--report", help="annual, q1, half, q3, or DART report code"
    ),
    fs_div: str = typer.Option("CFS", "--fs-div", help="CFS or OFS"),
    stock_codes: Optional[str] = typer.Option(
        None, "--stock-codes", help="Optional comma-separated stock codes"
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Optional company limit"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--no-skip-existing",
        help="Skip companies already loaded for target report",
    ),
    fallback_previous_annual: bool = typer.Option(
        True,
        "--fallback-annual/--no-fallback-annual",
        help="Fallback to previous annual report when latest report is unavailable",
    ),
) -> None:
    init_db()
    code_list = (
        [code.strip() for code in stock_codes.split(",") if code.strip()]
        if stock_codes
        else None
    )
    with SessionLocal() as db:
        result = collect_financial_statements_for_disclosure_companies(
            db,
            bsns_year=year,
            report=report,
            fs_div=fs_div,
            stock_codes=code_list,
            limit=limit,
            skip_existing=skip_existing,
            fallback_previous_annual=fallback_previous_annual,
        )
    typer.echo(
        f"Loaded {result['rows_loaded']} DART financial rows. {result['message']}"
    )


@app.command("collect-ecos")
def collect_ecos_command(
    series_code: str = typer.Option(..., "--series-code", help="ECOS statistic code"),
    cycle: str = typer.Option(..., "--cycle", help="D, M, Q, A, etc."),
    start_period: str = typer.Option(..., "--start", help="Start period"),
    end_period: str = typer.Option(..., "--end", help="End period"),
    item_code: str = typer.Option("?", "--item-code", help="ECOS item code"),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_ecos_series(
            db, series_code, cycle, start_period, end_period, item_code
        )
    typer.echo(f"Loaded {count} ECOS rows.")


@app.command("collect-yahoo-macro")
def collect_yahoo_macro_command(
    range_: str = typer.Option(
        "1y", "--range", help="Yahoo chart range, e.g. 1mo, 6mo, 1y"
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        count = collect_yahoo_macro_observations(db, range_=range_)
    typer.echo(f"Loaded {count} Yahoo macro rows.")


@app.command("collect-home-briefing")
def collect_home_briefing_command() -> None:
    init_db()
    with SessionLocal() as db:
        snapshot = collect_home_briefing(db)
        snapshot_id = snapshot.id
        snapshot_as_of = snapshot.as_of
    typer.echo(f"Created home briefing snapshot #{snapshot_id} at {snapshot_as_of}.")


@app.command("bootstrap-runtime")
def bootstrap_runtime_command(
    force_refresh: bool = typer.Option(
        False, "--force-refresh", help="Force refresh even when cached rows exist."
    ),
) -> None:
    result = bootstrap_runtime_data(get_settings(), force_refresh=force_refresh)
    typer.echo(
        "Bootstrap complete. "
        f"stocks={result['counts_after']['stocks']} "
        f"briefings={result['counts_after']['briefings']} "
        f"reports={result['counts_after']['reports']} "
        f"disclosures={result['counts_after']['disclosures']} "
        f"news={result['counts_after']['news']} "
        f"runtime_refreshed={result['refreshed_runtime']}"
    )


@app.command("verify-mcp-endpoint")
def verify_mcp_endpoint_command(
    url: str = typer.Option(
        ...,
        "--url",
        help="Public MCP endpoint URL, e.g. https://your-domain/ or https://your-domain/mcp/",
    ),
    query: str = typer.Option(
        "삼성전자", "--query", help="Stock search smoke-test query"
    ),
    timeout: int = typer.Option(30, "--timeout", help="HTTP timeout in seconds"),
    limit: int = typer.Option(3, "--limit", help="Preview result count"),
) -> None:
    try:
        payload = verify_mcp_endpoint_payload(
            url, query=query, timeout=timeout, limit=limit
        )
    except Exception as exc:
        typer.echo(f"MCP endpoint verification failed: {exc}")
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("collect-research-reports")
def collect_research_reports_command(
    categories: str = typer.Option(
        "company,industry,market,economy,invest,debenture",
        "--categories",
        help="Comma-separated categories",
    ),
    max_pages: int = typer.Option(2, "--max-pages", help="Pages per category"),
    days_back: int = typer.Option(3, "--days-back", help="Only keep recent N days"),
    include_detail: bool = typer.Option(
        True, "--include-detail/--no-include-detail", help="Fetch company detail page"
    ),
) -> None:
    init_db()
    category_list = [
        category.strip() for category in categories.split(",") if category.strip()
    ]
    with SessionLocal() as db:
        count = collect_research_reports(
            db,
            categories=category_list,
            max_pages=max_pages,
            days_back=days_back,
            include_detail=include_detail,
        )
    typer.echo(f"Loaded {count} research report rows.")


@app.command("collect-disclosures")
def collect_disclosures_command(
    days_back: int = typer.Option(7, "--days-back", help="Only keep recent N days"),
    page_count: int = typer.Option(
        100, "--page-count", help="Rows requested per DART page"
    ),
) -> None:
    init_db()
    with SessionLocal() as db:
        result = collect_disclosures(db, days_back=days_back, page_count=page_count)
    typer.echo(f"Loaded {result.rows_loaded} disclosure rows.")


@app.command("collect-news-items")
def collect_news_items_command(
    categories: str = typer.Option(
        "breaking,market,company,global,bond,disclosure_memo,fx",
        "--categories",
        help="Comma-separated categories",
    ),
    max_pages: int = typer.Option(2, "--max-pages", help="Pages per category"),
    days_back: int = typer.Option(3, "--days-back", help="Only keep recent N days"),
) -> None:
    init_db()
    category_list = [
        category.strip() for category in categories.split(",") if category.strip()
    ]
    with SessionLocal() as db:
        count = collect_news_items(
            db,
            categories=category_list,
            max_pages=max_pages,
            days_back=days_back,
        )
    typer.echo(f"Loaded {count} news rows.")


if __name__ == "__main__":
    app()
