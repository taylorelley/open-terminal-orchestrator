"""Sync users from Open WebUI into the ShellGuard users table."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User

logger = logging.getLogger(__name__)


async def fetch_owui_users() -> list[dict[str, Any]]:
    """Fetch all users from the Open WebUI API."""
    if not settings.open_webui_api_key:
        raise HTTPException(
            status_code=400,
            detail="OPEN_WEBUI_API_KEY is not configured. Set it before syncing users.",
        )

    url = f"{settings.open_webui_base_url.rstrip('/')}/api/v1/users/"
    headers = {"Authorization": f"Bearer {settings.open_webui_api_key}"}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            resp = await client.get(url, headers=headers)
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Failed to connect to Open WebUI at %s: %s", url, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Cannot reach Open WebUI at {settings.open_webui_base_url}: {exc}",
        ) from exc

    if resp.status_code != 200:
        logger.error("Open WebUI returned %d: %s", resp.status_code, resp.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Open WebUI returned HTTP {resp.status_code}",
        )

    data = resp.json()
    # Open WebUI may return a bare list or an object with a "data" key.
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "data" in data:
        return data["data"]
    return data if isinstance(data, list) else []


async def sync_users_from_owui(db: AsyncSession) -> dict[str, int]:
    """Fetch users from Open WebUI and upsert into the local database.

    Returns a dict with keys: created, updated, unchanged, total_remote.
    """
    remote_users = await fetch_owui_users()
    now = datetime.now(timezone.utc)

    # Load all existing users keyed by owui_id.
    rows = (await db.execute(select(User))).scalars().all()
    existing = {u.owui_id: u for u in rows}

    created = 0
    updated = 0
    unchanged = 0

    for ru in remote_users:
        owui_id = str(ru.get("id", ""))
        if not owui_id:
            continue

        username = ru.get("name", owui_id)
        email = ru.get("email", "")
        role = ru.get("role", "user")

        user = existing.get(owui_id)
        if user is None:
            # New user — create.
            db.add(User(
                id=uuid.uuid4(),
                owui_id=owui_id,
                username=username,
                email=email,
                owui_role=role,
                synced_at=now,
            ))
            created += 1
        elif user.username != username or user.email != email or user.owui_role != role:
            # Existing user with changed metadata — update.
            user.username = username
            user.email = email
            user.owui_role = role
            user.synced_at = now
            updated += 1
        else:
            unchanged += 1

    await db.flush()

    logger.info(
        "User sync complete: %d created, %d updated, %d unchanged (total remote: %d)",
        created, updated, unchanged, len(remote_users),
    )

    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "total_remote": len(remote_users),
    }
