"""Integration tests for the sandbox management API routes (/admin/api/sandboxes/*)."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    _make_result_scalar_one,
    _make_result_scalar_one_or_none,
    _make_result_scalars_all,
)


class TestListSandboxes:
    @pytest.mark.asyncio
    async def test_returns_paginated_sandboxes(self, client, mock_db, make_sandbox):
        sb1 = make_sandbox(state="ACTIVE")
        sb2 = make_sandbox(state="READY")

        # First call: count query; second call: rows query
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(2),
                _make_result_scalars_all([sb1, sb2]),
            ]
        )

        resp = await client.get("/admin/api/sandboxes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_filter_by_state(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="SUSPENDED")

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(1),
                _make_result_scalars_all([sb]),
            ]
        )

        resp = await client.get("/admin/api/sandboxes", params={"state": "SUSPENDED"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_db):
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(0),
                _make_result_scalars_all([]),
            ]
        )

        resp = await client.get("/admin/api/sandboxes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []


class TestGetSandbox:
    @pytest.mark.asyncio
    async def test_returns_sandbox(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))

        resp = await client.get(f"/admin/api/sandboxes/{sb.id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(sb.id)

    @pytest.mark.asyncio
    async def test_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.get(f"/admin/api/sandboxes/{uuid.uuid4()}")

        assert resp.status_code == 404


class TestSuspendSandbox:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_suspend_active_sandbox(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))
        mock_osh.suspend_sandbox = AsyncMock()

        resp = await client.post(f"/admin/api/sandboxes/{sb.id}/suspend")

        assert resp.status_code == 200
        assert sb.state == "SUSPENDED"
        mock_osh.suspend_sandbox.assert_awaited_once_with(sb.name)

    @pytest.mark.asyncio
    async def test_suspend_wrong_state_returns_409(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="DESTROYED")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))

        resp = await client.post(f"/admin/api/sandboxes/{sb.id}/suspend")

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_suspend_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.post(f"/admin/api/sandboxes/{uuid.uuid4()}/suspend")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_suspend_openshell_failure_returns_502(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))
        mock_osh.suspend_sandbox = AsyncMock(side_effect=RuntimeError("connection refused"))

        resp = await client.post(f"/admin/api/sandboxes/{sb.id}/suspend")

        assert resp.status_code == 502


class TestResumeSandbox:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_resume_suspended_sandbox(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        sb = make_sandbox(state="SUSPENDED")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))
        mock_osh.resume_sandbox = AsyncMock(return_value=SimpleNamespace(internal_ip="10.0.0.99"))

        resp = await client.post(f"/admin/api/sandboxes/{sb.id}/resume")

        assert resp.status_code == 200
        assert sb.state == "ACTIVE"
        assert sb.internal_ip == "10.0.0.99"

    @pytest.mark.asyncio
    async def test_resume_non_suspended_returns_409(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))

        resp = await client.post(f"/admin/api/sandboxes/{sb.id}/resume")

        assert resp.status_code == 409


class TestDestroySandbox:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_destroy_sandbox(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))
        mock_osh.destroy_sandbox = AsyncMock()

        resp = await client.delete(f"/admin/api/sandboxes/{sb.id}")

        assert resp.status_code == 200
        assert sb.state == "DESTROYED"
        assert sb.destroyed_at is not None

    @pytest.mark.asyncio
    async def test_destroy_already_destroyed_returns_409(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="DESTROYED")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))

        resp = await client.delete(f"/admin/api/sandboxes/{sb.id}")

        assert resp.status_code == 409

    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_destroy_openshell_failure_still_marks_destroyed(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        """Even if openshell fails, the sandbox is marked DESTROYED."""
        sb = make_sandbox(state="ACTIVE")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(sb))
        mock_osh.destroy_sandbox = AsyncMock(side_effect=RuntimeError("timeout"))

        resp = await client.delete(f"/admin/api/sandboxes/{sb.id}")

        assert resp.status_code == 200
        assert sb.state == "DESTROYED"


class TestUpdateSandboxPolicy:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.apply_policy_to_sandbox")
    async def test_update_policy_on_active_sandbox(self, mock_apply, mock_log, client, mock_db, make_sandbox, make_policy):
        sb = make_sandbox(state="ACTIVE")
        policy = make_policy(name="strict")
        mock_apply.return_value = None

        # First call: sandbox lookup, second: policy lookup
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(sb),
                _make_result_scalar_one_or_none(policy),
            ]
        )

        resp = await client.post(
            f"/admin/api/sandboxes/{sb.id}/policy",
            json={"policy_id": str(policy.id)},
        )

        assert resp.status_code == 200
        mock_apply.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_policy_sandbox_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.post(
            f"/admin/api/sandboxes/{uuid.uuid4()}/policy",
            json={"policy_id": str(uuid.uuid4())},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_policy_not_found(self, client, mock_db, make_sandbox):
        sb = make_sandbox(state="ACTIVE")

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(sb),
                _make_result_scalar_one_or_none(None),
            ]
        )

        resp = await client.post(
            f"/admin/api/sandboxes/{sb.id}/policy",
            json={"policy_id": str(uuid.uuid4())},
        )

        assert resp.status_code == 404


class TestSandboxLogs:
    @pytest.mark.asyncio
    async def test_returns_paginated_logs(self, client, mock_db, make_audit_entry):
        entry = make_audit_entry()

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one(1),
                _make_result_scalars_all([entry]),
            ]
        )

        resp = await client.get(f"/admin/api/sandboxes/{uuid.uuid4()}/logs")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1


class TestPoolStatus:
    @pytest.mark.asyncio
    async def test_returns_pool_counts(self, client, mock_db, make_system_config):
        cfg = make_system_config(
            key="pool",
            value={"max_sandboxes": 20, "max_active": 10, "warmup_size": 2},
        )

        # First call: state counts; second call: config lookup
        state_result = MagicMock()
        state_result.all.return_value = [("ACTIVE", 3), ("READY", 2)]

        mock_db.execute = AsyncMock(
            side_effect=[
                state_result,
                _make_result_scalar_one_or_none(cfg),
            ]
        )

        resp = await client.get("/admin/api/pool")

        assert resp.status_code == 200
        data = resp.json()
        assert data["active"] == 3
        assert data["ready"] == 2
        assert data["max_sandboxes"] == 20


class TestUpdatePool:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    async def test_update_pool_config(self, mock_log, client, mock_db, make_system_config):
        cfg = make_system_config(key="pool", value={"warmup_size": 2})
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(cfg))

        resp = await client.put(
            "/admin/api/pool",
            json={"value": {"warmup_size": 5, "max_sandboxes": 30}},
        )

        assert resp.status_code == 200
        assert cfg.value == {"warmup_size": 5, "max_sandboxes": 30}
