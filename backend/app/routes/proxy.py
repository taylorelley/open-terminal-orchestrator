"""Open Terminal-compatible proxy API.

These endpoints mirror the Open Terminal REST API surface so that Open WebUI
can connect to ShellGuard as if it were a single Open Terminal instance.
Each request is routed to the calling user's assigned sandbox.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.litellm_service import litellm_router
from app.services.proxy_client import forward_request
from app.services.sandbox_resolver import resolve_sandbox

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


@router.get("/api/search")
async def search_files(request: Request, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    """Search files in the user's sandbox."""
    return await _proxy(request, "/api/search", db)


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
