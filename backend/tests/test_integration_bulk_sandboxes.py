"""Integration tests for the bulk sandbox action endpoint (POST /admin/api/sandboxes/bulk)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import _make_result_scalar_one_or_none


class TestBulkSuspend:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_bulk_suspend(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        """Suspends multiple active sandboxes."""
        sb1 = make_sandbox(state="ACTIVE")
        sb2 = make_sandbox(state="ACTIVE")

        # Each sandbox gets a separate execute call for its lookup
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(sb1),
                _make_result_scalar_one_or_none(sb2),
            ]
        )
        mock_osh.suspend_sandbox = AsyncMock()

        resp = await client.post(
            "/admin/api/sandboxes/bulk",
            json={"action": "suspend", "sandbox_ids": [str(sb1.id), str(sb2.id)]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2
        assert all(r["status"] == "ok" for r in data["results"])
        assert sb1.state == "SUSPENDED"
        assert sb2.state == "SUSPENDED"


class TestBulkDestroy:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_bulk_destroy(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        """Destroys multiple sandboxes."""
        sb1 = make_sandbox(state="ACTIVE")
        sb2 = make_sandbox(state="SUSPENDED")

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(sb1),
                _make_result_scalar_one_or_none(sb2),
            ]
        )
        mock_osh.destroy_sandbox = AsyncMock()

        resp = await client.post(
            "/admin/api/sandboxes/bulk",
            json={"action": "destroy", "sandbox_ids": [str(sb1.id), str(sb2.id)]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert sb1.state == "DESTROYED"
        assert sb2.state == "DESTROYED"
        assert sb1.destroyed_at is not None
        assert sb2.destroyed_at is not None


class TestInvalidAction:
    @pytest.mark.asyncio
    async def test_invalid_action(self, client, mock_db, make_sandbox):
        """Returns 400 for an invalid action."""
        sb = make_sandbox(state="ACTIVE")

        resp = await client.post(
            "/admin/api/sandboxes/bulk",
            json={"action": "reboot", "sandbox_ids": [str(sb.id)]},
        )

        assert resp.status_code == 400
        assert "Invalid action" in resp.json()["detail"]


class TestEmptyList:
    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_db):
        """Returns success with 0 results for an empty sandbox_ids list."""
        resp = await client.post(
            "/admin/api/sandboxes/bulk",
            json={"action": "suspend", "sandbox_ids": []},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 0
        assert data["failed"] == 0
        assert data["results"] == []


class TestMixedResults:
    @pytest.mark.asyncio
    @patch("app.routes.sandboxes.log_admin")
    @patch("app.routes.sandboxes.openshell_client")
    async def test_mixed_results(self, mock_osh, mock_log, client, mock_db, make_sandbox):
        """Some succeed, some fail (not found)."""
        sb_exists = make_sandbox(state="ACTIVE")
        missing_id = uuid.uuid4()

        # First lookup finds the sandbox, second returns None (not found)
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(sb_exists),
                _make_result_scalar_one_or_none(None),
            ]
        )
        mock_osh.suspend_sandbox = AsyncMock()

        resp = await client.post(
            "/admin/api/sandboxes/bulk",
            json={"action": "suspend", "sandbox_ids": [str(sb_exists.id), str(missing_id)]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        results_by_id = {r["sandbox_id"]: r for r in data["results"]}
        assert results_by_id[str(sb_exists.id)]["status"] == "ok"
        assert results_by_id[str(missing_id)]["status"] == "error"
        assert "Not found" in results_by_id[str(missing_id)]["error"]
