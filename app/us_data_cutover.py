"""Transfer only canonical US user state between independent production DBs.

Exported JSON is sensitive. Pipe it directly from the domestic Railway SSH
session into the US Railway SSH session; never write it to a log or artifact.
The importer is dry-run by default, rejects conflicting target records, and
commits missing rows in one transaction only with --apply.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
import json
import sys
from typing import Any

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import (
    DesktopUserPreference,
    PushSubscription,
    RecommendationTrackState,
    WatchlistGroupState,
    WatchlistItem,
)


MIGRATION_SCHEMA = "us-user-state-v1"
MIGRATED_MODELS = (
    (WatchlistItem, ("share_id", "code"), (
        "share_id", "code", "name", "market", "investor_state",
        "average_buy_price", "sort_order", "created_at", "updated_at",
    )),
    (WatchlistGroupState, ("share_id",), (
        "share_id", "payload", "created_at", "updated_at",
    )),
    (RecommendationTrackState, ("share_id",), (
        "share_id", "payload", "created_at", "updated_at",
    )),
)
MANUAL_REVIEW_MODELS = (PushSubscription, DesktopUserPreference)
TIME_FIELDS = frozenset({"created_at", "updated_at"})


def _encode(value: Any) -> Any:
    if isinstance(value, (datetime, Decimal)):
        return str(value) if isinstance(value, Decimal) else value.isoformat()
    return value


def _public_row(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    return {column: _encode(getattr(row, column)) for column in columns}


def export_us_rows(session: Any) -> dict[str, Any]:
    tables: dict[str, list[dict[str, Any]]] = {}
    for model, key_fields, columns in MIGRATED_MODELS:
        rows = session.scalars(
            select(model)
            .where(model.share_id.like("us.%"))
            .order_by(*(getattr(model, key) for key in key_fields))
        ).all()
        tables[model.__tablename__] = [_public_row(row, columns) for row in rows]
    manual_counts = {
        model.__tablename__: int(
            session.scalar(
                select(func.count()).select_from(model).where(model.share_id.like("us.%"))
            ) or 0
        )
        for model in MANUAL_REVIEW_MODELS
    }
    return {"schema": MIGRATION_SCHEMA, "tables": tables, "manual_review_counts": manual_counts}


def _row_key(row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in fields)


def _comparable(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in TIME_FIELDS}


def migration_plan(session: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], list[Any]]:
    if payload.get("schema") != MIGRATION_SCHEMA or not isinstance(payload.get("tables"), dict):
        raise ValueError("unsupported US migration schema")
    expected_tables = {model.__tablename__ for model, _, _ in MIGRATED_MODELS}
    if set(payload["tables"]) != expected_tables:
        raise ValueError("US migration table set is incomplete")
    manual_counts = payload.get("manual_review_counts")
    if not isinstance(manual_counts, dict) or any(
        int(manual_counts.get(model.__tablename__, -1)) != 0
        for model in MANUAL_REVIEW_MODELS
    ):
        raise ValueError("US push or desktop preferences require separate review")

    pending: list[Any] = []
    counts: dict[str, dict[str, int]] = {}
    for model, key_fields, columns in MIGRATED_MODELS:
        table = model.__tablename__
        source_rows = payload["tables"][table]
        if not isinstance(source_rows, list) or len(source_rows) > 100_000:
            raise ValueError("US migration row count is invalid")
        existing = {
            _row_key(_public_row(row, columns), key_fields): _public_row(row, columns)
            for row in session.scalars(
                select(model).where(model.share_id.like("us.%"))
            ).all()
        }
        seen: set[tuple[str, ...]] = set()
        counts[table] = {"source": len(source_rows), "already_present": 0, "insert": 0, "conflict": 0}
        for row in source_rows:
            if (
                not isinstance(row, dict)
                or set(row) != set(columns)
                or not str(row.get("share_id") or "").startswith("us.")
            ):
                raise ValueError("US migration contains a malformed row")
            key = _row_key(row, key_fields)
            if not all(key) or key in seen:
                raise ValueError("US migration contains a duplicate or empty key")
            seen.add(key)
            destination = existing.get(key)
            if destination is not None:
                field = "already_present" if _comparable(destination) == _comparable(row) else "conflict"
                counts[table][field] += 1
                continue
            prepared = dict(row)
            for field in TIME_FIELDS:
                prepared[field] = datetime.fromisoformat(str(prepared[field]))
            if model is WatchlistItem and prepared["average_buy_price"] is not None:
                prepared["average_buy_price"] = Decimal(str(prepared["average_buy_price"]))
            pending.append(model(**prepared))
            counts[table]["insert"] += 1
    return {"schema": MIGRATION_SCHEMA, "tables": counts, "conflicts": sum(
        row["conflict"] for row in counts.values()
    )}, pending


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.action == "export" and args.apply:
        parser.error("--apply is only valid with import")

    try:
        with SessionLocal() as session:
            if args.action == "export":
                if sys.stdout.isatty():
                    raise ValueError("sensitive US state must be piped, not printed to a terminal")
                json.dump(export_us_rows(session), sys.stdout, ensure_ascii=False, separators=(",", ":"))
                sys.stdout.write("\n")
                return 0
            payload = json.load(sys.stdin)
            report, pending = migration_plan(session, payload)
            if report["conflicts"]:
                print(json.dumps({**report, "applied": False}, ensure_ascii=False))
                return 2
            if args.apply:
                session.add_all(pending)
                session.commit()
            print(json.dumps({**report, "applied": args.apply}, ensure_ascii=False))
            return 0
    except Exception:
        # SQLAlchemy errors may contain bind parameters and private user data.
        # Never print their exception text or a traceback in an operations log.
        print("US user-state migration could not be verified; no payload logged.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
