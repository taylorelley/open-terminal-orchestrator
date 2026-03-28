# ShellGuard — TODO

Project completeness assessment against [PRD.md](./PRD.md).

**Legend:** `[x]` = done, `[-]` = partial, `[ ]` = not started
**Priority:** P0 = critical/blocking, P1 = high, P2 = medium, P3 = low

---

## Overall Status

| Area | Completion | Notes |
|------|-----------|-------|
| Frontend UI (Section 8) | ~95% | All pages, components, routing implemented |
| Database Schema (Section 10) | 100% | All tables, RLS, indexes in place |
| Backend Orchestrator (Section 5) | 100% | FastAPI scaffold complete |
| API Proxy (Section 9.1) | 100% | All proxy endpoints, auth, sandbox resolution implemented |
| Management API (Section 9.2) | ~98% | All CRUD endpoints implemented; user sync placeholder remaining |
| Policy Engine (Section 7) | 100% | Resolution, validation, application, hot-reload, recreation, diff all implemented |
| Sandbox Lifecycle (Section 6) | ~85% | Pool manager, openshell client, lifecycle automation implemented |
| Integrations (Section 12) | 0% | UI config only, no backend |
| Deployment (Section 13) | 0% | No Docker/K3s manifests |

---

## 1. Backend Orchestrator — P0 (PRD Section 5)

- [x] Scaffold FastAPI Python project structure
- [x] Set up PostgreSQL connection (reuse existing Supabase schema)
- [x] Implement health check endpoint (`GET /health`)
- [x] Serve frontend SPA static files at `/admin`
- [x] Configure CORS and middleware
- [x] Add structured logging (JSON format)

## 2. API Proxy — P0 (PRD Section 9.1)

- [x] `POST /api/execute` — proxy to sandbox Open Terminal, provision if needed
- [x] `GET /api/files` — list files in sandbox
- [x] `GET /api/files/{path}` — read file from sandbox
- [x] `PUT /api/files/{path}` — write file to sandbox
- [x] `DELETE /api/files/{path}` — delete file in sandbox
- [x] `POST /api/files/upload` — upload file to sandbox
- [x] `GET /api/files/download/{path}` — download file from sandbox
- [x] `GET /api/search` — search files in sandbox
- [x] Extract user identity from `X-Open-WebUI-User-Id` header
- [x] Handle sandbox-not-ready states (HTTP 202 + `Retry-After`)
- [x] Support `Authorization: Bearer <api-key>` as alternative auth

## 3. Sandbox Pool Manager — P0 (PRD Section 6)

- [x] Integrate with `openshell` CLI for sandbox create/resume/suspend/destroy
- [x] Implement state machine (POOL → WARMING → READY → ACTIVE → SUSPENDED → DESTROYED)
- [x] Pre-warmed pool maintenance (create sandboxes to maintain `pool.warmup_size`)
- [x] Sandbox assignment on first user request
- [x] User data volume mounting (`/data/{user_id}`)
- [x] Idle timeout detection (ACTIVE/READY → SUSPENDED after `lifecycle.idle_timeout`)
- [x] Suspension expiry (SUSPENDED → DESTROYED after `lifecycle.suspend_timeout`)
- [x] Startup timeout enforcement (`lifecycle.startup_timeout`)
- [x] Resume timeout enforcement (`lifecycle.resume_timeout`)
- [x] Periodic cleanup loop (background task)
- [x] Respect `pool.max_sandboxes` and `pool.max_active` limits
- [x] Health checks / readiness probes for sandbox containers

## 4. Policy Engine — P0 (PRD Section 7)

- [x] YAML validation against OpenShell policy schema
- [x] Policy resolution: user → group → role → system default (priority cascade)
- [x] Apply policy at sandbox creation via `openshell policy set`
- [x] Hot-reload dynamic policy sections (network, inference) on running sandboxes
- [x] Schedule sandbox recreation for static policy changes (filesystem, process)
- [x] Dry-run / validate policy against OpenShell without applying
- [x] Policy diff view between versions (backend support)

## 5. Audit Logger — P1 (PRD Section 5.2, 8.7)

- [x] Automatic logging of policy enforcement events (allow/deny/route)
- [x] Automatic logging of sandbox lifecycle events (created/assigned/suspended/resumed/destroyed)
- [x] Automatic logging of admin actions (policy changes, config changes, manual operations)
- [x] Structured metadata capture (user, sandbox, source IP, request details)
- [x] Query API for management UI (`GET /admin/api/audit`)
- [x] Export endpoints (CSV, JSON, JSONL)
- [x] Retention policy enforcement (default 90 days)

## 6. Management API — P1 (PRD Section 9.2)

### Sandboxes
- [x] `GET /admin/api/sandboxes` — list all sandboxes
- [x] `GET /admin/api/sandboxes/{id}` — sandbox detail
- [x] `POST /admin/api/sandboxes/{id}/suspend` — suspend sandbox
- [x] `POST /admin/api/sandboxes/{id}/resume` — resume sandbox
- [x] `DELETE /admin/api/sandboxes/{id}` — destroy sandbox
- [x] `POST /admin/api/sandboxes/{id}/policy` — update sandbox policy
- [x] `GET /admin/api/sandboxes/{id}/logs` — sandbox enforcement logs
- [x] `GET /admin/api/pool` — pool status
- [x] `PUT /admin/api/pool` — update pool config

### Policies
- [x] `GET /admin/api/policies` — list policies
- [x] `POST /admin/api/policies` — create policy
- [x] `GET /admin/api/policies/{id}` — get policy detail
- [x] `PUT /admin/api/policies/{id}` — update policy (creates new version)
- [x] `DELETE /admin/api/policies/{id}` — delete policy
- [x] `GET /admin/api/policies/{id}/versions` — version history
- [x] `POST /admin/api/policies/{id}/validate` — YAML schema validation
- [x] `GET /admin/api/policies/assignments` — list all assignments
- [x] `PUT /admin/api/policies/assignments` — update assignments

### Users & Groups
- [-] `POST /admin/api/users/sync` — sync users from Open WebUI (placeholder, needs OWUI API)
- [x] `GET /admin/api/users` — list users
- [x] `GET /admin/api/groups` — list groups
- [x] `POST /admin/api/groups` — create group
- [x] `PUT /admin/api/groups/{id}` — update group
- [x] `DELETE /admin/api/groups/{id}` — delete group

### System
- [x] `GET /admin/api/health` — detailed health status
- [x] `GET /admin/api/metrics` — Prometheus-format metrics export
- [x] `GET /admin/api/config` — system configuration
- [x] `PUT /admin/api/config` — update configuration
- [x] `POST /admin/api/backup` — trigger database backup

## 7. Authentication & Authorization — P1 (PRD Section 12.1)

- [x] Admin authentication for management API (local credentials + API key)
- [ ] OIDC/OAuth2 SSO integration (Authentik, Keycloak)
- [x] API key management for programmatic access
- [x] Open WebUI `X-API-Key` header validation on proxy API

## 8. Frontend Enhancements — P2 (PRD Section 8)

- [-] YAML editor schema validation (UI exists, no backend validation endpoint)
- [-] Policy diff view between versions (UI exists, backend diff endpoint ready)
- [ ] Real-time streaming mode for audit log (Supabase realtime partially wired)
- [ ] Saved filter presets for audit log
- [ ] Threshold alerts configuration in monitoring
- [ ] Terminal embed in sandbox detail panel (operator debugging)
- [ ] Drag-and-drop policy assignment
- [ ] Bulk actions on sandbox table (suspend/destroy selected)
- [ ] Historical trend selector for monitoring charts (1h, 24h, 7d, 30d)

## 9. BYOC Sandbox Image — P1 (PRD Section 5.3)

- [ ] Create `shellguard-sandbox/Dockerfile` (slim variant from `open-terminal:slim`)
- [ ] Add health check (`curl -sf http://localhost:8000/health`)
- [ ] Create `shellguard-sandbox/Dockerfile.full` (full variant from `open-terminal:latest`)
- [ ] Register image with OpenShell as local BYOC source
- [ ] Document image customization for additional tooling

## 10. Integrations — P2 (PRD Section 12)

- [ ] Open WebUI integration (backend proxy mode, user ID extraction)
- [ ] OpenShell CLI integration (`openshell sandbox create/suspend/resume/destroy`)
- [ ] OpenShell policy management (`openshell policy set/get`)
- [ ] LiteLLM Proxy inference routing (intercept and redirect model API calls)
- [ ] Prometheus metrics export endpoint
- [ ] Webhook notifications for lifecycle events
- [ ] Syslog/SIEM forwarding for audit events

## 11. Deployment — P2 (PRD Section 13)

- [ ] `docker-compose.yml` — reference deployment (orchestrator + PostgreSQL + frontend)
- [ ] `Dockerfile` — ShellGuard orchestrator container
- [ ] Kubernetes/K3s manifests for production deployment
- [ ] Environment variable documentation and `.env.example`
- [ ] Database initialization and migration scripts (for non-Supabase PostgreSQL)
- [ ] TLS/reverse proxy configuration guide

## 12. Testing — P2

- [ ] Set up test framework (Vitest for frontend, pytest for backend)
- [ ] Unit tests for policy resolution logic
- [ ] Unit tests for sandbox state machine transitions
- [ ] Integration tests for API proxy routing
- [ ] Integration tests for management API endpoints
- [ ] End-to-end test: user request → sandbox provision → command execution → response
- [ ] Frontend component tests for critical UI flows

## 13. Documentation — P3

- [ ] Architecture overview with diagrams
- [ ] Deployment guide (Docker Compose + K3s)
- [ ] Policy authoring guide with examples
- [ ] API reference (OpenAPI/Swagger)
- [ ] Operator runbook (troubleshooting, backup/restore)
- [ ] Contributing guide
