import pytest
from sqlalchemy.exc import OperationalError

from app import db as database
from app.db import _normalize_database_url
from app.models import DisclosureItem
from app.repository import _deduplicate_upsert_rows


def test_normalize_database_url_converts_postgres_alias() -> None:
    assert (
        _normalize_database_url("postgres://user:pass@host:5432/dbname")
        == "postgresql+psycopg://user:pass@host:5432/dbname"
    )


def test_normalize_database_url_converts_plain_postgresql_scheme() -> None:
    assert (
        _normalize_database_url("postgresql://user:pass@host:5432/dbname")
        == "postgresql+psycopg://user:pass@host:5432/dbname"
    )


def test_normalize_database_url_keeps_explicit_driver() -> None:
    assert (
        _normalize_database_url("postgresql+psycopg://user:pass@host:5432/dbname")
        == "postgresql+psycopg://user:pass@host:5432/dbname"
    )


def test_startup_waits_for_railway_private_dns_and_then_recovers(monkeypatch) -> None:
    now = [0.0]
    attempts = []
    delays = []

    def initialize() -> None:
        attempts.append(now[0])
        if len(attempts) < 4:
            raise OperationalError(
                "connect", {}, OSError("failed to resolve host 'postgres.railway.internal'")
            )

    def sleep(seconds: float) -> None:
        delays.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(database, "init_db", initialize)
    database.init_db_with_retry(
        max_wait_seconds=300, sleeper=sleep, monotonic=lambda: now[0]
    )

    assert attempts == [0.0, 1.0, 3.0, 7.0]
    assert delays == [1.0, 2.0, 4.0]


def test_startup_does_not_retry_bad_database_credentials(monkeypatch) -> None:
    attempts = []

    def initialize() -> None:
        attempts.append(1)
        raise OperationalError("connect", {}, OSError("password authentication failed"))

    monkeypatch.setattr(database, "init_db", initialize)
    with pytest.raises(OperationalError):
        database.init_db_with_retry(sleeper=lambda _: pytest.fail("unexpected retry"))
    assert attempts == [1]


def test_startup_db_retry_has_a_deadline(monkeypatch) -> None:
    now = [0.0]
    attempts = []
    delays = []

    def initialize() -> None:
        attempts.append(now[0])
        raise OperationalError("connect", {}, OSError("connection refused"))

    def sleep(seconds: float) -> None:
        delays.append(seconds)
        now[0] += seconds

    monkeypatch.setattr(database, "init_db", initialize)
    with pytest.raises(OperationalError):
        database.init_db_with_retry(
            max_wait_seconds=3, sleeper=sleep, monotonic=lambda: now[0]
        )
    assert attempts == [0.0, 1.0, 3.0]
    assert delays == [1.0, 2.0]


def test_deduplicate_upsert_rows_keeps_last_value_for_same_conflict_key() -> None:
    rows = [
        {"source": "dart_api", "external_id": "202607220001", "report_name": "이전 제목"},
        {"source": "dart_api", "external_id": "202607220001", "report_name": "최신 제목"},
    ]

    deduped = _deduplicate_upsert_rows(DisclosureItem, rows)

    assert deduped == [
        {"source": "dart_api", "external_id": "202607220001", "report_name": "최신 제목"}
    ]
