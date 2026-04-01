# Configuration Reference

Open Terminal Orchestrator is configured through environment variables. In Docker Compose deployments, these are set in the `.env` file at the project root. For Kubernetes deployments, use ConfigMaps and Secrets.

Variables marked **required** must be set for Open Terminal Orchestrator to start. All other variables have sensible defaults.

---

## Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DATABASE_URL` | string | *(required)* | Database connection string. For PostgreSQL: `postgresql://user:password@host:port/dbname` (PostgreSQL 14+). For local/dev SQLite: `sqlite:///./oto.db`. When using SQLite, tables are auto-created on first startup (no migrations needed). |
| `SG_DB_PASS` | string | `oto` | Database password. Used by the Docker Compose stack to initialize the PostgreSQL container and injected into `DATABASE_URL` automatically when using the provided `docker-compose.yml`. |

---

## External Services

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OPENSHELL_GATEWAY` | string | `http://openshell-gateway:6443` | URL of the OpenShell gateway for sandbox lifecycle operations. Used only as a fallback when the Docker CLI is not available inside the OTO container. When Docker is available (docker socket mounted), sandbox containers are managed directly via `docker run`/`stop`/`start`/`rm`. |
| `OPEN_WEBUI_BASE_URL` | string | `""` | Base URL of the Open WebUI instance. When set, Open Terminal Orchestrator periodically syncs the user list from Open WebUI so that sandbox policies can be applied before a user's first session. |
| `OPEN_WEBUI_API_KEY` | string | `""` | API key for authenticating with the Open WebUI admin API during user sync. Required when `OPEN_WEBUI_BASE_URL` is set. |
| `ADMIN_API_KEY` | string | `""` | Bearer token for authenticating requests to Open Terminal Orchestrator management API endpoints (`/api/v1/admin/*`). When left empty, API-key authentication is disabled and only session-based auth is accepted. |

---

## Frontend (Build-Time)

These variables are embedded into the frontend bundle at build time by Vite. They have no effect on the backend.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `VITE_SUPABASE_URL` | string | *(optional)* | The Supabase project URL. Used by the React frontend to initialize the Supabase client for authentication and real-time subscriptions. **When omitted**, the frontend enters "local mode" and routes all data through the backend REST API using local JWT auth. |
| `VITE_SUPABASE_ANON_KEY` | string | *(optional)* | The Supabase anonymous (public) key. Required when `VITE_SUPABASE_URL` is set. This key is safe to expose in the browser -- Row-Level Security policies on the database enforce access control. |

---

## Sandbox Network

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SANDBOX_NETWORK` | string | `oto-internal` | Docker network that sandbox containers are attached to. Must be the same network the OTO container runs on so it can reach sandboxes by IP. The default matches the network defined in the provided `docker-compose.yml`. |

---

## Sandbox Proxy

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SANDBOX_PORT` | integer | `8000` | Port that the Open Terminal process listens on inside each sandbox container. Open Terminal Orchestrator's reverse proxy forwards user traffic to this port. |
| `PROXY_TIMEOUT` | integer | `30` | HTTP proxy timeout in seconds. If a sandbox does not respond within this duration, Open Terminal Orchestrator returns a 504 Gateway Timeout to the client. Increase this value if sandbox startup is slow or if long-running terminal operations are expected. |
| `SANDBOX_API_KEY` | string | `""` | API key for Open Terminal instances inside sandboxes. Open Terminal Orchestrator injects this as `OPEN_TERMINAL_API_KEY` when creating sandbox containers and includes it as a Bearer token when proxying requests. When empty, sandbox Open Terminal instances run without authentication. Generate a secure value with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. **Note:** Changing this value requires recreating all running sandboxes. |

---

## Pool Configuration

The sandbox pool pre-warms containers so that users get near-instant access when they open a terminal session.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `POOL_WARMUP_SIZE` | integer | `2` | Number of sandbox containers to keep in the WARMING/READY state at all times. When a sandbox is assigned to a user, a new one is created to replace it. |
| `POOL_MAX_SANDBOXES` | integer | `20` | Maximum total number of sandbox containers (across all states: POOL, WARMING, READY, ACTIVE, SUSPENDED). Requests that would exceed this limit are queued. |
| `POOL_MAX_ACTIVE` | integer | `10` | Maximum number of concurrently ACTIVE sandboxes (containers with a connected user). This limit prevents resource exhaustion on the host. |
| `DEFAULT_IMAGE_TAG` | string | `oto-sandbox:slim` | Default container image used for new sandboxes when no policy overrides the image. The image must be available in the container runtime accessible by the OpenShell gateway. |

---

## Lifecycle Timeouts

These timeouts govern the automatic state transitions of sandbox containers.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `IDLE_TIMEOUT` | integer | `1800` | Seconds of inactivity (no terminal input or output) before an ACTIVE sandbox is automatically suspended. Default is 30 minutes. Set to `0` to disable idle suspension. |
| `SUSPEND_TIMEOUT` | integer | `86400` | Seconds a sandbox remains in the SUSPENDED state before it is automatically destroyed. Default is 24 hours. Set to `0` to keep suspended sandboxes indefinitely. |
| `STARTUP_TIMEOUT` | integer | `120` | Maximum seconds to wait for a sandbox container to reach the READY state after creation. If the container does not become ready within this window, it is destroyed and an error is logged. |
| `RESUME_TIMEOUT` | integer | `30` | Maximum seconds to wait for a SUSPENDED sandbox to resume to the ACTIVE state. If the sandbox does not resume in time, it is destroyed and a fresh sandbox is assigned. |

---

## Audit

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `AUDIT_RETENTION_DAYS` | integer | `90` | Number of days to retain audit log entries in the database. A background job runs daily and deletes entries older than this threshold. Set to `0` to retain audit logs indefinitely (not recommended for production). |

---

## Server

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | string | `info` | Application log verbosity. Accepted values: `debug`, `info`, `warning`, `error`. The `debug` level includes all SQL queries, HTTP requests, and sandbox state transitions -- do not use in production. |
| `CORS_ORIGINS` | JSON array | `["*"]` | List of allowed CORS origins as a JSON array (e.g., `["https://admin.example.com"]`). The default `["*"]` allows all origins, which is acceptable for development but should be restricted in production. |

---

## Metrics

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `METRICS_TOKEN` | string | `""` | Bearer token required to access the `/metrics` Prometheus endpoint. When empty, the metrics endpoint is unauthenticated. In production, set this to a strong random token and configure it in your Prometheus scrape config. |

---

## OpenTelemetry

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `OTEL_ENABLED` | boolean | `false` | Enable OpenTelemetry distributed tracing. When `true`, Open Terminal Orchestrator exports traces via the OTLP gRPC protocol. |
| `OTEL_ENDPOINT` | string | `http://localhost:4317` | OTLP gRPC exporter endpoint. This is typically the address of an OpenTelemetry Collector, Jaeger, or Tempo instance. |
| `OTEL_SERVICE_NAME` | string | `oto` | Service name reported in trace spans. Useful for distinguishing Open Terminal Orchestrator from other services in a shared tracing backend. |

---

## Example `.env` File

```bash
# Required
DATABASE_URL=postgresql://oto:changeme@oto-db:5432/oto
SG_DB_PASS=changeme
OPENSHELL_GATEWAY=http://openshell-gateway:6443

# Open WebUI integration
OPEN_WEBUI_BASE_URL=http://open-webui:8080
OPEN_WEBUI_API_KEY=sk-webui-xxxxxxxxxxxx

# Admin API
ADMIN_API_KEY=sg-admin-xxxxxxxxxxxx

# Frontend
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Pool tuning
POOL_WARMUP_SIZE=3
POOL_MAX_SANDBOXES=50
POOL_MAX_ACTIVE=25

# Lifecycle
IDLE_TIMEOUT=900
SUSPEND_TIMEOUT=43200

# Observability
LOG_LEVEL=info
METRICS_TOKEN=prom-secret-token
OTEL_ENABLED=true
OTEL_ENDPOINT=http://otel-collector:4317

# Security
CORS_ORIGINS=["https://admin.example.com"]
```

> **Security note:** Never commit your `.env` file to version control. The `.gitignore` file in this repository already excludes it.
