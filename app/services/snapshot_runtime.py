from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import socket
from typing import Any, Callable, Iterable, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.services.complete_snapshots import (
    PayloadValidator,
    claim,
    mark_failed,
    publish,
)


logger = logging.getLogger(__name__)
SnapshotBuilder = Callable[[Session, str], Any]


@dataclass(frozen=True)
class SnapshotBuild:
    payload: Any
    fresh_for_seconds: Optional[int] = None
    schema_version: Optional[int] = None
    captured_at: Optional[datetime] = None
    validator: Optional[PayloadValidator] = None


@dataclass(frozen=True)
class SnapshotHandler:
    key_prefix: str
    builder: SnapshotBuilder
    fresh_for_seconds: int
    schema_version: int = 1
    validator: Optional[PayloadValidator] = None
    lane: str = "default"

    def matches(self, snapshot_key: str) -> bool:
        return snapshot_key == self.key_prefix or snapshot_key.startswith(self.key_prefix)


class SnapshotRuntime:
    """Generic worker for DB-queued complete snapshot refreshes.

    The runtime has no dependency on the FastAPI application. A web process can
    enqueue work through ``complete_snapshots.request_refresh`` while one or more
    worker processes safely compete for the same DB leases.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        handlers: Iterable[SnapshotHandler],
        *,
        lease_owner: Optional[str] = None,
        lease_seconds: int = 300,
        poll_seconds: float = 1.0,
        failure_retry_seconds: int = 30,
    ) -> None:
        self.session_factory = session_factory
        self.handlers = tuple(
            sorted(handlers, key=lambda handler: len(handler.key_prefix), reverse=True)
        )
        self.lease_owner = lease_owner or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"
        )
        self.lease_seconds = max(1, int(lease_seconds))
        self.poll_seconds = max(0.05, float(poll_seconds))
        self.failure_retry_seconds = max(0, int(failure_retry_seconds))
        self._tasks: dict[str, asyncio.Task] = {}
        self._stop_event: Optional[asyncio.Event] = None
        self._wake_events: dict[str, asyncio.Event] = {}

    def _handler_for(self, snapshot_key: str) -> Optional[SnapshotHandler]:
        return next(
            (handler for handler in self.handlers if handler.matches(snapshot_key)),
            None,
        )

    def _handlers_for_lane(self, lane: Optional[str]) -> tuple[SnapshotHandler, ...]:
        if lane is None:
            return self.handlers
        return tuple(handler for handler in self.handlers if handler.lane == lane)

    def _owner_for_lane(self, lane: Optional[str]) -> str:
        if lane is None:
            return self.lease_owner
        suffix = f":{lane}"
        return f"{self.lease_owner[: max(1, 160 - len(suffix))]}{suffix}"

    def run_once(self, lane: Optional[str] = None) -> bool:
        """Process at most one due key; return whether a key was claimed."""

        handlers = self._handlers_for_lane(lane)
        if not handlers:
            return False
        lease_owner = self._owner_for_lane(lane)
        with self.session_factory() as db:
            snapshot_claim = claim(
                db,
                lease_owner,
                lease_seconds=self.lease_seconds,
                key_prefixes=(handler.key_prefix for handler in handlers)
                if lane is not None
                else None,
            )
            if snapshot_claim is None:
                return False
            handler = next(
                (
                    candidate
                    for candidate in handlers
                    if candidate.matches(snapshot_claim.snapshot_key)
                ),
                None,
            )
            try:
                if handler is None:
                    raise LookupError(
                        f"No snapshot handler registered for {snapshot_claim.snapshot_key}"
                    )
                built = handler.builder(db, snapshot_claim.snapshot_key)
                if isinstance(built, SnapshotBuild):
                    payload = built.payload
                    fresh_for_seconds = (
                        handler.fresh_for_seconds
                        if built.fresh_for_seconds is None
                        else built.fresh_for_seconds
                    )
                    schema_version = (
                        handler.schema_version
                        if built.schema_version is None
                        else built.schema_version
                    )
                    captured_at = built.captured_at
                    validator = built.validator or handler.validator
                else:
                    payload = built
                    fresh_for_seconds = handler.fresh_for_seconds
                    schema_version = handler.schema_version
                    captured_at = None
                    validator = handler.validator
                publish(
                    db,
                    snapshot_claim.snapshot_key,
                    payload,
                    fresh_for_seconds=fresh_for_seconds,
                    schema_version=schema_version,
                    captured_at=captured_at,
                    validator=validator,
                    lease_owner=lease_owner,
                )
            except Exception as exc:
                db.rollback()
                preserved = mark_failed(
                    db,
                    snapshot_claim.snapshot_key,
                    lease_owner,
                    exc,
                    retry_after_seconds=self.failure_retry_seconds,
                )
                if preserved:
                    logger.warning(
                        "Snapshot refresh failed key=%s: %s",
                        snapshot_claim.snapshot_key,
                        exc,
                    )
                else:
                    logger.warning(
                        "Snapshot refresh lost lease key=%s: %s",
                        snapshot_claim.snapshot_key,
                        exc,
                    )
            return True

    async def start(self) -> None:
        if any(not task.done() for task in self._tasks.values()):
            return
        self._stop_event = asyncio.Event()
        lanes = tuple(dict.fromkeys(handler.lane for handler in self.handlers))
        self._wake_events = {lane: asyncio.Event() for lane in lanes}
        self._tasks = {
            lane: asyncio.create_task(self._run_loop(lane))
            for lane in lanes
        }

    async def stop(self) -> None:
        if not self._tasks:
            return
        if self._stop_event is not None:
            self._stop_event.set()
        for wake_event in self._wake_events.values():
            wake_event.set()
        await asyncio.gather(*self._tasks.values())
        self._tasks = {}
        self._stop_event = None
        self._wake_events = {}

    def wake(self) -> None:
        """Wake a sleeping local worker after a request enqueues work."""

        for wake_event in self._wake_events.values():
            wake_event.set()

    async def _run_loop(self, lane: str) -> None:
        wake_event = self._wake_events[lane]
        while self._stop_event is not None and not self._stop_event.is_set():
            try:
                processed = await asyncio.to_thread(self.run_once, lane)
            except Exception:
                logger.exception("Snapshot worker iteration failed")
                processed = False
            if processed:
                continue
            wake_event.clear()
            try:
                await asyncio.wait_for(wake_event.wait(), timeout=self.poll_seconds)
            except asyncio.TimeoutError:
                pass
