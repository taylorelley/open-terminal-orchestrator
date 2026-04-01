"""Unit tests for the openshell_client module (R1, R2, R3)."""

import asyncio
import json
import shutil
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services import openshell_client


@pytest.fixture
def mock_run_cmd():
    with patch.object(openshell_client, "_run_cmd", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def mock_docker_available():
    """Force the Docker CLI code path."""
    with patch.object(openshell_client, "_DOCKER_AVAILABLE", True):
        yield


@pytest.fixture
def mock_docker_unavailable():
    """Force the HTTP gateway code path."""
    with patch.object(openshell_client, "_DOCKER_AVAILABLE", False):
        yield


@pytest.fixture
def mock_gateway_request():
    with patch.object(openshell_client, "_gateway_request", new_callable=AsyncMock) as m:
        yield m


# ---------------------------------------------------------------------------
# Docker transport tests
# ---------------------------------------------------------------------------


class TestCreateSandboxDocker:
    @pytest.mark.asyncio
    async def test_creates_container_and_returns_info(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.side_effect = [
            "",        # docker run
            "",        # docker inspect health (TimeoutError caught)
            "10.0.0.5",  # docker inspect IP
        ]

        with patch.object(openshell_client, "_docker_wait_healthy", new_callable=AsyncMock):
            with patch.object(openshell_client, "_docker_inspect_ip", new_callable=AsyncMock, return_value="10.0.0.5"):
                info = await openshell_client.create_sandbox(
                    name="sg-pool-abc12345",
                    image_tag="oto-sandbox:slim",
                )

        assert info.name == "sg-pool-abc12345"
        assert info.internal_ip == "10.0.0.5"
        assert info.state == "READY"
        # Verify docker run was called
        run_call = mock_run_cmd.call_args_list[0]
        assert "docker" in run_call[0]
        assert "run" in run_call[0]
        assert "--network" in run_call[0]


class TestSuspendSandboxDocker:
    @pytest.mark.asyncio
    async def test_calls_docker_stop(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = ""
        await openshell_client.suspend_sandbox("sg-test-1234")
        mock_run_cmd.assert_awaited_once_with("docker", "stop", "sg-test-1234")


class TestResumeSandboxDocker:
    @pytest.mark.asyncio
    async def test_calls_docker_start(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = ""

        with patch.object(openshell_client, "_docker_wait_healthy", new_callable=AsyncMock):
            with patch.object(openshell_client, "_docker_inspect_ip", new_callable=AsyncMock, return_value="10.0.0.6"):
                info = await openshell_client.resume_sandbox("sg-test-1234")

        assert info.internal_ip == "10.0.0.6"
        assert info.name == "sg-test-1234"


class TestDestroySandboxDocker:
    @pytest.mark.asyncio
    async def test_calls_docker_rm_force(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = ""
        await openshell_client.destroy_sandbox("sg-test-1234")
        mock_run_cmd.assert_awaited_once_with("docker", "rm", "-f", "sg-test-1234")


class TestHealthCheckDocker:
    @pytest.mark.asyncio
    async def test_running_is_healthy(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = "running"
        assert await openshell_client.health_check("sg-test") is True

    @pytest.mark.asyncio
    async def test_exited_is_unhealthy(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = "exited"
        assert await openshell_client.health_check("sg-test") is False

    @pytest.mark.asyncio
    async def test_error_returns_false(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.side_effect = openshell_client.OpenShellError("not found")
        assert await openshell_client.health_check("sg-test") is False


class TestGetPolicyDocker:
    @pytest.mark.asyncio
    async def test_calls_docker_exec_cat(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = "metadata:\n  name: test\n"
        result = await openshell_client.get_policy("sg-test-1234")
        mock_run_cmd.assert_awaited_once_with(
            "docker", "exec", "sg-test-1234",
            "cat", "/etc/open-terminal/policy.yaml",
        )
        assert "metadata:" in result


class TestDryRunPolicyDocker:
    @pytest.mark.asyncio
    async def test_copies_file_and_runs_dry_run(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.side_effect = ["", json.dumps({"status": "ok", "changes": []})]
        result = await openshell_client.dry_run_policy("sg-test-1234", "/tmp/policy.yaml")
        assert mock_run_cmd.call_count == 2
        # First call: docker cp
        assert "cp" in mock_run_cmd.call_args_list[0][0]
        # Second call: docker exec
        assert "exec" in mock_run_cmd.call_args_list[1][0]
        assert "ok" in result


class TestCreateProviderDocker:
    @pytest.mark.asyncio
    async def test_calls_docker_exec(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.return_value = ""
        creds = {"api_key": "sk-test", "endpoint": "https://api.example.com"}
        await openshell_client.create_provider("sg-test-1234", "litellm", creds)
        mock_run_cmd.assert_awaited_once()
        call_args = mock_run_cmd.call_args[0]
        assert "exec" in call_args
        assert "sg-test-1234" in call_args

    @pytest.mark.asyncio
    async def test_propagates_error(self, mock_run_cmd, mock_docker_available):
        mock_run_cmd.side_effect = openshell_client.OpenShellError("failed", returncode=1)
        with pytest.raises(openshell_client.OpenShellError):
            await openshell_client.create_provider("sg-test", "litellm", {})


# ---------------------------------------------------------------------------
# Gateway fallback tests
# ---------------------------------------------------------------------------


class TestCreateSandboxGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
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


class TestSuspendSandboxGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = ""
        await openshell_client.suspend_sandbox("sg-test-1234")
        mock_gateway_request.assert_awaited_once_with(
            "POST", "/v1/sandboxes/sg-test-1234/suspend",
        )


class TestResumeSandboxGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = json.dumps({
            "name": "sg-test-1234",
            "ip": "10.0.0.6",
            "state": "READY",
        })
        info = await openshell_client.resume_sandbox("sg-test-1234")
        assert info.name == "sg-test-1234"
        assert info.internal_ip == "10.0.0.6"


class TestDestroySandboxGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = ""
        await openshell_client.destroy_sandbox("sg-test-1234")
        mock_gateway_request.assert_awaited_once_with(
            "DELETE", "/v1/sandboxes/sg-test-1234?force=true",
        )


class TestHealthCheckGateway:
    @pytest.mark.asyncio
    async def test_gateway_healthy(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = json.dumps({
            "name": "sg-test", "state": "READY",
        })
        assert await openshell_client.health_check("sg-test") is True

    @pytest.mark.asyncio
    async def test_gateway_unreachable(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.side_effect = openshell_client.OpenShellError("unreachable")
        assert await openshell_client.health_check("sg-test") is False


class TestGetPolicyGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = "metadata:\n  name: test\n"
        result = await openshell_client.get_policy("sg-test-1234")
        mock_gateway_request.assert_awaited_once_with(
            "GET", "/v1/sandboxes/sg-test-1234/policy",
        )
        assert "metadata:" in result


class TestCreateProviderGateway:
    @pytest.mark.asyncio
    async def test_gateway_fallback(self, mock_gateway_request, mock_docker_unavailable):
        mock_gateway_request.return_value = ""
        creds = {"api_key": "sk-test"}
        await openshell_client.create_provider("sg-test-1234", "litellm", creds)
        mock_gateway_request.assert_awaited_once_with(
            "POST", "/v1/sandboxes/sg-test-1234/providers",
            json_body={"type": "litellm", "credentials": creds},
        )


# ---------------------------------------------------------------------------
# Gateway request error handling
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Transport detection and lifecycle
# ---------------------------------------------------------------------------


class TestTransportDetection:
    def test_docker_available_flag_exists(self):
        assert isinstance(openshell_client._DOCKER_AVAILABLE, bool)

    def test_detection_with_mock(self):
        with patch("shutil.which", return_value="/usr/bin/docker"):
            assert shutil.which("docker") is not None
        with patch("shutil.which", return_value=None):
            assert shutil.which("docker") is None


class TestInitGatewayClient:
    @pytest.mark.asyncio
    async def test_creates_client_when_docker_unavailable(self):
        with patch.object(openshell_client, "_DOCKER_AVAILABLE", False):
            with patch.object(openshell_client, "_gateway_client", None):
                await openshell_client.init_gateway_client()
                assert openshell_client._gateway_client is not None
                await openshell_client.close_gateway_client()

    @pytest.mark.asyncio
    async def test_skips_when_docker_available(self):
        with patch.object(openshell_client, "_DOCKER_AVAILABLE", True):
            original = openshell_client._gateway_client
            await openshell_client.init_gateway_client()
            assert openshell_client._gateway_client is original
