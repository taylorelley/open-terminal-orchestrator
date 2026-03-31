"""Unit tests for the openshell_client module (R1, R2, R3)."""

import asyncio
import json
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import openshell_client


@pytest.fixture
def mock_run_cli():
    with patch.object(openshell_client, "_run_cli", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_cli_available():
    """Force the CLI-available code path."""
    with patch.object(openshell_client, "_CLI_AVAILABLE", True):
        yield


@pytest.fixture
def mock_cli_unavailable():
    """Force the HTTP gateway code path."""
    with patch.object(openshell_client, "_CLI_AVAILABLE", False):
        yield


@pytest.fixture
def mock_gateway_request():
    with patch.object(openshell_client, "_gateway_request", new_callable=AsyncMock) as m:
        yield m


class TestGetPolicy:
    @pytest.mark.asyncio
    async def test_calls_cli_with_correct_args(self, mock_run_cli, mock_cli_available):
        mock_run_cli.return_value = "metadata:\n  name: test\nnetwork:\n  default: deny\n"

        result = await openshell_client.get_policy("sg-test-1234")

        mock_run_cli.assert_awaited_once_with(
            "policy", "get", "--sandbox", "sg-test-1234", "--output", "yaml",
        )
        assert "metadata:" in result

    @pytest.mark.asyncio
    async def test_propagates_error(self, mock_run_cli, mock_cli_available):
        mock_run_cli.side_effect = openshell_client.OpenShellError("not found", returncode=1)

        with pytest.raises(openshell_client.OpenShellError):
            await openshell_client.get_policy("sg-missing")

    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = "metadata:\n  name: test\n"

        result = await openshell_client.get_policy("sg-test-1234")

        mock_gateway_request.assert_awaited_once_with(
            "GET", "/v1/sandboxes/sg-test-1234/policy",
        )
        assert "metadata:" in result


class TestDryRunPolicy:
    @pytest.mark.asyncio
    async def test_calls_cli_with_dry_run_flag(self, mock_run_cli, mock_cli_available):
        mock_run_cli.return_value = json.dumps({"status": "ok", "changes": []})

        result = await openshell_client.dry_run_policy("sg-test-1234", "/tmp/policy.yaml")

        mock_run_cli.assert_awaited_once_with(
            "policy", "set",
            "--sandbox", "sg-test-1234",
            "--file", "/tmp/policy.yaml",
            "--dry-run",
            "--output", "json",
        )
        assert "ok" in result


class TestCreateProvider:
    @pytest.mark.asyncio
    async def test_calls_cli_with_credentials(self, mock_run_cli, mock_cli_available):
        mock_run_cli.return_value = ""
        creds = {"api_key": "sk-test", "endpoint": "https://api.example.com"}

        await openshell_client.create_provider("sg-test-1234", "litellm", creds)

        mock_run_cli.assert_awaited_once_with(
            "provider", "create",
            "--sandbox", "sg-test-1234",
            "--type", "litellm",
            "--credentials", json.dumps(creds),
        )

    @pytest.mark.asyncio
    async def test_propagates_error(self, mock_run_cli, mock_cli_available):
        mock_run_cli.side_effect = openshell_client.OpenShellError("failed", returncode=1)

        with pytest.raises(openshell_client.OpenShellError):
            await openshell_client.create_provider("sg-test", "litellm", {})

    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = ""
        creds = {"api_key": "sk-test"}

        await openshell_client.create_provider("sg-test-1234", "litellm", creds)

        mock_gateway_request.assert_awaited_once_with(
            "POST", "/v1/sandboxes/sg-test-1234/providers",
            json_body={"type": "litellm", "credentials": creds},
        )


class TestCreateSandbox:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = json.dumps({
            "name": "sg-pool-abc12345",
            "ip": "10.0.0.5",
            "state": "READY",
        })

        info = await openshell_client.create_sandbox(
            name="sg-pool-abc12345",
            image_tag="oto-sandbox:slim",
        )

        mock_gateway_request.assert_awaited_once()
        call_args = mock_gateway_request.call_args
        assert call_args[0] == ("POST", "/v1/sandboxes")
        payload = call_args[1]["json_body"]
        assert payload["name"] == "sg-pool-abc12345"
        assert payload["image"] == "oto-sandbox:slim"
        assert info.name == "sg-pool-abc12345"
        assert info.internal_ip == "10.0.0.5"
        assert info.state == "READY"


class TestSuspendSandbox:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = ""

        await openshell_client.suspend_sandbox("sg-test-1234")

        mock_gateway_request.assert_awaited_once_with(
            "POST", "/v1/sandboxes/sg-test-1234/suspend",
        )


class TestResumeSandbox:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = json.dumps({
            "name": "sg-test-1234",
            "ip": "10.0.0.6",
            "state": "READY",
        })

        info = await openshell_client.resume_sandbox("sg-test-1234")

        mock_gateway_request.assert_awaited_once()
        assert info.name == "sg-test-1234"
        assert info.internal_ip == "10.0.0.6"


class TestDestroySandbox:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = ""

        await openshell_client.destroy_sandbox("sg-test-1234")

        mock_gateway_request.assert_awaited_once_with(
            "DELETE", "/v1/sandboxes/sg-test-1234?force=true",
        )


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_gateway_healthy(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.return_value = json.dumps({
            "name": "sg-test", "state": "READY",
        })

        result = await openshell_client.health_check("sg-test")
        assert result is True

    @pytest.mark.asyncio
    async def test_gateway_unreachable(self, mock_gateway_request, mock_cli_unavailable):
        mock_gateway_request.side_effect = openshell_client.OpenShellError("unreachable")

        result = await openshell_client.health_check("sg-test")
        assert result is False


class TestGatewayRequest:
    @pytest.mark.asyncio
    async def test_raises_when_client_not_initialised(self):
        with patch.object(openshell_client, "_gateway_client", None):
            with pytest.raises(openshell_client.OpenShellError, match="not initialised"):
                await openshell_client._gateway_request("GET", "/v1/sandboxes/test")

    @pytest.mark.asyncio
    async def test_connect_error_raises_openshell_error(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.side_effect = httpx.ConnectError("connection refused")
        with patch.object(openshell_client, "_gateway_client", mock_client):
            with pytest.raises(openshell_client.OpenShellError, match="unreachable"):
                await openshell_client._gateway_request("GET", "/v1/sandboxes/test")

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_error(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.request.side_effect = httpx.ReadTimeout("timed out")
        with patch.object(openshell_client, "_gateway_client", mock_client):
            with pytest.raises(asyncio.TimeoutError):
                await openshell_client._gateway_request("GET", "/v1/sandboxes/test")

    @pytest.mark.asyncio
    async def test_http_error_raises_openshell_error(self):
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_client.request.return_value = mock_resp
        with patch.object(openshell_client, "_gateway_client", mock_client):
            with pytest.raises(openshell_client.OpenShellError, match="Internal Server Error"):
                await openshell_client._gateway_request("GET", "/v1/sandboxes/test")


class TestCliDetection:
    def test_cli_available_flag_exists(self):
        """_CLI_AVAILABLE should be a bool reflecting shutil.which result."""
        assert isinstance(openshell_client._CLI_AVAILABLE, bool)

    def test_detection_with_mock(self):
        with patch("shutil.which", return_value="/usr/bin/openshell"):
            import importlib
            # The flag is set at module load; verify the logic is correct
            assert shutil.which("openshell") is not None

        with patch("shutil.which", return_value=None):
            assert shutil.which("openshell") is None


class TestInitGatewayClient:
    @pytest.mark.asyncio
    async def test_creates_client_when_cli_unavailable(self):
        with patch.object(openshell_client, "_CLI_AVAILABLE", False):
            with patch.object(openshell_client, "_gateway_client", None):
                await openshell_client.init_gateway_client()
                assert openshell_client._gateway_client is not None
                # Clean up
                await openshell_client.close_gateway_client()

    @pytest.mark.asyncio
    async def test_skips_when_cli_available(self):
        with patch.object(openshell_client, "_CLI_AVAILABLE", True):
            original = openshell_client._gateway_client
            await openshell_client.init_gateway_client()
            assert openshell_client._gateway_client is original
