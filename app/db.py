from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.replace("sqlite:///", "", 1)
    if raw_path == ":memory:":
        return
    Path(raw_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


settings = get_settings()
database_url = _normalize_database_url(settings.database_url)
_ensure_sqlite_parent(database_url)

engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False, "timeout": 30}
    if database_url.startswith("sqlite")
    else {},
    pool_size=10,
    max_overflow=20,
    pool_timeout=10,
    pool_pre_ping=True,
)


if database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        bigint_columns = {
            "daily_price": ("volume", "trading_value", "market_cap", "listed_shares"),
            "investor_flow": ("buy_volume", "sell_volume", "net_buy_volume", "buy_value", "sell_value", "net_buy_value"),
            "briefing_quote": ("volume", "trading_value"),
            "briefing_mover": ("volume", "trading_value"),
        }
        with engine.begin() as connection:
            for table_name, column_names in bigint_columns.items():
                for column_name in column_names:
                    connection.execute(
                        text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE BIGINT')
                    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
