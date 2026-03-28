"""Webhook notification service for audit events.

Delivers JSON payloads to configured webhook endpoints with HMAC-SHA256
signing, retry logic, and event filtering.  Configuration is stored in
the ``system_config`` table under key ``"webhooks"``.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx
from pydantic import BaseModel

from app.database import async_session
from app.models import SystemConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


class WebhookEventFilter(BaseModel):
    category: str | None = None
    event_type: str | None = None


class WebhookConfig(BaseModel):
    url: str
    secret: str = ""
    enabled: bool = True
    event_filters: list[WebhookEventFilter] = []


# ---------------------------------------------------------------------------
# Config cache
# ---------------------------------------------------------------------------

_CACHE_TTL = 30.0
_config_cache: tuple[float, list[WebhookConfig]] | None = None


async def _load_webhooks() -> list[WebhookConfig]:
    """Load webhook configs from the database with a TTL cache."""
    global _config_cache

    now = time.monotonic()
    if _config_cache is not None:
        cached_at, cached = _config_cache
        if now - cached_at < _CACHE_TTL:
            return cached

    try:
        from sqlalchemy import select

        async with async_session() as db:
            row = (
                await db.execute(
                    select(SystemConfig).where(SystemConfig.key == "webhooks")
                )
            ).scalar_one_or_none()

        if row and isinstance(row.value, dict):
            raw_list = row.value.get("webhooks", [])
            webhooks = [WebhookConfig(**w) for w in raw_list]
        else:
            webhooks = []
    except Exception:
        logger.exception("Failed to load webhook config")
        webhooks = []

    _config_cache = (now, webhooks)
    return webhooks


def invalidate_cache() -> None:
    """Clear the config cache (e.g. after a CRUD update)."""
    global _config_cache
    _config_cache = None


# ---------------------------------------------------------------------------
# Filter matching
# ---------------------------------------------------------------------------


def matches_filters(webhook: WebhookConfig, category: str, event_type: str) -> bool:
    """Return True if the event matches the webhook's filters.

    An empty filter list means "match all events".  Each filter entry is
    an OR clause — the event must match at least one filter.
    """
    if not webhook.event_filters:
        return True

    for f in webhook.event_filters:
        cat_match = f.category is None or f.category == category
        evt_match = f.event_type is None or f.event_type == event_type
        if cat_match and evt_match:
            return True

    return False


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS = 3
_http_client: httpx.AsyncClient | None = None


def _sign_payload(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature for the payload."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def _deliver(webhook: WebhookConfig, payload: dict) -> None:
    """Deliver a single webhook with retries."""
    from app.metrics import record_webhook_delivery

    if _http_client is None:
        logger.warning("Webhook HTTP client not initialized — skipping delivery")
        return

    body = json.dumps(payload, default=str).encode()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if webhook.secret:
        sig = _sign_payload(webhook.secret, body)
        headers["X-ShellGuard-Signature"] = f"sha256={sig}"

    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await _http_client.post(
                webhook.url,
                content=body,
                headers=headers,
                timeout=10.0,
            )
            if resp.status_code < 400:
                record_webhook_delivery("success", webhook.url)
                return
            logger.warning(
                "Webhook %s returned %d (attempt %d/%d)",
                webhook.url, resp.status_code, attempt + 1, _MAX_ATTEMPTS,
            )
        except Exception:
            logger.debug(
                "Webhook %s delivery failed (attempt %d/%d)",
                webhook.url, attempt + 1, _MAX_ATTEMPTS,
                exc_info=True,
            )

        if attempt < _MAX_ATTEMPTS - 1:
            await asyncio.sleep(2 ** attempt)

    record_webhook_delivery("failure", webhook.url)
    logger.error("Webhook %s delivery exhausted after %d attempts", webhook.url, _MAX_ATTEMPTS)


# ---------------------------------------------------------------------------
# Dispatch entry point
# ---------------------------------------------------------------------------


async def dispatch_webhooks(
    category: str,
    event_type: str,
    details: dict[str, Any],
    timestamp: str,
) -> None:
    """Fire matching webhooks for an audit event."""
    webhooks = await _load_webhooks()
    payload = {
        "event_type": event_type,
        "category": category,
        "timestamp": timestamp,
        "details": details,
    }

    for wh in webhooks:
        if wh.enabled and matches_filters(wh, category, event_type):
            asyncio.create_task(
                _deliver(wh, payload),
                name=f"webhook-{wh.url}",
            )


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


class WebhookService:
    """Manages the HTTP client used for webhook delivery."""

    async def start(self) -> None:
        global _http_client
        _http_client = httpx.AsyncClient(
            follow_redirects=True,
            limits=httpx.Limits(max_connections=20),
        )
        logger.info("Webhook service started")

    async def stop(self) -> None:
        global _http_client
        if _http_client is not None:
            await _http_client.aclose()
            _http_client = None
        logger.info("Webhook service stopped")


webhook_service = WebhookService()
