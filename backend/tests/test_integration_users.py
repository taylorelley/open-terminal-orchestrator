"""Integration tests for the users & groups API routes (/admin/api/users/*, /admin/api/groups/*)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    _make_result_scalar_one_or_none,
    _make_result_scalars_all,
)


class TestListUsers:
    @pytest.mark.asyncio
    async def test_returns_users(self, client, mock_db, make_user):
        u1 = make_user(username="alice")
        u2 = make_user(username="bob")

        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([u1, u2]))

        resp = await client.get("/admin/api/users")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["username"] == "alice"

    @pytest.mark.asyncio
    async def test_empty_users(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([]))

        resp = await client.get("/admin/api/users")

        assert resp.status_code == 200
        assert resp.json() == []


class TestUserSync:
    @pytest.mark.asyncio
    @patch("app.routes.users.log_admin")
    @patch("app.routes.users.sync_users_from_owui")
    async def test_sync_success(self, mock_sync, mock_log, client, mock_db):
        mock_sync.return_value = {
            "created": 5,
            "updated": 2,
            "unchanged": 10,
            "total_remote": 17,
            "message": "",
        }

        resp = await client.post("/admin/api/users/sync")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["created"] == 5
        assert data["total_remote"] == 17


class TestListGroups:
    @pytest.mark.asyncio
    async def test_returns_groups(self, client, mock_db, make_group):
        g1 = make_group(name="admins")
        g2 = make_group(name="users")

        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([g1, g2]))

        resp = await client.get("/admin/api/groups")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2


class TestCreateGroup:
    @pytest.mark.asyncio
    @patch("app.routes.users.log_admin")
    async def test_create_group(self, mock_log, client, mock_db):
        added = []
        mock_db.add = lambda obj: added.append(obj)

        async def mock_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()
            if not hasattr(obj, "policy"):
                obj.policy = None
            if not hasattr(obj, "members"):
                obj.members = []

        mock_db.refresh = mock_refresh

        resp = await client.post(
            "/admin/api/groups",
            json={"name": "new-group", "description": "A test group"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-group"
        assert data["description"] == "A test group"


class TestUpdateGroup:
    @pytest.mark.asyncio
    @patch("app.routes.users.log_admin")
    async def test_update_group_name(self, mock_log, client, mock_db, make_group):
        g = make_group(name="old-name")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(g))

        resp = await client.put(
            f"/admin/api/groups/{g.id}",
            json={"name": "new-name"},
        )

        assert resp.status_code == 200
        assert g.name == "new-name"

    @pytest.mark.asyncio
    async def test_update_group_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.put(
            f"/admin/api/groups/{uuid.uuid4()}",
            json={"name": "x"},
        )

        assert resp.status_code == 404


class TestDeleteGroup:
    @pytest.mark.asyncio
    @patch("app.routes.users.log_admin")
    async def test_delete_group(self, mock_log, client, mock_db, make_group):
        g = make_group()
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(g))

        resp = await client.delete(f"/admin/api/groups/{g.id}")

        assert resp.status_code == 204
        mock_db.delete.assert_awaited_once_with(g)

    @pytest.mark.asyncio
    async def test_delete_group_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.delete(f"/admin/api/groups/{uuid.uuid4()}")

        assert resp.status_code == 404
