"""CORS configuration, request-ID middleware, and Prometheus instrumentation."""

import time
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import settings


def configure_cors(app: FastAPI) -> None:
    """Add CORS middleware with origins from settings."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request count and latency as Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        from app.metrics import REQUEST_COUNT, REQUEST_LATENCY

        method = request.method
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        # Use the route path template (e.g. "/admin/api/sandboxes/{id}")
        # to avoid label cardinality explosion from path parameters.
        route = request.scope.get("route")
        path = route.path if route and hasattr(route, "path") else request.url.path
        status = str(response.status_code)

        REQUEST_COUNT.labels(method=method, path=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, path=path).observe(duration)

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate or propagate an X-Request-ID header on every request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
