# Backend Development Guide

This guide covers the architecture, conventions, and workflows for developing the ShellGuard backend.

## Architecture Overview

The ShellGuard backend is a Python application built with:

| Technology | Version | Purpose |
|------------|---------|---------|
| **FastAPI** | Latest | Async web framework |
| **SQLAlchemy** | 2.0 | Async ORM and database toolkit |
| **asyncpg** | Latest | PostgreSQL async driver |
| **Pydantic** | v2 | Request/response validation and serialization |
| **PyYAML** | Latest | Policy YAML parsing |
| **Authlib** | Latest | OIDC/OAuth2 authentication |
| **Prometheus client** | Latest | Metrics exposition |
| **OpenTelemetry** | Latest | Distributed tracing |

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application entry point, router registration
│   ├── config.py            # Settings class (environment variables)
│   ├── database.py          # SQLAlchemy async engine and session factory
│   ├── models.py            # SQLAlchemy ORM models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── routes/
│   │   ├── auth.py          # Authentication endpoints (OIDC, local)
│   │   ├── policies.py      # Policy CRUD and versioning
│   │   ├── sandboxes.py     # Sandbox lifecycle management
│   │   ├── users.py         # User and group management
│   │   ├── system.py        # System configuration and health
│   │   └── metrics_history.py # Historical metrics data
│   └── services/
│       ├── policy_engine.py     # Policy evaluation and enforcement
│       ├── audit_service.py     # Audit log recording
│       ├── openshell_client.py  # OpenShell gateway communication
│       ├── sandbox_resolver.py  # Sandbox-to-user resolution
│       ├── pool_manager.py      # Sandbox pool lifecycle
│       ├── alert_evaluator.py   # Alert rule evaluation
│       ├── webhook_service.py   # Webhook delivery
│       ├── syslog_service.py    # Syslog forwarding
│       ├── litellm_service.py   # LiteLLM inference routing
│       ├── user_sync_service.py # User sync from Open WebUI
│       ├── proxy_client.py      # API proxy to sandbox terminals
│       ├── oidc.py              # OIDC authentication logic
│       └── admin_auth.py        # Admin API key authentication
└── tests/                   # Test suite
```

## Adding a New Route

### 1. Define Pydantic Schemas

Add request and response schemas to `app/schemas.py`:

```python
# app/schemas.py

class ReportCreate(BaseModel):
    name: str
    description: str | None = None
    schedule: str

class ReportResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    schedule: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

### 2. Create the Route Module

Create a new file in `app/routes/`:

```python
# app/routes/reports.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas import ReportCreate, ReportResponse
from app.services.admin_auth import require_admin

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/", response_model=list[ReportResponse])
async def list_reports(
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
):
    result = await session.execute(select(Report))
    return result.scalars().all()


@router.post("/", response_model=ReportResponse, status_code=201)
async def create_report(
    payload: ReportCreate,
    session: AsyncSession = Depends(get_session),
    _admin=Depends(require_admin),
):
    report = Report(**payload.model_dump())
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report
```

### 3. Register the Router in main.py

Add the router to the FastAPI application in `app/main.py`:

```python
from app.routes.reports import router as reports_router

app.include_router(reports_router)
```

### 4. Add Admin Auth Dependency

All management API endpoints must be protected with the `require_admin` dependency. This validates either the `ADMIN_API_KEY` header or an authenticated admin session:

```python
from app.services.admin_auth import require_admin

@router.get("/", dependencies=[Depends(require_admin)])
async def list_items(...):
    ...
```

## Adding a Service

Services encapsulate business logic and external integrations. Create a new file in `app/services/`:

```python
# app/services/report_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Report


class ReportService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def generate_report(self, report_id: str) -> dict:
        # Business logic here
        ...
```

### Injecting Services

Use FastAPI's dependency injection to provide services to route handlers:

```python
async def get_report_service(
    session: AsyncSession = Depends(get_session),
) -> ReportService:
    return ReportService(session)


@router.post("/{report_id}/generate")
async def generate_report(
    report_id: str,
    service: ReportService = Depends(get_report_service),
):
    return await service.generate_report(report_id)
```

For simpler services, you can also import and instantiate them directly.

## Database Models

ORM models are defined in `app/models.py` using SQLAlchemy 2.0 declarative syntax:

```python
# app/models.py
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import uuid
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default="now()")
```

Models map directly to the tables managed by Supabase migrations. When adding new fields:

1. Create a migration in `supabase/migrations/` (see [Database Migrations Guide](database-migrations.md)).
2. Add the column to the model in `app/models.py`.
3. Add the field to the Pydantic schema in `app/schemas.py`.
4. Add the field to the TypeScript type in `src/types/index.ts` (frontend).

## Configuration

Application configuration is managed through the `Settings` class in `app/config.py`, which reads from environment variables:

```python
# app/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    ADMIN_API_KEY: str
    LOG_LEVEL: str = "info"
    OPENSHELL_GATEWAY_URL: str = "http://localhost:9000"
    POOL_WARMUP_SIZE: int = 5
    SANDBOX_STARTUP_TIMEOUT: int = 30
    SANDBOX_RESUME_TIMEOUT: int = 10
    PROXY_TIMEOUT: int = 30
    METRICS_ENABLED: bool = True
    METRICS_TOKEN: str = ""
    OIDC_DISCOVERY_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""
    OIDC_REDIRECT_URI: str = ""
    ALERT_EVALUATION_INTERVAL: int = 60

    model_config = {"env_file": ".env"}
```

Access settings via dependency injection or direct import:

```python
from app.config import Settings

settings = Settings()
```

## Error Handling

### HTTP Exceptions

Use FastAPI's `HTTPException` for client-facing errors:

```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Policy not found")
raise HTTPException(status_code=409, detail="Sandbox already active for this user")
raise HTTPException(status_code=422, detail="Invalid YAML in policy definition")
```

### Service-Level Errors

For service-layer errors, define custom exception classes and handle them with FastAPI exception handlers:

```python
class PolicyValidationError(Exception):
    def __init__(self, message: str):
        self.message = message


# In main.py
@app.exception_handler(PolicyValidationError)
async def policy_validation_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": exc.message})
```

### Logging

Use Python's standard logging throughout the backend:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Sandbox %s transitioned to %s", sandbox_id, new_state)
logger.error("Failed to connect to gateway: %s", str(e))
```

The log level is configured via the `LOG_LEVEL` environment variable.

## Testing

Tests are located in `backend/tests/` and use pytest with async support.

### Running Tests

```bash
cd backend
python -m pytest -v            # Run all tests
python -m pytest -v -k "test_policy"  # Run tests matching a pattern
python -m pytest -v --tb=short # Shorter traceback output
```

### Writing Tests

```python
# backend/tests/test_policies.py
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_policies(async_client: AsyncClient, admin_headers: dict):
    response = await async_client.get("/api/v1/policies", headers=admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_policy_invalid_yaml(async_client: AsyncClient, admin_headers: dict):
    response = await async_client.post(
        "/api/v1/policies",
        json={"name": "test", "yaml_content": "invalid: [yaml: content"},
        headers=admin_headers,
    )
    assert response.status_code == 422
```

See the [Testing Guide](testing.md) for more details on test patterns and fixtures.
