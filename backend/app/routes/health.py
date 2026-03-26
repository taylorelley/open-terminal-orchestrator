"""Health check endpoint."""

from fastapi import APIRouter, Response

from app.database import check_db_connection

router = APIRouter()


@router.get("/health")
async def health_check(response: Response) -> dict:
    """Return service health status including database connectivity."""
    db_ok = await check_db_connection()

    if not db_ok:
        response.status_code = 503
        return {
            "status": "degraded",
            "version": "0.1.0",
            "checks": {"database": "disconnected"},
        }

    return {
        "status": "healthy",
        "version": "0.1.0",
        "checks": {"database": "connected"},
    }
