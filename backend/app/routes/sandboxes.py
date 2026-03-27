"""Sandbox management API routes."""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLogEntry, Policy, Sandbox, SystemConfig
from app.services import openshell_client
from app.services.audit_service import log_admin
from app.services.policy_engine import apply_policy_to_sandbox

logger = logging.getLogger(__name__)
from app.schemas import (
    AuditLogResponse,
    PaginatedResponse,
    PoolStatusResponse,
    SandboxResponse,
    SandboxUpdatePolicy,
    SystemConfigUpdate,
)

router = APIRouter(prefix="/admin/api", tags=["sandboxes"])


@router.get("/sandboxes", response_model=PaginatedResponse[SandboxResponse])
async def list_sandboxes(
    state: str | None = Query(None, description="Filter by state"),
    include_destroyed: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Sandbox)
    count_query = select(func.count(Sandbox.id))

    if not include_destroyed:
        query = query.where(Sandbox.state != "DESTROYED")
        count_query = count_query.where(Sandbox.state != "DESTROYED")

    if state:
        query = query.where(Sandbox.state == state)
        count_query = count_query.where(Sandbox.state == state)

    query = query.order_by(Sandbox.last_active_at.desc()).offset(offset).limit(limit)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(items=rows, total=total, offset=offset, limit=limit)


@router.get("/sandboxes/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return row


@router.post("/sandboxes/{sandbox_id}/suspend", response_model=SandboxResponse)
async def suspend_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if row.state not in ("ACTIVE", "READY"):
        raise HTTPException(status_code=409, detail=f"Cannot suspend sandbox in state {row.state}")

    try:
        await openshell_client.suspend_sandbox(row.name)
    except Exception:
        logger.exception("openshell suspend failed for %s", row.name)
        raise HTTPException(status_code=502, detail="Failed to suspend sandbox via openshell")

    row.state = "SUSPENDED"
    row.suspended_at = datetime.now(timezone.utc)
    row.cpu_usage = 0
    row.memory_usage = 0
    row.network_io = 0
    log_admin(
        db, "policy_change",
        details={"action": "manual_suspend", "sandbox_name": row.name, "sandbox_id": str(sandbox_id)},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    await db.refresh(row)
    return row


@router.post("/sandboxes/{sandbox_id}/resume", response_model=SandboxResponse)
async def resume_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if row.state != "SUSPENDED":
        raise HTTPException(status_code=409, detail=f"Cannot resume sandbox in state {row.state}")

    try:
        info = await openshell_client.resume_sandbox(row.name)
        row.internal_ip = info.internal_ip or row.internal_ip
    except Exception:
        logger.exception("openshell resume failed for %s", row.name)
        raise HTTPException(status_code=502, detail="Failed to resume sandbox via openshell")

    row.state = "ACTIVE"
    row.suspended_at = None
    row.last_active_at = datetime.now(timezone.utc)
    log_admin(
        db, "policy_change",
        details={"action": "manual_resume", "sandbox_name": row.name, "sandbox_id": str(sandbox_id)},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/sandboxes/{sandbox_id}", response_model=SandboxResponse)
async def destroy_sandbox(
    sandbox_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if row.state == "DESTROYED":
        raise HTTPException(status_code=409, detail="Sandbox is already destroyed")

    try:
        await openshell_client.destroy_sandbox(row.name)
    except Exception:
        logger.exception("openshell destroy failed for %s — marking destroyed anyway", row.name)

    row.state = "DESTROYED"
    row.destroyed_at = datetime.now(timezone.utc)
    row.cpu_usage = 0
    row.memory_usage = 0
    row.network_io = 0
    log_admin(
        db, "policy_change",
        details={"action": "manual_destroy", "sandbox_name": row.name, "sandbox_id": str(sandbox_id)},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    await db.refresh(row)
    return row


@router.post("/sandboxes/{sandbox_id}/policy", response_model=SandboxResponse)
async def update_sandbox_policy(
    sandbox_id: uuid.UUID,
    request: Request,
    body: SandboxUpdatePolicy,
    db: AsyncSession = Depends(get_db),
):
    row = (await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    policy = (await db.execute(select(Policy).where(Policy.id == body.policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Apply via openshell if sandbox is running; otherwise just store the assignment.
    if row.state in ("ACTIVE", "READY"):
        try:
            await apply_policy_to_sandbox(row, policy, db)
        except Exception:
            logger.exception("Failed to apply policy to sandbox %s via openshell", row.name)
            raise HTTPException(status_code=502, detail="Failed to apply policy via openshell")
    else:
        row.policy_id = body.policy_id

    log_admin(
        db, "policy_change",
        details={
            "action": "sandbox_policy_update",
            "sandbox_name": row.name,
            "sandbox_id": str(sandbox_id),
            "policy_id": str(body.policy_id),
            "policy_name": policy.name,
        },
        source_ip=request.client.host if request.client else "",
    )

    await db.flush()
    await db.refresh(row)
    return row


@router.get("/sandboxes/{sandbox_id}/logs", response_model=PaginatedResponse[AuditLogResponse])
async def get_sandbox_logs(
    sandbox_id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    base = select(AuditLogEntry).where(AuditLogEntry.sandbox_id == sandbox_id)
    count_query = select(func.count(AuditLogEntry.id)).where(AuditLogEntry.sandbox_id == sandbox_id)

    query = base.order_by(AuditLogEntry.timestamp.desc()).offset(offset).limit(limit)

    total = (await db.execute(count_query)).scalar_one()
    rows = (await db.execute(query)).scalars().all()

    return PaginatedResponse(items=rows, total=total, offset=offset, limit=limit)


# ---------------------------------------------------------------------------
# Pool
# ---------------------------------------------------------------------------


@router.get("/pool", response_model=PoolStatusResponse)
async def get_pool_status(db: AsyncSession = Depends(get_db)):
    # Count sandboxes by state
    state_counts = (
        await db.execute(
            select(Sandbox.state, func.count(Sandbox.id))
            .where(Sandbox.state != "DESTROYED")
            .group_by(Sandbox.state)
        )
    ).all()

    counts: dict[str, int] = {row[0]: row[1] for row in state_counts}
    total = sum(counts.values())

    # Read pool config from system_config
    cfg = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "pool"))
    ).scalar_one_or_none()

    pool_cfg = cfg.value if cfg else {}

    return PoolStatusResponse(
        total=total,
        active=counts.get("ACTIVE", 0),
        ready=counts.get("READY", 0),
        warming=counts.get("WARMING", 0),
        suspended=counts.get("SUSPENDED", 0),
        pool=counts.get("POOL", 0),
        max_sandboxes=pool_cfg.get("max_sandboxes", 0),
        max_active=pool_cfg.get("max_active", 0),
        warmup_size=pool_cfg.get("warmup_size", 0),
    )


@router.put("/pool")
async def update_pool_config(
    request: Request,
    body: SystemConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "pool"))
    ).scalar_one_or_none()

    old_value = row.value if row else {}
    now = datetime.now(timezone.utc)
    if row:
        row.value = body.value
        row.updated_at = now
    else:
        db.add(SystemConfig(key="pool", value=body.value, updated_at=now))

    log_admin(
        db, "config_change",
        details={"setting": "pool", "old_value": old_value, "new_value": body.value},
        source_ip=request.client.host if request.client else "",
    )

    await db.flush()
    return {"status": "ok"}
