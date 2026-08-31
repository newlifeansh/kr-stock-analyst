from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import CompletePayloadSnapshot


PayloadValidator = Callable[[Any], Any]


class SnapshotLeaseLostError(RuntimeError):
    """Raised when a worker tries to publish after losing its lease."""


class SnapshotPublishConflictError(RuntimeError):
    """Raised when an unleased publisher races an existing complete payload."""

    def __init__(
        self,
        message: str,
        *,
        attempted_snapshot: Optional["CompleteSnapshot"] = None,
    ) -> None:
        super().__init__(message)
        self.attempted_snapshot = attempted_snapshot


@dataclass(frozen=True)
class CompleteSnapshot:
    snapshot_key: str
    payload: Any
    schema_version: int
    captured_at: datetime
    fresh_until: datetime
    is_fresh: bool


@dataclass(frozen=True)
class SnapshotClaim:
    snapshot_key: str
    lease_owner: str
    lease_until: datetime
    schema_version: int
    failure_count: int


def _utc_naive(value: Optional[datetime] = None) -> datetime:
    current = value or datetime.utcnow()
    if current.tzinfo is None:
        return current
    return current.astimezone(timezone.utc).replace(tzinfo=None)


def _snapshot_key(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("snapshot_key must not be empty")
    if len(normalized) > 255:
        raise ValueError("snapshot_key must be at most 255 characters")
    return normalized


def _lease_owner(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("lease_owner must not be empty")
    if len(normalized) > 160:
        raise ValueError("lease_owner must be at most 160 characters")
    return normalized


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def _prepared_payload(
    payload: Any,
    validator: Optional[PayloadValidator],
) -> tuple[str, Any]:
    candidate = deepcopy(payload)
    if validator is not None:
        validated = validator(candidate)
        if validated is not None:
            candidate = validated
    model_dump = getattr(candidate, "model_dump", None)
    if callable(model_dump):
        candidate = model_dump(mode="json")
    serialized = json.dumps(
        candidate,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
        default=_json_default,
    )
    return serialized, json.loads(serialized)


def _dialect_insert(db: Session):
    dialect_name = db.get_bind().dialect.name
    if dialect_name == "postgresql":
        return postgresql_insert(CompletePayloadSnapshot)
    if dialect_name == "sqlite":
        return sqlite_insert(CompletePayloadSnapshot)
    raise RuntimeError(f"Unsupported snapshot database dialect: {dialect_name}")


def get(
    db: Session,
    snapshot_key: str,
    *,
    schema_version: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Optional[CompleteSnapshot]:
    """Return the last complete payload, including stale payloads.

    Staleness is metadata for callers; it never makes the last complete value
    disappear. A corrupt or placeholder row is ignored rather than exposed.
    """

    key = _snapshot_key(snapshot_key)
    row = db.get(CompletePayloadSnapshot, key)
    if row is None or row.payload is None or row.captured_at is None or row.fresh_until is None:
        return None
    if schema_version is not None and row.schema_version != int(schema_version):
        return None
    try:
        payload = json.loads(row.payload)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    current = _utc_naive(now)
    return CompleteSnapshot(
        snapshot_key=row.snapshot_key,
        payload=payload,
        schema_version=row.schema_version,
        captured_at=row.captured_at,
        fresh_until=row.fresh_until,
        is_fresh=row.fresh_until > current,
    )


def publish(
    db: Session,
    snapshot_key: str,
    payload: Any,
    *,
    fresh_for_seconds: int,
    schema_version: int = 1,
    captured_at: Optional[datetime] = None,
    validator: Optional[PayloadValidator] = None,
    lease_owner: Optional[str] = None,
    now: Optional[datetime] = None,
) -> CompleteSnapshot:
    """Atomically replace a snapshot only after validation and JSON encoding.

    A leased publish also checks that the lease is still current. Thus a slow
    worker cannot overwrite the result of a worker that reclaimed an expired
    lease.
    """

    key = _snapshot_key(snapshot_key)
    version = max(1, int(schema_version))
    ttl_seconds = max(0, int(fresh_for_seconds))
    serialized, normalized_payload = _prepared_payload(payload, validator)
    published_at = _utc_naive(now)
    captured = _utc_naive(captured_at or published_at)
    fresh_until = captured + timedelta(seconds=ttl_seconds)
    attempted_snapshot = CompleteSnapshot(
        snapshot_key=key,
        payload=normalized_payload,
        schema_version=version,
        captured_at=captured,
        fresh_until=fresh_until,
        is_fresh=fresh_until > published_at,
    )
    values = {
        "payload": serialized,
        "schema_version": version,
        "captured_at": captured,
        "fresh_until": fresh_until,
        "refresh_requested_at": None,
        "lease_owner": None,
        "lease_until": None,
        "last_error": None,
        "failure_count": 0,
        "updated_at": published_at,
    }

    try:
        if lease_owner is not None:
            owner = _lease_owner(lease_owner)
            result = db.execute(
                update(CompletePayloadSnapshot)
                .where(
                    CompletePayloadSnapshot.snapshot_key == key,
                    CompletePayloadSnapshot.lease_owner == owner,
                    CompletePayloadSnapshot.lease_until.is_not(None),
                    CompletePayloadSnapshot.lease_until > published_at,
                )
                .values(**values)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                db.rollback()
                raise SnapshotLeaseLostError(f"Snapshot lease was lost for {key}")
        else:
            insert_statement = _dialect_insert(db).values(
                snapshot_key=key,
                **values,
            )
            table = CompletePayloadSnapshot.__table__
            result = db.execute(
                insert_statement.on_conflict_do_update(
                    index_elements=[CompletePayloadSnapshot.snapshot_key],
                    set_=values,
                    where=(
                        table.c.payload.is_(None)
                        & or_(
                            table.c.lease_owner.is_(None),
                            table.c.lease_until.is_(None),
                            table.c.lease_until <= published_at,
                        )
                    ),
                )
            )
            if result.rowcount != 1:
                db.rollback()
                raise SnapshotPublishConflictError(
                    f"Snapshot already has a complete payload or active lease for {key}",
                    attempted_snapshot=attempted_snapshot,
                )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return attempted_snapshot


def request_refresh(
    db: Session,
    snapshot_key: str,
    *,
    schema_version: int = 1,
    requested_at: Optional[datetime] = None,
) -> None:
    """Queue a refresh without modifying an existing complete payload.

    Repeated requests preserve the oldest queued time, preventing hot endpoints
    from continually pushing the work to the back of the queue.
    """

    key = _snapshot_key(snapshot_key)
    queued_at = _utc_naive(requested_at)
    insert_statement = _dialect_insert(db).values(
        snapshot_key=key,
        payload=None,
        schema_version=max(1, int(schema_version)),
        captured_at=None,
        fresh_until=None,
        refresh_requested_at=queued_at,
        lease_owner=None,
        lease_until=None,
        last_error=None,
        failure_count=0,
        updated_at=queued_at,
    )
    table = CompletePayloadSnapshot.__table__
    statement = insert_statement.on_conflict_do_update(
        index_elements=[CompletePayloadSnapshot.snapshot_key],
        set_={
            "refresh_requested_at": func.coalesce(
                table.c.refresh_requested_at,
                queued_at,
            ),
            "updated_at": queued_at,
        },
    )
    try:
        db.execute(statement)
        db.commit()
    except Exception:
        db.rollback()
        raise


def claim(
    db: Session,
    lease_owner: str,
    *,
    lease_seconds: int = 300,
    now: Optional[datetime] = None,
    candidate_limit: int = 16,
    key_prefixes: Optional[Iterable[str]] = None,
) -> Optional[SnapshotClaim]:
    """Atomically claim the oldest due refresh across processes."""

    owner = _lease_owner(lease_owner)
    current = _utc_naive(now)
    lease_until = current + timedelta(seconds=max(1, int(lease_seconds)))
    available_lease = or_(
        CompletePayloadSnapshot.lease_owner.is_(None),
        CompletePayloadSnapshot.lease_until.is_(None),
        CompletePayloadSnapshot.lease_until <= current,
    )
    normalized_prefixes = tuple(
        dict.fromkeys(
            str(prefix or "").strip()
            for prefix in (key_prefixes or ())
            if str(prefix or "").strip()
        )
    )
    lane_filter = None
    if normalized_prefixes:
        lane_filter = or_(
            *(
                or_(
                    CompletePayloadSnapshot.snapshot_key == prefix,
                    CompletePayloadSnapshot.snapshot_key.startswith(prefix),
                )
                for prefix in normalized_prefixes
            )
        )
    candidate_statement = select(CompletePayloadSnapshot).where(
        CompletePayloadSnapshot.refresh_requested_at.is_not(None),
        CompletePayloadSnapshot.refresh_requested_at <= current,
        available_lease,
    )
    if lane_filter is not None:
        candidate_statement = candidate_statement.where(lane_filter)
    candidates = list(
        db.scalars(
            candidate_statement
            .order_by(
                CompletePayloadSnapshot.refresh_requested_at,
                CompletePayloadSnapshot.snapshot_key,
            )
            .limit(max(1, int(candidate_limit)))
        )
    )

    for candidate in candidates:
        claim_conditions = [
            CompletePayloadSnapshot.snapshot_key == candidate.snapshot_key,
            CompletePayloadSnapshot.refresh_requested_at.is_not(None),
            CompletePayloadSnapshot.refresh_requested_at <= current,
            or_(
                CompletePayloadSnapshot.lease_owner.is_(None),
                CompletePayloadSnapshot.lease_until.is_(None),
                CompletePayloadSnapshot.lease_until <= current,
            ),
        ]
        if lane_filter is not None:
            claim_conditions.append(lane_filter)
        result = db.execute(
            update(CompletePayloadSnapshot)
            .where(*claim_conditions)
            .values(
                lease_owner=owner,
                lease_until=lease_until,
                updated_at=current,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            db.commit()
            return SnapshotClaim(
                snapshot_key=candidate.snapshot_key,
                lease_owner=owner,
                lease_until=lease_until,
                schema_version=candidate.schema_version,
                failure_count=candidate.failure_count,
            )
        db.commit()
    return None


def mark_failed(
    db: Session,
    snapshot_key: str,
    lease_owner: str,
    error: object,
    *,
    retry_after_seconds: int = 30,
    now: Optional[datetime] = None,
) -> bool:
    """Release a claimed job for retry without touching its complete payload."""

    key = _snapshot_key(snapshot_key)
    owner = _lease_owner(lease_owner)
    failed_at = _utc_naive(now)
    retry_at = failed_at + timedelta(seconds=max(0, int(retry_after_seconds)))
    message = str(error or "snapshot refresh failed").strip() or "snapshot refresh failed"
    result = db.execute(
        update(CompletePayloadSnapshot)
        .where(
            CompletePayloadSnapshot.snapshot_key == key,
            CompletePayloadSnapshot.lease_owner == owner,
        )
        .values(
            refresh_requested_at=retry_at,
            lease_owner=None,
            lease_until=None,
            last_error=message[:4000],
            failure_count=CompletePayloadSnapshot.failure_count + 1,
            updated_at=failed_at,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    db.commit()
    return True
