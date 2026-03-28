"""Unit tests for sandbox resolver — user identity extraction and state transitions.

Tests cover:
- User identity extraction from request headers
- Proxy API key validation
- Sandbox resolution state machine transitions
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.sandbox_resolver import (
    _extract_owui_id,
    _validate_proxy_api_key,
    resolve_sandbox,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class _MockHeaders(dict):
    """Dict subclass that mimics Starlette Headers (case-sensitive get)."""
    pass


def _make_request(headers: dict | None = None) -> MagicMock:
    """Create a mock FastAPI Request with given headers."""
    request = MagicMock()
    request.headers = _MockHeaders(headers or {})
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    return request


# ===================================================================
# _extract_owui_id
# ===================================================================


class TestExtractOwuiId:
    """Tests for user identity extraction from request headers."""

    def test_extracts_from_owui_header(self):
        """Should extract user ID from X-Open-WebUI-User-Id header."""
        request = _make_request({"X-Open-WebUI-User-Id": "user-123"})
        assert _extract_owui_id(request) == "user-123"

    def test_falls_back_to_bearer_token(self):
        """Should use Bearer token when OWUI header is missing."""
        request = _make_request({"Authorization": "Bearer token-abc"})
        assert _extract_owui_id(request) == "token-abc"

    def test_prefers_owui_header_over_bearer(self):
        """OWUI header should take precedence over Bearer token."""
        request = _make_request({
            "X-Open-WebUI-User-Id": "user-123",
            "Authorization": "Bearer token-abc",
        })
        assert _extract_owui_id(request) == "user-123"

    def test_raises_401_when_no_identity(self):
        """Should raise 401 when neither header is present."""
        request = _make_request({})
        with pytest.raises(HTTPException) as exc_info:
            _extract_owui_id(request)
        assert exc_info.value.status_code == 401

    def test_raises_401_for_empty_bearer(self):
        """Should raise 401 when Authorization header is just 'Bearer '."""
        request = _make_request({"Authorization": "Bearer "})
        with pytest.raises(HTTPException) as exc_info:
            _extract_owui_id(request)
        assert exc_info.value.status_code == 401


# ===================================================================
# _validate_proxy_api_key
# ===================================================================


class TestValidateProxyApiKey:
    """Tests for proxy API key validation."""

    @patch("app.services.sandbox_resolver.settings")
    def test_passes_when_no_key_configured(self, mock_settings):
        """Should pass when open_webui_api_key is empty."""
        mock_settings.open_webui_api_key = ""
        request = _make_request({})
        _validate_proxy_api_key(request)  # Should not raise

    @patch("app.services.sandbox_resolver.settings")
    def test_passes_with_matching_key(self, mock_settings):
        """Should pass when X-API-Key matches configured key."""
        mock_settings.open_webui_api_key = "secret-key"
        request = _make_request({"X-API-Key": "secret-key"})
        _validate_proxy_api_key(request)  # Should not raise

    @patch("app.services.sandbox_resolver.settings")
    def test_raises_401_with_wrong_key(self, mock_settings):
        """Should raise 401 when X-API-Key doesn't match."""
        mock_settings.open_webui_api_key = "secret-key"
        request = _make_request({"X-API-Key": "wrong-key"})
        with pytest.raises(HTTPException) as exc_info:
            _validate_proxy_api_key(request)
        assert exc_info.value.status_code == 401

    @patch("app.services.sandbox_resolver.settings")
    def test_raises_401_with_missing_key(self, mock_settings):
        """Should raise 401 when X-API-Key is missing but configured."""
        mock_settings.open_webui_api_key = "secret-key"
        request = _make_request({})
        with pytest.raises(HTTPException) as exc_info:
            _validate_proxy_api_key(request)
        assert exc_info.value.status_code == 401


# ===================================================================
# resolve_sandbox — state transitions
# ===================================================================


class TestResolveSandbox:
    """Tests for sandbox resolution and state machine transitions."""

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver.apply_policy_to_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver.resolve_policy_for_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_active_sandbox_returns_directly(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_resolve_policy, mock_apply_policy, make_sandbox, make_user,
    ):
        """ACTIVE sandbox should update last_active_at and return."""
        user = make_user()
        sandbox = make_sandbox(state="ACTIVE", user_id=user.id)
        old_active = sandbox.last_active_at

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox
        mock_resolve_policy.return_value = None

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        result = await resolve_sandbox(request, db)

        assert result.sandbox is sandbox
        assert result.user is user
        assert result.sandbox.state == "ACTIVE"

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver.apply_policy_to_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver.resolve_policy_for_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_ready_sandbox_transitions_to_active(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_resolve_policy, mock_apply_policy, make_sandbox, make_user,
    ):
        """READY sandbox should transition to ACTIVE."""
        user = make_user()
        sandbox = make_sandbox(state="READY", user_id=user.id)

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox
        mock_resolve_policy.return_value = None

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        result = await resolve_sandbox(request, db)

        assert result.sandbox.state == "ACTIVE"

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver.asyncio")
    @patch("app.services.sandbox_resolver.log_lifecycle")
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_suspended_sandbox_transitions_to_warming(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_log, mock_asyncio, make_sandbox, make_user,
    ):
        """SUSPENDED sandbox should transition to WARMING and raise 202."""
        user = make_user()
        sandbox = make_sandbox(
            state="SUSPENDED",
            user_id=user.id,
            suspended_at=_utcnow() - timedelta(hours=1),
        )

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox
        mock_asyncio.create_task = MagicMock()

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        with pytest.raises(HTTPException) as exc_info:
            await resolve_sandbox(request, db)

        assert exc_info.value.status_code == 202
        assert sandbox.state == "WARMING"
        assert sandbox.warming_started_at is not None
        # Background resume task should be created
        mock_asyncio.create_task.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_warming_sandbox_raises_202(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        make_sandbox, make_user,
    ):
        """WARMING sandbox should raise 202 (already provisioning)."""
        user = make_user()
        sandbox = make_sandbox(
            state="WARMING",
            user_id=user.id,
            warming_started_at=_utcnow(),
        )

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        with pytest.raises(HTTPException) as exc_info:
            await resolve_sandbox(request, db)

        assert exc_info.value.status_code == 202
        assert "provisioning" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver._claim_pool_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_no_sandbox_claims_from_pool(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_claim, make_sandbox, make_user,
    ):
        """User with no sandbox should get one claimed from the pool."""
        user = make_user()
        pool_sandbox = make_sandbox(state="ACTIVE", user_id=user.id)

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = None  # no existing sandbox
        mock_claim.return_value = pool_sandbox

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        result = await resolve_sandbox(request, db)

        assert result.sandbox is pool_sandbox
        mock_claim.assert_called_once_with(user, db)

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver._claim_pool_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_no_sandbox_empty_pool_raises_503(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_claim, make_user,
    ):
        """No sandbox and empty pool should raise 503."""
        user = make_user()

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = None
        mock_claim.return_value = None

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        with pytest.raises(HTTPException) as exc_info:
            await resolve_sandbox(request, db)

        assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver._recreate_sandbox_for_policy", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver.resolve_policy_for_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_pending_recreation_triggers_recreate(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_resolve_policy, mock_recreate, make_sandbox, make_user,
    ):
        """ACTIVE sandbox with pending_recreation should trigger recreation."""
        user = make_user()
        sandbox = make_sandbox(state="ACTIVE", user_id=user.id, pending_recreation=True)
        new_sandbox = make_sandbox(state="ACTIVE", user_id=user.id)

        from app.services.sandbox_resolver import ResolvedSandbox

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox
        mock_recreate.return_value = ResolvedSandbox(sandbox=new_sandbox, user=user)

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        result = await resolve_sandbox(request, db)

        mock_recreate.assert_called_once()
        assert result.sandbox is new_sandbox

    @pytest.mark.asyncio
    @patch("app.services.sandbox_resolver.apply_policy_to_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver.resolve_policy_for_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._find_user_sandbox", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._get_or_create_user", new_callable=AsyncMock)
    @patch("app.services.sandbox_resolver._validate_proxy_api_key")
    @patch("app.services.sandbox_resolver._extract_owui_id")
    async def test_policy_recheck_on_active_sandbox(
        self, mock_extract, mock_validate, mock_get_user, mock_find,
        mock_resolve_policy, mock_apply_policy, make_sandbox, make_user,
    ):
        """Should re-apply policy if it changed since last session."""
        user = make_user()
        old_policy_id = uuid.uuid4()
        new_policy_id = uuid.uuid4()
        sandbox = make_sandbox(state="ACTIVE", user_id=user.id)
        sandbox.policy_id = old_policy_id

        new_policy = MagicMock()
        new_policy.id = new_policy_id

        mock_extract.return_value = user.owui_id
        mock_get_user.return_value = user
        mock_find.return_value = sandbox
        mock_resolve_policy.return_value = new_policy

        db = AsyncMock()
        request = _make_request({"X-Open-WebUI-User-Id": user.owui_id})

        result = await resolve_sandbox(request, db)

        mock_apply_policy.assert_called_once()
        assert result.sandbox is sandbox
