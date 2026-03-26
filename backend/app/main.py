"""FastAPI application factory and entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import check_db_connection, engine
from app.logging import setup_logging
from app.middleware import RequestIDMiddleware, configure_cors
from app.routes.health import router as health_router

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

    yield

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
app.add_middleware(RequestIDMiddleware)
configure_cors(app)

# API routes
app.include_router(health_router)

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
