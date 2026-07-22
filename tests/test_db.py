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


def test_deduplicate_upsert_rows_keeps_last_value_for_same_conflict_key() -> None:
    rows = [
        {"source": "dart_api", "external_id": "202607220001", "report_name": "이전 제목"},
        {"source": "dart_api", "external_id": "202607220001", "report_name": "최신 제목"},
    ]

    deduped = _deduplicate_upsert_rows(DisclosureItem, rows)

    assert deduped == [
        {"source": "dart_api", "external_id": "202607220001", "report_name": "최신 제목"}
    ]
