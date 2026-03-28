"""Unit tests for the openshell_client module (R1, R2, R3)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services import openshell_client


@pytest.fixture
def mock_run_cli():
    with patch.object(openshell_client, "_run_cli", new_callable=AsyncMock) as m:
        yield m


class TestGetPolicy:
    @pytest.mark.asyncio
    async def test_calls_cli_with_correct_args(self, mock_run_cli):
        mock_run_cli.return_value = "metadata:\n  name: test\nnetwork:\n  default: deny\n"

        result = await openshell_client.get_policy("sg-test-1234")

        mock_run_cli.assert_awaited_once_with(
            "policy", "get", "--sandbox", "sg-test-1234", "--output", "yaml",
        )
        assert "metadata:" in result

    @pytest.mark.asyncio
    async def test_propagates_error(self, mock_run_cli):
        mock_run_cli.side_effect = openshell_client.OpenShellError("not found", returncode=1)

        with pytest.raises(openshell_client.OpenShellError):
            await openshell_client.get_policy("sg-missing")


class TestDryRunPolicy:
    @pytest.mark.asyncio
    async def test_calls_cli_with_dry_run_flag(self, mock_run_cli):
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
    async def test_calls_cli_with_credentials(self, mock_run_cli):
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
    async def test_propagates_error(self, mock_run_cli):
        mock_run_cli.side_effect = openshell_client.OpenShellError("failed", returncode=1)

        with pytest.raises(openshell_client.OpenShellError):
            await openshell_client.create_provider("sg-test", "litellm", {})
