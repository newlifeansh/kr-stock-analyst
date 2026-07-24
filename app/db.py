from __future__ import annotations

from pathlib import Path

from sqlalchemy import BigInteger, String, create_engine, event, inspect, text
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
    inspector = inspect(engine)
    stock_master_columns = {column["name"] for column in inspector.get_columns("stock_master")}
    if "is_active" not in stock_master_columns:
        active_type = "BOOLEAN" if engine.dialect.name == "postgresql" else "INTEGER"
        active_default = "TRUE" if engine.dialect.name == "postgresql" else "1"
        with engine.begin() as connection:
            connection.execute(
                text(
                    f'ALTER TABLE "stock_master" ADD COLUMN "is_active" '
                    f'{active_type} NOT NULL DEFAULT {active_default}'
                )
            )
    push_subscription_columns = {column["name"] for column in inspector.get_columns("push_subscription")}
    if "notification_preferences" not in push_subscription_columns:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE "push_subscription" ADD COLUMN "notification_preferences" TEXT'))
    if engine.dialect.name == "postgresql":
        inspector = inspect(engine)
        bigint_columns = {
            "daily_price": ("volume", "trading_value", "market_cap", "listed_shares"),
            "investor_flow": ("buy_volume", "sell_volume", "net_buy_volume", "buy_value", "sell_value", "net_buy_value"),
            "briefing_quote": ("volume", "trading_value"),
            "briefing_mover": ("volume", "trading_value"),
        }
        with engine.begin() as connection:
            for table_name, column_names in bigint_columns.items():
                columns = {column["name"]: column for column in inspector.get_columns(table_name)}
                for column_name in column_names:
                    column_type = columns.get(column_name, {}).get("type")
                    if isinstance(column_type, BigInteger):
                        continue
                    connection.execute(
                        text(f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" TYPE BIGINT')
                    )
            statement_columns = {
                column["name"]: column for column in inspector.get_columns("financial_statement_line")
            }
            account_id_type = statement_columns.get("account_id", {}).get("type")
            if not (
                isinstance(account_id_type, String)
                and account_id_type.length is not None
                and account_id_type.length >= 255
            ):
                connection.execute(
                    text(
                        'ALTER TABLE "financial_statement_line" '
                        'ALTER COLUMN "account_id" TYPE VARCHAR(255)'
                    )
                )


def recover_interrupted_ingestions() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE ingestion_run "
                "SET status = 'interrupted', finished_at = CURRENT_TIMESTAMP, "
                "message = COALESCE(message, 'Previous process stopped before completion') "
                "WHERE status = 'running'"
            )
        )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
