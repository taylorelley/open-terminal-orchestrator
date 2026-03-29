"""Prometheus metrics definitions and collection helpers."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group, Policy, Sandbox, SystemConfig, User

# Custom registry — avoids default process/platform collectors.
REGISTRY = CollectorRegistry()

# ---------------------------------------------------------------------------
# Gauges (populated from DB at scrape time)
# ---------------------------------------------------------------------------

SANDBOX_COUNT = Gauge(
    "oto_sandbox_count",
    "Number of sandboxes by state",
    ["state"],
    registry=REGISTRY,
)

SANDBOX_TOTAL = Gauge(
    "oto_sandbox_total",
    "Total number of sandboxes",
    registry=REGISTRY,
)

POLICY_COUNT = Gauge(
    "oto_policy_count",
    "Number of policies",
    registry=REGISTRY,
)

USER_COUNT = Gauge(
    "oto_user_count",
    "Number of registered users",
    registry=REGISTRY,
)

GROUP_COUNT = Gauge(
    "oto_group_count",
    "Number of groups",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Counters (incremented in real-time)
# ---------------------------------------------------------------------------

AUDIT_EVENTS = Counter(
    "oto_audit_events_total",
    "Audit log events",
    ["category", "event_type"],
    registry=REGISTRY,
)

REQUEST_COUNT = Counter(
    "oto_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Histogram
# ---------------------------------------------------------------------------

REQUEST_LATENCY = Histogram(
    "oto_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    registry=REGISTRY,
)

SANDBOX_STARTUP_DURATION = Histogram(
    "oto_sandbox_startup_duration_seconds",
    "Time for a sandbox to transition from WARMING to READY",
    buckets=(0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0),
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Gauges (computed at scrape time)
# ---------------------------------------------------------------------------

POOL_UTILIZATION = Gauge(
    "oto_pool_utilization_ratio",
    "Ratio of active sandboxes to max_active limit",
    registry=REGISTRY,
)

# ---------------------------------------------------------------------------
# Webhook delivery counter
# ---------------------------------------------------------------------------

WEBHOOK_DELIVERIES = Counter(
    "oto_webhook_deliveries_total",
    "Webhook delivery attempts",
    ["status", "url"],
    registry=REGISTRY,
)

# All known sandbox states — used to zero-fill gauges before setting.
_SANDBOX_STATES = ("POOL", "WARMING", "READY", "ACTIVE", "SUSPENDED", "DESTROYED")


async def collect_db_gauges(db: AsyncSession) -> None:
    """Query the database and set gauge values for the current scrape."""

    # Sandbox counts by state
    result = await db.execute(
        select(Sandbox.state, func.count(Sandbox.id)).group_by(Sandbox.state)
    )
    for state in _SANDBOX_STATES:
        SANDBOX_COUNT.labels(state=state).set(0)
    total = 0
    for state, count in result.all():
        SANDBOX_COUNT.labels(state=state).set(count)
        total += count
    SANDBOX_TOTAL.set(total)

    # Policy count
    policy_count = (await db.execute(select(func.count(Policy.id)))).scalar_one()
    POLICY_COUNT.set(policy_count)

    # User count
    user_count = (await db.execute(select(func.count(User.id)))).scalar_one()
    USER_COUNT.set(user_count)

    # Group count
    group_count = (await db.execute(select(func.count(Group.id)))).scalar_one()
    GROUP_COUNT.set(group_count)

    # Pool utilization (active / max_active)
    active_count = 0
    for state, count in (await db.execute(
        select(Sandbox.state, func.count(Sandbox.id)).group_by(Sandbox.state)
    )).all():
        if state == "ACTIVE":
            active_count = count

    pool_cfg = (
        await db.execute(select(SystemConfig).where(SystemConfig.key == "pool"))
    ).scalar_one_or_none()
    max_active = (
        int(pool_cfg.value.get("max_active", 0))
        if pool_cfg and isinstance(pool_cfg.value, dict)
        else 0
    )
    POOL_UTILIZATION.set(active_count / max_active if max_active > 0 else 0.0)


def generate_metrics_output() -> str:
    """Return Prometheus exposition format text."""
    return generate_latest(REGISTRY).decode("utf-8")


def record_audit_event(category: str, event_type: str) -> None:
    """Increment the audit events counter."""
    AUDIT_EVENTS.labels(category=category, event_type=event_type).inc()


def record_startup_duration(seconds: float) -> None:
    """Observe a sandbox startup duration."""
    SANDBOX_STARTUP_DURATION.observe(seconds)


def record_webhook_delivery(status: str, url: str) -> None:
    """Increment the webhook delivery counter."""
    WEBHOOK_DELIVERIES.labels(status=status, url=url).inc()
