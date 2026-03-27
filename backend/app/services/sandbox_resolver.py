"""Resolve the sandbox assigned to a requesting user.

This service handles:
- Extracting user identity from Open WebUI headers or Bearer tokens
- Looking up (or auto-creating) the User record
- Finding the user's sandbox and handling state transitions
"""

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Sandbox, User
from app.services import openshell_client
from app.services.audit_service import log_lifecycle
from app.services.policy_engine import apply_policy_to_sandbox, resolve_policy_for_user

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


def _ensure_user_data_dir(user: User) -> str:
    """Create and return the host-side data directory for a user."""
    path = os.path.join(settings.user_data_base_dir, str(user.id))
    os.makedirs(path, mode=0o750, exist_ok=True)
    return path


async def _claim_pool_sandbox(user: User, db: AsyncSession) -> Sandbox | None:
    """Assign an available pre-warmed pool sandbox to the user.

    The pool sandbox is destroyed and recreated with the user's data volume
    mounted at ``/data`` inside the container.  This ensures persistent user
    files across sandbox lifecycles.
    """
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
    user_data_dir = _ensure_user_data_dir(user)

    # Destroy the anonymous pool sandbox so we can recreate it with the
    # user's data volume mounted.
    try:
        await openshell_client.destroy_sandbox(sandbox.name)
    except openshell_client.OpenShellError:
        logger.warning(
            "Failed to destroy pool sandbox %s for re-creation", sandbox.name,
        )
        sandbox.state = "DESTROYED"
        sandbox.destroyed_at = now
        await db.flush()
        return None

    try:
        info = await openshell_client.create_sandbox(
            name=sandbox.name,
            image_tag=sandbox.image_tag,
            user_data_dir=user_data_dir,
        )
    except (openshell_client.OpenShellError, asyncio.TimeoutError):
        logger.exception(
            "Failed to recreate sandbox %s with user data volume", sandbox.name,
        )
        sandbox.state = "DESTROYED"
        sandbox.destroyed_at = now
        await db.flush()
        return None

    sandbox.user_id = user.id
    sandbox.state = "ACTIVE"
    sandbox.internal_ip = info.internal_ip or sandbox.internal_ip
    sandbox.data_dir = user_data_dir
    sandbox.last_active_at = now

    # Resolve and apply the user's policy to this sandbox.
    policy = await resolve_policy_for_user(user, db)
    policy_name: str | None = None
    if policy is not None:
        try:
            await apply_policy_to_sandbox(sandbox, policy, db)
            policy_name = policy.name
        except Exception:
            logger.warning(
                "Policy application failed for sandbox %s — continuing without policy",
                sandbox.name,
            )

    # Record the assignment in the audit log.
    log_lifecycle(
        db, "assigned",
        user_id=user.id,
        sandbox_id=sandbox.id,
        details={
            "pool_sandbox": sandbox.name,
            "owui_id": user.owui_id,
            "policy": policy_name,
            "data_dir": user_data_dir,
        },
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

            # Re-check policy assignment in case it changed since last session.
            policy = await resolve_policy_for_user(user, db)
            expected_id = policy.id if policy else None
            if expected_id != sandbox.policy_id and policy is not None:
                try:
                    await apply_policy_to_sandbox(
                        sandbox, policy, db,
                        source_ip=request.client.host if request.client else "",
                    )
                except Exception:
                    logger.warning(
                        "Policy re-application failed for sandbox %s — keeping existing policy",
                        sandbox.name,
                    )

            await db.flush()
            return ResolvedSandbox(sandbox=sandbox, user=user)

        if sandbox.state == "SUSPENDED":
            sandbox.state = "WARMING"
            log_lifecycle(
                db, "resumed",
                user_id=user.id,
                sandbox_id=sandbox.id,
                details={"trigger": "proxy_request"},
                source_ip=request.client.host if request.client else "",
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
