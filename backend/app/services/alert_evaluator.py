"""Background service that evaluates threshold alert rules.

Periodically checks configured alert rules against current metrics
and fires webhooks when thresholds are breached.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import MetricSnapshot, Sandbox, SystemConfig

logger = logging.getLogger(__name__)

# In-memory state: tracks which alerts are currently firing to avoid duplicates.
_firing: dict[str, datetime] = {}


async def _load_alert_rules(db: AsyncSession) -> list[dict]:
    row = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "alerts"))
    ).scalar_one_or_none()
    if not row:
        return []
    return row.value.get("rules", [])


async def _get_metric_value(db: AsyncSession, metric: str) -> float:
    """Get the current value for a metric."""
    if metric == "cpu":
        result = await db.execute(
            select(func.avg(Sandbox.cpu_usage)).where(Sandbox.state.in_(["ACTIVE", "READY"]))
        )
        return float(result.scalar_one_or_none() or 0)

    if metric == "memory":
        result = await db.execute(
            select(func.avg(Sandbox.memory_usage)).where(Sandbox.state.in_(["ACTIVE", "READY"]))
        )
        return float(result.scalar_one_or_none() or 0)

    if metric == "active_sandboxes":
        result = await db.execute(
            select(func.count(Sandbox.id)).where(Sandbox.state == "ACTIVE")
        )
        return float(result.scalar_one())

    if metric == "pool_available":
        result = await db.execute(
            select(func.count(Sandbox.id)).where(Sandbox.state.in_(["POOL", "READY"]))
        )
        return float(result.scalar_one())

    # Try from recent snapshots
    result = await db.execute(
        select(MetricSnapshot.value)
        .where(MetricSnapshot.metric_type == metric)
        .order_by(MetricSnapshot.timestamp.desc())
        .limit(1)
    )
    val = result.scalar_one_or_none()
    return float(val) if val is not None else 0.0


def _check_threshold(value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    if operator == "eq":
        return value == threshold
    return False


async def _evaluate_rules() -> None:
    """Run one evaluation cycle for all alert rules."""
    async with async_session() as db:
        try:
            rules = await _load_alert_rules(db)
            now = datetime.now(timezone.utc)

            for rule in rules:
                if not rule.get("enabled", True):
                    continue

                name = rule.get("name", "unnamed")
                metric = rule.get("metric", "")
                operator = rule.get("operator", "gt")
                threshold = rule.get("threshold", 0)
                duration = rule.get("duration_seconds", 60)

                value = await _get_metric_value(db, metric)
                breached = _check_threshold(value, operator, threshold)

                if breached:
                    if name not in _firing:
                        _firing[name] = now
                    elif (now - _firing[name]).total_seconds() >= duration:
                        # Threshold breached for long enough — fire alert
                        logger.warning(
                            "Alert '%s' triggered: %s=%s %s %s for %ds",
                            name, metric, value, operator, threshold, duration,
                        )
                        await _fire_alert(db, rule, value)
                        # Keep firing but don't re-fire on next cycle
                        _firing[name] = now
                else:
                    if name in _firing:
                        logger.info("Alert '%s' resolved: %s=%s", name, metric, value)
                        del _firing[name]

            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("Alert evaluation cycle failed")


async def _fire_alert(db: AsyncSession, rule: dict, value: float) -> None:
    """Dispatch a webhook for a triggered alert."""
    try:
        from app.services.webhook_service import dispatch_webhooks

        await dispatch_webhooks(
            category="alert",
            event_type="threshold_breach",
            details={
                "alert_name": rule.get("name"),
                "metric": rule.get("metric"),
                "value": value,
                "threshold": rule.get("threshold"),
                "operator": rule.get("operator"),
            },
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception:
        logger.exception("Failed to dispatch alert webhook for '%s'", rule.get("name"))


class AlertEvaluator:
    """Manages alert evaluation as a background asyncio task."""

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._loop(), name="alert-evaluator")
        logger.info("Alert evaluator started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Alert evaluator stopped")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            await _evaluate_rules()
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=30)
            except asyncio.TimeoutError:
                pass


alert_evaluator = AlertEvaluator()
