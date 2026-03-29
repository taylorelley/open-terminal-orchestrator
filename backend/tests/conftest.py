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
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient


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
        image_tag: str = "oto-sandbox:slim",
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


# ---------------------------------------------------------------------------
# Integration test fixtures
# ---------------------------------------------------------------------------


def _make_result_scalars_all(items: list) -> MagicMock:
    """Build a mock result whose .scalars().all() returns *items*."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _make_result_scalar_one_or_none(item) -> MagicMock:
    """Build a mock result whose .scalar_one_or_none() returns *item*."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


def _make_result_scalar_one(value) -> MagicMock:
    """Build a mock result whose .scalar_one() returns *value*."""
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession for integration tests.

    Callers configure ``db.execute`` via ``side_effect`` to return the
    appropriate mock results for each sequential DB query in the endpoint.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def make_policy():
    """Factory fixture for policy-like objects."""

    def _make(
        *,
        name: str = "test-policy",
        tier: str = "restricted",
        description: str = "",
        yaml: str = "",
        current_version: str = "1.0.0",
    ) -> SimpleNamespace:
        now = _utcnow()
        return SimpleNamespace(
            id=uuid.uuid4(),
            name=name,
            tier=tier,
            description=description,
            yaml=yaml,
            current_version=current_version,
            created_at=now,
            updated_at=now,
            versions=[],
        )

    return _make


@pytest.fixture
def make_group():
    """Factory fixture for group-like objects."""

    def _make(
        *,
        name: str = "test-group",
        description: str = "",
        policy_id: uuid.UUID | None = None,
    ) -> SimpleNamespace:
        now = _utcnow()
        return SimpleNamespace(
            id=uuid.uuid4(),
            name=name,
            description=description,
            policy_id=policy_id,
            created_at=now,
            updated_at=now,
            policy=None,
            members=[],
        )

    return _make


@pytest.fixture
def make_audit_entry():
    """Factory fixture for audit log entry-like objects."""

    def _make(
        *,
        event_type: str = "policy_change",
        category: str = "admin",
        details: dict | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid.uuid4(),
            timestamp=_utcnow(),
            event_type=event_type,
            category=category,
            user_id=None,
            sandbox_id=None,
            details=details or {},
            source_ip="127.0.0.1",
            user=None,
            sandbox=None,
        )

    return _make


@pytest.fixture
def make_system_config():
    """Factory fixture for system config-like objects."""

    def _make(*, key: str = "pool", value: dict | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            key=key,
            value=value or {},
            updated_at=_utcnow(),
            updated_by=None,
        )

    return _make


@pytest.fixture
async def client(mock_db):
    """Async HTTP client wired to the FastAPI app with mocked DB and auth.

    The ``get_db`` dependency yields ``mock_db``; ``require_admin`` is a no-op.
    Callers must configure ``mock_db.execute`` per test.
    """
    from app.database import get_db
    from app.main import app
    from app.services.admin_auth import require_admin

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_admin] = lambda: None

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
