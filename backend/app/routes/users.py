"""User and group management API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Group, User
from app.schemas import GroupCreate, GroupMembersUpdate, GroupResponse, GroupUpdate, UserResponse, UserSyncResponse
from app.services.admin_auth import require_admin
from app.services.audit_service import log_admin
from app.services.user_sync_service import sync_users_from_owui

router = APIRouter(
    prefix="/admin/api",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.get("/users", response_model=list[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(User).order_by(User.username))
    ).scalars().all()
    return rows


@router.post("/users/sync", response_model=UserSyncResponse)
async def sync_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Sync users from Open WebUI into ShellGuard."""
    result = await sync_users_from_owui(db)
    log_admin(
        db,
        "user_sync",
        details=result,
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    return UserSyncResponse(status="success", **result)


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


@router.put("/groups/{group_id}/members", response_model=list[UserResponse])
async def set_group_members(
    group_id: uuid.UUID,
    request: Request,
    body: GroupMembersUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Set the members of a group, replacing any existing membership."""
    group = (
        await db.execute(select(Group).where(Group.id == group_id))
    ).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Clear existing members of this group
    current_members = (
        await db.execute(select(User).where(User.group_id == group_id))
    ).scalars().all()
    for user in current_members:
        user.group_id = None

    # Assign new members
    new_members: list[User] = []
    if body.user_ids:
        rows = (
            await db.execute(select(User).where(User.id.in_(body.user_ids)))
        ).scalars().all()
        for user in rows:
            user.group_id = group_id
            new_members.append(user)

    log_admin(
        db, "config_change",
        details={
            "action": "group_members_updated",
            "group_name": group.name,
            "group_id": str(group_id),
            "member_count": len(new_members),
        },
        source_ip=request.client.host if request.client else "",
    )
    await db.flush()
    return new_members
