"""HTTP client for forwarding requests to sandbox Open Terminal instances."""

import logging

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import settings

logger = logging.getLogger(__name__)

# Hop-by-hop headers that must not be forwarded.
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)

# Global async client — initialised/closed via the FastAPI lifespan.
http_client: httpx.AsyncClient | None = None


async def init_client() -> None:
    """Create the module-level httpx.AsyncClient."""
    global http_client  # noqa: PLW0603
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.proxy_timeout, connect=5.0),
        follow_redirects=False,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=40),
    )
    logger.info("Proxy HTTP client initialised")


async def close_client() -> None:
    """Gracefully close the httpx.AsyncClient."""
    global http_client  # noqa: PLW0603
    if http_client is not None:
        await http_client.aclose()
        http_client = None
        logger.info("Proxy HTTP client closed")


def _filter_request_headers(request: Request) -> dict[str, str]:
    """Return request headers safe to forward to the sandbox.

    Strips hop-by-hop headers and replaces the caller's Authorization
    header with the sandbox API key (if configured).
    """
    filtered = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "authorization"
    }
    if settings.sandbox_api_key:
        filtered["authorization"] = f"Bearer {settings.sandbox_api_key}"
    return filtered


def _filter_response_headers(headers: httpx.Headers) -> dict[str, str]:
    """Return response headers safe to send back to the caller."""
    return {
        k: v
        for k, v in headers.items()
        if k.lower() not in _HOP_BY_HOP
    }


async def forward_request(
    request: Request,
    sandbox_ip: str,
    path: str,
    *,
    port: int | None = None,
) -> StreamingResponse:
    """Forward *request* to the sandbox at *sandbox_ip* and stream back the response.

    Args:
        port: Override the target port (defaults to ``settings.sandbox_port``).
              Used by the ``/proxy/{port}/{path}`` service proxy route.

    Raises:
        HTTPException(502) — sandbox is unreachable.
        HTTPException(504) — request timed out.
    """
    if http_client is None:
        raise HTTPException(status_code=503, detail="Proxy client not initialised")

    target_port = port if port is not None else settings.sandbox_port
    target_url = f"http://{sandbox_ip}:{target_port}{path}"
    if request.url.query:
        target_url = f"{target_url}?{request.url.query}"

    headers = _filter_request_headers(request)
    body = await request.body()

    try:
        response = await http_client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
        )
    except httpx.ConnectError:
        logger.warning("Sandbox unreachable at %s", sandbox_ip)
        raise HTTPException(status_code=502, detail="Sandbox unreachable")
    except httpx.TimeoutException:
        logger.warning("Request to sandbox %s timed out", sandbox_ip)
        raise HTTPException(status_code=504, detail="Sandbox request timeout")
    except httpx.HTTPError as exc:
        logger.error("Proxy error for %s: %s", sandbox_ip, exc)
        raise HTTPException(status_code=502, detail="Sandbox unreachable")

    return StreamingResponse(
        content=iter([response.content]),
        status_code=response.status_code,
        headers=_filter_response_headers(response.headers),
        media_type=response.headers.get("content-type"),
    )
