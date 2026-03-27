"""Resolve the sandbox assigned to a requesting user.

This service handles:
- Extracting user identity from Open WebUI headers or Bearer tokens
- Looking up (or auto-creating) the User record
- Finding the user's sandbox and handling state transitions
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLogEntry, Sandbox, User
from app.services import openshell_client

logger = logging.getLogger(__name__)

# Header injected by Open WebUI's backend proxy mode.
_OWUI_USER_HEADER = "X-Open-WebUI-User-Id"


@dataclass
class ResolvedSandbox:
    """A sandbox that is ready to receive proxied requests."""

    sandbox: Sandbox
    user: User


async def _get_or_create_user(owui_id: str, db: AsyncSession) -> User:
    """Return the User for *owui_id*, creating a stub record on first sight."""
    result = await db.execute(select(User).where(User.owui_id == owui_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    # Auto-create a stub user on first proxy request (lazy sync).
    user = User(
        id=uuid.uuid4(),
        owui_id=owui_id,
        username=owui_id,
        email="",
        owui_role="user",
        synced_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()
    logger.info("Auto-created user stub for owui_id=%s", owui_id)
    return user


async def _find_user_sandbox(user: User, db: AsyncSession) -> Sandbox | None:
    """Find the user's non-destroyed sandbox (most recently active first)."""
    result = await db.execute(
        select(Sandbox)
        .where(Sandbox.user_id == user.id, Sandbox.state != "DESTROYED")
        .order_by(Sandbox.last_active_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _claim_pool_sandbox(user: User, db: AsyncSession) -> Sandbox | None:
    """Assign an available pre-warmed pool sandbox to the user."""
    result = await db.execute(
        select(Sandbox)
        .where(Sandbox.user_id.is_(None), Sandbox.state.in_(["POOL", "READY"]))
        .order_by(Sandbox.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    sandbox = result.scalar_one_or_none()
    if sandbox is None:
        return None

    now = datetime.now(timezone.utc)
    sandbox.user_id = user.id
    sandbox.state = "ACTIVE"
    sandbox.last_active_at = now

    # Record the assignment in the audit log.
    db.add(
        AuditLogEntry(
            id=uuid.uuid4(),
            timestamp=now,
            event_type="assigned",
            category="lifecycle",
            user_id=user.id,
            sandbox_id=sandbox.id,
            details={"pool_sandbox": sandbox.name, "owui_id": user.owui_id},
            source_ip="",
        )
    )
    await db.flush()
    logger.info("Assigned pool sandbox %s to user %s", sandbox.name, user.owui_id)
    return sandbox


def _extract_owui_id(request: Request) -> str:
    """Extract the Open WebUI user ID from the request.

    Checks (in order):
    1. ``X-Open-WebUI-User-Id`` header
    2. ``Authorization: Bearer <token>`` (treated as owui_id for now)

    Raises HTTPException(401) if neither is present.
    """
    owui_id = request.headers.get(_OWUI_USER_HEADER)
    if owui_id:
        return owui_id

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 7:
        return auth[7:].strip()

    raise HTTPException(status_code=401, detail="Missing user identity")


async def _background_resume(sandbox_name: str, sandbox_id: uuid.UUID) -> None:
    """Resume a sandbox via openshell in the background.

    On success the sandbox row is updated to ACTIVE with the new IP.
    On failure it is reverted to SUSPENDED so the next request can retry.
    """
    from app.database import async_session as _async_session

    async with _async_session() as db:
        try:
            info = await openshell_client.resume_sandbox(sandbox_name)

            sandbox = (
                await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
            ).scalar_one_or_none()
            if sandbox is None:
                return

            sandbox.state = "ACTIVE"
            sandbox.internal_ip = info.internal_ip or sandbox.internal_ip
            sandbox.suspended_at = None
            sandbox.last_active_at = datetime.now(timezone.utc)
            await db.commit()
            logger.info("Background resume succeeded for %s", sandbox_name)
        except Exception:
            logger.exception("Background resume failed for %s", sandbox_name)
            # Revert to SUSPENDED so the next request can retry.
            try:
                sandbox = (
                    await db.execute(select(Sandbox).where(Sandbox.id == sandbox_id))
                ).scalar_one_or_none()
                if sandbox and sandbox.state == "WARMING":
                    sandbox.state = "SUSPENDED"
                await db.commit()
            except Exception:
                await db.rollback()


async def resolve_sandbox(request: Request, db: AsyncSession) -> ResolvedSandbox:
    """Identify the calling user and return their ready sandbox.

    Raises:
        HTTPException(401) — no user identity in headers.
        HTTPException(202) — sandbox is warming / resuming (includes Retry-After).
        HTTPException(503) — no sandbox available in the pool.
    """
    owui_id = _extract_owui_id(request)
    user = await _get_or_create_user(owui_id, db)
    sandbox = await _find_user_sandbox(user, db)

    if sandbox is not None:
        if sandbox.state in ("ACTIVE", "READY"):
            sandbox.last_active_at = datetime.now(timezone.utc)
            if sandbox.state == "READY":
                sandbox.state = "ACTIVE"
            await db.flush()
            return ResolvedSandbox(sandbox=sandbox, user=user)

        if sandbox.state == "SUSPENDED":
            sandbox.state = "WARMING"
            db.add(
                AuditLogEntry(
                    id=uuid.uuid4(),
                    timestamp=datetime.now(timezone.utc),
                    event_type="resumed",
                    category="lifecycle",
                    user_id=user.id,
                    sandbox_id=sandbox.id,
                    details={"trigger": "proxy_request"},
                    source_ip=request.client.host if request.client else "",
                )
            )
            await db.flush()

            # Kick off the actual openshell resume in the background so the
            # sandbox transitions to READY/ACTIVE on the next request.
            asyncio.create_task(
                _background_resume(sandbox.name, sandbox.id),
                name=f"resume-{sandbox.name}",
            )

            raise HTTPException(
                status_code=202,
                detail="Sandbox is resuming",
                headers={"Retry-After": "5"},
            )

        if sandbox.state == "WARMING":
            raise HTTPException(
                status_code=202,
                detail="Sandbox is provisioning",
                headers={"Retry-After": "5"},
            )

    # No usable sandbox — try to claim one from the pool.
    claimed = await _claim_pool_sandbox(user, db)
    if claimed is not None:
        return ResolvedSandbox(sandbox=claimed, user=user)

    raise HTTPException(status_code=503, detail="No sandbox available")
