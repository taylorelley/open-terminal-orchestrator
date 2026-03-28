"""Shared audit logging service and retention manager.

Provides convenience functions for writing audit log entries across
all three categories (lifecycle, enforcement, admin) and a background
task that enforces the configurable retention policy.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import AuditLogEntry, Sandbox, SystemConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audit log helpers
# ---------------------------------------------------------------------------


def log_lifecycle(
    db: AsyncSession,
    event_type: str,
    *,
    sandbox: Sandbox | None = None,
    user_id: uuid.UUID | None = None,
    sandbox_id: uuid.UUID | None = None,
    details: dict | None = None,
    source_ip: str = "",
) -> AuditLogEntry:
    """Create a lifecycle audit entry and add it to the session.

    If a ``Sandbox`` object is provided, ``user_id`` and ``sandbox_id``
    are extracted from it automatically.
    """
    from app.metrics import record_audit_event

    entry = AuditLogEntry(
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        category="lifecycle",
        user_id=sandbox.user_id if sandbox else user_id,
        sandbox_id=sandbox.id if sandbox else sandbox_id,
        details=details or {},
        source_ip=source_ip,
    )
    db.add(entry)
    record_audit_event("lifecycle", event_type)
    return entry


def log_enforcement(
    db: AsyncSession,
    event_type: str,
    *,
    user_id: uuid.UUID | None = None,
    sandbox_id: uuid.UUID | None = None,
    details: dict | None = None,
    source_ip: str = "",
) -> AuditLogEntry:
    """Create an enforcement audit entry and add it to the session."""
    from app.metrics import record_audit_event

    entry = AuditLogEntry(
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        category="enforcement",
        user_id=user_id,
        sandbox_id=sandbox_id,
        details=details or {},
        source_ip=source_ip,
    )
    db.add(entry)
    record_audit_event("enforcement", event_type)
    return entry


def log_admin(
    db: AsyncSession,
    event_type: str,
    *,
    details: dict | None = None,
    source_ip: str = "",
) -> AuditLogEntry:
    """Create an admin audit entry and add it to the session."""
    from app.metrics import record_audit_event

    entry = AuditLogEntry(
        id=uuid.uuid4(),
        timestamp=datetime.now(timezone.utc),
        event_type=event_type,
        category="admin",
        details=details or {},
        source_ip=source_ip,
    )
    db.add(entry)
    record_audit_event("admin", event_type)
    return entry


# ---------------------------------------------------------------------------
# Retention manager
# ---------------------------------------------------------------------------


async def _get_retention_days() -> int:
    """Load retention days from system_config or fall back to settings."""
    async with async_session() as db:
        row = (
            await db.execute(
                select(SystemConfig).where(SystemConfig.key == "audit")
            )
        ).scalar_one_or_none()
        if row and isinstance(row.value, dict):
            return int(row.value.get("retention_days", settings.audit_retention_days))
    return settings.audit_retention_days


async def _purge_old_entries() -> None:
    """Delete audit log entries older than the configured retention period."""
    retention_days = await _get_retention_days()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    async with async_session() as db:
        try:
            count_result = await db.execute(
                select(func.count(AuditLogEntry.id)).where(
                    AuditLogEntry.timestamp < cutoff
                )
            )
            count = count_result.scalar_one()

            if count > 0:
                await db.execute(
                    delete(AuditLogEntry).where(AuditLogEntry.timestamp < cutoff)
                )
                await db.commit()
                logger.info(
                    "Audit retention: purged %d entries older than %d days",
                    count,
                    retention_days,
                )
            else:
                logger.debug("Audit retention: no entries to purge")
        except Exception:
            await db.rollback()
            logger.exception("Audit retention purge failed")


class AuditRetentionManager:
    """Background task that periodically purges old audit log entries."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="audit-retention")
        logger.info(
            "Audit retention manager started (interval=%ds, default_retention=%dd)",
            settings.audit_retention_interval,
            settings.audit_retention_days,
        )

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Audit retention manager stopped")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await _purge_old_entries()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=settings.audit_retention_interval,
                )
            except asyncio.TimeoutError:
                pass


# Module-level singleton — started/stopped via the FastAPI lifespan.
audit_retention_manager = AuditRetentionManager()
