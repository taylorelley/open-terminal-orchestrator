"""Unit tests for sandbox pool manager lifecycle operations.

Tests cover all state machine transitions managed by the pool manager:
- Pool replenishment (WARMING → READY)
- Idle suspension (ACTIVE/READY → SUSPENDED)
- Suspension expiry (SUSPENDED → DESTROYED)
- Startup timeout (WARMING → DESTROYED for pool sandboxes)
- Resume timeout (WARMING → SUSPENDED for user sandboxes)
- Health checks on ACTIVE sandboxes
- Proactive recreation of pending sandboxes
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.openshell_client import OpenShellError, SandboxInfo

# All pool manager functions accept (db, cfg) so we can test them
# directly without running the full cycle.
from app.services.pool_manager import (
    _destroy_expired,
    _enforce_resume_timeout,
    _enforce_startup_timeout,
    _health_checks,
    _recreate_pending,
    _replenish_pool,
    _suspend_idle,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers for mocking SQLAlchemy async queries
# ---------------------------------------------------------------------------


def _mock_db_with_scalars(sandboxes: list) -> AsyncMock:
    """Create a mock AsyncSession whose execute().scalars().all() returns *sandboxes*."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = sandboxes
    db.execute.return_value = result_mock
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _mock_db_with_scalar_one(value: int) -> AsyncMock:
    """Create a mock AsyncSession whose execute().scalar_one() returns *value*.

    Supports being called multiple times returning different values
    via side_effect on the scalar_one method.
    """
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _mock_db_count_then_scalars(counts: list[int], sandboxes: list | None = None) -> AsyncMock:
    """Mock DB that returns count values for initial calls, then scalars for later calls."""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()

    call_idx = 0

    def make_result(*args, **kwargs):
        nonlocal call_idx
        result = MagicMock()
        if call_idx < len(counts):
            result.scalar_one.return_value = counts[call_idx]
            call_idx += 1
        else:
            result.scalars.return_value.all.return_value = sandboxes or []
        return result

    db.execute = AsyncMock(side_effect=make_result)
    return db


# ===================================================================
# _replenish_pool
# ===================================================================


class TestReplenishPool:
    """Tests for pool replenishment logic."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_creates_sandbox_when_pool_below_warmup(self, mock_log, mock_osh, default_pool_cfg):
        """Should create sandboxes when pool count < warmup_size."""
        cfg = {**default_pool_cfg, "warmup_size": 2, "max_sandboxes": 20}

        # First call: count non-destroyed (returns 5)
        # Second call: count pool/warming/ready (returns 0)
        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 5  # total non-destroyed
                call_count += 1
            elif call_count == 1:
                result.scalar_one.return_value = 0  # pool count
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_osh.create_sandbox = AsyncMock(
            return_value=SandboxInfo(name="sg-pool-test", internal_ip="10.0.0.5", state="READY")
        )

        await _replenish_pool(db, cfg)

        assert mock_osh.create_sandbox.call_count == 2
        assert db.add.call_count >= 2  # sandbox objects added

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_no_creation_at_max_sandboxes(self, mock_log, mock_osh, default_pool_cfg):
        """Should not create when total non-destroyed >= max_sandboxes."""
        cfg = {**default_pool_cfg, "max_sandboxes": 10}

        db = AsyncMock()
        db.flush = AsyncMock()
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 10  # at capacity
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        await _replenish_pool(db, cfg)

        mock_osh.create_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_no_creation_pool_already_at_warmup(self, mock_log, mock_osh, default_pool_cfg):
        """Should not create when pool count >= warmup_size."""
        cfg = {**default_pool_cfg, "warmup_size": 2}

        db = AsyncMock()
        db.flush = AsyncMock()
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 5  # non-destroyed
                call_count += 1
            elif call_count == 1:
                result.scalar_one.return_value = 3  # pool >= warmup_size
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        await _replenish_pool(db, cfg)

        mock_osh.create_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_caps_creation_at_available_slots(self, mock_log, mock_osh, default_pool_cfg):
        """Should only create min(needed, slots_available) sandboxes."""
        cfg = {**default_pool_cfg, "warmup_size": 5, "max_sandboxes": 12}

        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 11  # 1 slot available
                call_count += 1
            elif call_count == 1:
                result.scalar_one.return_value = 0  # need 5
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_osh.create_sandbox = AsyncMock(
            return_value=SandboxInfo(name="sg-pool-test", internal_ip="10.0.0.5", state="READY")
        )

        await _replenish_pool(db, cfg)

        # Only 1 slot available, so only 1 created
        assert mock_osh.create_sandbox.call_count == 1

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_creation_failure_marks_destroyed(self, mock_log, mock_osh, default_pool_cfg):
        """On openshell create failure, sandbox should be marked DESTROYED."""
        cfg = {**default_pool_cfg, "warmup_size": 1}

        db = AsyncMock()
        db.flush = AsyncMock()
        db.add = MagicMock()
        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 0
                call_count += 1
            elif call_count == 1:
                result.scalar_one.return_value = 0
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_osh.create_sandbox = AsyncMock(side_effect=OpenShellError("create failed"))

        await _replenish_pool(db, cfg)

        # The sandbox was added to db and should have been set to DESTROYED.
        assert db.add.called
        # log_lifecycle called for both "creating" and "create_failed"
        assert mock_log.call_count >= 2

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_successful_creation_sets_ready_with_ip(self, mock_log, mock_osh, default_pool_cfg):
        """Successful creation should transition sandbox to READY with IP."""
        cfg = {**default_pool_cfg, "warmup_size": 1}

        created_sandboxes = []
        original_add = MagicMock()

        db = AsyncMock()
        db.flush = AsyncMock()

        def capture_add(obj):
            if hasattr(obj, "state"):
                created_sandboxes.append(obj)
            original_add(obj)

        db.add = capture_add

        call_count = 0

        def execute_side_effect(*args, **kwargs):
            nonlocal call_count
            result = MagicMock()
            if call_count == 0:
                result.scalar_one.return_value = 0
                call_count += 1
            elif call_count == 1:
                result.scalar_one.return_value = 0
                call_count += 1
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        mock_osh.create_sandbox = AsyncMock(
            return_value=SandboxInfo(name="sg-pool-abc", internal_ip="10.0.0.99", state="READY")
        )

        await _replenish_pool(db, cfg)

        assert len(created_sandboxes) == 1
        assert created_sandboxes[0].state == "READY"
        assert created_sandboxes[0].internal_ip == "10.0.0.99"


# ===================================================================
# _suspend_idle
# ===================================================================


class TestSuspendIdle:
    """Tests for idle sandbox suspension."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_suspends_active_past_idle_timeout(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """ACTIVE sandbox past idle_timeout should be suspended."""
        sandbox = make_sandbox(
            state="ACTIVE",
            user_id=uuid.uuid4(),
            last_active_at=_utcnow() - timedelta(seconds=3600),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.suspend_sandbox = AsyncMock()

        await _suspend_idle(db, default_pool_cfg)

        mock_osh.suspend_sandbox.assert_called_once_with(sandbox.name)
        assert sandbox.state == "SUSPENDED"
        assert sandbox.suspended_at is not None

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_suspends_ready_assigned_past_timeout(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """READY sandbox with user_id past idle_timeout should be suspended."""
        sandbox = make_sandbox(
            state="READY",
            user_id=uuid.uuid4(),
            last_active_at=_utcnow() - timedelta(seconds=3600),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.suspend_sandbox = AsyncMock()

        await _suspend_idle(db, default_pool_cfg)

        assert sandbox.state == "SUSPENDED"

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_sandbox_within_timeout(self, mock_log, mock_osh, default_pool_cfg):
        """Sandbox active within idle_timeout window should not be suspended."""
        # DB query filters by last_active_at < cutoff, so returning empty means no match.
        db = _mock_db_with_scalars([])
        mock_osh.suspend_sandbox = AsyncMock()

        await _suspend_idle(db, default_pool_cfg)

        mock_osh.suspend_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_resets_metrics_on_suspension(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """Suspension should reset cpu_usage, memory_usage, and network_io to 0."""
        sandbox = make_sandbox(
            state="ACTIVE",
            user_id=uuid.uuid4(),
            last_active_at=_utcnow() - timedelta(seconds=3600),
        )
        sandbox.cpu_usage = 50.0
        sandbox.memory_usage = 512.0
        sandbox.network_io = 1000.0
        db = _mock_db_with_scalars([sandbox])
        mock_osh.suspend_sandbox = AsyncMock()

        await _suspend_idle(db, default_pool_cfg)

        assert sandbox.cpu_usage == 0
        assert sandbox.memory_usage == 0
        assert sandbox.network_io == 0

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_suspend_failure_leaves_state_unchanged(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """If openshell suspend fails, sandbox state should remain unchanged."""
        sandbox = make_sandbox(
            state="ACTIVE",
            user_id=uuid.uuid4(),
            last_active_at=_utcnow() - timedelta(seconds=3600),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.suspend_sandbox = AsyncMock(side_effect=OpenShellError("suspend failed"))

        await _suspend_idle(db, default_pool_cfg)

        assert sandbox.state == "ACTIVE"  # unchanged


# ===================================================================
# _destroy_expired
# ===================================================================


class TestDestroyExpired:
    """Tests for suspension expiry destruction."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_destroys_expired_suspended(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """SUSPENDED sandbox past suspend_timeout should be destroyed."""
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=uuid.uuid4(),
            suspended_at=_utcnow() - timedelta(seconds=90000),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock()

        await _destroy_expired(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_called_once_with(sandbox.name)
        assert sandbox.state == "DESTROYED"
        assert sandbox.destroyed_at is not None

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_within_timeout(self, mock_log, mock_osh, default_pool_cfg):
        """SUSPENDED sandbox within timeout window should be skipped."""
        db = _mock_db_with_scalars([])
        mock_osh.destroy_sandbox = AsyncMock()

        await _destroy_expired(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_marks_destroyed_on_openshell_failure(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """Should mark DESTROYED even if openshell destroy call fails."""
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=uuid.uuid4(),
            suspended_at=_utcnow() - timedelta(seconds=90000),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock(side_effect=OpenShellError("destroy failed"))

        await _destroy_expired(db, default_pool_cfg)

        assert sandbox.state == "DESTROYED"
        assert sandbox.destroyed_at is not None

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_resets_metrics_on_destroy(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """Destruction should reset resource metrics to 0."""
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=uuid.uuid4(),
            suspended_at=_utcnow() - timedelta(seconds=90000),
        )
        sandbox.cpu_usage = 10.0
        sandbox.memory_usage = 256.0
        sandbox.network_io = 500.0
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock()

        await _destroy_expired(db, default_pool_cfg)

        assert sandbox.cpu_usage == 0
        assert sandbox.memory_usage == 0
        assert sandbox.network_io == 0


# ===================================================================
# _enforce_startup_timeout
# ===================================================================


class TestEnforceStartupTimeout:
    """Tests for startup timeout enforcement on WARMING pool sandboxes."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_destroys_stuck_warming_pool_sandbox(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """WARMING pool sandbox (no user) past startup_timeout should be destroyed."""
        sandbox = make_sandbox(
            state="WARMING",
            user_id=None,
            warming_started_at=_utcnow() - timedelta(seconds=300),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock()

        await _enforce_startup_timeout(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_called_once_with(sandbox.name)
        assert sandbox.state == "DESTROYED"
        assert sandbox.destroyed_at is not None

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_warming_user_sandbox(self, mock_log, mock_osh, default_pool_cfg):
        """WARMING sandbox with user_id should be skipped (handled by resume timeout)."""
        # The SQL query filters user_id IS NULL, so this sandbox won't appear.
        db = _mock_db_with_scalars([])
        mock_osh.destroy_sandbox = AsyncMock()

        await _enforce_startup_timeout(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_within_startup_timeout(self, mock_log, mock_osh, default_pool_cfg):
        """WARMING sandbox within startup_timeout window should be skipped."""
        db = _mock_db_with_scalars([])
        mock_osh.destroy_sandbox = AsyncMock()

        await _enforce_startup_timeout(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_handles_destroy_failure(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """Should mark DESTROYED even if openshell destroy fails."""
        sandbox = make_sandbox(
            state="WARMING",
            user_id=None,
            warming_started_at=_utcnow() - timedelta(seconds=300),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock(side_effect=OpenShellError("destroy failed"))

        await _enforce_startup_timeout(db, default_pool_cfg)

        assert sandbox.state == "DESTROYED"


# ===================================================================
# _enforce_resume_timeout
# ===================================================================


class TestEnforceResumeTimeout:
    """Tests for resume timeout enforcement on WARMING user sandboxes."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_reverts_to_suspended_on_timeout(self, mock_log, make_sandbox, default_pool_cfg):
        """WARMING user sandbox past resume_timeout should revert to SUSPENDED."""
        user_id = uuid.uuid4()
        sandbox = make_sandbox(
            state="WARMING",
            user_id=user_id,
            warming_started_at=_utcnow() - timedelta(seconds=60),
        )
        db = _mock_db_with_scalars([sandbox])

        await _enforce_resume_timeout(db, default_pool_cfg)

        assert sandbox.state == "SUSPENDED"
        assert sandbox.suspended_at is not None
        assert sandbox.warming_started_at is None

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_pool_sandbox(self, mock_log, default_pool_cfg):
        """WARMING pool sandbox (no user) should be skipped by resume timeout."""
        db = _mock_db_with_scalars([])

        await _enforce_resume_timeout(db, default_pool_cfg)

        # No state changes expected — no sandboxes returned
        mock_log.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_within_resume_timeout(self, mock_log, default_pool_cfg):
        """WARMING user sandbox within resume_timeout should be skipped."""
        db = _mock_db_with_scalars([])

        await _enforce_resume_timeout(db, default_pool_cfg)

        mock_log.assert_not_called()


# ===================================================================
# _health_checks
# ===================================================================


class TestHealthChecks:
    """Tests for sandbox health check enforcement."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_logs_unhealthy_sandbox(self, mock_log, mock_osh, make_sandbox):
        """Unhealthy ACTIVE sandbox should trigger a log entry."""
        sandbox = make_sandbox(state="ACTIVE", user_id=uuid.uuid4())
        db = _mock_db_with_scalars([sandbox])
        mock_osh.health_check = AsyncMock(return_value=False)

        await _health_checks(db)

        mock_osh.health_check.assert_called_once_with(sandbox.name)
        mock_log.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_no_log_for_healthy_sandbox(self, mock_log, mock_osh, make_sandbox):
        """Healthy ACTIVE sandbox should not trigger a log entry."""
        sandbox = make_sandbox(state="ACTIVE", user_id=uuid.uuid4())
        db = _mock_db_with_scalars([sandbox])
        mock_osh.health_check = AsyncMock(return_value=True)

        await _health_checks(db)

        mock_osh.health_check.assert_called_once_with(sandbox.name)
        mock_log.assert_not_called()


# ===================================================================
# _recreate_pending
# ===================================================================


class TestRecreatePending:
    """Tests for proactive recreation of sandboxes with pending policy changes."""

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_destroys_suspended_pending_recreation(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """SUSPENDED sandbox with pending_recreation should be destroyed."""
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=uuid.uuid4(),
            pending_recreation=True,
            suspended_at=_utcnow(),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock()

        await _recreate_pending(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_called_once_with(sandbox.name)
        assert sandbox.state == "DESTROYED"
        assert sandbox.destroyed_at is not None
        assert sandbox.pending_recreation is False

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_skips_non_suspended(self, mock_log, mock_osh, default_pool_cfg):
        """Non-SUSPENDED sandboxes with pending_recreation should be skipped."""
        # The SQL query filters state == SUSPENDED, so non-matching won't appear.
        db = _mock_db_with_scalars([])
        mock_osh.destroy_sandbox = AsyncMock()

        await _recreate_pending(db, default_pool_cfg)

        mock_osh.destroy_sandbox.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.pool_manager.openshell_client")
    @patch("app.services.pool_manager.log_lifecycle")
    async def test_handles_destroy_failure(self, mock_log, mock_osh, make_sandbox, default_pool_cfg):
        """Should mark DESTROYED even if openshell destroy fails."""
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=uuid.uuid4(),
            pending_recreation=True,
            suspended_at=_utcnow(),
        )
        db = _mock_db_with_scalars([sandbox])
        mock_osh.destroy_sandbox = AsyncMock(side_effect=OpenShellError("destroy failed"))

        await _recreate_pending(db, default_pool_cfg)

        assert sandbox.state == "DESTROYED"
        assert sandbox.pending_recreation is False
