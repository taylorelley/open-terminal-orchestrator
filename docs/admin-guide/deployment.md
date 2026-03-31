# Open Terminal Orchestrator Deployment Guide

This document covers deploying Open Terminal Orchestrator using Docker Compose for quick-start/development and K3s for production environments.

## Prerequisites

- Docker and Docker Compose v2
- Access to an OpenShell gateway (K3s cluster with OpenShell installed)
- An Open WebUI instance to integrate with
- (Production) A K3s cluster with `kubectl` configured

## SQLite Local Mode

For evaluation, demos, or development without external dependencies, set `DATABASE_URL=sqlite:///./oto.db` in your `.env` file and omit `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`. Tables are auto-created on first startup and authentication uses local email/password with JWT tokens. No PostgreSQL, Supabase, or Docker required.

## Docker Compose Quick Start

The provided `docker-compose.yml` starts Open Terminal Orchestrator and its PostgreSQL database.

### 1. Clone and Configure

```bash
git clone <repository-url> oto
cd open-terminal-orchestrator
cp .env.example .env   # or create .env manually
```

Edit `.env` with your values:

```bash
# Required
OPENSHELL_GATEWAY=http://openshell-gateway:6443
OPEN_WEBUI_BASE_URL=http://open-webui:8080
OPEN_WEBUI_API_KEY=your-open-webui-api-key
ADMIN_API_KEY=your-admin-api-key

# Optional overrides
SG_DB_PASS=oto
POOL_WARMUP_SIZE=2
POOL_MAX_SANDBOXES=20
POOL_MAX_ACTIVE=10
DEFAULT_IMAGE_TAG=oto-sandbox:slim
IDLE_TIMEOUT=1800
SUSPEND_TIMEOUT=86400
LOG_LEVEL=info

# Frontend (only needed if building the image locally)
VITE_SUPABASE_URL=your-supabase-url
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### 2. Start Services

```bash
docker compose up -d
```

This starts two containers:

- **oto** -- The backend API + admin UI on port 8080
- **oto-db** -- PostgreSQL 16 Alpine with a health check

The Open Terminal Orchestrator container depends on the database being healthy before starting.

### 3. Verify

```bash
# Check container status
docker compose ps

# Check health endpoint
curl http://localhost:8080/health
```

You should see `{"status": "healthy", "version": "0.1.0", "checks": {"database": "connected"}}`.

### 4. Configure Open WebUI

In Open WebUI admin settings, go to Integrations and set the terminal endpoint to:

```
http://oto:8080
```

(Use the Docker network hostname if Open WebUI is on the same Docker network, or `http://host:8080` if accessing externally.)

### Docker Compose Architecture

```
docker compose up
  |
  +-- oto-db (postgres:16-alpine)
  |     Port: internal only
  |     Volume: oto-db-data
  |
  +-- oto (FastAPI + React SPA)
        Port: 8080:8080
        Volume: oto-user-data -> /var/lib/oto/user-data
        Volume: /var/run/docker.sock (for container management)
        Depends on: oto-db (healthy)
```

## K3s Production Deployment

The `deploy/k3s/` directory contains Kubernetes manifests managed with Kustomize.

### Manifest Overview

| File | Purpose |
|---|---|
| `namespace.yaml` | Creates the `oto` namespace |
| `secret.yaml` | Stores database password, API keys, OIDC secrets |
| `configmap.yaml` | Non-sensitive configuration (pool sizes, timeouts, URLs) |
| `postgres.yaml` | PostgreSQL StatefulSet with PVC |
| `pvc.yaml` | PersistentVolumeClaim for user data volumes |
| `oto.yaml` | Open Terminal Orchestrator Deployment |
| `service.yaml` | ClusterIP Service for Open Terminal Orchestrator |
| `ingress.yaml` | Ingress resource for external access |
| `kustomization.yaml` | Kustomize configuration tying it all together |

### 1. Create Secrets

Edit `deploy/k3s/secret.yaml` or use `kubectl create secret`:

```bash
kubectl create namespace oto

kubectl -n oto create secret generic oto-secrets \
  --from-literal=database-url='postgresql://oto:YOUR_DB_PASS@oto-db:5432/oto' \
  --from-literal=admin-api-key='YOUR_ADMIN_KEY' \
  --from-literal=open-webui-api-key='YOUR_OWUI_KEY' \
  --from-literal=oidc-client-secret='YOUR_OIDC_SECRET'
```

### 2. Configure

Edit `deploy/k3s/configmap.yaml` with your environment-specific values:

```yaml
data:
  OPENSHELL_GATEWAY: "http://openshell-gateway.openshell.svc:6443"
  OPEN_WEBUI_BASE_URL: "http://open-webui.default.svc:8080"
  POOL_WARMUP_SIZE: "2"
  POOL_MAX_SANDBOXES: "20"
  POOL_MAX_ACTIVE: "10"
  IDLE_TIMEOUT: "1800"
  SUSPEND_TIMEOUT: "86400"
```

### 3. Deploy

```bash
kubectl apply -k deploy/k3s/
```

### 4. Verify

```bash
kubectl -n oto get pods
kubectl -n oto logs deployment/oto
curl https://oto.your-domain.com/health
```

### Ingress

Edit `deploy/k3s/ingress.yaml` to match your domain and TLS configuration. The default expects a TLS secret named `oto-tls` and routes to the Open Terminal Orchestrator service on port 8080.

## Environment Variable Reference

All configuration is read from environment variables by the backend `Settings` class. A `.env` file in the project root is also loaded automatically.

### Database

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://oto:open-terminal-orchestrator@localhost:5432/oto` | PostgreSQL connection string. The `postgresql://` prefix is auto-converted to `postgresql+asyncpg://`. |

### External Services

| Variable | Default | Description |
|---|---|---|
| `OPENSHELL_GATEWAY` | `http://openshell-gateway:6443` | OpenShell gateway API endpoint |
| `OPEN_WEBUI_BASE_URL` | `http://open-webui:8080` | Open WebUI base URL for user sync |
| `OPEN_WEBUI_API_KEY` | (empty) | API key for authenticating with Open WebUI |
| `ADMIN_API_KEY` | (empty) | Primary admin API key for management API access |

### Proxy

| Variable | Default | Description |
|---|---|---|
| `SANDBOX_PORT` | `8000` | Port that Open Terminal listens on inside sandboxes |
| `PROXY_TIMEOUT` | `30` | Timeout in seconds for proxied requests to sandboxes |

### User Data

| Variable | Default | Description |
|---|---|---|
| `USER_DATA_BASE_DIR` | `/var/lib/oto/user-data` | Base directory for per-user data volumes |

### Pool Configuration

| Variable | Default | Description |
|---|---|---|
| `POOL_WARMUP_SIZE` | `2` | Number of pre-warmed sandboxes to maintain |
| `POOL_MAX_SANDBOXES` | `20` | Maximum total sandboxes |
| `POOL_MAX_ACTIVE` | `10` | Maximum concurrently active sandboxes |
| `DEFAULT_IMAGE_TAG` | `oto-sandbox:slim` | Docker image tag for sandbox containers |

### Lifecycle Timeouts

| Variable | Default | Description |
|---|---|---|
| `IDLE_TIMEOUT` | `1800` (30 min) | Seconds of inactivity before sandbox suspension |
| `SUSPEND_TIMEOUT` | `86400` (24 hr) | Seconds a suspended sandbox is kept before destruction |
| `STARTUP_TIMEOUT` | `120` (2 min) | Maximum seconds to wait for sandbox to reach READY |
| `RESUME_TIMEOUT` | `30` | Maximum seconds to wait for a suspended sandbox to resume |
| `CLEANUP_INTERVAL` | `30` | Seconds between pool manager cleanup loop runs |

### Audit

| Variable | Default | Description |
|---|---|---|
| `AUDIT_RETENTION_DAYS` | `90` | Number of days to retain audit log entries |
| `AUDIT_RETENTION_INTERVAL` | `86400` (24 hr) | Seconds between audit retention cleanup runs |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `AUTH_METHOD` | `local` | Authentication method: `local`, `oidc`, or `both` |
| `OIDC_ISSUER` | (empty) | OIDC provider issuer URL (e.g., Authentik, Keycloak) |
| `OIDC_CLIENT_ID` | (empty) | OIDC client ID |
| `OIDC_CLIENT_SECRET` | (empty) | OIDC client secret |
| `OIDC_REDIRECT_URI` | (empty) | OIDC callback URL (e.g., `https://oto.example.com/admin/api/auth/oidc/callback`) |
| `OIDC_SCOPES` | `openid email profile` | OIDC scopes to request |
| `OIDC_SESSION_SECRET` | (empty, auto-generated) | Secret for signing session JWTs |

### Server

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8080` | Bind port |
| `LOG_LEVEL` | `info` | Logging level (`debug`, `info`, `warning`, `error`) |
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins |

### Metrics

| Variable | Default | Description |
|---|---|---|
| `METRICS_TOKEN` | (empty) | Bearer token for the Prometheus `/metrics` endpoint |

### Frontend

| Variable | Default | Description |
|---|---|---|
| `FRONTEND_DIST_PATH` | `../dist` | Path to the built React SPA dist directory |

## Database Initialization

Open Terminal Orchestrator uses SQLAlchemy with Alembic-style migrations. On first startup, the backend automatically creates the required tables if they do not exist.

For manual schema management, migration files are located in `supabase/migrations/`. These can be applied using the Supabase CLI or directly against PostgreSQL:

```bash
# Apply migrations manually (if not using auto-creation)
psql -h localhost -U oto -d oto -f supabase/migrations/001_initial.sql
```

### Backup and Restore

Open Terminal Orchestrator provides a built-in backup endpoint that exports all policies, policy versions, assignments, groups, and system configuration as a JSON archive:

```bash
curl -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
     -X POST http://localhost:8080/admin/api/backup \
     -o oto-backup-$(date +%Y%m%d).json
```

For full database backups (including audit logs and sandbox records), use standard PostgreSQL tools:

```bash
# Backup
pg_dump -h localhost -U oto oto > oto-full-backup.sql

# Restore
psql -h localhost -U oto oto < oto-full-backup.sql
```
