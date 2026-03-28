"""System configuration, audit log, health, and export API routes."""

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import check_db_connection, get_db
from app.models import AuditLogEntry, Group, Policy, PolicyAssignment, PolicyVersion, SystemConfig
from app.schemas import (
    AuditLogResponse,
    PaginatedResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
)
from app.services.admin_auth import generate_api_key, list_api_keys, require_admin, revoke_api_key
from app.services.audit_service import log_admin

router = APIRouter(
    prefix="/admin/api",
    tags=["system"],
    dependencies=[Depends(require_admin)],
)


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
    request: Request,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    ).scalar_one_or_none()

    old_value = row.value if row else None
    now = datetime.now(timezone.utc)
    if row:
        row.value = body.value
        row.updated_at = now
    else:
        row = SystemConfig(key=key, value=body.value, updated_at=now)
        db.add(row)

    log_admin(
        db, "config_change",
        details={"setting": key, "old_value": old_value, "new_value": body.value},
        source_ip=request.client.host if request.client else "",
    )

    await db.flush()
    await db.refresh(row)
    return row


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


def _build_audit_query(
    category: str | None,
    event_type: str | None,
    user_id: uuid.UUID | None,
    sandbox_id: uuid.UUID | None,
    since: datetime | None,
    until: datetime | None,
):
    """Build a filtered audit log query (shared between list and export)."""
    query = select(AuditLogEntry)

    if category:
        query = query.where(AuditLogEntry.category == category)
    if event_type:
        query = query.where(AuditLogEntry.event_type == event_type)
    if user_id:
        query = query.where(AuditLogEntry.user_id == user_id)
    if sandbox_id:
        query = query.where(AuditLogEntry.sandbox_id == sandbox_id)
    if since:
        query = query.where(AuditLogEntry.timestamp >= since)
    if until:
        query = query.where(AuditLogEntry.timestamp <= until)

    return query


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
    base = _build_audit_query(category, event_type, user_id, sandbox_id, since, until)
    count_query = select(func.count(AuditLogEntry.id))

    # Apply same filters to count query
    if category:
        count_query = count_query.where(AuditLogEntry.category == category)
    if event_type:
        count_query = count_query.where(AuditLogEntry.event_type == event_type)
    if user_id:
        count_query = count_query.where(AuditLogEntry.user_id == user_id)
    if sandbox_id:
        count_query = count_query.where(AuditLogEntry.sandbox_id == sandbox_id)
    if since:
        count_query = count_query.where(AuditLogEntry.timestamp >= since)
    if until:
        count_query = count_query.where(AuditLogEntry.timestamp <= until)

    query = base.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(items=rows, total=total, offset=offset, limit=limit)


# ---------------------------------------------------------------------------
# Audit Export
# ---------------------------------------------------------------------------

_EXPORT_LIMIT = 10_000


@router.get("/audit/export")
async def export_audit_log(
    format: str = Query("json", description="Export format: csv, json, or jsonl"),
    category: str | None = Query(None),
    event_type: str | None = Query(None),
    user_id: uuid.UUID | None = Query(None),
    sandbox_id: uuid.UUID | None = Query(None),
    since: datetime | None = Query(None, description="ISO 8601 timestamp"),
    until: datetime | None = Query(None, description="ISO 8601 timestamp"),
    db: AsyncSession = Depends(get_db),
):
    query = _build_audit_query(category, event_type, user_id, sandbox_id, since, until)
    query = query.order_by(AuditLogEntry.timestamp.desc()).limit(_EXPORT_LIMIT)

    rows = (await db.execute(query)).scalars().all()

    if format == "csv":
        return _export_csv(rows)
    if format == "jsonl":
        return _export_jsonl(rows)
    return _export_json(rows)


def _row_to_dict(entry: AuditLogEntry) -> dict:
    return {
        "id": str(entry.id),
        "timestamp": entry.timestamp.isoformat(),
        "event_type": entry.event_type,
        "category": entry.category,
        "user_id": str(entry.user_id) if entry.user_id else None,
        "sandbox_id": str(entry.sandbox_id) if entry.sandbox_id else None,
        "details": entry.details,
        "source_ip": entry.source_ip,
    }


def _export_json(rows: list[AuditLogEntry]) -> StreamingResponse:
    data = json.dumps([_row_to_dict(r) for r in rows], indent=2)
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log.json"},
    )


def _export_jsonl(rows: list[AuditLogEntry]) -> StreamingResponse:
    lines = "\n".join(json.dumps(_row_to_dict(r)) for r in rows)
    return StreamingResponse(
        iter([lines]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit_log.jsonl"},
    )


def _export_csv(rows: list[AuditLogEntry]) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["timestamp", "event_type", "category", "user_id", "sandbox_id", "details", "source_ip"])
    for entry in rows:
        writer.writerow([
            entry.timestamp.isoformat(),
            entry.event_type,
            entry.category,
            str(entry.user_id) if entry.user_id else "",
            str(entry.sandbox_id) if entry.sandbox_id else "",
            json.dumps(entry.details),
            entry.source_ip,
        ])

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
    )


# ---------------------------------------------------------------------------
# Metrics (placeholder)
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics():
    """Placeholder — Prometheus-format metrics to be implemented."""
    return {"status": "pending", "message": "Prometheus metrics export not yet implemented"}


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


@router.post("/backup")
async def trigger_backup(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Export all policies, policy versions, assignments, groups, and config as a single JSON archive."""
    policies = (await db.execute(select(Policy))).scalars().all()
    versions = (await db.execute(select(PolicyVersion).order_by(PolicyVersion.created_at))).scalars().all()
    assignments = (await db.execute(select(PolicyAssignment))).scalars().all()
    groups = (await db.execute(select(Group))).scalars().all()
    config_rows = (await db.execute(select(SystemConfig))).scalars().all()

    backup = {
        "meta": {
            "version": "0.1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "shellguard-backup",
        },
        "policies": [
            {
                "id": str(p.id),
                "name": p.name,
                "tier": p.tier,
                "description": p.description,
                "current_version": p.current_version,
                "yaml": p.yaml,
                "created_at": p.created_at.isoformat(),
                "updated_at": p.updated_at.isoformat(),
            }
            for p in policies
        ],
        "policy_versions": [
            {
                "id": str(v.id),
                "policy_id": str(v.policy_id),
                "version": v.version,
                "yaml": v.yaml,
                "changelog": v.changelog,
                "created_by": str(v.created_by) if v.created_by else None,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
        "policy_assignments": [
            {
                "id": str(a.id),
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "policy_id": str(a.policy_id),
                "priority": a.priority,
                "created_by": str(a.created_by) if a.created_by else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in assignments
        ],
        "groups": [
            {
                "id": str(g.id),
                "name": g.name,
                "description": g.description,
                "policy_id": str(g.policy_id) if g.policy_id else None,
                "created_at": g.created_at.isoformat(),
                "updated_at": g.updated_at.isoformat(),
            }
            for g in groups
        ],
        "system_config": [
            {
                "key": c.key,
                "value": c.value,
                "updated_at": c.updated_at.isoformat(),
            }
            for c in config_rows
        ],
    }

    log_admin(
        db, "backup_created",
        details={
            "policies": len(policies),
            "policy_versions": len(versions),
            "policy_assignments": len(assignments),
            "groups": len(groups),
            "config_entries": len(config_rows),
        },
        source_ip=request.client.host if request.client else "",
    )
    await db.commit()

    data = json.dumps(backup, indent=2)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return StreamingResponse(
        iter([data]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=shellguard-backup-{ts}.json"},
    )


# ---------------------------------------------------------------------------
# API Key Management
# ---------------------------------------------------------------------------


@router.post("/auth/keys")
async def create_api_key(
    request: Request,
    label: str = Query("", description="Human-readable label for the key"),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new admin API key.  The raw key is returned only once."""
    result = await generate_api_key(db, label=label)
    log_admin(
        db, "api_key_created",
        details={"key_id": result["id"], "label": label},
        source_ip=request.client.host if request.client else "",
    )
    await db.commit()
    return result


@router.get("/auth/keys")
async def get_api_keys(db: AsyncSession = Depends(get_db)):
    """List all API keys (hashes are not returned)."""
    return await list_api_keys(db)


@router.delete("/auth/keys/{key_id}")
async def delete_api_key(
    key_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key by its ID."""
    removed = await revoke_api_key(db, key_id)
    if not removed:
        raise HTTPException(status_code=404, detail="API key not found")
    log_admin(
        db, "api_key_revoked",
        details={"key_id": key_id},
        source_ip=request.client.host if request.client else "",
    )
    await db.commit()
    return {"status": "revoked", "key_id": key_id}
