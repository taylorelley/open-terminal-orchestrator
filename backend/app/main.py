"""FastAPI application factory and entry point."""

import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import check_db_connection, engine, get_db
from app.logging import setup_logging
from app.middleware import PrometheusMiddleware, RequestIDMiddleware, configure_cors
from app.routes.health import router as health_router
from app.routes.policies import router as policies_router
from app.routes.proxy import router as proxy_router
from app.routes.sandboxes import router as sandboxes_router
from app.routes.system import router as system_router
from app.routes.users import router as users_router
from app.services.audit_service import audit_retention_manager
from app.services.pool_manager import pool_manager
from app.services.proxy_client import close_client, init_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Startup and shutdown lifecycle hooks."""
    setup_logging(settings.log_level)
    logger.info("ShellGuard starting", extra={"port": settings.port})

    db_ok = await check_db_connection()
    if db_ok:
        logger.info("Database connection verified")
    else:
        logger.warning("Database is not reachable — running in degraded mode")

    await init_client()
    await pool_manager.start()
    await audit_retention_manager.start()

    yield

    await audit_retention_manager.stop()
    await pool_manager.stop()
    await close_client()
    await engine.dispose()
    logger.info("ShellGuard stopped")


app = FastAPI(
    title="ShellGuard",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(PrometheusMiddleware)
app.add_middleware(RequestIDMiddleware)
configure_cors(app)

# API routes
app.include_router(health_router)
app.include_router(proxy_router)
app.include_router(sandboxes_router)
app.include_router(policies_router)
app.include_router(users_router)
app.include_router(system_router)

# Root-level metrics endpoint for Prometheus scraping (optional token auth).
@app.get("/metrics", tags=["metrics"])
async def prometheus_metrics(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    from app.metrics import collect_db_gauges, generate_metrics_output

    if settings.metrics_token:
        expected = f"Bearer {settings.metrics_token}"
        if not authorization or not secrets.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="Invalid metrics token")

    await collect_db_gauges(db)
    return PlainTextResponse(
        content=generate_metrics_output(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


# Serve the frontend SPA at /admin if the build output exists.
_dist = Path(settings.frontend_dist_path)
if not _dist.is_absolute():
    _dist = (Path(__file__).resolve().parent.parent / settings.frontend_dist_path).resolve()

if _dist.is_dir():
    app.mount("/admin", StaticFiles(directory=str(_dist), html=True), name="admin")
    logger.info("Frontend SPA mounted at /admin", extra={"path": str(_dist)})
else:
    logger.info(
        "Frontend dist directory not found — /admin will not be served",
        extra={"path": str(_dist)},
    )


def run() -> None:
    """Entry point for the ``shellguard`` console script."""
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )


if __name__ == "__main__":
    run()
