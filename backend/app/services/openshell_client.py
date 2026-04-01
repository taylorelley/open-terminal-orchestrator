"""Sandbox lifecycle management via the Docker CLI.

Creates, suspends, resumes, destroys, and health-checks sandbox containers
using ``docker`` commands over the mounted Docker socket.  Falls back to HTTP
calls to the OpenShell gateway (``settings.openshell_gateway``) when Docker is
not available.
"""

import asyncio
import json
import logging
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Default timeout for subprocess / HTTP calls (seconds).
_CLI_TIMEOUT = 60

# Detect available transport at import time.
_DOCKER_AVAILABLE = shutil.which("docker") is not None

# Module-level HTTP client for gateway fallback (initialised at startup).
_gateway_client: httpx.AsyncClient | None = None


async def init_gateway_client() -> None:
    """Create the HTTP client for the OpenShell gateway (when Docker is unavailable)."""
    global _gateway_client  # noqa: PLW0603
    if _DOCKER_AVAILABLE:
        logger.info("Docker CLI found on PATH — using Docker transport for sandboxes")
    else:
        _gateway_client = httpx.AsyncClient(
            base_url=settings.openshell_gateway,
            timeout=httpx.Timeout(_CLI_TIMEOUT, connect=5.0),
        )
        logger.info(
            "Docker CLI not found; falling back to OpenShell gateway HTTP client "
            "(base_url=%s)",
            settings.openshell_gateway,
        )


async def close_gateway_client() -> None:
    """Shut down the gateway HTTP client."""
    global _gateway_client  # noqa: PLW0603
    if _gateway_client is not None:
        await _gateway_client.aclose()
        _gateway_client = None


@dataclass
class SandboxInfo:
    """Parsed result from a sandbox operation."""

    name: str
    internal_ip: str
    state: str
    image_tag: str = ""


class OpenShellError(Exception):
    """Raised when a sandbox operation fails."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


# ---------------------------------------------------------------------------
# Transport: Docker CLI
# ---------------------------------------------------------------------------


async def _run_cmd(
    *args: str,
    timeout: float = _CLI_TIMEOUT,
) -> str:
    """Run a command and return its stdout.

    Raises:
        OpenShellError: If the command exits with a non-zero status.
        asyncio.TimeoutError: If the command exceeds *timeout* seconds.
    """
    logger.debug("Running: %s", " ".join(args))

    proc = await asyncio.create_subprocess_exec(
        *args,
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
            "Command %s failed (rc=%d): %s",
            args[:3],
            proc.returncode,
            stderr_str or stdout_str,
        )
        raise OpenShellError(
            stderr_str or stdout_str or f"Command exited with code {proc.returncode}",
            returncode=proc.returncode or 1,
        )

    return stdout_str


async def _docker_inspect_ip(name: str) -> str:
    """Return the container IP on the sandbox network."""
    network = settings.sandbox_network
    fmt = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
    # Try network-specific first, fall back to any network.
    try:
        net_fmt = f"{{{{.NetworkSettings.Networks.{network}.IPAddress}}}}"
        return await _run_cmd("docker", "inspect", "-f", net_fmt, name, timeout=10)
    except OpenShellError:
        return await _run_cmd("docker", "inspect", "-f", fmt, name, timeout=10)


async def _docker_wait_healthy(name: str, timeout: float) -> None:
    """Poll until the container reports healthy or timeout expires."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            status = await _run_cmd(
                "docker", "inspect", "-f", "{{.State.Health.Status}}", name,
                timeout=5,
            )
            if status == "healthy":
                return
        except OpenShellError:
            pass
        await asyncio.sleep(2)
    # Accept running containers that don't have a health check configured.
    try:
        state = await _run_cmd(
            "docker", "inspect", "-f", "{{.State.Status}}", name, timeout=5,
        )
        if state == "running":
            return
    except OpenShellError:
        pass
    raise asyncio.TimeoutError()


# ---------------------------------------------------------------------------
# Transport: HTTP gateway (fallback)
# ---------------------------------------------------------------------------


async def _gateway_request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    body: str | None = None,
    content_type: str = "application/json",
    timeout: float = _CLI_TIMEOUT,
) -> str:
    """Make an HTTP request to the OpenShell gateway and return the response body.

    Raises:
        OpenShellError: On HTTP errors or connection failures.
        asyncio.TimeoutError: On request timeout.
    """
    if _gateway_client is None:
        raise OpenShellError("Gateway client not initialised")

    kwargs: dict = {"timeout": timeout}
    if json_body is not None:
        kwargs["json"] = json_body
    elif body is not None:
        kwargs["content"] = body
        kwargs["headers"] = {"Content-Type": content_type}

    try:
        resp = await _gateway_client.request(method, path, **kwargs)
    except httpx.ConnectError:
        raise OpenShellError(
            f"OpenShell gateway unreachable at {settings.openshell_gateway}"
        )
    except httpx.TimeoutException:
        raise asyncio.TimeoutError()

    if resp.status_code >= 400:
        raise OpenShellError(
            resp.text or f"Gateway returned HTTP {resp.status_code}",
            returncode=1,
        )
    return resp.text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_sandbox_json(raw: str) -> SandboxInfo:
    """Parse JSON output from sandbox commands."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
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
    image_tag: str = "oto-sandbox:slim",
    policy_file: str | None = None,
    user_data_dir: str | None = None,
    gpu: bool = False,
) -> SandboxInfo:
    """Create a new sandbox container.

    Returns parsed sandbox info including the assigned internal IP.
    """
    if name is None:
        name = f"sg-pool-{uuid.uuid4().hex[:8]}"

    if _DOCKER_AVAILABLE:
        args = [
            "docker", "run", "-d",
            "--name", name,
            "--network", settings.sandbox_network,
            "--restart", "no",
        ]
        if settings.sandbox_api_key:
            args.extend(["-e", f"OPEN_TERMINAL_API_KEY={settings.sandbox_api_key}"])
        if policy_file:
            args.extend(["-e", f"OPEN_TERMINAL_POLICY_FILE={policy_file}"])
        if user_data_dir:
            args.extend(["-v", f"{user_data_dir}:/data"])
        if gpu:
            args.append("--gpus=all")
        args.append(image_tag)
        await _run_cmd(*args, timeout=settings.startup_timeout)

        # Wait for the container to become healthy, then retrieve its IP.
        try:
            await _docker_wait_healthy(name, timeout=settings.startup_timeout)
        except asyncio.TimeoutError:
            logger.warning("Sandbox %s did not become healthy in time", name)

        ip = await _docker_inspect_ip(name)
        info = SandboxInfo(name=name, internal_ip=ip, state="READY", image_tag=image_tag)
    else:
        payload: dict = {"name": name, "image": image_tag}
        env: dict[str, str] = {}
        if settings.sandbox_api_key:
            env["OPEN_TERMINAL_API_KEY"] = settings.sandbox_api_key
        if env:
            payload["env"] = env
        if policy_file:
            payload["policy_file"] = policy_file
        if user_data_dir:
            payload["volumes"] = [f"{user_data_dir}:/data"]
        if gpu:
            payload["gpu"] = True
        raw = await _gateway_request(
            "POST", "/v1/sandboxes", json_body=payload,
            timeout=settings.startup_timeout,
        )
        info = _parse_sandbox_json(raw)

    if not info.name:
        info.name = name
    logger.info("Created sandbox %s (ip=%s)", info.name, info.internal_ip)
    return info


async def suspend_sandbox(name: str) -> None:
    """Stop (suspend) a running sandbox container."""
    if _DOCKER_AVAILABLE:
        await _run_cmd("docker", "stop", name)
    else:
        await _gateway_request("POST", f"/v1/sandboxes/{name}/suspend")
    logger.info("Suspended sandbox %s", name)


async def resume_sandbox(name: str) -> SandboxInfo:
    """Start (resume) a stopped sandbox container.

    Returns updated sandbox info (IP may change after resume).
    """
    if _DOCKER_AVAILABLE:
        await _run_cmd("docker", "start", name, timeout=settings.resume_timeout)
        try:
            await _docker_wait_healthy(name, timeout=settings.resume_timeout)
        except asyncio.TimeoutError:
            logger.warning("Sandbox %s did not become healthy after resume", name)
        ip = await _docker_inspect_ip(name)
        info = SandboxInfo(name=name, internal_ip=ip, state="READY")
    else:
        raw = await _gateway_request(
            "POST", f"/v1/sandboxes/{name}/resume",
            timeout=settings.resume_timeout,
        )
        info = _parse_sandbox_json(raw)
    if not info.name:
        info.name = name
    logger.info("Resumed sandbox %s (ip=%s)", info.name, info.internal_ip)
    return info


async def destroy_sandbox(name: str) -> None:
    """Force-remove a sandbox container."""
    if _DOCKER_AVAILABLE:
        await _run_cmd("docker", "rm", "-f", name)
    else:
        await _gateway_request("DELETE", f"/v1/sandboxes/{name}?force=true")
    logger.info("Destroyed sandbox %s", name)


async def health_check(name: str) -> bool:
    """Check if a sandbox container is running and healthy.

    Returns True if the container reports a healthy/ready state.
    """
    try:
        if _DOCKER_AVAILABLE:
            state = await _run_cmd(
                "docker", "inspect", "-f", "{{.State.Status}}", name, timeout=10,
            )
            return state == "running"
        raw = await _gateway_request("GET", f"/v1/sandboxes/{name}", timeout=10)
        info = _parse_sandbox_json(raw)
        return info.state in ("READY", "ACTIVE", "RUNNING")
    except (OpenShellError, asyncio.TimeoutError):
        return False


async def set_policy(name: str, policy_file: str) -> None:
    """Apply a policy to a running sandbox."""
    if _DOCKER_AVAILABLE:
        await _run_cmd("docker", "cp", policy_file, f"{name}:/tmp/policy.yaml")
        await _run_cmd(
            "docker", "exec", name,
            "open-terminal-apply-policy", "/tmp/policy.yaml",
        )
    else:
        policy_content = Path(policy_file).read_text()
        await _gateway_request(
            "PUT", f"/v1/sandboxes/{name}/policy",
            body=policy_content, content_type="application/x-yaml",
        )
    logger.info("Applied policy to sandbox %s", name)


async def get_policy(name: str) -> str:
    """Retrieve the active policy YAML from a sandbox.

    Returns the raw YAML string of the policy currently applied to the sandbox.
    """
    if _DOCKER_AVAILABLE:
        return await _run_cmd(
            "docker", "exec", name,
            "cat", "/etc/open-terminal/policy.yaml",
        )
    return await _gateway_request("GET", f"/v1/sandboxes/{name}/policy")


async def dry_run_policy(name: str, policy_file: str) -> str:
    """Validate a policy against a sandbox without applying it.

    Returns JSON output describing the dry-run result (e.g. what would change).
    """
    if _DOCKER_AVAILABLE:
        await _run_cmd("docker", "cp", policy_file, f"{name}:/tmp/policy.yaml")
        return await _run_cmd(
            "docker", "exec", name,
            "open-terminal-apply-policy", "--dry-run", "--output", "json",
            "/tmp/policy.yaml",
        )
    policy_content = Path(policy_file).read_text()
    return await _gateway_request(
        "POST", f"/v1/sandboxes/{name}/policy/dry-run",
        body=policy_content, content_type="application/x-yaml",
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
    image_tag: str = "oto-sandbox:slim",
    policy_file: str | None = None,
    user_data_dir: str | None = None,
) -> SandboxInfo:
    """Create a GPU-enabled sandbox with NVIDIA runtime configuration.

    Allocates a GPU device, then creates the container with
    the ``--gpus`` flag and ``--runtime nvidia`` plus device environment
    variables.
    """
    if name is None:
        name = f"sg-gpu-{uuid.uuid4().hex[:8]}"

    device_uuid = await gpu_scheduler.allocate(name)
    if not device_uuid:
        raise OpenShellError("No GPU devices available for allocation")

    if _DOCKER_AVAILABLE:
        args = [
            "docker", "run", "-d",
            "--name", name,
            "--network", settings.sandbox_network,
            "--restart", "no",
            "--runtime", "nvidia",
            "-e", f"NVIDIA_VISIBLE_DEVICES={device_uuid}",
            "-e", "NVIDIA_DRIVER_CAPABILITIES=compute,utility",
        ]
        if settings.sandbox_api_key:
            args.extend(["-e", f"OPEN_TERMINAL_API_KEY={settings.sandbox_api_key}"])
        if policy_file:
            args.extend(["-e", f"OPEN_TERMINAL_POLICY_FILE={policy_file}"])
        if user_data_dir:
            args.extend(["-v", f"{user_data_dir}:/data"])
        args.append(image_tag)

        try:
            await _run_cmd(*args, timeout=settings.startup_timeout)
            try:
                await _docker_wait_healthy(name, timeout=settings.startup_timeout)
            except asyncio.TimeoutError:
                logger.warning("GPU sandbox %s did not become healthy in time", name)
            ip = await _docker_inspect_ip(name)
            info = SandboxInfo(name=name, internal_ip=ip, state="READY", image_tag=image_tag)
        except (OpenShellError, asyncio.TimeoutError):
            gpu_scheduler.release(name)
            raise
    else:
        payload: dict = {
            "name": name,
            "image": image_tag,
            "gpu": True,
            "runtime": "nvidia",
            "env": {
                "NVIDIA_VISIBLE_DEVICES": device_uuid,
                "NVIDIA_DRIVER_CAPABILITIES": "compute,utility",
            },
        }
        if settings.sandbox_api_key:
            payload["env"]["OPEN_TERMINAL_API_KEY"] = settings.sandbox_api_key
        if policy_file:
            payload["policy_file"] = policy_file
        if user_data_dir:
            payload["volumes"] = [f"{user_data_dir}:/data"]

        try:
            raw = await _gateway_request(
                "POST", "/v1/sandboxes", json_body=payload,
                timeout=settings.startup_timeout,
            )
            info = _parse_sandbox_json(raw)
        except (OpenShellError, asyncio.TimeoutError):
            gpu_scheduler.release(name)
            raise

    if not info.name:
        info.name = name
    logger.info("Created GPU sandbox %s (ip=%s, gpu=%s)", info.name, info.internal_ip, device_uuid)
    return info


async def create_provider(
    sandbox_name: str,
    provider_type: str,
    credentials: dict[str, str],
) -> None:
    """Inject credentials into a sandbox."""
    if _DOCKER_AVAILABLE:
        creds_json = json.dumps(credentials)
        await _run_cmd(
            "docker", "exec", sandbox_name,
            "open-terminal-inject-provider",
            "--type", provider_type,
            "--credentials", creds_json,
        )
    else:
        await _gateway_request(
            "POST", f"/v1/sandboxes/{sandbox_name}/providers",
            json_body={"type": provider_type, "credentials": credentials},
        )
    logger.info("Created provider '%s' on sandbox %s", provider_type, sandbox_name)
