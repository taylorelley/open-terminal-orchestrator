"""Authentication dependency for the management API.

Provides a ``require_admin`` FastAPI dependency that validates requests to
``/admin/api/*`` routes using one of two mechanisms:

1. **Environment API key** — the ``ADMIN_API_KEY`` env var (``settings.admin_api_key``).
   Requests supply this via ``Authorization: Bearer <key>`` or ``X-Admin-API-Key``
   header.

2. **Stored API keys** — keys generated via the ``/admin/api/auth/keys`` endpoint
   and stored (hashed) in the ``system_config`` table under the ``api_keys`` key.

If ``settings.admin_api_key`` is empty **and** no stored keys exist, authentication
is skipped (dev/bootstrap mode).
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import SystemConfig

logger = logging.getLogger(__name__)

_API_KEYS_CONFIG_KEY = "api_keys"


def _hash_key(raw_key: str) -> str:
    """Return a SHA-256 hex digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _extract_bearer_token(request: Request) -> str | None:
    """Extract a bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 7:
        return auth[7:].strip()
    return None


async def _load_stored_keys(db: AsyncSession) -> list[dict]:
    """Load stored API keys from the ``system_config`` table."""
    row = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.key == _API_KEYS_CONFIG_KEY)
        )
    ).scalar_one_or_none()
    if row is None:
        return []
    return row.value.get("keys", [])


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> None:
    """FastAPI dependency that enforces admin authentication.

    Raises ``HTTPException(401)`` if no valid credential is provided.
    In dev/bootstrap mode (no keys configured at all), access is allowed.
    """
    # Extract credential from request.
    token = _extract_bearer_token(request)
    api_key_header = request.headers.get("X-Admin-API-Key")
    credential = token or api_key_header

    # Check environment API key first (fast path).
    if settings.admin_api_key:
        if credential and secrets.compare_digest(credential, settings.admin_api_key):
            return
    else:
        # No env key set — check if stored keys exist.
        stored_keys = await _load_stored_keys(db)
        if not stored_keys:
            # Dev/bootstrap mode: no auth configured at all.
            return
        if credential:
            hashed = _hash_key(credential)
            for key_entry in stored_keys:
                if secrets.compare_digest(hashed, key_entry.get("hash", "")):
                    return

        raise HTTPException(status_code=401, detail="Invalid or missing admin API key")

    # Env key is set but credential didn't match — also check stored keys.
    if credential:
        stored_keys = await _load_stored_keys(db)
        hashed = _hash_key(credential)
        for key_entry in stored_keys:
            if secrets.compare_digest(hashed, key_entry.get("hash", "")):
                return

    raise HTTPException(status_code=401, detail="Invalid or missing admin API key")


# ---------------------------------------------------------------------------
# API key management helpers
# ---------------------------------------------------------------------------


async def generate_api_key(
    db: AsyncSession,
    label: str = "",
) -> dict:
    """Generate a new API key, store its hash, and return the raw key.

    Returns ``{"id": ..., "key": ..., "label": ..., "created_at": ...}``.
    The raw key is only returned once — only the hash is persisted.
    """
    raw_key = f"sg_{secrets.token_urlsafe(32)}"
    key_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    entry = {
        "id": key_id,
        "hash": _hash_key(raw_key),
        "label": label,
        "created_at": now,
    }

    row = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.key == _API_KEYS_CONFIG_KEY)
        )
    ).scalar_one_or_none()

    if row is None:
        row = SystemConfig(
            key=_API_KEYS_CONFIG_KEY,
            value={"keys": [entry]},
            updated_at=datetime.now(timezone.utc),
        )
        db.add(row)
    else:
        keys = row.value.get("keys", [])
        keys.append(entry)
        row.value = {"keys": keys}
        row.updated_at = datetime.now(timezone.utc)

    await db.flush()

    return {"id": key_id, "key": raw_key, "label": label, "created_at": now}


async def list_api_keys(db: AsyncSession) -> list[dict]:
    """Return stored API keys with hashes masked."""
    stored = await _load_stored_keys(db)
    return [
        {"id": k["id"], "label": k.get("label", ""), "created_at": k["created_at"]}
        for k in stored
    ]


async def revoke_api_key(db: AsyncSession, key_id: str) -> bool:
    """Remove an API key by its ID.  Returns True if found and removed."""
    row = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.key == _API_KEYS_CONFIG_KEY)
        )
    ).scalar_one_or_none()

    if row is None:
        return False

    keys = row.value.get("keys", [])
    new_keys = [k for k in keys if k["id"] != key_id]
    if len(new_keys) == len(keys):
        return False

    row.value = {"keys": new_keys}
    row.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return True
