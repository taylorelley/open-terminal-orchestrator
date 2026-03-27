"""Background service that manages the sandbox pool lifecycle.

Responsibilities:
- Maintain a pre-warmed pool of unassigned sandboxes.
- Suspend idle sandboxes after ``idle_timeout``.
- Destroy suspended sandboxes after ``suspend_timeout``.
- Enforce startup/resume timeouts for stuck sandboxes.
- Run periodic health checks on active sandboxes.
- Respect ``max_sandboxes`` and ``max_active`` limits.

The manager runs as a single ``asyncio.Task`` started during the FastAPI
lifespan and cancelled on shutdown.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models import Sandbox, SystemConfig
from app.services import openshell_client
from app.services.audit_service import log_lifecycle

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


async def _load_pool_config(db: AsyncSession) -> dict:
    """Load pool/lifecycle configuration from the database, with env defaults."""
    result = {}

    for key in ("pool", "lifecycle"):
        row = (
            await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        ).scalar_one_or_none()
        if row:
            result.update(row.value)

    return {
        "warmup_size": result.get("warmup_size", settings.pool_warmup_size),
        "max_sandboxes": result.get("max_sandboxes", settings.pool_max_sandboxes),
        "max_active": result.get("max_active", settings.pool_max_active),
        "idle_timeout": result.get("idle_timeout", settings.idle_timeout),
        "suspend_timeout": result.get("suspend_timeout", settings.suspend_timeout),
        "startup_timeout": result.get("startup_timeout", settings.startup_timeout),
        "resume_timeout": result.get("resume_timeout", settings.resume_timeout),
    }


# ---------------------------------------------------------------------------
# Lifecycle operations
# ---------------------------------------------------------------------------


async def _count_by_states(db: AsyncSession, states: list[str]) -> int:
    result = await db.execute(
        select(func.count(Sandbox.id)).where(Sandbox.state.in_(states))
    )
    return result.scalar_one()


async def _replenish_pool(db: AsyncSession, cfg: dict) -> None:
    """Create new sandboxes to maintain the pre-warmed pool at ``warmup_size``."""
    total_non_destroyed = await _count_by_states(
        db, ["POOL", "WARMING", "READY", "ACTIVE", "SUSPENDED"]
    )
    if total_non_destroyed >= cfg["max_sandboxes"]:
        return

    pool_count = await _count_by_states(db, ["POOL", "WARMING", "READY"])
    needed = cfg["warmup_size"] - pool_count
    slots_available = cfg["max_sandboxes"] - total_non_destroyed

    to_create = min(needed, slots_available)
    if to_create <= 0:
        return

    logger.info("Pool replenishment: creating %d sandbox(es)", to_create)

    for _ in range(to_create):
        sandbox_id = uuid.uuid4()
        name = f"sg-pool-{sandbox_id.hex[:8]}"
        now = datetime.now(timezone.utc)

        # Insert the DB record in WARMING state first.
        sandbox = Sandbox(
            id=sandbox_id,
            name=name,
            state="WARMING",
            image_tag=settings.default_image_tag,
            created_at=now,
            last_active_at=now,
        )
        db.add(sandbox)
        log_lifecycle(db, "creating", sandbox=sandbox, details={"trigger": "pool_replenish"})
        await db.flush()

        # Issue the openshell create in the background — the periodic loop
        # will detect WARMING → READY transition or timeout.
        try:
            info = await openshell_client.create_sandbox(
                name=name,
                image_tag=settings.default_image_tag,
            )
            sandbox.internal_ip = info.internal_ip
            sandbox.state = "READY"
            log_lifecycle(db, "ready", sandbox=sandbox, details={"trigger": "pool_replenish"})
            logger.info("Sandbox %s is READY (ip=%s)", name, info.internal_ip)
        except Exception:
            logger.exception("Failed to create sandbox %s", name)
            sandbox.state = "DESTROYED"
            sandbox.destroyed_at = datetime.now(timezone.utc)
            log_lifecycle(db, "create_failed", sandbox=sandbox, details={"trigger": "pool_replenish"})

        await db.flush()


async def _suspend_idle(db: AsyncSession, cfg: dict) -> None:
    """Suspend sandboxes that have been idle longer than ``idle_timeout``."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cfg["idle_timeout"])

    result = await db.execute(
        select(Sandbox).where(
            Sandbox.state.in_(["ACTIVE", "READY"]),
            Sandbox.user_id.isnot(None),
            Sandbox.last_active_at < cutoff,
        )
    )

    for sandbox in result.scalars().all():
        logger.info("Suspending idle sandbox %s (last_active=%s)", sandbox.name, sandbox.last_active_at)
        try:
            await openshell_client.suspend_sandbox(sandbox.name)
            sandbox.state = "SUSPENDED"
            sandbox.suspended_at = datetime.now(timezone.utc)
            sandbox.cpu_usage = 0
            sandbox.memory_usage = 0
            sandbox.network_io = 0
            log_lifecycle(db, "suspended", sandbox=sandbox, details={"reason": "idle_timeout"})
        except Exception:
            logger.exception("Failed to suspend sandbox %s", sandbox.name)

        await db.flush()


async def _destroy_expired(db: AsyncSession, cfg: dict) -> None:
    """Destroy suspended sandboxes that have exceeded ``suspend_timeout``.

    Note: only the openshell container is destroyed.  The host-side user data
    directory (``sandbox.data_dir``) is intentionally preserved so that files
    persist when the user is assigned a new sandbox later.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cfg["suspend_timeout"])

    result = await db.execute(
        select(Sandbox).where(
            Sandbox.state == "SUSPENDED",
            Sandbox.suspended_at.isnot(None),
            Sandbox.suspended_at < cutoff,
        )
    )

    for sandbox in result.scalars().all():
        logger.info("Destroying expired sandbox %s (suspended_at=%s)", sandbox.name, sandbox.suspended_at)
        try:
            await openshell_client.destroy_sandbox(sandbox.name)
        except Exception:
            logger.exception("openshell destroy failed for %s — marking destroyed anyway", sandbox.name)

        sandbox.state = "DESTROYED"
        sandbox.destroyed_at = datetime.now(timezone.utc)
        sandbox.cpu_usage = 0
        sandbox.memory_usage = 0
        sandbox.network_io = 0
        log_lifecycle(db, "destroyed", sandbox=sandbox, details={"reason": "suspend_timeout"})
        await db.flush()


async def _enforce_startup_timeout(db: AsyncSession, cfg: dict) -> None:
    """Mark WARMING sandboxes as DESTROYED if they exceed ``startup_timeout``."""
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=cfg["startup_timeout"])

    result = await db.execute(
        select(Sandbox).where(
            Sandbox.state == "WARMING",
            Sandbox.created_at < cutoff,
        )
    )

    for sandbox in result.scalars().all():
        logger.warning("Sandbox %s stuck in WARMING — destroying", sandbox.name)
        try:
            await openshell_client.destroy_sandbox(sandbox.name)
        except Exception:
            logger.exception("openshell destroy failed for stuck sandbox %s", sandbox.name)

        sandbox.state = "DESTROYED"
        sandbox.destroyed_at = datetime.now(timezone.utc)
        log_lifecycle(db, "destroyed", sandbox=sandbox, details={"reason": "startup_timeout"})
        await db.flush()


async def _health_checks(db: AsyncSession) -> None:
    """Run health checks on ACTIVE sandboxes and mark unhealthy ones."""
    result = await db.execute(
        select(Sandbox).where(Sandbox.state == "ACTIVE")
    )

    for sandbox in result.scalars().all():
        healthy = await openshell_client.health_check(sandbox.name)
        if not healthy:
            logger.warning("Sandbox %s failed health check", sandbox.name)
            log_lifecycle(db, "health_check_failed", sandbox=sandbox, details={"ip": sandbox.internal_ip})
            await db.flush()


# ---------------------------------------------------------------------------
# Proactive recreation
# ---------------------------------------------------------------------------


async def _recreate_pending(db: AsyncSession, cfg: dict) -> None:
    """Destroy SUSPENDED sandboxes that are marked for recreation.

    When a policy update includes static section changes (filesystem, process),
    affected sandboxes are flagged with ``pending_recreation=True``.  Suspended
    sandboxes can be destroyed proactively here; active ones are handled in
    ``sandbox_resolver.resolve_sandbox`` on the next user request.
    """
    result = await db.execute(
        select(Sandbox).where(
            Sandbox.pending_recreation.is_(True),
            Sandbox.state == "SUSPENDED",
        )
    )

    for sandbox in result.scalars().all():
        logger.info(
            "Destroying suspended sandbox %s for pending policy recreation",
            sandbox.name,
        )
        try:
            await openshell_client.destroy_sandbox(sandbox.name)
        except Exception:
            logger.exception(
                "openshell destroy failed for %s — marking destroyed anyway",
                sandbox.name,
            )

        sandbox.state = "DESTROYED"
        sandbox.destroyed_at = datetime.now(timezone.utc)
        sandbox.pending_recreation = False
        log_lifecycle(
            db, "destroyed",
            sandbox=sandbox,
            details={"reason": "policy_recreation"},
        )
        await db.flush()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


async def _run_cycle() -> None:
    """Execute one full pool management cycle."""
    async with async_session() as db:
        try:
            cfg = await _load_pool_config(db)

            await _recreate_pending(db, cfg)
            await _enforce_startup_timeout(db, cfg)
            await _destroy_expired(db, cfg)
            await _suspend_idle(db, cfg)
            await _replenish_pool(db, cfg)
            await _health_checks(db)

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Pool manager cycle failed")


class PoolManager:
    """Manages the sandbox pool as a background asyncio task."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start(self) -> None:
        """Start the background pool management loop."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="pool-manager")
        logger.info(
            "Pool manager started (interval=%ds)",
            settings.cleanup_interval,
        )

    async def stop(self) -> None:
        """Signal the loop to stop and wait for it to finish."""
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Pool manager stopped")

    async def _loop(self) -> None:
        """Periodic cleanup loop."""
        while not self._stop_event.is_set():
            await _run_cycle()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=settings.cleanup_interval,
                )
            except asyncio.TimeoutError:
                # Normal: the event was not set within the interval — loop again.
                pass


# Module-level singleton — initialised/stopped via the FastAPI lifespan.
pool_manager = PoolManager()
