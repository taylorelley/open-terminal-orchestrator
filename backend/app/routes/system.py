"""System configuration, audit log, health, and export API routes."""

import csv
import io
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import check_db_connection, get_db
from app.models import AuditLogEntry, Group, Policy, PolicyAssignment, PolicyVersion, SystemConfig
from app.schemas import (
    AlertRule,
    AlertsConfigResponse,
    AlertsConfigUpdate,
    AuditLogResponse,
    PaginatedResponse,
    SystemConfigResponse,
    SystemConfigUpdate,
    WebhookConfigCreate,
    WebhookConfigResponse,
    WebhookConfigUpdate,
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
# Webhooks
# ---------------------------------------------------------------------------


async def _load_webhook_list(db: AsyncSession) -> tuple[SystemConfig | None, list[dict]]:
    """Load the webhooks config row and return the raw list."""
    row = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.key == "webhooks").with_for_update()
        )
    ).scalar_one_or_none()
    if row and isinstance(row.value, dict):
        return row, row.value.get("webhooks", [])
    return row, []


@router.get("/webhooks", response_model=list[WebhookConfigResponse])
async def list_webhooks(db: AsyncSession = Depends(get_db)):
    """List all configured webhooks."""
    _, wh_list = await _load_webhook_list(db)
    return [
        WebhookConfigResponse(index=i, url=w.get("url", ""), enabled=w.get("enabled", True), event_filters=w.get("event_filters", []))
        for i, w in enumerate(wh_list)
    ]


@router.post("/webhooks", response_model=WebhookConfigResponse, status_code=201)
async def create_webhook(
    body: WebhookConfigCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Add a new webhook configuration."""
    from app.services.webhook_service import invalidate_cache

    row, wh_list = await _load_webhook_list(db)
    new_entry = body.model_dump()
    wh_list.append(new_entry)
    now = datetime.now(timezone.utc)

    if row:
        row.value = {"webhooks": wh_list}
        row.updated_at = now
    else:
        row = SystemConfig(key="webhooks", value={"webhooks": wh_list}, updated_at=now)
        db.add(row)

    log_admin(
        db, "webhook_created",
        details={"url": body.url, "index": len(wh_list) - 1},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    invalidate_cache()
    return WebhookConfigResponse(
        index=len(wh_list) - 1,
        url=body.url,
        enabled=body.enabled,
        event_filters=[f.model_dump() for f in body.event_filters],
    )


@router.put("/webhooks/{index}", response_model=WebhookConfigResponse)
async def update_webhook(
    index: int,
    body: WebhookConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update a webhook configuration by index."""
    from app.services.webhook_service import invalidate_cache

    row, wh_list = await _load_webhook_list(db)
    if index < 0 or index >= len(wh_list):
        raise HTTPException(status_code=404, detail="Webhook index out of range")

    existing = wh_list[index]
    updates = body.model_dump(exclude_unset=True)
    if "event_filters" in updates and updates["event_filters"] is not None:
        updates["event_filters"] = [f.model_dump() if hasattr(f, "model_dump") else f for f in updates["event_filters"]]
    existing.update(updates)
    wh_list[index] = existing

    row.value = {"webhooks": wh_list}
    row.updated_at = datetime.now(timezone.utc)

    log_admin(
        db, "webhook_updated",
        details={"index": index, "url": existing.get("url")},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    invalidate_cache()
    return WebhookConfigResponse(
        index=index,
        url=existing.get("url", ""),
        enabled=existing.get("enabled", True),
        event_filters=existing.get("event_filters", []),
    )


@router.delete("/webhooks/{index}")
async def delete_webhook(
    index: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Remove a webhook configuration by index."""
    from app.services.webhook_service import invalidate_cache

    row, wh_list = await _load_webhook_list(db)
    if index < 0 or index >= len(wh_list):
        raise HTTPException(status_code=404, detail="Webhook index out of range")

    removed = wh_list.pop(index)
    row.value = {"webhooks": wh_list}
    row.updated_at = datetime.now(timezone.utc)

    log_admin(
        db, "webhook_deleted",
        details={"index": index, "url": removed.get("url")},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    invalidate_cache()
    return {"status": "deleted", "index": index}


@router.post("/webhooks/{index}/test")
async def test_webhook(
    index: int,
    db: AsyncSession = Depends(get_db),
):
    """Send a test event to a specific webhook."""
    from app.services.webhook_service import WebhookConfig, _deliver

    _, wh_list = await _load_webhook_list(db)
    if index < 0 or index >= len(wh_list):
        raise HTTPException(status_code=404, detail="Webhook index out of range")

    wh = WebhookConfig(**wh_list[index])
    payload = {
        "event_type": "test",
        "category": "admin",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": {"message": "This is a test webhook from ShellGuard"},
    }
    await _deliver(wh, payload)
    return {"status": "sent", "url": wh.url}


# ---------------------------------------------------------------------------
# Syslog
# ---------------------------------------------------------------------------


@router.post("/syslog/test")
async def test_syslog():
    """Send a test syslog message to verify configuration."""
    from app.services.syslog_service import dispatch_syslog

    await dispatch_syslog(
        "admin",
        "test",
        {"message": "This is a test syslog message from ShellGuard"},
        datetime.now(timezone.utc).isoformat(),
    )
    return {"status": "sent"}


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@router.get("/alerts", response_model=AlertsConfigResponse)
async def get_alerts(db: AsyncSession = Depends(get_db)):
    """Get the threshold alerts configuration."""
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "alerts"))
    ).scalar_one_or_none()
    if not row:
        return AlertsConfigResponse(rules=[])
    raw_rules = row.value.get("rules", [])
    return AlertsConfigResponse(rules=[AlertRule(**r) for r in raw_rules])


@router.put("/alerts", response_model=AlertsConfigResponse)
async def update_alerts(
    body: AlertsConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Update the threshold alerts configuration."""
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "alerts"))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    new_value = {"rules": [r.model_dump() for r in body.rules]}

    if row:
        old_value = row.value
        row.value = new_value
        row.updated_at = now
    else:
        old_value = None
        row = SystemConfig(key="alerts", value=new_value, updated_at=now)
        db.add(row)

    log_admin(
        db, "config_change",
        details={"setting": "alerts", "old_value": old_value, "new_value": new_value},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    return AlertsConfigResponse(rules=body.rules)


# ---------------------------------------------------------------------------
# Metrics (placeholder)
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics(db: AsyncSession = Depends(get_db)):
    """Export Prometheus-format metrics (admin-authed)."""
    from app.metrics import collect_db_gauges, generate_metrics_output

    await collect_db_gauges(db)
    return PlainTextResponse(
        content=generate_metrics_output(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


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
