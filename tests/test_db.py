from app.db import _normalize_database_url


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
