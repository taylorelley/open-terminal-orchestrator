"""Open Terminal-compatible proxy API.

These endpoints mirror the full Open Terminal REST API surface so that Open
WebUI can connect to ShellGuard as if it were a single Open Terminal instance.
Each request is routed to the calling user's assigned sandbox.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.litellm_service import litellm_router
from app.services.proxy_client import forward_request
from app.services.sandbox_resolver import resolve_sandbox
from app.services.ws_relay import relay_websocket

logger = logging.getLogger(__name__)

router = APIRouter(tags=["proxy"])


async def _proxy(request: Request, path: str, db: AsyncSession) -> StreamingResponse:
    """Common proxy handler: resolve sandbox then forward the request."""
    resolved = await resolve_sandbox(request, db)
    sandbox = resolved.sandbox
    return await forward_request(request, sandbox.internal_ip, path)


async def _llm_proxy(request: Request, path: str, db: AsyncSession) -> StreamingResponse:
    """LLM inference proxy with credential stripping and injection.

    1. Resolve the user's sandbox.
    2. Strip any user-supplied API keys from the request.
    3. Extract the requested model from the JSON body (if present).
    4. Inject operator-configured provider credentials.
    5. Forward to the sandbox's LiteLLM proxy.
    """
    resolved = await resolve_sandbox(request, db)
    sandbox = resolved.sandbox

    # Try to extract the model from the request body for routing.
    model: str | None = None
    try:
        body = await request.body()
        if body:
            data = json.loads(body)
            model = data.get("model")
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass

    # Transform headers: strip user creds, inject operator creds.
    original_headers = dict(request.headers)
    transformed = litellm_router.transform_request_headers(original_headers, model=model)

    # Replace request headers for the forward_request call.
    request._headers = transformed  # type: ignore[attr-defined]

    return await forward_request(request, sandbox.internal_ip, path)


# ------------------------------------------------------------------
# Command execution
# ------------------------------------------------------------------


@router.post("/api/execute")
async def execute(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Execute a command in the user's sandbox."""
    return await _proxy(request, "/api/execute", db)


# ------------------------------------------------------------------
# File operations
# ------------------------------------------------------------------


@router.get("/api/files")
async def list_files(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """List files in the user's sandbox."""
    return await _proxy(request, "/api/files", db)


@router.get("/api/files/{path:path}")
async def read_file(path: str, request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Read a file from the user's sandbox."""
    return await _proxy(request, f"/api/files/{path}", db)


@router.put("/api/files/{path:path}")
async def write_file(path: str, request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Write a file to the user's sandbox."""
    return await _proxy(request, f"/api/files/{path}", db)


@router.delete("/api/files/{path:path}")
async def delete_file(path: str, request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Delete a file in the user's sandbox."""
    return await _proxy(request, f"/api/files/{path}", db)


@router.post("/api/files/upload")
async def upload_file(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Upload a file to the user's sandbox."""
    return await _proxy(request, "/api/files/upload", db)


@router.get("/api/files/download/{path:path}")
async def download_file(path: str, request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Download a file from the user's sandbox."""
    return await _proxy(request, f"/api/files/download/{path}", db)


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


@router.post("/api/files/move")
async def move_file(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Move or rename a file in the user's sandbox."""
    return await _proxy(request, "/api/files/move", db)


@router.post("/api/files/mkdir")
async def mkdir(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Create a directory in the user's sandbox."""
    return await _proxy(request, "/api/files/mkdir", db)


# ------------------------------------------------------------------
# Search
# ------------------------------------------------------------------


@router.get("/api/search")
async def search_files(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Search files in the user's sandbox."""
    return await _proxy(request, "/api/search", db)


# ------------------------------------------------------------------
# Config and metadata discovery
# ------------------------------------------------------------------


@router.get("/api/config")
async def get_config(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Return sandbox feature/config discovery for Open WebUI."""
    return await _proxy(request, "/api/config", db)


@router.get("/system")
async def get_system(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Return system information from the user's sandbox."""
    return await _proxy(request, "/system", db)


@router.get("/info")
async def get_info(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Return environment metadata from the user's sandbox."""
    return await _proxy(request, "/info", db)


# ------------------------------------------------------------------
# Port detection and service proxy
# ------------------------------------------------------------------


@router.get("/api/ports")
async def list_ports(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Detect listening ports in the user's sandbox."""
    return await _proxy(request, "/api/ports", db)


@router.api_route(
    "/proxy/{port}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
)
async def service_proxy(
    port: int,
    path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Reverse proxy to a service running on an arbitrary port inside the sandbox."""
    resolved = await resolve_sandbox(request, db)
    sandbox = resolved.sandbox
    return await forward_request(request, sandbox.internal_ip, f"/{path}", port=port)


# ------------------------------------------------------------------
# Terminal session management (REST)
# ------------------------------------------------------------------


@router.get("/api/terminals")
async def list_terminals(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """List active PTY terminal sessions in the user's sandbox."""
    return await _proxy(request, "/api/terminals", db)


@router.post("/api/terminals")
async def create_terminal(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Create a new PTY terminal session in the user's sandbox."""
    return await _proxy(request, "/api/terminals", db)


@router.delete("/api/terminals/{terminal_id}")
async def delete_terminal(
    terminal_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Delete a PTY terminal session in the user's sandbox."""
    return await _proxy(request, f"/api/terminals/{terminal_id}", db)


# ------------------------------------------------------------------
# WebSocket terminal (user-facing)
# ------------------------------------------------------------------


@router.websocket("/ws/terminal")
async def ws_terminal(websocket: WebSocket):
    """WebSocket PTY relay to the user's sandbox Open Terminal instance.

    Open WebUI connects here for interactive terminal sessions.
    Authentication is via query parameter ``token`` (the Open WebUI API key
    or user identity) since WebSocket connections cannot send custom headers.
    """
    from app.database import async_session as _async_session
    from app.services.sandbox_resolver import (
        _get_or_create_user,
        _find_user_sandbox,
        _validate_proxy_api_key,
    )

    # Extract user identity from query params.
    user_id = websocket.query_params.get("user_id", "")
    if not user_id:
        await websocket.close(code=4001, reason="Missing user_id query parameter")
        return

    async with _async_session() as db:
        user = await _get_or_create_user(user_id, db)
        sandbox = await _find_user_sandbox(user, db)
        await db.commit()

    if not sandbox or sandbox.state not in ("ACTIVE", "READY"):
        await websocket.close(code=4009, reason="No active sandbox")
        return

    await websocket.accept()

    target_url = f"ws://{sandbox.internal_ip}:{settings.sandbox_port}/ws/terminal"
    extra_headers: dict[str, str] = {}
    if settings.sandbox_api_key:
        extra_headers["Authorization"] = f"Bearer {settings.sandbox_api_key}"

    await relay_websocket(websocket, target_url, extra_headers=extra_headers)


# ------------------------------------------------------------------
# LLM Inference (LiteLLM proxy)
# ------------------------------------------------------------------


@router.post("/v1/chat/completions")
async def chat_completions(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Proxy OpenAI-compatible chat completions with credential routing."""
    return await _llm_proxy(request, "/v1/chat/completions", db)


@router.post("/v1/completions")
async def completions(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Proxy OpenAI-compatible completions with credential routing."""
    return await _llm_proxy(request, "/v1/completions", db)


@router.get("/v1/models")
async def list_models(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """List available models via the user's sandbox LiteLLM proxy."""
    return await _proxy(request, "/v1/models", db)
