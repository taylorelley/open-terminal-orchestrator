"""Integration tests for the metrics history endpoint (GET /admin/api/metrics/history)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import (
    _make_result_scalar_one_or_none,
    _make_result_scalars_all,
)


def _make_metric_snapshot(*, metric_type: str = "cpu", value: float = 42.5) -> SimpleNamespace:
    """Create a lightweight metric snapshot object."""
    return SimpleNamespace(
        id=1,
        metric_type=metric_type,
        value=value,
        timestamp=datetime.now(timezone.utc),
    )


class TestValidCpuMetric:
    @pytest.mark.asyncio
    async def test_valid_cpu_metric(self, client, mock_db):
        """Returns points for cpu metric with range=24h."""
        snap1 = _make_metric_snapshot(metric_type="cpu", value=25.0)
        snap2 = _make_metric_snapshot(metric_type="cpu", value=40.0)

        mock_db.execute = AsyncMock(
            return_value=_make_result_scalars_all([snap1, snap2]),
        )

        resp = await client.get(
            "/admin/api/metrics/history",
            params={"metric": "cpu", "range": "24h"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "cpu"
        assert data["range"] == "24h"
        assert len(data["points"]) == 2
        assert data["points"][0]["value"] == 25.0
        assert data["points"][1]["value"] == 40.0


class TestValidMemoryMetric:
    @pytest.mark.asyncio
    async def test_valid_memory_metric(self, client, mock_db):
        """Returns points for memory metric."""
        snap = _make_metric_snapshot(metric_type="memory", value=512.0)

        mock_db.execute = AsyncMock(
            return_value=_make_result_scalars_all([snap]),
        )

        resp = await client.get(
            "/admin/api/metrics/history",
            params={"metric": "memory", "range": "1h"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "memory"
        assert data["range"] == "1h"
        assert len(data["points"]) == 1
        assert data["points"][0]["value"] == 512.0


class TestInvalidRange:
    @pytest.mark.asyncio
    async def test_invalid_range(self, client, mock_db):
        """Returns 400 for an invalid range parameter."""
        resp = await client.get(
            "/admin/api/metrics/history",
            params={"metric": "cpu", "range": "99h"},
        )

        assert resp.status_code == 400
        assert "Invalid range" in resp.json()["detail"]


class TestInvalidMetric:
    @pytest.mark.asyncio
    async def test_invalid_metric(self, client, mock_db):
        """Returns 400 for an invalid metric parameter."""
        resp = await client.get(
            "/admin/api/metrics/history",
            params={"metric": "bogus", "range": "24h"},
        )

        assert resp.status_code == 400
        assert "Invalid metric" in resp.json()["detail"]
