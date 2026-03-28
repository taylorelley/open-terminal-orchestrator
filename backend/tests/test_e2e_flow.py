"""E2E-style integration tests for the proxy request flow.

Tests cover the full request path: user request -> sandbox resolution ->
command execution -> response, exercising the proxy endpoint with mocked
openshell and proxy_client dependencies.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def _make_resolved(ip: str = "10.0.0.1", sandbox_name: str = "sg-test-1") -> SimpleNamespace:
    """Create a mock resolved sandbox result."""
    return SimpleNamespace(
        sandbox=SimpleNamespace(internal_ip=ip, name=sandbox_name),
        user=SimpleNamespace(owui_id="user-1"),
    )


def _make_stream_response(body: bytes = b'{"output":"hello"}', status: int = 200) -> StreamingResponse:
    return StreamingResponse(iter([body]), status_code=status, media_type="application/json")


class TestE2EHappyPath:
    """Full happy-path: POST /api/execute resolves a sandbox and forwards the command."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_happy_path(self, mock_resolve, mock_forward, client):
        """User request -> sandbox resolved from pool -> command executed -> response."""
        mock_resolve.return_value = _make_resolved(ip="10.0.0.42", sandbox_name="sg-user-abc")
        mock_forward.return_value = _make_stream_response(b'{"output":"listing files..."}')

        resp = await client.post("/api/execute", json={"command": "ls -la"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["output"] == "listing files..."

        # Verify resolve was called
        mock_resolve.assert_awaited_once()

        # Verify forward was called with the correct sandbox IP and path
        mock_forward.assert_awaited_once()
        call_args = mock_forward.call_args
        assert call_args[0][1] == "10.0.0.42"
        assert call_args[0][2] == "/api/execute"


class TestE2ENoPoolAvailable:
    """All sandboxes at max capacity -- expect 503."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_no_pool_available(self, mock_resolve, client):
        """When no sandbox is available in the pool, resolve_sandbox raises 503."""
        mock_resolve.side_effect = HTTPException(
            status_code=503,
            detail="No sandbox available",
        )

        resp = await client.post("/api/execute", json={"command": "whoami"})

        assert resp.status_code == 503
        mock_resolve.assert_awaited_once()


class TestE2ESandboxSuspended:
    """User's sandbox is SUSPENDED -- expect 202 with Retry-After."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_sandbox_suspended(self, mock_resolve, client):
        """SUSPENDED sandbox triggers 202 with Retry-After header."""
        mock_resolve.side_effect = HTTPException(
            status_code=202,
            detail="Sandbox is resuming",
            headers={"Retry-After": "5"},
        )

        resp = await client.post("/api/execute", json={"command": "echo hi"})

        assert resp.status_code == 202
        mock_resolve.assert_awaited_once()


class TestE2EPolicyDeny:
    """Request triggers a policy deny -- expect 403."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_policy_deny(self, mock_resolve, mock_forward, client):
        """When the sandbox enforces a policy deny, forward returns 403."""
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(
            body=b'{"error":"policy denied: command not allowed"}',
            status=403,
        )

        resp = await client.post("/api/execute", json={"command": "rm -rf /"})

        assert resp.status_code == 403
        body = resp.json()
        assert "denied" in body["error"]

        mock_resolve.assert_awaited_once()
        mock_forward.assert_awaited_once()
