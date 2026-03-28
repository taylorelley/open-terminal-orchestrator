"""Unit tests for the webhook service."""

import hashlib
import hmac
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.webhook_service import (
    WebhookConfig,
    WebhookEventFilter,
    _deliver,
    _sign_payload,
    dispatch_webhooks,
    invalidate_cache,
    matches_filters,
)


# ---------------------------------------------------------------------------
# Filter matching
# ---------------------------------------------------------------------------


class TestMatchesFilters:
    def test_empty_filters_matches_all(self):
        wh = WebhookConfig(url="https://example.com", event_filters=[])
        assert matches_filters(wh, "lifecycle", "assigned") is True

    def test_category_match(self):
        wh = WebhookConfig(
            url="https://example.com",
            event_filters=[WebhookEventFilter(category="lifecycle")],
        )
        assert matches_filters(wh, "lifecycle", "assigned") is True
        assert matches_filters(wh, "admin", "config_change") is False

    def test_event_type_match(self):
        wh = WebhookConfig(
            url="https://example.com",
            event_filters=[WebhookEventFilter(event_type="assigned")],
        )
        assert matches_filters(wh, "lifecycle", "assigned") is True
        assert matches_filters(wh, "lifecycle", "destroyed") is False

    def test_both_category_and_event_type(self):
        wh = WebhookConfig(
            url="https://example.com",
            event_filters=[WebhookEventFilter(category="lifecycle", event_type="assigned")],
        )
        assert matches_filters(wh, "lifecycle", "assigned") is True
        assert matches_filters(wh, "lifecycle", "destroyed") is False
        assert matches_filters(wh, "admin", "assigned") is False

    def test_multiple_filters_or_logic(self):
        wh = WebhookConfig(
            url="https://example.com",
            event_filters=[
                WebhookEventFilter(category="lifecycle"),
                WebhookEventFilter(event_type="config_change"),
            ],
        )
        assert matches_filters(wh, "lifecycle", "assigned") is True
        assert matches_filters(wh, "admin", "config_change") is True
        assert matches_filters(wh, "enforcement", "policy_applied") is False

    def test_none_filter_fields_match_any(self):
        wh = WebhookConfig(
            url="https://example.com",
            event_filters=[WebhookEventFilter(category=None, event_type=None)],
        )
        assert matches_filters(wh, "anything", "anything") is True


# ---------------------------------------------------------------------------
# HMAC signature
# ---------------------------------------------------------------------------


class TestSignPayload:
    def test_signature_correctness(self):
        secret = "my-secret"
        body = b'{"event":"test"}'
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        assert _sign_payload(secret, body) == expected

    def test_empty_secret(self):
        sig = _sign_payload("", b"data")
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


class TestDeliver:
    @pytest.mark.asyncio
    @patch("app.services.webhook_service._http_client")
    async def test_success_on_first_attempt(self, mock_client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client.post = AsyncMock(return_value=mock_resp)

        wh = WebhookConfig(url="https://example.com/hook", secret="sec")
        with patch("app.metrics.record_webhook_delivery") as mock_record:
            await _deliver(wh, {"event": "test"})
            mock_record.assert_called_once_with("success", wh.url)

    @pytest.mark.asyncio
    @patch("app.services.webhook_service._http_client")
    async def test_retry_then_success(self, mock_client):
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        ok_resp = MagicMock()
        ok_resp.status_code = 200
        mock_client.post = AsyncMock(side_effect=[fail_resp, ok_resp])

        wh = WebhookConfig(url="https://example.com/hook")
        with patch("app.metrics.record_webhook_delivery") as mock_record:
            await _deliver(wh, {"event": "test"})
            # Should record success on second attempt
            calls = [c.args for c in mock_record.call_args_list]
            assert ("success", wh.url) in calls

    @pytest.mark.asyncio
    @patch("app.services.webhook_service._http_client")
    async def test_exhausts_retries(self, mock_client):
        fail_resp = MagicMock()
        fail_resp.status_code = 500
        mock_client.post = AsyncMock(return_value=fail_resp)

        wh = WebhookConfig(url="https://example.com/hook")
        with patch("app.metrics.record_webhook_delivery") as mock_record:
            await _deliver(wh, {"event": "test"})
            calls = [c.args for c in mock_record.call_args_list]
            assert ("failure", wh.url) in calls

    @pytest.mark.asyncio
    @patch("app.services.webhook_service._http_client")
    async def test_connection_error_retries(self, mock_client):
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        wh = WebhookConfig(url="https://example.com/hook")
        with patch("app.metrics.record_webhook_delivery") as mock_record:
            await _deliver(wh, {"event": "test"})
            calls = [c.args for c in mock_record.call_args_list]
            assert ("failure", wh.url) in calls

    @pytest.mark.asyncio
    async def test_no_client_skips_delivery(self):
        """When the HTTP client is not initialized, delivery is skipped."""
        wh = WebhookConfig(url="https://example.com/hook")
        with patch("app.services.webhook_service._http_client", None):
            # Should not raise
            await _deliver(wh, {"event": "test"})


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


class TestDispatchWebhooks:
    @pytest.mark.asyncio
    async def test_skips_disabled_webhooks(self):
        wh_disabled = WebhookConfig(url="https://a.com", enabled=False)
        wh_enabled = WebhookConfig(url="https://b.com", enabled=True)

        with (
            patch("app.services.webhook_service._load_webhooks", return_value=[wh_disabled, wh_enabled]),
            patch("app.services.webhook_service._deliver", new_callable=AsyncMock) as mock_deliver,
            patch("asyncio.create_task") as mock_task,
        ):
            await dispatch_webhooks("lifecycle", "assigned", {}, "2026-01-01T00:00:00Z")
            # Only the enabled webhook should get a task
            assert mock_task.call_count == 1

    @pytest.mark.asyncio
    async def test_filters_by_category(self):
        wh = WebhookConfig(
            url="https://a.com",
            event_filters=[WebhookEventFilter(category="admin")],
        )

        with (
            patch("app.services.webhook_service._load_webhooks", return_value=[wh]),
            patch("asyncio.create_task") as mock_task,
        ):
            await dispatch_webhooks("lifecycle", "assigned", {}, "2026-01-01T00:00:00Z")
            assert mock_task.call_count == 0

            await dispatch_webhooks("admin", "config_change", {}, "2026-01-01T00:00:00Z")
            assert mock_task.call_count == 1


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_invalidate_cache(self):
        """invalidate_cache should clear the module-level cache."""
        import app.services.webhook_service as ws

        ws._config_cache = (0.0, [])
        invalidate_cache()
        assert ws._config_cache is None
