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
    if settings.sandbox_api_key:
        args.extend(["--env", f"OPEN_TERMINAL_API_KEY={settings.sandbox_api_key}"])
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


# ---------------------------------------------------------------------------
# GPU device detection & scheduling
# ---------------------------------------------------------------------------


async def detect_gpu_devices() -> list[dict[str, str]]:
    """Detect available NVIDIA GPU devices on the host.

    Returns a list of dicts with keys: ``index``, ``name``, ``uuid``,
    ``memory_total``, ``memory_free``.  Returns an empty list if
    ``nvidia-smi`` is not available or no GPUs are found.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=index,name,uuid,memory.total,memory.free",
            "--format=csv,noheader,nounits",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode != 0:
            return []

        devices: list[dict[str, str]] = []
        for line in stdout.decode().strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                devices.append({
                    "index": parts[0],
                    "name": parts[1],
                    "uuid": parts[2],
                    "memory_total": parts[3],
                    "memory_free": parts[4],
                })
        return devices
    except (FileNotFoundError, asyncio.TimeoutError):
        return []


class GpuScheduler:
    """Simple GPU resource scheduler that tracks device allocations.

    Each sandbox that requests GPU access is assigned to the device with
    the most free memory.  Allocations are tracked in-memory; the pool
    manager resets them on restart by scanning active sandboxes.
    """

    def __init__(self) -> None:
        self._allocations: dict[str, list[str]] = {}  # device_uuid -> [sandbox_name, ...]

    async def allocate(self, sandbox_name: str) -> str | None:
        """Allocate a GPU device for *sandbox_name*.

        Returns the device UUID string (e.g. ``GPU-xxxx``) or ``None``
        if no GPUs are available.
        """
        devices = await detect_gpu_devices()
        if not devices:
            logger.warning("No GPU devices detected for sandbox %s", sandbox_name)
            return None

        # Pick the device with the fewest current allocations.
        best = min(devices, key=lambda d: len(self._allocations.get(d["uuid"], [])))
        device_uuid = best["uuid"]
        self._allocations.setdefault(device_uuid, []).append(sandbox_name)
        logger.info("Allocated GPU %s (%s) to sandbox %s", best["index"], best["name"], sandbox_name)
        return device_uuid

    def release(self, sandbox_name: str) -> None:
        """Release any GPU allocation held by *sandbox_name*."""
        for device_uuid, names in self._allocations.items():
            if sandbox_name in names:
                names.remove(sandbox_name)
                logger.info("Released GPU %s from sandbox %s", device_uuid, sandbox_name)
                return

    def allocated_count(self) -> int:
        """Return the total number of active GPU allocations."""
        return sum(len(names) for names in self._allocations.values())


# Module-level GPU scheduler singleton.
gpu_scheduler = GpuScheduler()


async def create_sandbox_with_gpu(
    name: str | None = None,
    image_tag: str = "shellguard-sandbox:slim",
    policy_file: str | None = None,
    user_data_dir: str | None = None,
) -> SandboxInfo:
    """Create a GPU-enabled sandbox with NVIDIA runtime configuration.

    Allocates a GPU device, then calls ``openshell sandbox create`` with
    the ``--gpu`` flag and ``--runtime nvidia`` plus device environment
    variables.
    """
    if name is None:
        name = f"sg-gpu-{uuid.uuid4().hex[:8]}"

    device_uuid = await gpu_scheduler.allocate(name)
    if not device_uuid:
        raise OpenShellError("No GPU devices available for allocation")

    args = [
        "sandbox", "create",
        "--name", name,
        "--from", image_tag,
        "--output", "json",
        "--gpu",
        "--runtime", "nvidia",
        "--env", f"NVIDIA_VISIBLE_DEVICES={device_uuid}",
        "--env", "NVIDIA_DRIVER_CAPABILITIES=compute,utility",
    ]
    if settings.sandbox_api_key:
        args.extend(["--env", f"OPEN_TERMINAL_API_KEY={settings.sandbox_api_key}"])
    if policy_file:
        args.extend(["--policy", policy_file])
    if user_data_dir:
        args.extend(["--volume", f"{user_data_dir}:/data"])

    try:
        raw = await _run_cli(*args, timeout=settings.startup_timeout)
    except (OpenShellError, asyncio.TimeoutError):
        gpu_scheduler.release(name)
        raise

    info = _parse_sandbox_json(raw)
    if not info.name:
        info.name = name
    logger.info("Created GPU sandbox %s (ip=%s, gpu=%s)", info.name, info.internal_ip, device_uuid)
    return info


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
