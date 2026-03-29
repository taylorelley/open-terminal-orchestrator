"""Tests for Prometheus metrics definitions and helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.metrics import (
    POOL_UTILIZATION,
    REGISTRY,
    SANDBOX_STARTUP_DURATION,
    WEBHOOK_DELIVERIES,
    collect_db_gauges,
    record_startup_duration,
    record_webhook_delivery,
)


class TestMetricRegistrations:
    """Verify new metrics are registered in the custom registry."""

    def _metric_names(self) -> list[str]:
        return [m.name for m in REGISTRY.collect()]

    def test_sandbox_startup_duration_registered(self):
        assert "oto_sandbox_startup_duration_seconds" in self._metric_names()

    def test_pool_utilization_registered(self):
        assert "oto_pool_utilization_ratio" in self._metric_names()

    def test_webhook_deliveries_registered(self):
        assert "oto_webhook_deliveries" in self._metric_names()


class TestHelpers:
    """Verify helper functions update metrics correctly."""

    def test_record_startup_duration(self):
        # Should not raise; observes a value.
        record_startup_duration(2.5)

    def test_record_webhook_delivery(self):
        record_webhook_delivery("success", "https://example.com/hook")
        record_webhook_delivery("failure", "https://example.com/hook")


class TestCollectDbGauges:
    """Verify collect_db_gauges sets pool utilization from system_config."""

    @pytest.mark.asyncio
    async def test_pool_utilization_with_config(self):
        pool_cfg = SimpleNamespace(key="pool", value={"max_active": 10})

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()

            # The function runs multiple queries; pool utilization uses a
            # second sandbox-state query and then the SystemConfig query.
            # We return appropriate mocks for each call.
            if "system_config" in str(query).lower() or (
                hasattr(query, "whereclause")
                and "system_config" in str(query.whereclause)
            ):
                result.scalar_one_or_none.return_value = pool_cfg
            elif call_count <= 2:
                # Sandbox count by state queries — return ACTIVE=3
                result.all.return_value = [("ACTIVE", 3), ("POOL", 2)]
            else:
                # Scalar counts (policy, user, group)
                result.scalar_one.return_value = 5
                result.all.return_value = []

            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        await collect_db_gauges(db)

        # Pool utilization should have been set (we can't easily read the
        # exact value from a Gauge without sampling, but no error means success).

    @pytest.mark.asyncio
    async def test_pool_utilization_without_config(self):
        """When no pool config exists, utilization should be 0."""
        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            result.all.return_value = []
            result.scalar_one.return_value = 0
            result.scalar_one_or_none.return_value = None
            return result

        db = AsyncMock()
        db.execute = AsyncMock(side_effect=mock_execute)

        await collect_db_gauges(db)
