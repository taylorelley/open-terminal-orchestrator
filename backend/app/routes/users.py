"""User and group management API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Group, User
from app.schemas import GroupCreate, GroupResponse, GroupUpdate, UserResponse
from app.services.audit_service import log_admin

router = APIRouter(prefix="/admin/api", tags=["users"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(User).order_by(User.username))
    ).scalars().all()
    return rows


@router.post("/users/sync")
async def sync_users():
    """Placeholder — real sync requires Open WebUI API integration."""
    return {"status": "pending", "message": "Open WebUI sync not yet implemented"}


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Group).order_by(Group.name))
    ).scalars().all()
    return rows


@router.post("/groups", response_model=GroupResponse, status_code=201)
async def create_group(
    request: Request,
    body: GroupCreate,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    group = Group(
        name=body.name,
        description=body.description,
        policy_id=body.policy_id,
        created_at=now,
        updated_at=now,
    )
    db.add(group)
    log_admin(
        db, "config_change",
        details={"action": "group_created", "group_name": body.name},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    await db.refresh(group)
    return group


@router.put("/groups/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    request: Request,
    body: GroupUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Group).where(Group.id == group_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")

    if body.name is not None:
        row.name = body.name
    if body.description is not None:
        row.description = body.description
    if body.policy_id is not None:
        row.policy_id = body.policy_id

    row.updated_at = datetime.now(timezone.utc)
    changes = [k for k in ("name", "description", "policy_id") if getattr(body, k, None) is not None]
    log_admin(
        db, "config_change",
        details={"action": "group_updated", "group_name": row.name, "group_id": str(group_id), "changes": changes},
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Group).where(Group.id == group_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Group not found")

    log_admin(
        db, "config_change",
        details={"action": "group_deleted", "group_name": row.name, "group_id": str(group_id)},
        source_ip=request.client.host if request.client else "",
    )
    await db.delete(row)
    await db.flush()
