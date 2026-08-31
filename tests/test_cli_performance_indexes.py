from __future__ import annotations

import json
from collections import defaultdict

import pytest
from sqlalchemy import create_engine, inspect, text
from typer.testing import CliRunner

import app.cli as cli_module
from app.cli import (
    PERFORMANCE_INDEX_DEFINITIONS,
    app,
    ensure_performance_indexes,
    performance_index_statements,
)


def _empty_performance_tables(database_engine) -> None:
    statements = (
        """
        CREATE TABLE investor_flow (
            id INTEGER PRIMARY KEY,
            code VARCHAR(12) NOT NULL,
            trade_date DATE NOT NULL,
            investor_type VARCHAR(40) NOT NULL
        )
        """,
        """
        CREATE TABLE research_report (
            id INTEGER PRIMARY KEY,
            stock_code VARCHAR(12),
            published_at DATETIME
        )
        """,
        """
        CREATE TABLE disclosure_item (
            id INTEGER PRIMARY KEY,
            stock_code VARCHAR(12),
            published_at DATETIME,
            external_id VARCHAR(40) NOT NULL
        )
        """,
        """
        CREATE TABLE market_ranking_snapshot (
            snapshot_id VARCHAR(64) PRIMARY KEY,
            category VARCHAR(40) NOT NULL,
            captured_at DATETIME NOT NULL
        )
        """,
    )
    with database_engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def test_performance_index_statements_use_safe_dialect_specific_ddl():
    postgres = performance_index_statements("postgresql")
    sqlite = performance_index_statements("sqlite")

    assert len(postgres) == len(sqlite) == 4
    assert all("CREATE INDEX CONCURRENTLY" in item for item in postgres)
    assert all("CREATE INDEX" in item for item in sqlite)
    assert all("IF NOT EXISTS" not in item for item in postgres + sqlite)
    assert all("CONCURRENTLY" not in item for item in sqlite)
    assert '"trade_date" DESC' in sqlite[0]
    assert '"published_at" DESC, "external_id" DESC, "id" DESC' in sqlite[2]
    with pytest.raises(ValueError, match="PostgreSQL and SQLite"):
        performance_index_statements("mysql")


def test_sqlite_performance_index_migration_is_idempotent(tmp_path):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'indexes.db'}")
    _empty_performance_tables(database_engine)
    try:
        first = ensure_performance_indexes(database_engine)
        second = ensure_performance_indexes(database_engine)

        assert first["dialect"] == second["dialect"] == "sqlite"
        assert [item["action"] for item in first["actions"]] == ["created"] * 4
        assert [item["action"] for item in second["actions"]] == ["verified"] * 4
        inspector = inspect(database_engine)
        for index_name, table_name, _columns in PERFORMANCE_INDEX_DEFINITIONS:
            reflected = {item["name"] for item in inspector.get_indexes(table_name)}
            assert index_name in reflected
    finally:
        database_engine.dispose()


def test_sqlite_performance_index_migration_repairs_wrong_definition(tmp_path):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'wrong-index.db'}")
    _empty_performance_tables(database_engine)
    first_index_name = PERFORMANCE_INDEX_DEFINITIONS[0][0]
    with database_engine.begin() as connection:
        connection.execute(
            text(
                f'CREATE INDEX "{first_index_name}" ON "research_report" ("stock_code")'
            )
        )
    try:
        payload = ensure_performance_indexes(database_engine)

        first_action = payload["actions"][0]
        assert first_action["action"] == "recreated"
        assert any(
            "expected 'investor_flow'" in error
            for error in first_action["preflight_errors"]
        )
        with database_engine.connect() as connection:
            relation = connection.execute(
                text(
                    "SELECT tbl_name FROM sqlite_master "
                    "WHERE type = 'index' AND name = :index_name"
                ),
                {"index_name": first_index_name},
            ).scalar_one()
            columns = (
                connection.execute(text(f'PRAGMA index_xinfo("{first_index_name}")'))
                .mappings()
                .all()
            )
        assert relation == "investor_flow"
        keys = [item for item in columns if item["key"] == 1]
        assert [(item["name"], item["desc"]) for item in keys] == [
            ("code", 0),
            ("trade_date", 1),
            ("investor_type", 0),
        ]
    finally:
        database_engine.dispose()


def _valid_postgresql_state(index_name, table_name, columns_sql, **overrides):
    column_names, sort_directions = cli_module._expected_index_columns(columns_sql)
    state = {
        "target_schema_name": "public",
        "target_table_name": table_name,
        "index_name": index_name,
        "relation_kind": "i",
        "indexed_table_schema_name": "public",
        "indexed_table_name": table_name,
        "is_valid": True,
        "is_ready": True,
        "is_unique": False,
        "access_method": "btree",
        "is_partial": False,
        "has_expressions": False,
        "key_column_count": len(column_names),
        "total_column_count": len(column_names),
        "column_names": column_names,
        "sort_directions": sort_directions,
    }
    state.update(overrides)
    return state


def _missing_postgresql_state(table_name):
    return {
        "target_schema_name": "public",
        "target_table_name": table_name,
        "index_name": None,
    }


def test_postgresql_performance_index_migration_uses_autocommit(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.execution_options_values = None
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execution_options(self, **values):
            self.execution_options_values = values
            return self

        def execute(self, statement, _parameters=None):
            self.statements.append(str(statement))

    class FakeEngine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

        def __init__(self):
            self.connection = FakeConnection()

        def connect(self):
            return self.connection

        def begin(self):
            raise AssertionError("PostgreSQL concurrent indexes must not use begin()")

    calls = defaultdict(int)
    definitions = {
        index_name: (table_name, columns_sql)
        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS
    }

    def fake_state(_connection, *, index_name, table_name):
        calls[index_name] += 1
        if calls[index_name] == 1:
            return _missing_postgresql_state(table_name)
        expected_table, columns_sql = definitions[index_name]
        return _valid_postgresql_state(index_name, expected_table, columns_sql)

    monkeypatch.setattr(cli_module, "_read_postgresql_index_state", fake_state)
    database_engine = FakeEngine()
    payload = ensure_performance_indexes(database_engine)

    assert payload["dialect"] == "postgresql"
    assert database_engine.connection.execution_options_values == {
        "isolation_level": "AUTOCOMMIT"
    }
    assert len(database_engine.connection.statements) == 4
    assert all(
        "CREATE INDEX CONCURRENTLY" in statement
        for statement in database_engine.connection.statements
    )
    assert all(
        "IF NOT EXISTS" not in statement
        for statement in database_engine.connection.statements
    )
    assert [item["action"] for item in payload["actions"]] == ["created"] * 4


def test_postgresql_performance_index_migration_repairs_invalid_or_wrong_index(
    monkeypatch,
):
    class FakeConnection:
        def __init__(self):
            self.statements = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execution_options(self, **_values):
            return self

        def execute(self, statement, _parameters=None):
            self.statements.append(str(statement))

    class FakeEngine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

        def __init__(self):
            self.connection = FakeConnection()

        def connect(self):
            return self.connection

    calls = defaultdict(int)
    definitions = {
        index_name: (table_name, columns_sql)
        for index_name, table_name, columns_sql in PERFORMANCE_INDEX_DEFINITIONS
    }
    broken_index_name = PERFORMANCE_INDEX_DEFINITIONS[0][0]

    def fake_state(_connection, *, index_name, table_name):
        calls[index_name] += 1
        expected_table, columns_sql = definitions[index_name]
        state = _valid_postgresql_state(
            index_name,
            expected_table,
            columns_sql,
        )
        if index_name == broken_index_name and calls[index_name] == 1:
            state.update(
                {
                    "is_valid": False,
                    "is_ready": False,
                    "column_names": ["investor_type", "trade_date", "code"],
                    "sort_directions": ["ASC", "ASC", "ASC"],
                }
            )
        return state

    monkeypatch.setattr(cli_module, "_read_postgresql_index_state", fake_state)
    database_engine = FakeEngine()

    payload = ensure_performance_indexes(database_engine)

    assert payload["actions"][0]["action"] == "recreated"
    assert "index is not valid" in payload["actions"][0]["preflight_errors"]
    assert database_engine.connection.statements[0].startswith(
        'DROP INDEX CONCURRENTLY IF EXISTS "public".'
    )
    assert database_engine.connection.statements[1].startswith(
        'CREATE INDEX CONCURRENTLY "ix_investor_flow'
    )
    assert all(item["action"] == "verified" for item in payload["actions"][1:])


def test_postgresql_performance_index_migration_fails_explicitly_on_bad_postflight(
    monkeypatch,
):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execution_options(self, **_values):
            return self

        def execute(self, _statement, _parameters=None):
            return None

    class FakeEngine:
        dialect = type("Dialect", (), {"name": "postgresql"})()

        def connect(self):
            return FakeConnection()

    calls = defaultdict(int)

    def fake_state(_connection, *, index_name, table_name):
        calls[index_name] += 1
        return _missing_postgresql_state(table_name)

    monkeypatch.setattr(cli_module, "_read_postgresql_index_state", fake_state)

    with pytest.raises(RuntimeError, match="Postflight verification failed"):
        ensure_performance_indexes(FakeEngine())


def test_postgresql_catalog_preflight_covers_definition_and_validity():
    catalog_sql = cli_module.POSTGRESQL_INDEX_STATE_SQL

    assert "pg_catalog.pg_index" in catalog_sql
    assert "indisvalid" in catalog_sql
    assert "indisready" in catalog_sql
    assert "indkey" in catalog_sql
    assert "indoption" in catalog_sql
    assert "indexed_table.relname" in catalog_sql


def test_migrate_performance_indexes_cli_dry_run_does_not_touch_database(
    tmp_path,
    monkeypatch,
):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'dry-run.db'}")
    monkeypatch.setattr(cli_module, "engine", database_engine)
    try:
        result = CliRunner().invoke(app, ["migrate-performance-indexes", "--dry-run"])

        assert result.exit_code == 0
        payload = json.loads(result.stdout)
        assert payload["dialect"] == "sqlite"
        assert payload["dry_run"] is True
        assert payload["indexes"] == [
            definition[0] for definition in PERFORMANCE_INDEX_DEFINITIONS
        ]
        assert inspect(database_engine).get_table_names() == []
    finally:
        database_engine.dispose()
