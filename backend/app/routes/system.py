"""System configuration, audit log, and health API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import check_db_connection, get_db
from app.models import AuditLogEntry, SystemConfig
from app.schemas import (
    AuditLogResponse,
    PaginatedResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)

router = APIRouter(prefix="/admin/api", tags=["system"])


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@router.get("/health")
async def detailed_health():
    db_ok = await check_db_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "0.1.0",
        "checks": {
            "database": "connected" if db_ok else "disconnected",
        },
    }


# ---------------------------------------------------------------------------
# System Config
# ---------------------------------------------------------------------------


@router.get("/config", response_model=list[SystemConfigResponse])
async def list_config(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(SystemConfig))).scalars().all()
    return rows


@router.put("/config/{key}", response_model=SystemConfigResponse)
async def update_config(
    key: str,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row:
        row.value = body.value
        row.updated_at = now
    else:
        row = SystemConfig(key=key, value=body.value, updated_at=now)
        db.add(row)

    await db.flush()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


@router.get("/audit", response_model=PaginatedResponse[AuditLogResponse])
async def list_audit_log(
    category: str | None = Query(None),
    event_type: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    sandbox_id: uuid.UUID | None = Query(None),
    since: datetime | None = Query(None, description="ISO 8601 timestamp"),
    until: datetime | None = Query(None, description="ISO 8601 timestamp"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(AuditLogEntry)
    count_query = select(func.count(AuditLogEntry.id))

    if category:
        query = query.where(AuditLogEntry.category == category)
        count_query = count_query.where(AuditLogEntry.category == category)
    if event_type:
        query = query.where(AuditLogEntry.event_type == event_type)
        count_query = count_query.where(AuditLogEntry.event_type == event_type)
    if user_id:
        query = query.where(AuditLogEntry.user_id == user_id)
        count_query = count_query.where(AuditLogEntry.user_id == user_id)
    if sandbox_id:
        query = query.where(AuditLogEntry.sandbox_id == sandbox_id)
        count_query = count_query.where(AuditLogEntry.sandbox_id == sandbox_id)
    if since:
        query = query.where(AuditLogEntry.timestamp >= since)
        count_query = count_query.where(AuditLogEntry.timestamp >= since)
    if until:
        query = query.where(AuditLogEntry.timestamp <= until)
        count_query = count_query.where(AuditLogEntry.timestamp <= until)

    query = query.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(items=rows, total=total, offset=offset, limit=limit)


# ---------------------------------------------------------------------------
# Metrics (placeholder)
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics():
    """Placeholder — Prometheus-format metrics to be implemented."""
    return {"status": "pending", "message": "Prometheus metrics export not yet implemented"}
