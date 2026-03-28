"""Shared test fixtures and environment setup.

Sets DATABASE_URL before any app modules are imported so that the
import-time engine creation in ``app.database`` doesn't fail when
no real database is available.
"""

import os

# Ensure a DATABASE_URL is set so the app module can import without error.
# Unit tests never touch the database — this value is only used to satisfy
# the import-time engine creation in app.database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/testdb",
)

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def make_sandbox():
    """Factory fixture that creates lightweight sandbox-like objects for testing.

    Uses SimpleNamespace to avoid SQLAlchemy instrumentation issues with
    detached ORM objects.  The returned objects support attribute get/set
    just like real Sandbox instances.
    """

    def _make(
        *,
        state: str = "ACTIVE",
        user_id: uuid.UUID | None = None,
        name: str | None = None,
        last_active_at: datetime | None = None,
        suspended_at: datetime | None = None,
        warming_started_at: datetime | None = None,
        pending_recreation: bool = False,
        internal_ip: str = "10.0.0.1",
        image_tag: str = "shellguard-sandbox:slim",
    ) -> SimpleNamespace:
        now = _utcnow()
        return SimpleNamespace(
            id=uuid.uuid4(),
            name=name or f"sg-test-{uuid.uuid4().hex[:8]}",
            state=state,
            user_id=user_id,
            policy_id=None,
            internal_ip=internal_ip,
            image_tag=image_tag,
            data_dir="",
            gpu_enabled=False,
            cpu_usage=5.0,
            memory_usage=128.0,
            disk_usage=0,
            network_io=100.0,
            created_at=now,
            last_active_at=last_active_at or now,
            suspended_at=suspended_at,
            warming_started_at=warming_started_at,
            destroyed_at=None,
            pending_recreation=pending_recreation,
        )

    return _make


@pytest.fixture
def make_user():
    """Factory fixture that creates lightweight user-like objects for testing."""

    def _make(
        *,
        owui_id: str | None = None,
        username: str = "testuser",
        owui_role: str = "user",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
            owui_id=owui_id or f"owui-{uuid.uuid4().hex[:8]}",
            username=username,
            email=f"{username}@test.local",
            owui_role=owui_role,
            group_id=None,
            synced_at=_utcnow(),
        )

    return _make


@pytest.fixture
def default_pool_cfg():
    """Return a default pool/lifecycle config dict for testing."""
    return {
        "warmup_size": 2,
        "max_sandboxes": 20,
        "max_active": 10,
        "idle_timeout": 1800,
        "suspend_timeout": 86400,
        "startup_timeout": 120,
        "resume_timeout": 30,
    }
