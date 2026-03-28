"""Integration tests for the proxy API routes (/api/*)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import StreamingResponse


def _make_resolved(ip: str = "10.0.0.1") -> SimpleNamespace:
    """Create a mock resolved sandbox result."""
    return SimpleNamespace(
        sandbox=SimpleNamespace(internal_ip=ip, name="sg-test-1"),
        user=SimpleNamespace(owui_id="user-1"),
    )


def _make_stream_response(body: bytes = b'{"ok":true}', status: int = 200) -> StreamingResponse:
    return StreamingResponse(iter([body]), status_code=status, media_type="application/json")


class TestProxyRouting:
    """Verify that each proxy endpoint resolves a sandbox and forwards the request."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_execute_forwards_to_sandbox(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response()

        resp = await client.post("/api/execute", json={"command": "ls"})

        assert resp.status_code == 200
        mock_resolve.assert_awaited_once()
        mock_forward.assert_awaited_once()
        # Verify the forward was called with the sandbox IP and correct path
        call_args = mock_forward.call_args
        assert call_args[0][1] == "10.0.0.1"
        assert call_args[0][2] == "/api/execute"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_list_files_forwards(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b'[{"name":"file.txt"}]')

        resp = await client.get("/api/files")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_read_file_with_path(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b"file contents")

        resp = await client.get("/api/files/home/user/test.txt")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files/home/user/test.txt"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_write_file(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response()

        resp = await client.put("/api/files/tmp/out.txt", content=b"data")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files/tmp/out.txt"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_delete_file(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response()

        resp = await client.delete("/api/files/tmp/old.log")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files/tmp/old.log"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_upload_file(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response()

        resp = await client.post("/api/files/upload", content=b"filedata")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files/upload"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_download_file(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b"binary")

        resp = await client.get("/api/files/download/data/export.csv")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/files/download/data/export.csv"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_search(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b"[]")

        resp = await client.get("/api/search", params={"q": "hello"})

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/api/search"


class TestLLMProxyRouting:
    """Verify LiteLLM proxy endpoints resolve a sandbox and forward the request."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_chat_completions_forwards(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b'{"choices":[]}')

        resp = await client.post("/v1/chat/completions", json={"model": "gpt-4", "messages": []})

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][1] == "10.0.0.1"
        assert call_args[0][2] == "/v1/chat/completions"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_completions_forwards(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b'{"choices":[]}')

        resp = await client.post("/v1/completions", json={"model": "gpt-4", "prompt": "Hello"})

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/v1/completions"

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_list_models_forwards(self, mock_resolve, mock_forward, client):
        mock_resolve.return_value = _make_resolved()
        mock_forward.return_value = _make_stream_response(b'{"data":[]}')

        resp = await client.get("/v1/models")

        assert resp.status_code == 200
        call_args = mock_forward.call_args
        assert call_args[0][2] == "/v1/models"


class TestProxyErrors:
    """Verify error handling in the proxy layer."""

    @pytest.mark.asyncio
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_no_user_header_returns_401(self, mock_resolve, client):
        """When resolve_sandbox raises 401, the proxy returns 401."""
        mock_resolve.side_effect = HTTPException(status_code=401, detail="Missing user identity")

        resp = await client.post("/api/execute", json={"command": "ls"})

        assert resp.status_code == 401

    @pytest.mark.asyncio
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_sandbox_not_ready_returns_202(self, mock_resolve, client):
        """When resolve_sandbox raises 202, the proxy returns 202 with Retry-After."""
        mock_resolve.side_effect = HTTPException(
            status_code=202,
            detail="Sandbox is warming up",
            headers={"Retry-After": "5"},
        )

        resp = await client.post("/api/execute", json={"command": "ls"})

        assert resp.status_code == 202

    @pytest.mark.asyncio
    @patch("app.routes.proxy.forward_request")
    @patch("app.routes.proxy.resolve_sandbox")
    async def test_forward_failure_returns_502(self, mock_resolve, mock_forward, client):
        """When forward_request raises a connection error, the proxy returns 502."""
        mock_resolve.return_value = _make_resolved()
        mock_forward.side_effect = HTTPException(status_code=502, detail="Sandbox unreachable")

        resp = await client.post("/api/execute", json={"command": "ls"})

        assert resp.status_code == 502
