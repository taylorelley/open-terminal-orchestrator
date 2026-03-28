"""Historical metrics API for monitoring charts."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditLogEntry, MetricSnapshot, Sandbox
from app.schemas import MetricHistoryResponse, MetricPointResponse
from app.services.admin_auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/api/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_admin)],
)

_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_INTERVAL_MAP = {
    "1h": timedelta(minutes=1),
    "24h": timedelta(hours=1),
    "7d": timedelta(hours=6),
    "30d": timedelta(days=1),
}


def _format_time(dt: datetime, range_key: str) -> str:
    if range_key == "1h":
        return dt.strftime("%H:%M")
    if range_key == "24h":
        return dt.strftime("%H:%M")
    if range_key == "7d":
        return dt.strftime("%a %H:%M")
    return dt.strftime("%m/%d")


@router.get("/history", response_model=MetricHistoryResponse)
async def get_metrics_history(
    metric: str = Query(description="Metric: cpu, memory, requests, errors, latency, startup"),
    range: str = Query("24h", description="Time range: 1h, 24h, 7d, 30d"),
    db: AsyncSession = Depends(get_db),
):
    if range not in _RANGE_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid range: {range}. Must be one of: {', '.join(_RANGE_MAP)}")

    valid_metrics = ("cpu", "memory", "requests", "errors", "latency", "startup")
    if metric not in valid_metrics:
        raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}. Must be one of: {', '.join(valid_metrics)}")

    delta = _RANGE_MAP[range]
    since = datetime.now(timezone.utc) - delta

    # Try metric_snapshots table first
    rows = (
        await db.execute(
            select(MetricSnapshot)
            .where(
                MetricSnapshot.metric_type == metric,
                MetricSnapshot.timestamp >= since,
            )
            .order_by(MetricSnapshot.timestamp.asc())
        )
    ).scalars().all()

    if rows:
        points = [
            MetricPointResponse(
                time=_format_time(r.timestamp, range),
                value=round(r.value, 2),
            )
            for r in rows
        ]
    elif metric == "requests":
        # Fall back to audit_log aggregation for request counts
        points = await _aggregate_audit_requests(db, since, range)
    elif metric == "errors":
        points = await _aggregate_audit_errors(db, since, range)
    elif metric in ("cpu", "memory"):
        # Fall back to current sandbox resource data
        points = await _current_resource_snapshot(db, metric, range)
    else:
        points = []

    return MetricHistoryResponse(metric=metric, range=range, points=points)


async def _aggregate_audit_requests(
    db: AsyncSession, since: datetime, range_key: str
) -> list[MetricPointResponse]:
    """Aggregate request counts from the audit log by time buckets."""
    rows = (
        await db.execute(
            select(AuditLogEntry.timestamp)
            .where(
                AuditLogEntry.timestamp >= since,
                AuditLogEntry.category == "enforcement",
            )
            .order_by(AuditLogEntry.timestamp.asc())
        )
    ).scalars().all()

    return _bucket_timestamps(rows, since, range_key)


async def _aggregate_audit_errors(
    db: AsyncSession, since: datetime, range_key: str
) -> list[MetricPointResponse]:
    """Aggregate error counts from the audit log."""
    rows = (
        await db.execute(
            select(AuditLogEntry.timestamp)
            .where(
                AuditLogEntry.timestamp >= since,
                AuditLogEntry.event_type.in_(["policy_deny", "sandbox_error", "proxy_error"]),
            )
            .order_by(AuditLogEntry.timestamp.asc())
        )
    ).scalars().all()

    return _bucket_timestamps(rows, since, range_key)


async def _current_resource_snapshot(
    db: AsyncSession, metric: str, range_key: str
) -> list[MetricPointResponse]:
    """Generate a single-point snapshot from current sandbox data."""
    col = Sandbox.cpu_usage if metric == "cpu" else Sandbox.memory_usage
    result = await db.execute(
        select(func.avg(col)).where(Sandbox.state.in_(["ACTIVE", "READY"]))
    )
    avg_val = result.scalar_one_or_none() or 0

    now = datetime.now(timezone.utc)
    return [MetricPointResponse(time=_format_time(now, range_key), value=round(float(avg_val), 2))]


def _bucket_timestamps(
    timestamps: list[datetime], since: datetime, range_key: str
) -> list[MetricPointResponse]:
    """Group timestamps into time buckets and count per bucket."""
    interval = _INTERVAL_MAP[range_key]
    now = datetime.now(timezone.utc)
    buckets: list[MetricPointResponse] = []

    current = since
    while current < now:
        bucket_end = current + interval
        count = sum(1 for t in timestamps if current <= t < bucket_end)
        buckets.append(MetricPointResponse(
            time=_format_time(current, range_key),
            value=float(count),
        ))
        current = bucket_end

    return buckets
