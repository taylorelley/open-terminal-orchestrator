"""Integration tests for webhook CRUD endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_result_scalar_one_or_none(item):
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


class TestWebhookCRUD:
    """Test webhook CRUD operations via the admin API."""

    @pytest.mark.asyncio
    async def test_list_webhooks_empty(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))
        resp = await client.get("/admin/api/webhooks")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_webhooks_with_data(self, client, mock_db):
        cfg = SimpleNamespace(
            key="webhooks",
            value={"webhooks": [
                {"url": "https://a.com", "secret": "s", "enabled": True, "event_filters": []},
            ]},
            updated_at="2026-01-01T00:00:00Z",
            updated_by=None,
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(cfg))
        resp = await client.get("/admin/api/webhooks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["url"] == "https://a.com"
        assert data[0]["index"] == 0
        # Secret should not be in response
        assert "secret" not in data[0]

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_create_webhook(self, mock_log, client, mock_db):
        # First call: load existing (none), second call: flush
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.post("/admin/api/webhooks", json={
            "url": "https://new.com/hook",
            "secret": "my-secret",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://new.com/hook"
        assert data["index"] == 0

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_delete_webhook_not_found(self, mock_log, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))
        resp = await client.delete("/admin/api/webhooks/0")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_update_webhook(self, mock_log, client, mock_db):
        cfg = SimpleNamespace(
            key="webhooks",
            value={"webhooks": [
                {"url": "https://old.com", "secret": "s", "enabled": True, "event_filters": []},
            ]},
            updated_at="2026-01-01T00:00:00Z",
            updated_by=None,
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(cfg))

        resp = await client.put("/admin/api/webhooks/0", json={"url": "https://updated.com"})
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://updated.com"

    @pytest.mark.asyncio
    @patch("app.routes.system.log_admin")
    async def test_delete_webhook(self, mock_log, client, mock_db):
        cfg = SimpleNamespace(
            key="webhooks",
            value={"webhooks": [
                {"url": "https://del.com", "secret": "s", "enabled": True, "event_filters": []},
            ]},
            updated_at="2026-01-01T00:00:00Z",
            updated_by=None,
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(cfg))

        resp = await client.delete("/admin/api/webhooks/0")
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"
