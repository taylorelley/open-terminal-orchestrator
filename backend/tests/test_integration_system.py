"""Integration tests for system, audit, and auth API routes (/admin/api/*)."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    _make_result_scalar_one,
    _make_result_scalar_one_or_none,
    _make_result_scalars_all,
)


class TestDetailedHealth:
    @pytest.mark.asyncio
    @patch("app.routes.system.check_db_connection")
    async def test_healthy(self, mock_check, client):
        mock_check.return_value = True

        resp = await client.get("/admin/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["checks"]["database"] == "connected"

    @pytest.mark.asyncio
    @patch("app.routes.system.check_db_connection")
    async def test_degraded(self, mock_check, client):
        mock_check.return_value = False

        resp = await client.get("/admin/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["checks"]["database"] == "disconnected"


class TestConfig:
    @pytest.mark.asyncio
    async def test_list_config(self, client, mock_db, make_system_config):
        cfg = make_system_config(key="pool", value={"warmup_size": 2})
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([cfg]))

        resp = await client.get("/admin/api/config")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["key"] == "pool"

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_update_existing_config(self, mock_log, client, mock_db, make_system_config):
        cfg = make_system_config(key="pool", value={"warmup_size": 2})
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(cfg))

        resp = await client.put(
            "/admin/api/config/pool",
            json={"value": {"warmup_size": 5}},
        )

        assert resp.status_code == 200
        assert cfg.value == {"warmup_size": 5}

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_create_new_config(self, mock_log, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        added = []
        mock_db.add = lambda obj: added.append(obj)

        async def mock_refresh(obj):
            if not hasattr(obj, "updated_by"):
                obj.updated_by = None

        mock_db.refresh = mock_refresh

        resp = await client.put(
            "/admin/api/config/new_key",
            json={"value": {"setting": "enabled"}},
        )

        assert resp.status_code == 200
        assert len(added) == 1


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_list_audit_log(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry(event_type="policy_change", category="admin")

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(1),
                _make_result_scalars_all([entry]),
            ]
        )

        resp = await client.get("/admin/api/audit")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["event_type"] == "policy_change"

    @pytest.mark.asyncio
    async def test_list_audit_log_with_filters(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry(event_type="sandbox_created", category="lifecycle")

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(1),
                _make_result_scalars_all([entry]),
            ]
        )

        resp = await client.get(
            "/admin/api/audit",
            params={"category": "lifecycle", "event_type": "sandbox_created"},
        )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_json(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry()
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([entry]))

        resp = await client.get("/admin/api/audit/export", params={"format": "json"})

        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_export_csv(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry()
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([entry]))

        resp = await client.get("/admin/api/audit/export", params={"format": "csv"})

        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_export_jsonl(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry()
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([entry]))

        resp = await client.get("/admin/api/audit/export", params={"format": "jsonl"})

        assert resp.status_code == 200


class TestBackup:
    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_backup_returns_json(self, mock_log, client, mock_db, make_policy, make_group, make_system_config):
        policy = make_policy(name="p1")
        group = make_group(name="g1")
        cfg = make_system_config(key="pool", value={})

        # 5 sequential queries: policies, versions, assignments, groups, config
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalars_all([policy]),
                _make_result_scalars_all([]),
                _make_result_scalars_all([]),
                _make_result_scalars_all([group]),
                _make_result_scalars_all([cfg]),
            ]
        )

        resp = await client.post("/admin/api/backup")

        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["type"] == "shellguard-backup"
        assert len(data["policies"]) == 1
        assert len(data["groups"]) == 1


class TestApiKeyManagement:
    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    @patch("app.routes.system.generate_api_key")
    async def test_create_api_key(self, mock_gen, mock_log, client, mock_db):
        mock_gen.return_value = {
            "id": str(uuid.uuid4()),
            "key": "sg_test_key_abc123",
            "label": "ci",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        resp = await client.post("/admin/api/auth/keys", params={"label": "ci"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["key"].startswith("sg_")
        assert data["label"] == "ci"

    @pytest.mark.asyncio
    @patch("app.routes.system.list_api_keys")
    async def test_list_api_keys(self, mock_list, client, mock_db):
        mock_list.return_value = [
            {"id": str(uuid.uuid4()), "label": "ci", "created_at": "2026-01-01T00:00:00Z"},
        ]

        resp = await client.get("/admin/api/auth/keys")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    @patch("app.routes.system.revoke_api_key")
    async def test_revoke_api_key(self, mock_revoke, mock_log, client, mock_db):
        mock_revoke.return_value = True

        resp = await client.delete(f"/admin/api/auth/keys/{uuid.uuid4()}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

    @pytest.mark.asyncio
    @patch("app.routes.system.revoke_api_key")
    async def test_revoke_nonexistent_key(self, mock_revoke, client, mock_db):
        mock_revoke.return_value = False

        resp = await client.delete(f"/admin/api/auth/keys/{uuid.uuid4()}")

        assert resp.status_code == 404


class TestAdminAuth:
    """Test that admin auth is enforced when the override is removed."""

    @pytest.mark.asyncio
    async def test_unauthenticated_request_returns_401(self, mock_db):
        """Without the require_admin override, requests should be rejected."""
        from httpx import ASGITransport, AsyncClient

        from app.database import get_db
        from app.main import app

        # Override DB but NOT require_admin
        async def _override_db():
            yield mock_db

        app.dependency_overrides[get_db] = _override_db
        # Ensure require_admin is NOT overridden
        from app.services.admin_auth import require_admin
        app.dependency_overrides.pop(require_admin, None)

        # Configure mock_db for the auth check (loads stored keys)
        stored_keys_cfg = SimpleNamespace(
            key="api_keys",
            value={"keys": [{"id": "k1", "hash": "abc", "label": "ci", "created_at": "2026-01-01"}]},
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(stored_keys_cfg))

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.get("/admin/api/sandboxes")

        app.dependency_overrides.clear()

        assert resp.status_code == 401
