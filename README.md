# ShellGuard

An open-source orchestration layer that provisions and manages secure, per-user terminal sandboxes for [Open WebUI](https://github.com/open-webui/open-webui). ShellGuard replaces shared container setups with policy-enforced isolation, giving operators granular control over what AI-assisted terminal sessions can access.

## The Problem

Open WebUI's existing terminal modes fall short in multi-user deployments:

- **Shared container** (`MULTI_USER=true`) provides no isolation between users — one misbehaving process affects everyone.
- **Enterprise terminals** are closed-source, expensive, and lack granular audit trails or policy enforcement.

ShellGuard bridges this gap by combining **Open Terminal's REST API** (familiar to Open WebUI), **OpenShell's sandbox runtime** (enforced security policies), and a **management orchestrator** (per-user lifecycle, pooling, and auditing).

## Architecture

```
┌─────────────────────────────┐
│        Open WebUI           │
│   (Terminal Integration)    │
└──────────────┬──────────────┘
               │  X-Open-WebUI-User-Id header
               v
┌──────────────────────────────────────────┐
│       ShellGuard Orchestrator            │
│            (FastAPI)                     │
│                                          │
│  API Proxy ── Policy Engine              │
│  Pool Manager ── Audit Logger            │
│  PostgreSQL state store                  │
│  React Admin UI (/admin)                 │
└──────────────┬───────────────────────────┘
               │  openshell CLI
               v
┌──────────────────────────────────────────┐
│     OpenShell Gateway (K3s cluster)      │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │  Sandbox: sg-alice-a1b2c3          │  │
│  │  Open Terminal :8000               │  │
│  │  Policy: standard                  │  │
│  │  Volume: /data/alice               │  │
│  └────────────────────────────────────┘  │
│  L7 Policy Enforcement                   │
└──────────────────────────────────────────┘
```

ShellGuard appears as a **single Open Terminal instance** to Open WebUI. No Open WebUI modifications are needed — just point your terminal integration at `http://shellguard:8080` and ShellGuard transparently routes each user to their own isolated sandbox.

## Key Features

- **Per-user isolation** — Each user gets a dedicated container with separate filesystem, network, and process namespaces.
- **Declarative policies** — YAML-based, version-controlled security policies with three tiers (restricted, standard, elevated) controlling network egress, filesystem access, process capabilities, and inference routing.
- **Sandbox pooling** — Pre-warmed sandboxes reduce cold-start latency. Configurable pool size, max active limits, and automatic lifecycle management.
- **Lifecycle automation** — Sandboxes transition through POOL, WARMING, READY, ACTIVE, SUSPENDED, and DESTROYED states based on configurable idle and suspend timeouts.
- **Complete audit trail** — Every enforcement decision, lifecycle event, and admin action is logged with full context, filterable, and exportable.
- **Real-time monitoring** — CPU, memory, disk, and network I/O per sandbox with configurable alert thresholds and webhook integration.
- **L7 network control** — Restrict HTTP methods, destinations, and paths per policy. Block or allow specific egress targets.
- **Inference routing** — Route model API calls through LiteLLM proxy with automatic credential injection and stripping.
- **Admin dashboard** — React SPA for operators covering sandbox management, policy editing, user/group administration, audit logs, and system monitoring.
- **Multi-auth** — Local credentials or OIDC/SSO (Authentik, Keycloak) for admin authentication.
- **Observability** — OpenTelemetry tracing, Prometheus-compatible metrics endpoint, webhook and syslog event forwarding.

## How It Works

### Request Flow

**First request from a new user (alice):**

1. Open WebUI sends `POST /api/execute` with header `X-Open-WebUI-User-Id: alice`.
2. The API proxy resolves alice's effective policy (user override > group > role > system default).
3. The pool manager claims a pre-warmed sandbox and assigns it to alice.
4. The policy engine applies the resolved policy via `openshell policy set`.
5. Alice's data volume is mounted at `/data/alice`.
6. The request is proxied to the sandbox's internal IP on port 8000.
7. A replacement pre-warmed sandbox is created to maintain pool size.

**Returning user:** The request is routed directly to alice's ACTIVE sandbox — no setup delay.

**Suspended user:** The sandbox resumes automatically. The API returns HTTP 202 with `Retry-After` until the sandbox is ready, then proxies normally.

### Sandbox Lifecycle

```
POOL ──create──> WARMING ──assign──> READY ──request──> ACTIVE
                                       ^                  │
                                       │    idle_timeout   │
                                       │                  v
                                       └───────────── SUSPENDED
                                                          │
                                            suspend_timeout│
                                                          v
                                                      DESTROYED
```

| State | Description |
|-------|-------------|
| POOL | Pre-warmed, unassigned, waiting for a user |
| WARMING | Being created or initializing |
| READY | Assigned to a user, not yet serving requests |
| ACTIVE | Actively serving requests |
| SUSPENDED | Idle past `idle_timeout` (default 30 min), kept for rapid resume |
| DESTROYED | Expired past `suspend_timeout` (default 24h) or manually destroyed |

### Policy System

Policies are YAML documents with four sections:

```yaml
metadata:
  name: standard
  tier: standard        # restricted | standard | elevated
  version: 1.0.0

network:
  egress:
    - destination: "github.com"
      methods: ["GET"]
  default: deny

filesystem:
  writable: ["/home/user", "/tmp"]
  readable: ["/home/user", "/tmp", "/usr"]
  default: deny

process:
  allow_sudo: false
  allow_ptrace: false
  blocked_syscalls: ["mount", "umount"]

inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
```

**Policy resolution precedence:** User override > Group assignment > Role default > System default.

Network and inference rules are **dynamic** (hot-reload on running sandboxes). Filesystem and process rules are **static** (require sandbox recreation to apply).

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, React Router 7, Recharts, Lucide React |
| Backend | Python, FastAPI, SQLAlchemy 2.0, asyncpg, Pydantic, PyYAML |
| Database | PostgreSQL 16 with Row-Level Security |
| Auth | Supabase Auth (frontend), OIDC/SSO or local credentials (backend) |
| Observability | OpenTelemetry, Prometheus client |
| Infrastructure | Docker, Docker Compose, OpenShell Gateway (K3s) |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- An [OpenShell](https://openshell.dev) gateway (for sandbox provisioning)
- An Open WebUI instance (optional, for end-to-end integration)

### 1. Clone and configure

```bash
git clone https://github.com/taylorelley/shellguard.git
cd shellguard
cp .env.example .env
```

Edit `.env` with your values. At minimum, set:

```bash
OPENSHELL_GATEWAY=http://your-openshell-gateway:6443
ADMIN_API_KEY=your-secret-admin-key
```

### 2. Start the stack

```bash
docker compose up -d
```

This starts:
- **shellguard** — The orchestrator (API + admin UI) on port 8080
- **shellguard-db** — PostgreSQL 16 database

### 3. Access the admin dashboard

Open `http://localhost:8080` in your browser and log in with your admin credentials.

### 4. Connect Open WebUI

In Open WebUI's settings, configure the terminal integration URL:

```
http://shellguard:8080
```

Open WebUI will inject the `X-Open-WebUI-User-Id` header automatically. ShellGuard handles the rest.

## Development Setup

### Frontend

```bash
npm install
npm run dev          # Start Vite dev server
npm run lint         # Run ESLint
npm run typecheck    # TypeScript type checking
npm run build        # Production build
```

### Backend

```bash
cd backend
pip install -e ".[test]"
python -m pytest -v  # Run tests
```

### Environment Variables

The frontend requires Supabase credentials at build time:

```bash
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

See [`.env.example`](.env.example) for the full list of configuration options including pool sizing, lifecycle timeouts, audit retention, metrics, and OpenTelemetry settings.

## Project Structure

```
src/
├── main.tsx                    # React entry point
├── App.tsx                     # Router with auth-protected routes
├── types/index.ts              # All TypeScript interfaces
├── lib/
│   ├── supabase.ts             # Supabase client
│   └── utils.ts                # Shared utilities
├── contexts/
│   └── AuthContext.tsx          # Auth provider
├── hooks/
│   └── useSupabaseQuery.ts     # Data fetching with realtime subscriptions
├── pages/                      # Route-level components
│   ├── Dashboard.tsx            # Operational overview
│   ├── Sandboxes.tsx            # Sandbox management
│   ├── Policies.tsx             # Policy editor and assignments
│   ├── UsersGroups.tsx          # User and group admin
│   ├── AuditLog.tsx             # Filterable event logs
│   ├── Monitoring.tsx           # Resource usage and alerts
│   ├── Settings.tsx             # System configuration
│   └── Login.tsx                # Authentication
└── components/
    ├── layout/                  # App shell (Sidebar, TopBar)
    └── ui/                      # Reusable primitives

backend/
├── app/
│   ├── main.py                  # FastAPI application
│   ├── models.py                # SQLAlchemy ORM models
│   ├── routes/                  # API endpoints
│   │   ├── proxy.py             # Open Terminal-compatible API proxy
│   │   ├── sandboxes.py         # Sandbox CRUD
│   │   ├── policies.py          # Policy management
│   │   ├── auth.py              # Authentication
│   │   └── system.py            # Settings and config
│   └── services/                # Business logic
│       ├── policy_engine.py     # Policy resolution and validation
│       ├── sandbox_resolver.py  # User-to-sandbox mapping
│       ├── pool_manager.py      # Pool lifecycle management
│       ├── openshell_client.py  # OpenShell CLI wrapper
│       ├── audit_service.py     # Audit logging
│       ├── user_sync_service.py # Open WebUI user sync
│       ├── litellm_service.py   # Inference routing
│       └── proxy_client.py      # HTTP forwarding to sandboxes
└── pyproject.toml               # Python dependencies

supabase/
└── migrations/                  # PostgreSQL schema migrations

shellguard-sandbox/
├── Dockerfile                   # Slim sandbox image
└── Dockerfile.full              # Full sandbox image
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | (required) | PostgreSQL connection string |
| `OPENSHELL_GATEWAY` | (required) | OpenShell gateway endpoint |
| `ADMIN_API_KEY` | (empty) | API key for management endpoints |
| `POOL_WARMUP_SIZE` | `2` | Pre-warmed sandboxes to maintain |
| `POOL_MAX_SANDBOXES` | `20` | Maximum total sandboxes |
| `POOL_MAX_ACTIVE` | `10` | Maximum concurrently active sandboxes |
| `DEFAULT_IMAGE_TAG` | `shellguard-sandbox:slim` | Sandbox container image |
| `IDLE_TIMEOUT` | `1800` | Seconds before suspending idle sandboxes |
| `SUSPEND_TIMEOUT` | `86400` | Seconds before destroying suspended sandboxes |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warning, error) |

See [`.env.example`](.env.example) for additional options.

## Documentation

- [Architecture Overview](docs/architecture.md)
- [Policy Guide](docs/policy-guide.md)
- [Deployment Guide](docs/deployment.md)
- [API Reference](docs/api-reference.md)
- [TLS & Reverse Proxy Setup](docs/tls-reverse-proxy.md)
- [Operational Runbook](docs/runbook.md)
- [Security Review](docs/security-review.md)

## Security

ShellGuard enforces isolation at multiple levels: container namespaces, L7 network policies, filesystem whitelists, process restrictions, and credential management. Row-Level Security is enabled on all database tables.

For security best practices and vulnerability reporting, see [SECURITY.md](SECURITY.md).

## License

MIT
