# Open Terminal Orchestrator — Product Requirements Document

**Secure Terminal Orchestration for Open WebUI via OpenShell Sandboxes**

**Version:** 1.0
**Date:** 2026-03-27
**Author:** Open Terminal Orchestrator Contributors
**Status:** Draft

---

## 1. Executive Summary

Open Terminal Orchestrator is an open-source orchestration layer that provisions and manages per-user secure terminal environments for Open WebUI. It replaces the proprietary Open WebUI Terminals project with a security-first alternative, combining Open Terminal's lightweight REST API with OpenShell's policy-enforced sandbox runtime. Each Open WebUI user receives an isolated, policy-governed container with granular controls over network egress, filesystem access, process privileges, and inference routing — all managed through a dedicated admin web UI.

The project targets self-hosted deployments where AI agents need code execution capabilities but operators require auditable, enforceable constraints on what those agents can touch. It is designed for both personal infrastructure (homelabs, developer workstations) and regulated enterprise environments where formal evidence of access control is required.

---

## 2. Problem Statement

Open WebUI's terminal integration currently offers two modes, neither of which is adequate for security-conscious multi-user deployments:

**Single shared container (Open Terminal with `MULTI_USER=true`):** All users share the same kernel, network, and system resources. Isolation is limited to Unix user permissions. A misbehaving process affects all users. Open Terminal's own documentation explicitly states this is not suitable for production multi-user use.

**Per-user containers (Terminals):** The official Open WebUI Terminals project promises container-per-user isolation with tenant scoping, but it is closed-source under the Open WebUI Enterprise License, has no published code, and offers no policy enforcement beyond basic container boundaries. There is no mechanism for administrators to define or audit what agents within those containers can access.

Neither approach provides the granular, declarative, auditable access controls that regulated or security-conscious environments require. There is no way to restrict outbound network access at the HTTP method/path level, enforce filesystem boundaries beyond container defaults, control privilege escalation, route inference traffic through managed backends, or produce an audit trail of policy enforcement decisions.

---

## 3. Goals

### 3.1 Primary Goals

- **G1 — Per-user sandbox isolation:** Every Open WebUI user gets a dedicated OpenShell sandbox running Open Terminal, with full container-level isolation including separate filesystem, network namespace, and process tree.

- **G2 — Declarative policy enforcement:** Administrators define security policies as versioned YAML files controlling network egress (L7), filesystem access, process restrictions, and inference routing. Policies are assignable per user, per group, or per role.

- **G3 — Transparent Open WebUI integration:** Open Terminal Orchestrator presents the standard Open Terminal REST API surface to Open WebUI. No modifications to Open WebUI are required. The system-level Open Terminal integration (admin settings → integrations) connects to Open Terminal Orchestrator as if it were a single Open Terminal instance.

- **G4 — Management web UI:** A dedicated admin interface for managing sandboxes, policies, user assignments, resource utilisation, and audit logs. Accessible to operators independently of Open WebUI.

- **G5 — Lifecycle automation:** Sandboxes are provisioned on first use, suspended after configurable idle timeouts, resumed on next request, and destroyed after extended inactivity. Resource consumption scales with active users, not total registered users.

### 3.2 Secondary Goals

- **G6 — Policy-as-code workflow:** Policies are stored in Git-compatible YAML files, enabling version control, pull request review, and CI/CD integration for policy changes.

- **G7 — Inference routing integration:** Sandbox model API traffic can be routed through an existing LiteLLM Proxy or similar gateway, inheriting RBAC, priority queuing, and model access controls.

- **G8 — Audit trail:** All policy enforcement decisions (allows, denies, routes) are logged with timestamps, user context, and request metadata, queryable through the management UI.

- **G9 — GPU passthrough:** Sandboxes can optionally be granted GPU access for local inference or compute workloads, controlled via policy.

### 3.3 Non-Goals

- **NG1:** Modifying or forking Open WebUI itself. Open Terminal Orchestrator operates as an external service.
- **NG2:** Replacing OpenShell's core sandbox runtime. Open Terminal Orchestrator orchestrates OpenShell; it does not reimplement it.
- **NG3:** Providing a general-purpose Kubernetes management interface. The management UI is scoped to Open Terminal Orchestrator's domain.
- **NG4:** Supporting non-Open-Terminal workloads in v1. The BYOC image is purpose-built for Open Terminal.
- **NG5:** Multi-cluster or multi-gateway deployments in v1. Single OpenShell gateway only.

---

## 4. Users and Personas

### 4.1 Operator / Administrator

Responsible for deploying and configuring Open Terminal Orchestrator, defining security policies, managing user-to-policy assignments, monitoring resource usage, and reviewing audit logs. May be the same person as the Open WebUI admin in smaller deployments.

**Needs:** Policy authoring tools, real-time visibility into sandbox states, resource consumption dashboards, audit log search, ability to terminate or restart sandboxes, bulk user management.

### 4.2 End User (via Open WebUI)

Uses Open WebUI's terminal integration to run code, manage files, and execute commands within AI-assisted workflows. Unaware of Open Terminal Orchestrator's existence — the experience is identical to connecting to a standard Open Terminal instance.

**Needs:** Fast sandbox startup (or instant if pre-warmed), persistent files across sessions, responsive terminal, no friction from the security layer.

### 4.3 Security Reviewer / Compliance Auditor

Reviews policy definitions, audit logs, and enforcement records to verify that AI agent execution environments meet organisational or regulatory requirements.

**Needs:** Exportable audit logs, policy version history, evidence that enforcement is applied consistently, clear documentation of the security model.

---

## 5. System Architecture

### 5.1 High-Level Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         Open WebUI                               │
│          (System-level Terminal integration)                      │
│          Configured endpoint: http://oto:8080             │
└────────────────────────┬─────────────────────────────────────────┘
                         │
          REST API calls with X-Open-WebUI-User-Id header
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Open Terminal Orchestrator Orchestrator                        │
│                       (FastAPI + Python)                          │
│                                                                  │
│  ┌──────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐  │
│  │  API     │ │  Sandbox     │ │  Policy    │ │  Audit       │  │
│  │  Proxy   │ │  Pool Mgr    │ │  Engine    │ │  Logger      │  │
│  └────┬─────┘ └──────┬───────┘ └─────┬──────┘ └──────┬───────┘  │
│       │              │               │               │           │
│  ┌────┴──────────────┴───────────────┴───────────────┴────────┐  │
│  │                  State Store (PostgreSQL)                   │  │
│  │  users, sandboxes, policies, assignments, audit_log        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Management Web UI (React/TypeScript)           │  │
│  │              Served at: http://oto:8080/admin        │  │
│  └────────────────────────────────────────────────────────────┘  │
└────────────────────────┬─────────────────────────────────────────┘
                         │
              openshell CLI / API calls
                         │
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OpenShell Gateway (K3s)                        │
│                                                                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐       │
│  │  Sandbox:      │ │  Sandbox:      │ │  Sandbox:      │       │
│  │  usr-a1b2c3    │ │  usr-d4e5f6    │ │  (pre-warmed)  │       │
│  │                │ │                │ │                │       │
│  │ ┌────────────┐ │ │ ┌────────────┐ │ │ ┌────────────┐ │       │
│  │ │   Open     │ │ │ │   Open     │ │ │ │   Open     │ │       │
│  │ │  Terminal  │ │ │ │  Terminal  │ │ │ │  Terminal  │ │       │
│  │ │  :8000     │ │ │ │  :8000     │ │ │ │  :8000     │ │       │
│  │ └────────────┘ │ │ └────────────┘ │ │ └────────────┘ │       │
│  │                │ │                │ │                │       │
│  │ Policy: std    │ │ Policy: elev   │ │ Policy: std    │       │
│  │ Vol: /data/a1  │ │ Vol: /data/d4  │ │ (unassigned)   │       │
│  └────────────────┘ └────────────────┘ └────────────────┘       │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                  Policy Engine (L7)                       │   │
│  │         Network · Filesystem · Process · Inference        │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Component Descriptions

**API Proxy** — Receives all inbound REST requests from Open WebUI. Extracts the user identity from the `X-Open-WebUI-User-Id` header (injected by Open WebUI's backend proxy mode). Routes the request to the correct sandbox's internal Open Terminal API. Handles sandbox-not-ready states with appropriate retry/wait responses.

**Sandbox Pool Manager** — Manages the full sandbox lifecycle: creation, assignment, suspension, resumption, and destruction. Maintains a configurable pool of pre-warmed unassigned sandboxes to reduce cold-start latency. Communicates with OpenShell via the `openshell` CLI (v1) or OpenShell's gateway API (future). Runs a periodic cleanup loop to suspend/destroy idle sandboxes.

**Policy Engine** — Stores and manages policy definitions (YAML). Handles policy-to-user/group/role assignment. Applies policies at sandbox creation (static: filesystem, process) and hot-reloads dynamic policies (network, inference) on running sandboxes. Validates policy syntax before application.

**Audit Logger** — Records all policy enforcement events, sandbox lifecycle events, and administrative actions. Writes to the state store with structured metadata. Provides query APIs for the management UI and export endpoints for compliance tooling.

**State Store** — PostgreSQL database holding all persistent state. Chosen for compatibility with the existing Open WebUI/Supabase ecosystem. Schema covers: user registry (synced from Open WebUI), sandbox records, policy definitions, policy assignments, audit log entries, and pool configuration.

**Management Web UI** — React/TypeScript single-page application served by the orchestrator. Provides dashboard, sandbox management, policy editor, user/group management, audit log viewer, and system configuration interfaces. Authenticated independently or via SSO (Authentik integration).

### 5.3 BYOC Sandbox Image

The custom Open Terminal sandbox image is built from Open Terminal's slim variant to minimise attack surface:

```dockerfile
# oto-sandbox/Dockerfile
FROM ghcr.io/open-webui/open-terminal:slim

LABEL org.opencontainers.image.title="Open Terminal Orchestrator Sandbox"
LABEL org.opencontainers.image.description="Open Terminal in OpenShell sandbox"

# Health check for pool manager readiness probes
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/entrypoint-slim.sh"]
```

The image is registered with OpenShell as a local BYOC source:

```bash
openshell sandbox create \
  --from ./oto-sandbox/ \
  --name <sandbox-name> \
  --policy <policy-file>
```

For deployments requiring additional tooling (Python packages, data science libraries, language runtimes), a `full` variant based on Open Terminal's `latest` tag is also provided.

---

## 6. Sandbox Lifecycle

### 6.1 State Machine

```
                    ┌──────────────────────┐
                    │                      │
                    ▼                      │
┌──────┐   create  ┌─────────┐   assign   ┌──────────┐
│      ├──────────►│         ├───────────►│          │
│ POOL │           │ WARMING │            │ READY    │
│      │◄──────────┤         │            │          │
└──────┘  reclaim  └─────────┘            └────┬─────┘
                                               │
                              idle timeout     │  request
                         ┌─────────────────────┤
                         │                     │
                         ▼                     ▼
                   ┌───────────┐         ┌───────────┐
                   │           │ request │           │
                   │ SUSPENDED ├────────►│  ACTIVE   │
                   │           │         │           │
                   └─────┬─────┘         └───────────┘
                         │
              expire timeout
                         │
                         ▼
                   ┌───────────┐
                   │           │
                   │ DESTROYED │
                   │           │
                   └───────────┘
```

### 6.2 Lifecycle Parameters

| Parameter | Default | Description |
|---|---|---|
| `pool.warmup_size` | 2 | Number of pre-warmed unassigned sandboxes to maintain |
| `pool.max_sandboxes` | 20 | Maximum total sandboxes (active + suspended) |
| `pool.max_active` | 10 | Maximum concurrently running sandboxes |
| `lifecycle.idle_timeout` | 30m | Time after last activity before a sandbox is suspended |
| `lifecycle.suspend_timeout` | 24h | Time a suspended sandbox is retained before destruction |
| `lifecycle.startup_timeout` | 120s | Maximum time to wait for a sandbox to reach READY state |
| `lifecycle.resume_timeout` | 30s | Maximum time to wait for a suspended sandbox to resume |

### 6.3 Request Flow — First Access

1. Open WebUI backend sends `POST /api/execute` with header `X-Open-WebUI-User-Id: alice`.
2. API Proxy extracts user ID `alice`, queries state store for active sandbox.
3. No sandbox exists. Sandbox Pool Manager checks for available pre-warmed sandbox.
4. Pre-warmed sandbox `sg-pool-001` is claimed and assigned to `alice`.
5. Policy Engine resolves alice's policy assignment (user-level → group-level → default) and applies it via `openshell policy set`.
6. User data volume `/data/alice` is mounted.
7. Sandbox state transitions from POOL → WARMING → READY.
8. API Proxy forwards the original request to `http://<sandbox-ip>:8000/api/execute`.
9. Response is proxied back to Open WebUI.
10. Pool Manager triggers creation of a replacement pre-warmed sandbox to maintain pool size.

### 6.4 Request Flow — Returning User

1. Request arrives with `X-Open-WebUI-User-Id: alice`.
2. State store shows sandbox `sg-alice-a1b2c3` in ACTIVE state.
3. Last-activity timestamp updated.
4. Request proxied directly to sandbox. No provisioning delay.

### 6.5 Request Flow — Suspended Sandbox

1. Request arrives for user `bob` whose sandbox is in SUSPENDED state.
2. Sandbox Pool Manager issues `openshell sandbox resume sg-bob-d4e5f6`.
3. API Proxy returns HTTP 202 with `Retry-After: 5` header.
4. Open WebUI retries. If sandbox reaches READY within `resume_timeout`, request is proxied normally.
5. If resume fails, a new sandbox is provisioned and the old one is destroyed.

---

## 7. Policy System

### 7.1 Policy Definition Schema

Policies are YAML files conforming to the OpenShell policy specification with Open Terminal Orchestrator-specific metadata extensions:

```yaml
# policies/restricted.yaml
metadata:
  name: restricted
  description: "Default policy for standard users. Package registry access only."
  tier: restricted
  version: "1.2.0"
  changelog: "Added registry.npmjs.org to allowed egress"

network:
  egress:
    - destination: "pypi.org"
      methods: ["GET"]
    - destination: "files.pythonhosted.org"
      methods: ["GET"]
    - destination: "registry.npmjs.org"
      methods: ["GET"]
  default: deny

filesystem:
  writable:
    - /home/user
    - /tmp
  readable:
    - /home/user
    - /tmp
    - /usr
    - /lib
    - /etc/ssl/certs
  default: deny

process:
  allow_sudo: false
  allow_ptrace: false
  blocked_syscalls:
    - mount
    - umount
    - reboot
    - kexec_load

inference:
  routes: []
```

```yaml
# policies/standard.yaml
metadata:
  name: standard
  description: "Trusted users. GitHub, GitLab access, inference routing."
  tier: standard
  version: "1.0.0"

network:
  egress:
    - destination: "pypi.org"
      methods: ["GET"]
    - destination: "files.pythonhosted.org"
      methods: ["GET"]
    - destination: "registry.npmjs.org"
      methods: ["GET"]
    - destination: "api.github.com"
      methods: ["GET"]
    - destination: "github.com"
      methods: ["GET"]
    - destination: "gitlab.com"
      methods: ["GET"]
  default: deny

filesystem:
  writable:
    - /home/user
    - /tmp
    - /shared/projects
  readable:
    - /home/user
    - /tmp
    - /shared/projects
    - /usr
    - /lib
    - /etc/ssl/certs
  default: deny

process:
  allow_sudo: false
  allow_ptrace: false

inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
    - match: "api.anthropic.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
```

```yaml
# policies/elevated.yaml
metadata:
  name: elevated
  description: "Administrators. Broad access, GPU eligible, full inference."
  tier: elevated
  version: "1.0.0"

network:
  egress:
    - destination: "*.pypi.org"
      methods: ["GET"]
    - destination: "*.npmjs.org"
      methods: ["GET"]
    - destination: "*.github.com"
      methods: ["GET", "POST", "PUT", "PATCH"]
    - destination: "*.gitlab.com"
      methods: ["GET", "POST", "PUT", "PATCH"]
    - destination: "*.docker.io"
      methods: ["GET"]
  default: deny

filesystem:
  writable:
    - /home/user
    - /tmp
    - /shared/projects
    - /shared/datasets
  readable:
    - /home/user
    - /tmp
    - /shared
    - /usr
    - /lib
    - /etc
  default: deny

process:
  allow_sudo: true
  allow_ptrace: false

inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
    - match: "api.anthropic.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true

gpu:
  enabled: true
  devices: ["all"]
```

### 7.2 Policy Assignment Hierarchy

Policies resolve in the following precedence order (highest wins):

1. **User-level override** — Explicit policy assigned to a specific user.
2. **Group-level assignment** — Policy assigned to the user's Open WebUI group.
3. **Role-level default** — Policy mapped to the user's Open WebUI role (admin, user).
4. **System default** — Fallback policy defined in Open Terminal Orchestrator configuration.

### 7.3 Policy Versioning

All policy definitions are stored with full version history in the state store. When a policy is updated, existing sandboxes using that policy receive the new dynamic sections (network, inference) via hot-reload. Static sections (filesystem, process) require sandbox recreation, which is scheduled for the next idle cycle. The management UI displays policy diff views for version comparisons.

---

## 8. Management Web UI

### 8.1 Overview

The management UI is a React/TypeScript SPA served at `/admin` on the Open Terminal Orchestrator orchestrator. It communicates with the orchestrator's management API (separate from the Open Terminal proxy API). Authentication is handled via local credentials or SSO (Authentik/OIDC).

### 8.2 Information Architecture

```
Open Terminal Orchestrator Admin
├── Dashboard
├── Sandboxes
│   ├── Active Sandboxes
│   ├── Suspended Sandboxes
│   └── Pre-warmed Pool
├── Policies
│   ├── Policy Library
│   ├── Policy Editor
│   └── Policy Assignments
├── Users & Groups
│   ├── User Directory (synced from Open WebUI)
│   ├── Group Management
│   └── Role Mappings
├── Audit Log
│   ├── Enforcement Events
│   ├── Lifecycle Events
│   └── Admin Actions
├── Monitoring
│   ├── Resource Usage
│   ├── Gateway Health
│   └── Request Metrics
└── Settings
    ├── General Configuration
    ├── Pool Settings
    ├── Lifecycle Timeouts
    ├── Authentication
    ├── Integration Endpoints
    └── Backup & Export
```

### 8.3 Dashboard

The dashboard is the default landing page providing an at-a-glance operational overview.

**Key Metrics (top row cards):**
- Total active sandboxes / max capacity (with utilisation percentage)
- Total suspended sandboxes
- Pre-warmed pool size / target
- Policy enforcement events (last 24h): allows, denies, routes
- Average sandbox startup time (last hour)

**Active Sandboxes Table:**
- User, sandbox name, state, assigned policy, uptime, last activity, CPU/memory usage
- Row actions: connect (shell), suspend, destroy, change policy, view logs
- Sortable by any column, filterable by state/policy

**Recent Activity Feed:**
- Chronological stream of lifecycle events and policy enforcement decisions
- Severity-coded: info (allow, create), warning (deny), error (failure)
- Click-through to full audit detail

**Resource Utilisation Chart:**
- Time-series graph (last 24h) showing active sandbox count, CPU aggregate, memory aggregate
- Overlaid with pool headroom indicator

### 8.4 Sandboxes View

**Active Sandboxes Tab:**
- Full table with all ACTIVE and READY sandboxes
- Bulk actions: suspend selected, destroy selected, apply policy to selected
- Detail panel (slide-out on row click):
  - Sandbox metadata (name, user, created, image version)
  - Current policy (rendered YAML with syntax highlighting)
  - Resource consumption (CPU, memory, disk, network I/O)
  - Recent enforcement log entries for this sandbox
  - Active network connections
  - Terminal embed (optional, for operator debugging)

**Suspended Sandboxes Tab:**
- Table with SUSPENDED sandboxes
- Shows time since suspension, scheduled destruction time
- Actions: resume, destroy, extend retention

**Pre-warmed Pool Tab:**
- Pool status: current size vs target, creation queue
- Individual pool sandbox status (WARMING, READY)
- Configuration controls: adjust pool size, image selection
- Pool health: average warmup time, failure rate

### 8.5 Policy Management

**Policy Library:**
- Card grid or table of all defined policies
- Each card shows: name, tier badge (restricted/standard/elevated), version, description, assignment count (how many users/groups use it)
- Actions: edit, clone, delete, view history, view assignments

**Policy Editor:**
- Full-featured YAML editor with syntax highlighting and OpenShell schema validation
- Split-pane view: YAML source on left, rendered summary on right
- Real-time validation with inline error markers
- Diff view against previous version
- Dry-run option: validate policy against OpenShell without applying
- Save creates a new version; previous versions are retained
- Section toggles for guided editing:
  - Network rules builder (add/remove egress rules via form inputs)
  - Filesystem path selector
  - Process restrictions checkboxes
  - Inference route configuration

**Policy Assignments:**
- Three-column layout: Users | Groups | Roles
- Each column shows assigned policy for each entity
- Drag-and-drop or dropdown to change policy assignment
- Conflict/override indicators (e.g., user has explicit assignment overriding group)
- Preview: select a user to see the resolved effective policy with inheritance trace

### 8.6 Users & Groups

**User Directory:**
- Synced from Open WebUI's user database (read-only for user attributes)
- Table: username, email, Open WebUI role, assigned group, effective policy, active sandbox status
- Click to view user detail: sandbox history, enforcement events, policy override
- Action: assign/change policy override for individual user

**Group Management:**
- Create/edit/delete groups (Open Terminal Orchestrator-specific, not Open WebUI groups)
- Assign users to groups
- Assign policy to group
- Groups serve as the primary policy assignment mechanism for multi-user deployments

**Role Mappings:**
- Map Open WebUI roles (admin, user, pending) to default Open Terminal Orchestrator policies
- Simple table: role → policy dropdown

### 8.7 Audit Log

**Enforcement Events Tab:**
- Filterable table of all policy enforcement decisions
- Columns: timestamp, user, sandbox, event type (allow/deny/route), rule matched, destination, method, path
- Full-text search across all fields
- Export: CSV, JSON, or JSONL for external analysis
- Retention configuration (default 90 days)

**Lifecycle Events Tab:**
- All sandbox state transitions
- Columns: timestamp, sandbox, user, event (created, assigned, suspended, resumed, destroyed), trigger (user request, idle timeout, manual, pool reclaim), duration

**Admin Actions Tab:**
- All changes made through the management UI
- Columns: timestamp, admin user, action type, target entity, details (diff for policy changes)

**Cross-cutting features:**
- Date range picker with presets (last hour, 24h, 7d, 30d, custom)
- Saved filter presets
- Real-time streaming mode (new events appear without refresh)
- Click any event to expand full detail including raw request/response metadata

### 8.8 Monitoring

**Resource Usage:**
- Per-sandbox CPU, memory, disk, and network I/O charts
- Aggregate cluster resource utilisation
- Historical trends (1h, 24h, 7d, 30d)
- Threshold alerts configuration (e.g., alert if any sandbox exceeds 2 GB memory)

**Gateway Health:**
- OpenShell gateway status (healthy/degraded/unreachable)
- K3s cluster health indicators
- Container runtime status
- Last successful health check timestamp

**Request Metrics:**
- Requests per second through the proxy (total, per user)
- Response time percentiles (p50, p95, p99)
- Error rate breakdown (proxy errors, sandbox errors, policy denials)
- Sandbox startup/resume latency histogram

### 8.9 Settings

**General Configuration:**
- Open Terminal Orchestrator instance name, base URL
- OpenShell gateway connection details
- Open WebUI integration endpoint and API key
- BYOC image registry and tag configuration

**Pool Settings:**
- All lifecycle parameters from section 6.2, editable with validation
- Apply changes (triggers pool resize if warmup_size changed)

**Authentication:**
- Local admin credentials management
- OIDC/OAuth2 SSO configuration (Authentik, Keycloak, etc.)
- API key management for programmatic access to the management API

**Integration Endpoints:**
- LiteLLM Proxy URL for inference routing
- Prometheus endpoint for metrics export
- Webhook URLs for lifecycle event notifications
- Syslog/SIEM forwarding for audit events

**Backup & Export:**
- Export all policies as a YAML bundle (for Git storage)
- Export all configuration as TOML/YAML
- Database backup trigger
- Import policies from YAML bundle

---

## 9. API Specification

### 9.1 Proxy API (Open Terminal Compatible)

Open Terminal Orchestrator exposes the full Open Terminal REST API on its root path. Open WebUI connects to this as a standard Open Terminal instance. All endpoints require the `X-Open-WebUI-User-Id` header (injected by Open WebUI's backend proxy mode) or an `Authorization: Bearer <api-key>` header.

The proxy transparently forwards requests to the user's assigned sandbox. If the sandbox is not ready, the proxy handles provisioning/resumption and returns appropriate HTTP status codes.

| Method | Path | Description | Sandbox State Handling |
|---|---|---|---|
| POST | `/api/execute` | Execute a command | Provision if needed, 202 while warming |
| GET | `/api/files` | List files | Provision if needed |
| GET | `/api/files/{path}` | Read file | Provision if needed |
| PUT | `/api/files/{path}` | Write file | Provision if needed |
| DELETE | `/api/files/{path}` | Delete file | Provision if needed |
| POST | `/api/files/upload` | Upload file | Provision if needed |
| GET | `/api/files/download/{path}` | Download file | Provision if needed |
| GET | `/api/search` | Search files | Provision if needed |
| GET | `/health` | Orchestrator health | Always available |

### 9.2 Management API

The management API is served under `/admin/api/` and requires admin authentication.

**Sandboxes**

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api/sandboxes` | List all sandboxes with status |
| GET | `/admin/api/sandboxes/{id}` | Get sandbox detail |
| POST | `/admin/api/sandboxes/{id}/suspend` | Suspend a sandbox |
| POST | `/admin/api/sandboxes/{id}/resume` | Resume a sandbox |
| DELETE | `/admin/api/sandboxes/{id}` | Destroy a sandbox |
| POST | `/admin/api/sandboxes/{id}/policy` | Update sandbox policy |
| GET | `/admin/api/sandboxes/{id}/logs` | Get sandbox enforcement logs |
| GET | `/admin/api/pool` | Get pool status |
| PUT | `/admin/api/pool` | Update pool configuration |

**Policies**

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api/policies` | List all policies |
| POST | `/admin/api/policies` | Create a new policy |
| GET | `/admin/api/policies/{id}` | Get policy with version history |
| PUT | `/admin/api/policies/{id}` | Update policy (creates new version) |
| DELETE | `/admin/api/policies/{id}` | Delete policy (fails if assigned) |
| GET | `/admin/api/policies/{id}/versions` | List all versions |
| GET | `/admin/api/policies/{id}/versions/{v}` | Get specific version |
| POST | `/admin/api/policies/{id}/validate` | Validate policy YAML |
| POST | `/admin/api/policies/{id}/dry-run` | Test policy against OpenShell |
| GET | `/admin/api/policies/assignments` | List all assignments |
| PUT | `/admin/api/policies/assignments/users/{uid}` | Assign policy to user |
| PUT | `/admin/api/policies/assignments/groups/{gid}` | Assign policy to group |
| PUT | `/admin/api/policies/assignments/roles/{role}` | Assign policy to role |
| GET | `/admin/api/policies/resolve/{uid}` | Resolve effective policy for user |

**Users & Groups**

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api/users` | List users (synced from Open WebUI) |
| GET | `/admin/api/users/{id}` | Get user detail with sandbox history |
| POST | `/admin/api/users/sync` | Trigger user sync from Open WebUI |
| GET | `/admin/api/groups` | List groups |
| POST | `/admin/api/groups` | Create group |
| PUT | `/admin/api/groups/{id}` | Update group |
| DELETE | `/admin/api/groups/{id}` | Delete group |
| PUT | `/admin/api/groups/{id}/members` | Set group membership |

**Audit**

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api/audit/enforcement` | Query enforcement events |
| GET | `/admin/api/audit/lifecycle` | Query lifecycle events |
| GET | `/admin/api/audit/admin` | Query admin action events |
| GET | `/admin/api/audit/export` | Export audit data (CSV/JSON/JSONL) |

**System**

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api/system/health` | Full system health check |
| GET | `/admin/api/system/metrics` | Prometheus-compatible metrics |
| GET | `/admin/api/system/config` | Get current configuration |
| PUT | `/admin/api/system/config` | Update configuration |
| POST | `/admin/api/system/backup` | Trigger configuration backup |

---

## 10. Data Model

### 10.1 Core Entities

```
┌───────────┐       ┌──────────────┐       ┌───────────┐
│   users   │       │  sandboxes   │       │ policies  │
├───────────┤       ├──────────────┤       ├───────────┤
│ id (PK)   │──┐    │ id (PK)      │    ┌──│ id (PK)   │
│ owui_id   │  │    │ name         │    │  │ name      │
│ username  │  ├───►│ user_id (FK) │    │  │ tier      │
│ email     │  │    │ state        │    │  │ version   │
│ owui_role │  │    │ policy_id(FK)│◄───┘  │ yaml      │
│ group_id  │  │    │ internal_ip  │       │ created   │
│ synced_at │  │    │ api_key      │       │ updated   │
└───────────┘  │    │ image_tag    │       └───────────┘
               │    │ gpu_enabled  │
┌───────────┐  │    │ created_at   │   ┌─────────────────┐
│  groups   │  │    │ last_active  │   │ policy_versions │
├───────────┤  │    │ suspended_at │   ├─────────────────┤
│ id (PK)   │  │    │ destroyed_at │   │ id (PK)         │
│ name      │  │    └──────────────┘   │ policy_id (FK)  │
│ policy_id │──┘                       │ version         │
│ created   │    ┌──────────────────┐  │ yaml            │
└───────────┘    │ policy_assign    │  │ created_by      │
                 ├──────────────────┤  │ created_at      │
                 │ id (PK)          │  │ changelog       │
                 │ entity_type      │  └─────────────────┘
                 │ entity_id        │
                 │ policy_id (FK)   │  ┌──────────────────┐
                 │ priority         │  │ audit_log        │
                 │ created_by       │  ├──────────────────┤
                 │ created_at       │  │ id (PK)          │
                 └──────────────────┘  │ timestamp        │
                                       │ event_type       │
                                       │ category         │
                                       │ user_id (FK)     │
                                       │ sandbox_id (FK)  │
                                       │ details (JSONB)  │
                                       │ source_ip        │
                                       └──────────────────┘
```

### 10.2 Sandbox States

| State | Description | Transitions To |
|---|---|---|
| `POOL` | In pre-warmed pool, unassigned | WARMING |
| `WARMING` | Being provisioned/configured | READY, DESTROYED (on failure) |
| `READY` | Running, assigned to user, waiting for requests | ACTIVE, SUSPENDED |
| `ACTIVE` | Currently processing requests | READY (request complete), SUSPENDED |
| `SUSPENDED` | Stopped, retaining state and volumes | READY (on resume), DESTROYED |
| `DESTROYED` | Terminated, volumes optionally retained | (terminal state) |

---

## 11. Security Model

### 11.1 Defence in Depth Layers

```
Layer 1: Open Terminal Orchestrator Authentication
  └── Open WebUI backend proxy validates user session
  └── Management UI authenticated via OIDC or local credentials
  └── Management API requires admin bearer token

Layer 2: OpenShell Network Policy (L7)
  └── Per-sandbox egress rules at HTTP method + path level
  └── Default deny — only explicitly allowed destinations reachable
  └── Hot-reloadable without sandbox restart

Layer 3: OpenShell Filesystem Policy
  └── Per-sandbox mount and access restrictions
  └── User data volumes isolated per user
  └── Locked at sandbox creation (immutable during runtime)

Layer 4: OpenShell Process Policy
  └── Syscall restrictions via seccomp profiles
  └── Privilege escalation prevention
  └── Locked at sandbox creation

Layer 5: Container Isolation (K3s/containerd)
  └── Separate PID, network, mount namespaces per sandbox
  └── Resource limits (CPU, memory) via cgroups
  └── No shared writable volumes between sandboxes

Layer 6: Credential Isolation
  └── API keys injected as runtime env vars via OpenShell providers
  └── Never written to sandbox filesystem
  └── Inference routing strips sandbox credentials, injects backend credentials
```

### 11.2 Threat Model Summary

| Threat | Mitigation |
|---|---|
| Agent exfiltrates data via network | L7 egress policy blocks unapproved destinations and methods |
| Agent reads another user's files | Filesystem policy + per-user volume isolation |
| Agent escalates privileges | Process policy blocks sudo, dangerous syscalls |
| Agent accesses credentials on disk | Credentials injected as env vars only, never written to FS |
| Agent uses inference API to bypass controls | Inference routing strips credentials, routes through managed backend |
| User accesses another user's sandbox | Sandbox-to-user mapping enforced at orchestrator level |
| Operator makes unauthorised policy change | Admin actions logged in audit trail, OIDC authentication required |
| Compromised sandbox attacks gateway | K3s network policies isolate sandbox-to-gateway communication |

### 11.3 Credential Flow

```
Admin configures provider    OpenShell injects at    Open Terminal reads
in Open Terminal Orchestrator settings  ───► sandbox creation via  ──► env var as API key
                             openshell provider        (never on disk)
                             create --type custom
                             --from-existing

Inference request from   ──► OpenShell policy     ──► LiteLLM Proxy    ──► Model API
sandbox agent                engine strips              injects               (OpenAI,
                             sandbox creds,             backend creds         Anthropic)
                             routes to backend
```

---

## 12. Integration Points

### 12.1 Open WebUI

- **Connection mode:** System-level (admin settings → integrations → Open Terminal)
- **Endpoint:** `http://oto:8080` (the orchestrator's proxy API)
- **Authentication:** Open Terminal Orchestrator API key configured in Open WebUI admin panel
- **User identification:** Open WebUI injects `X-Open-WebUI-User-Id` header in backend proxy mode
- **No Open WebUI modifications required**

### 12.2 OpenShell

- **Interface:** `openshell` CLI (v1), gateway REST API (future)
- **Gateway location:** Local Docker container or remote host
- **Sandbox image:** Open Terminal Orchestrator BYOC image (Open Terminal slim/full)
- **Policy application:** `openshell policy set` and `openshell policy get`
- **Credential injection:** `openshell provider create`

### 12.3 Authentik (SSO)

- **Protocol:** OIDC
- **Scope:** Management UI and management API authentication
- **Flow:** Authentik provider configured with Open Terminal Orchestrator as OIDC client
- **User mapping:** Authentik groups can optionally map to Open Terminal Orchestrator groups

### 12.4 LiteLLM Proxy

- **Role:** Managed inference backend for sandbox model API traffic
- **Integration:** Configured as inference route backend in policy YAML
- **Benefits:** Inherits LiteLLM RBAC, priority queuing, model access controls, spend tracking
- **Credential flow:** OpenShell strips sandbox credentials and injects LiteLLM backend key

### 12.5 Observability Stack

- **Prometheus:** Open Terminal Orchestrator exposes `/admin/api/system/metrics` in Prometheus exposition format
- **Grafana:** Pre-built dashboard template provided for Open Terminal Orchestrator metrics
- **OpenTelemetry:** Trace context propagated from Open WebUI through orchestrator to sandbox
- **Log forwarding:** Audit log exportable to syslog or SIEM via webhook

---

## 13. Deployment

### 13.1 Docker Compose (Reference Deployment)

```yaml
# docker-compose.oto.yml
version: "3.8"

services:
  oto:
    build: ./oto
    container_name: oto
    restart: unless-stopped
    ports:
      - "8080:8080"
    environment:
      - DATABASE_URL=postgresql://oto:${SG_DB_PASS}@oto-db:5432/oto
      - OPENSHELL_GATEWAY=http://openshell-gateway:6443
      - OPEN_WEBUI_API_KEY=${OWUI_TERMINAL_KEY}
      - ADMIN_API_KEY=${SG_ADMIN_KEY}
      - AUTHENTIK_ISSUER=https://auth.example.com/application/o/oto/
      - AUTHENTIK_CLIENT_ID=${SG_OIDC_CLIENT_ID}
      - AUTHENTIK_CLIENT_SECRET=${SG_OIDC_CLIENT_SECRET}
      - LITELLM_PROXY_URL=http://litellm:4000
      - LITELLM_API_KEY=${LITELLM_KEY}
      - POOL_WARMUP_SIZE=2
      - POOL_MAX_SANDBOXES=20
      - LIFECYCLE_IDLE_TIMEOUT=30m
      - LIFECYCLE_SUSPEND_TIMEOUT=24h
    volumes:
      - ./policies:/app/policies:ro
      - /var/run/docker.sock:/var/run/docker.sock
      - oto-data:/data
    depends_on:
      - oto-db
    networks:
      - oto-internal
      - proxy

  oto-db:
    image: postgres:16-alpine
    container_name: oto-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=oto
      - POSTGRES_PASSWORD=${SG_DB_PASS}
      - POSTGRES_DB=oto
    volumes:
      - oto-db:/var/lib/postgresql/data
    networks:
      - oto-internal

volumes:
  oto-data:
  oto-db:

networks:
  oto-internal:
  proxy:
    external: true
```

### 13.2 Prerequisites

- Docker Engine 24+ with Compose v2
- OpenShell gateway running (local or remote)
- PostgreSQL 15+ (provided in Compose or external)
- Open WebUI instance with system-level terminal integration
- 4 GB RAM minimum for orchestrator + pool of 2 sandboxes (scale with pool size)

---

## 14. Development Phasing

### Phase 1 — Foundation (Weeks 1–4)

**Scope:** Core orchestrator with basic sandbox lifecycle, single policy, no management UI.

**Deliverables:**
- FastAPI orchestrator with Open Terminal API proxy
- Sandbox Pool Manager with create/destroy/connect lifecycle
- User-to-sandbox mapping via SQLite (upgrade to PostgreSQL in Phase 2)
- BYOC Dockerfile for Open Terminal slim
- Single hardcoded policy applied to all sandboxes
- Health check endpoint
- Docker Compose for orchestrator + OpenShell gateway
- Integration tested with Open WebUI

**Exit criteria:** A user in Open WebUI can open a terminal, execute commands, and manage files. The terminal runs inside an OpenShell sandbox with a default restrictive policy. Sandbox is provisioned on first access and destroyed after idle timeout.

### Phase 2 — Policy & Persistence (Weeks 5–8)

**Scope:** Multi-policy support, policy assignments, persistent user storage, PostgreSQL state store.

**Deliverables:**
- PostgreSQL state store with full schema (section 10)
- Policy CRUD API (management API, section 9.2)
- Policy assignment hierarchy (user → group → role → default)
- Per-user persistent data volumes
- Sandbox suspend/resume lifecycle
- Pre-warmed pool with configurable size
- Policy hot-reload for running sandboxes
- Audit logging for enforcement and lifecycle events
- CLI tool for policy management and diagnostics

**Exit criteria:** Different users can have different policies applied to their sandboxes. Policies can be created, edited, and assigned via the management API. Sandboxes survive suspension and resume with user data intact.

### Phase 3 — Management UI (Weeks 9–14)

**Scope:** Full management web UI as specified in section 8.

**Deliverables:**
- React/TypeScript SPA scaffolding with routing and auth
- Dashboard view with key metrics and active sandboxes
- Sandbox management views (active, suspended, pool)
- Policy library and visual editor with YAML validation
- Policy assignment interface with inheritance visualisation
- User directory and group management
- Audit log viewer with filtering and export
- Settings interface for all configurable parameters
- Authentik OIDC integration for admin authentication

**Exit criteria:** An operator can manage all aspects of Open Terminal Orchestrator through the web UI without touching the CLI or API directly. Audit logs are queryable and exportable.

### Phase 4 — Observability & Hardening (Weeks 15–18)

**Scope:** Monitoring integration, Grafana dashboards, security hardening, documentation.

**Deliverables:**
- Prometheus metrics endpoint with comprehensive instrumentation
- Grafana dashboard template for Open Terminal Orchestrator
- OpenTelemetry trace propagation
- Resource usage monitoring per sandbox
- Threshold alerting configuration
- Inference routing integration with LiteLLM Proxy
- GPU passthrough support in policy and sandbox creation
- Security review of orchestrator-to-gateway communication
- Comprehensive documentation (deployment guide, policy authoring guide, API reference)
- Automated integration test suite

**Exit criteria:** Full production-ready deployment with monitoring, alerting, GPU support, inference routing, and documentation sufficient for a new operator to deploy and configure the system independently.

---

## 15. Open Questions

| # | Question | Impact | Notes |
|---|---|---|---|
| Q1 | OpenShell gateway API stability — the project is alpha. Will the CLI interface remain stable enough to build against? | High | Mitigation: wrap all OpenShell interactions in an adapter layer that can be swapped between CLI and API backends. |
| Q2 | Open WebUI's `X-Open-WebUI-User-Id` header — is this reliably present in system-level terminal proxy mode? | High | Needs verification against Open WebUI source. Fallback: use API key per user. |
| Q3 | Sandbox cold-start latency — what is the practical time for OpenShell to provision a sandbox from a BYOC image? | Medium | If >10s, pre-warming pool is critical. Benchmark during Phase 1. |
| Q4 | OpenShell's K3s resource overhead — how much memory/CPU does the gateway itself consume? | Medium | Important for sizing the host. Benchmark during Phase 1. |
| Q5 | Should Open Terminal Orchestrator support multiple BYOC images simultaneously (e.g., slim for basic users, full for data science users)? | Low | Defer to Phase 2+ based on user feedback. Architecture supports it. |
| Q6 | Licensing — OpenShell is Apache 2.0, Open Terminal is MIT. Open Terminal Orchestrator should be Apache 2.0 or MIT. | Low | Decision needed before public release. |

---

## Appendix A — Glossary

| Term | Definition |
|---|---|
| **BYOC** | Bring Your Own Container — OpenShell feature for using custom Docker images as sandbox bases. |
| **Gateway** | The OpenShell control-plane component that manages sandbox lifecycle and policy enforcement. Runs as K3s inside Docker. |
| **L7 policy** | Application-layer (HTTP method + path) network policy enforcement, as opposed to L3/L4 IP/port filtering. |
| **Pre-warmed sandbox** | A sandbox that has been created and is running but not yet assigned to a user. Reduces first-access latency. |
| **Provider** | OpenShell's credential management primitive. Named bundles of secrets injected into sandboxes as environment variables. |
| **Sandbox** | An isolated container environment managed by OpenShell, running an Open Terminal instance. |
| **Open Terminal Orchestrator** | The name of this project: the orchestration layer between Open WebUI and OpenShell. |

## Appendix B — Reference Links

- [NVIDIA OpenShell](https://github.com/NVIDIA/OpenShell) — Sandbox runtime
- [Open Terminal](https://github.com/open-webui/open-terminal) — Terminal REST API
- [Open WebUI](https://github.com/open-webui/open-webui) — AI chat interface
- [Open WebUI Terminals](https://github.com/open-webui/terminals) — Enterprise orchestrator (closed source, reference only)
- [OpenShell Documentation](https://docs.nvidia.com/openshell/latest/index.html) — Full OpenShell docs
- [OpenShell Community Sandboxes](https://github.com/NVIDIA/OpenShell-Community) — BYOC examples
