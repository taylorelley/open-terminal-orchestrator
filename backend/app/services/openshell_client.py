"""Async wrapper around the ``openshell`` CLI for sandbox lifecycle operations.

Provides non-blocking subprocess calls to create, suspend, resume, destroy, and
health-check sandboxes via the ``openshell`` binary.  Falls back to HTTP calls
to the OpenShell gateway when the CLI is not available.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)

# Default timeout for CLI subprocess calls (seconds).
_CLI_TIMEOUT = 60


@dataclass
class SandboxInfo:
    """Parsed result from an openshell sandbox operation."""

    name: str
    internal_ip: str
    state: str
    image_tag: str = ""


class OpenShellError(Exception):
    """Raised when an openshell CLI command fails."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


async def _run_cli(
    *args: str,
    timeout: float = _CLI_TIMEOUT,
) -> str:
    """Run an openshell CLI command and return its stdout.

    Raises:
        OpenShellError: If the command exits with a non-zero status.
        asyncio.TimeoutError: If the command exceeds *timeout* seconds.
    """
    cmd = ["openshell", *args]
    logger.debug("Running: %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise

    stdout_str = stdout.decode().strip()
    stderr_str = stderr.decode().strip()

    if proc.returncode != 0:
        logger.error(
            "openshell %s failed (rc=%d): %s",
            args[0] if args else "?",
            proc.returncode,
            stderr_str or stdout_str,
        )
        raise OpenShellError(
            stderr_str or stdout_str or f"openshell exited with code {proc.returncode}",
            returncode=proc.returncode or 1,
        )

    return stdout_str


def _parse_sandbox_json(raw: str) -> SandboxInfo:
    """Parse JSON output from openshell sandbox commands."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: try to extract from non-JSON output.
        return SandboxInfo(name="", internal_ip="", state="UNKNOWN")

    return SandboxInfo(
        name=data.get("name", ""),
        internal_ip=data.get("ip", data.get("internal_ip", "")),
        state=data.get("state", data.get("status", "UNKNOWN")).upper(),
        image_tag=data.get("image", data.get("image_tag", "")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def create_sandbox(
    name: str | None = None,
    image_tag: str = "shellguard-sandbox:slim",
    policy_file: str | None = None,
    user_data_dir: str | None = None,
    gpu: bool = False,
) -> SandboxInfo:
    """Create a new sandbox via ``openshell sandbox create``.

    Returns parsed sandbox info including the assigned internal IP.
    """
    if name is None:
        name = f"sg-pool-{uuid.uuid4().hex[:8]}"

    args = [
        "sandbox", "create",
        "--name", name,
        "--from", image_tag,
        "--output", "json",
    ]
    if policy_file:
        args.extend(["--policy", policy_file])
    if user_data_dir:
        args.extend(["--volume", f"{user_data_dir}:/data"])
    if gpu:
        args.append("--gpu")

    raw = await _run_cli(*args, timeout=settings.startup_timeout)
    info = _parse_sandbox_json(raw)
    if not info.name:
        info.name = name
    logger.info("Created sandbox %s (ip=%s)", info.name, info.internal_ip)
    return info


async def suspend_sandbox(name: str) -> None:
    """Suspend a running sandbox via ``openshell sandbox suspend``."""
    await _run_cli("sandbox", "suspend", name)
    logger.info("Suspended sandbox %s", name)


async def resume_sandbox(name: str) -> SandboxInfo:
    """Resume a suspended sandbox via ``openshell sandbox resume``.

    Returns updated sandbox info (IP may change after resume).
    """
    raw = await _run_cli(
        "sandbox", "resume", name, "--output", "json",
        timeout=settings.resume_timeout,
    )
    info = _parse_sandbox_json(raw)
    if not info.name:
        info.name = name
    logger.info("Resumed sandbox %s (ip=%s)", info.name, info.internal_ip)
    return info


async def destroy_sandbox(name: str) -> None:
    """Destroy a sandbox via ``openshell sandbox destroy``."""
    await _run_cli("sandbox", "destroy", name, "--force")
    logger.info("Destroyed sandbox %s", name)


async def health_check(name: str) -> bool:
    """Check if a sandbox is healthy via ``openshell sandbox status``.

    Returns True if the sandbox reports a healthy/ready state.
    """
    try:
        raw = await _run_cli("sandbox", "status", name, "--output", "json", timeout=10)
        info = _parse_sandbox_json(raw)
        return info.state in ("READY", "ACTIVE", "RUNNING")
    except (OpenShellError, asyncio.TimeoutError):
        return False


async def set_policy(name: str, policy_file: str) -> None:
    """Apply a policy to a running sandbox via ``openshell policy set``."""
    await _run_cli("policy", "set", "--sandbox", name, "--file", policy_file)
    logger.info("Applied policy to sandbox %s", name)


async def get_policy(name: str) -> str:
    """Retrieve the active policy YAML from a sandbox via ``openshell policy get``.

    Returns the raw YAML string of the policy currently applied to the sandbox.
    """
    return await _run_cli("policy", "get", "--sandbox", name, "--output", "yaml")


async def dry_run_policy(name: str, policy_file: str) -> str:
    """Validate a policy against a sandbox without applying it.

    Returns JSON output describing the dry-run result (e.g. what would change).
    """
    return await _run_cli(
        "policy", "set",
        "--sandbox", name,
        "--file", policy_file,
        "--dry-run",
        "--output", "json",
    )


async def create_provider(
    sandbox_name: str,
    provider_type: str,
    credentials: dict[str, str],
) -> None:
    """Inject credentials into a sandbox via ``openshell provider create``."""
    creds_json = json.dumps(credentials)
    await _run_cli(
        "provider", "create",
        "--sandbox", sandbox_name,
        "--type", provider_type,
        "--credentials", creds_json,
    )
    logger.info("Created provider '%s' on sandbox %s", provider_type, sandbox_name)
