# Open Terminal Orchestrator Architecture

This document describes the system architecture of Open Terminal Orchestrator, the secure terminal orchestration layer for Open WebUI.

## Overview

Open Terminal Orchestrator sits between Open WebUI and OpenShell, providing policy-enforced, per-user sandbox isolation. It consists of a FastAPI backend, a React admin UI, a PostgreSQL state store, and integration with the OpenShell sandbox runtime.

## High-Level Component Diagram

```
+-----------------------------------------------------------------+
|                         Open WebUI                              |
|          (System-level Terminal integration)                     |
|          Configured endpoint: http://oto:8080            |
+-----------------------------+-----------------------------------+
                              |
           REST API calls with X-Open-WebUI-User-Id header
                              |
                              v
+-----------------------------------------------------------------+
|                   Open Terminal Orchestrator Orchestrator                        |
|                     (FastAPI + Python)                           |
|                                                                 |
|  +----------+  +--------------+  +------------+  +------------+ |
|  |  API     |  |  Sandbox     |  |  Policy    |  |  Audit     | |
|  |  Proxy   |  |  Pool Mgr   |  |  Engine    |  |  Logger    | |
|  +----+-----+  +------+-------+  +-----+------+  +------+-----+ |
|       |               |               |                |        |
|  +----+---------------+---------------+----------------+------+ |
|  |                  State Store (PostgreSQL)                   | |
|  |  users, sandboxes, policies, assignments, audit_log        | |
|  +------------------------------------------------------------+ |
|                                                                 |
|  +------------------------------------------------------------+ |
|  |            Management Web UI (React/TypeScript)             | |
|  |            Served at: http://oto:8080/admin          | |
|  +------------------------------------------------------------+ |
+-----------------------------------------------------------------+
                              |
               openshell CLI / API calls
                              |
                              v
+-----------------------------------------------------------------+
|                   OpenShell Gateway (K3s)                        |
|                                                                 |
|  +----------------+  +----------------+  +----------------+     |
|  | Sandbox:       |  | Sandbox:       |  | Sandbox:       |     |
|  | usr-a1b2c3     |  | usr-d4e5f6     |  | (pre-warmed)   |     |
|  |                |  |                |  |                |     |
|  | +------------+ |  | +------------+ |  | +------------+ |     |
|  | | Open       | |  | | Open       | |  | | Open       | |     |
|  | | Terminal   | |  | | Terminal   | |  | | Terminal   | |     |
|  | | :8000      | |  | | :8000      | |  | | :8000      | |     |
|  | +------------+ |  | +------------+ |  | +------------+ |     |
|  |                |  |                |  |                |     |
|  | Policy: std    |  | Policy: elev   |  | Policy: std    |     |
|  | Vol: /data/a1  |  | Vol: /data/d4  |  | (unassigned)   |     |
|  +----------------+  +----------------+  +----------------+     |
|                                                                 |
|  +------------------------------------------------------------+ |
|  |                Policy Engine (L7)                           | |
|  |       Network - Filesystem - Process - Inference            | |
|  +------------------------------------------------------------+ |
+-----------------------------------------------------------------+
```

## Component Descriptions

### API Proxy

Receives all inbound REST requests from Open WebUI. Extracts the user identity from the `X-Open-WebUI-User-Id` header (injected by Open WebUI's backend proxy mode). Routes the request to the correct sandbox's internal Open Terminal API. Handles sandbox-not-ready states by triggering provisioning or resumption and returning appropriate HTTP status codes (202 with `Retry-After` while warming).

### Sandbox Pool Manager

Manages the full sandbox lifecycle: creation, assignment, suspension, resumption, and destruction. Maintains a configurable pool of pre-warmed unassigned sandboxes to reduce cold-start latency. Communicates with OpenShell via the `openshell` CLI or gateway API. Runs a periodic cleanup loop (configurable interval, default 30s) to suspend and destroy idle sandboxes.

### Policy Engine

Stores and manages policy definitions (YAML). Handles policy-to-user/group/role assignment with a priority-based resolution cascade. Applies policies at sandbox creation (static sections: filesystem, process) and hot-reloads dynamic policies (network, inference) on running sandboxes. Validates policy syntax before application.

### Audit Logger

Records all policy enforcement events, sandbox lifecycle events, and administrative actions. Writes structured metadata to the state store. Provides query APIs for the management UI and export endpoints (CSV, JSON, JSONL) for compliance tooling. Configurable retention (default 90 days).

### State Store (PostgreSQL)

Holds all persistent state: user registry (synced from Open WebUI), sandbox records, policy definitions and versions, policy assignments, audit log entries, system configuration, and metric snapshots.

### Management Web UI

React/TypeScript SPA served at `/admin` on the orchestrator. Provides dashboard, sandbox management, policy editor, user/group management, audit log viewer, monitoring charts, and system configuration. Authenticated independently via API key or OIDC SSO.

## Request Flow Diagrams

### Proxy Flow: Open WebUI to Sandbox

```
Open WebUI           Open Terminal Orchestrator Proxy         Pool Manager         OpenShell           Sandbox
    |                      |                       |                    |                  |
    |  POST /api/execute   |                       |                    |                  |
    |  X-Open-WebUI-User-Id: alice                 |                    |                  |
    |--------------------->|                       |                    |                  |
    |                      |  lookup sandbox(alice)|                    |                  |
    |                      |---------------------->|                    |                  |
    |                      |                       |                    |                  |
    |              [Case 1: sandbox ACTIVE]         |                    |                  |
    |                      |  sandbox IP returned   |                    |                  |
    |                      |<----------------------|                    |                  |
    |                      |  forward request ------------------------------>|             |
    |                      |<-------------------------------------------------------|     |
    |  <-- 200 response ---|                       |                    |                  |
    |                      |                       |                    |                  |
    |              [Case 2: no sandbox exists]      |                    |                  |
    |                      |  claim pre-warmed     |                    |                  |
    |                      |---------------------->|                    |                  |
    |                      |                       |  assign + policy   |                  |
    |                      |                       |  openshell create  |                  |
    |                      |                       |------------------->|                  |
    |                      |                       |  sandbox ready     |                  |
    |                      |                       |<------------------|                  |
    |                      |  sandbox IP returned   |                    |                  |
    |                      |<----------------------|                    |                  |
    |                      |  forward request ------------------------------>|             |
    |  <-- 200 response ---|                       |                    |                  |
    |                      |                       |                    |                  |
    |              [Case 3: sandbox SUSPENDED]      |                    |                  |
    |                      |  resume requested     |                    |                  |
    |                      |---------------------->|                    |                  |
    |  <-- 202 Retry-After |                       |  openshell resume  |                  |
    |                      |                       |------------------->|                  |
    |  POST /api/execute   |                       |                    |                  |
    |--------------------->|  sandbox now ACTIVE    |                    |                  |
    |                      |  forward request ------------------------------>|             |
    |  <-- 200 response ---|                       |                    |                  |
```

### Admin UI Flow

```
Admin Browser          Open Terminal Orchestrator Backend         PostgreSQL
    |                        |                        |
    |  GET /admin            |                        |
    |  (serves React SPA)    |                        |
    |----------------------->|                        |
    |  <-- index.html -------|                        |
    |                        |                        |
    |  GET /admin/api/sandboxes                       |
    |  Authorization: Bearer <api-key>                |
    |----------------------->|                        |
    |                        |  SELECT FROM sandboxes |
    |                        |----------------------->|
    |                        |  <-- rows -------------|
    |  <-- JSON response ----|                        |
    |                        |                        |
    |  PUT /admin/api/policies/{id}                   |
    |  { yaml: "...", changelog: "..." }              |
    |----------------------->|                        |
    |                        |  validate YAML         |
    |                        |  INSERT policy_version |
    |                        |  hot-reload sandboxes  |
    |                        |----------------------->|
    |  <-- 200 updated ------|                        |
```

## Pool Manager Lifecycle

```
                    +----------------------+
                    |                      |
                    v                      |
+------+   create  +---------+   assign   +----------+
|      +---------->|         +----------->|          |
| POOL |           | WARMING |            | READY    |
|      |<----------|         |            |          |
+------+  reclaim  +---------+            +----+-----+
                                               |
                              idle timeout     |  request
                         +---------------------+
                         |                     |
                         v                     v
                   +-----------+         +-----------+
                   |           | request |           |
                   | SUSPENDED +-------->|  ACTIVE   |
                   |           |         |           |
                   +-----+-----+         +-----------+
                         |
              expire timeout
                         |
                         v
                   +-----------+
                   |           |
                   | DESTROYED |
                   |           |
                   +-----------+
```

**Lifecycle parameters (defaults):**

| Parameter | Default | Description |
|---|---|---|
| `pool.warmup_size` | 2 | Pre-warmed unassigned sandboxes to maintain |
| `pool.max_sandboxes` | 20 | Maximum total sandboxes (active + suspended) |
| `pool.max_active` | 10 | Maximum concurrently running sandboxes |
| `lifecycle.idle_timeout` | 30m | Time after last activity before suspension |
| `lifecycle.suspend_timeout` | 24h | Time a suspended sandbox is retained before destruction |
| `lifecycle.startup_timeout` | 120s | Maximum time to wait for READY state |
| `lifecycle.resume_timeout` | 30s | Maximum time to wait for resume |

The Pool Manager runs a periodic cleanup loop (default every 30 seconds) that:

1. Checks for ACTIVE/READY sandboxes that have exceeded `idle_timeout` and suspends them.
2. Checks for SUSPENDED sandboxes that have exceeded `suspend_timeout` and destroys them.
3. Counts POOL/WARMING sandboxes and creates new ones if below `warmup_size`.

## Policy Engine Resolution Cascade

When a request arrives for a user, the Policy Engine resolves the effective policy using a priority cascade:

```
+--------------------------------------------------+
|  1. User-level override     (highest priority)   |
|     Explicit policy assigned to a specific user   |
+--------------------------------------------------+
          |  not found? fall through
          v
+--------------------------------------------------+
|  2. Group-level assignment                        |
|     Policy assigned to the user's group           |
+--------------------------------------------------+
          |  not found? fall through
          v
+--------------------------------------------------+
|  3. Role-level default                            |
|     Policy mapped to user's Open WebUI role       |
|     (admin, user, pending)                        |
+--------------------------------------------------+
          |  not found? fall through
          v
+--------------------------------------------------+
|  4. System default          (lowest priority)     |
|     Fallback policy from system configuration     |
+--------------------------------------------------+
```

Each level is checked in order. The first match wins. This allows administrators to set broad defaults at the role level, customize per group, and apply individual overrides where needed.

### Policy Hot-Reload vs Recreation

When a policy is updated, changes are classified:

- **Dynamic sections** (network egress rules, inference routes): Hot-reloaded on running sandboxes immediately via `openshell policy set`. No downtime.
- **Static sections** (filesystem mounts, process restrictions): Require sandbox recreation. The sandbox is marked for recreation and will be rebuilt on the next idle cycle.

## Technology Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.12, FastAPI, SQLAlchemy (async), Pydantic |
| Database | PostgreSQL 16 |
| Frontend | React 18, TypeScript, Vite 5, Tailwind CSS 3, Recharts |
| Sandbox Runtime | OpenShell Gateway (K3s) |
| Sandbox Image | Custom BYOC based on Open Terminal slim |
| Authentication | API key + OIDC (Authentik, Keycloak, etc.) |
