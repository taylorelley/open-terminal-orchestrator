# ShellGuard — TODO

Project completeness assessment against [PRD.md](./PRD.md).

**Legend:** `[x]` = done, `[-]` = partial, `[ ]` = not started
**Priority:** P0 = critical/blocking, P1 = high, P2 = medium, P3 = low

---

## Overall Status

| Area | Completion | Notes |
|------|-----------|-------|
| Frontend UI (Section 8) | 100% | All pages, components, routing, monitoring, bulk actions, DnD implemented |
| Database Schema (Section 10) | 100% | All tables, RLS, indexes, metric_snapshots in place |
| Backend Orchestrator (Section 5) | 100% | FastAPI scaffold complete |
| API Proxy (Section 9.1) | 100% | All proxy endpoints, auth, sandbox resolution implemented |
| Management API (Section 9.2) | ~90% | Core CRUD + bulk + metrics + alerts done; some granular PRD endpoints missing |
| Policy Engine (Section 7) | ~95% | Resolution, validation, application, hot-reload, recreation, diff done; dry-run not implemented |
| Sandbox Lifecycle (Section 6) | 100% | Pool manager, openshell client, lifecycle automation, metric snapshots implemented |
| Integrations (Section 12) | ~85% | Open WebUI, OpenShell CLI, LiteLLM, Prometheus, webhooks, syslog done; `policy get`, `provider create`, OTel, Grafana remaining |
| Testing (Section 12) | ~85% | Backend pytest comprehensive (19 files); frontend Vitest not started |
| Deployment (Section 13) | 100% | Docker Compose, K3s, Alembic, TLS guide all done |
| Documentation (Section 13) | 100% | Architecture, deployment, policy, API, runbook, contributing all done |

---

## Remaining Work

~10 items remain, organized by priority. All items are independent unless noted.

### P1 — Integration Gaps

| # | Item | Section | Notes |
|---|------|---------|-------|
| R1 | `openshell policy get` — add `get_policy()` to `openshell_client.py` | §12.2 | `policy set` exists; `get` not implemented |
| R2 | `openshell provider create` — credential injection via OpenShell providers | §12.2, §11.3 | Credential flow described in PRD but not implemented |

### P2 — API Completeness (PRD §9.2)

| # | Item | Section | Notes |
|---|------|---------|-------|
| R3 | `POST /admin/api/policies/{id}/dry-run` — test policy against OpenShell without applying | §9.2 | Validate endpoint exists; dry-run does not |
| R4 | `GET /admin/api/policies/{id}/versions/{v}` — get specific version | §9.2 | Version list exists; individual version fetch does not |
| R5 | `GET /admin/api/policies/resolve/{uid}` — resolve effective policy for user | §9.2 | Policy engine has resolution logic; no dedicated endpoint |
| R6 | `PUT /admin/api/groups/{id}/members` — set group membership | §9.2 | Group CRUD exists; dedicated members endpoint does not |

### P2 — Observability (PRD §12.5)

| # | Item | Section | Notes |
|---|------|---------|-------|
| R7 | OpenTelemetry trace propagation — propagate trace context from Open WebUI through orchestrator to sandbox | §12.5 | Not started |
| R8 | Grafana dashboard template — pre-built dashboard for ShellGuard Prometheus metrics | §12.5 | Not started |

### P2 — Testing

| # | Item | Section | Notes |
|---|------|---------|-------|
| R9 | Frontend component tests — add Vitest + React Testing Library, cover Sandboxes, Policies, Monitoring pages | §8 | No test framework, files, or dependencies configured |

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
- [-] Dry-run / validate policy against OpenShell without applying — validate endpoint exists; dedicated dry-run endpoint not implemented (R3)
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
- [ ] `POST /admin/api/policies/{id}/dry-run` — test policy against OpenShell (R3)
- [x] `GET /admin/api/policies/assignments` — list all assignments
- [x] `PUT /admin/api/policies/assignments` — update assignments
- [ ] `GET /admin/api/policies/{id}/versions/{v}` — get specific version (R4)
- [ ] `GET /admin/api/policies/resolve/{uid}` — resolve effective policy for user (R5)

### Users & Groups
- [x] `POST /admin/api/users/sync` — sync users from Open WebUI
- [x] `GET /admin/api/users` — list users
- [x] `GET /admin/api/groups` — list groups
- [x] `POST /admin/api/groups` — create group
- [x] `PUT /admin/api/groups/{id}` — update group
- [x] `DELETE /admin/api/groups/{id}` — delete group
- [ ] `PUT /admin/api/groups/{id}/members` — set group membership (R6)

### System
- [x] `GET /admin/api/health` — detailed health status
- [x] `GET /admin/api/metrics` — Prometheus-format metrics export
- [x] `GET /admin/api/config` — system configuration
- [x] `PUT /admin/api/config` — update configuration
- [x] `POST /admin/api/backup` — trigger database backup

## 7. Authentication & Authorization — P1 (PRD Section 12.1)

- [x] Admin authentication for management API (local credentials + API key)
- [x] OIDC/OAuth2 SSO integration (Authentik, Keycloak)
- [x] API key management for programmatic access
- [x] Open WebUI `X-API-Key` header validation on proxy API

## 8. Frontend Enhancements — P2 (PRD Section 8)

- [x] YAML editor schema validation (frontend wired to backend validation endpoint)
- [x] Policy diff view between versions (UI + backend diff endpoint integrated)
- [x] Real-time streaming mode for audit log (Supabase realtime fully wired)
- [x] Saved filter presets for audit log
- [x] Threshold alerts configuration in monitoring
- [x] Terminal embed in sandbox detail panel (operator debugging)
- [x] Drag-and-drop policy assignment
- [x] Bulk actions on sandbox table (suspend/destroy selected)
- [x] Historical trend selector for monitoring charts (1h, 24h, 7d, 30d)

## 9. BYOC Sandbox Image — P1 (PRD Section 5.3)

- [x] Create `shellguard-sandbox/Dockerfile` (slim variant from `open-terminal:slim`)
- [x] Add health check (`curl -sf http://localhost:8000/health`)
- [x] Create `shellguard-sandbox/Dockerfile.full` (full variant from `open-terminal:latest`)
- [x] Register image with OpenShell as local BYOC source
- [x] Document image customization for additional tooling

## 10. Integrations — P2 (PRD Section 12)

- [x] Open WebUI integration (backend proxy mode, `X-Open-WebUI-User-Id` extraction, `X-API-Key` validation)
- [x] OpenShell CLI sandbox lifecycle (`openshell sandbox create/suspend/resume/destroy` via `openshell_client.py`)
- [-] OpenShell policy management — `policy set` done; `policy get` not implemented (R1)
- [ ] OpenShell credential injection — `openshell provider create` not implemented (R2)
- [x] LiteLLM Proxy inference routing (intercept and redirect model API calls)
- [x] Prometheus metrics export endpoint (hardened with startup histograms, pool utilization, webhook counters)
- [x] Webhook notifications for lifecycle events
- [x] Syslog/SIEM forwarding for audit events
- [ ] OpenTelemetry trace propagation (R7)
- [ ] Grafana dashboard template for Prometheus metrics (R8)

## 11. Deployment — P2 (PRD Section 13)

- [x] `docker-compose.yml` — reference deployment (orchestrator + PostgreSQL + frontend)
- [x] `Dockerfile` — ShellGuard orchestrator container (multi-stage: Node + Python)
- [x] Kubernetes/K3s manifests for production deployment
- [x] Environment variable documentation and `.env.example`
- [x] Database initialization and migration scripts (for non-Supabase PostgreSQL)
- [x] TLS/reverse proxy configuration guide

## 12. Testing — P2

- [x] Set up test framework (pytest for backend — Vitest for frontend is future)
- [x] Unit tests for policy validation and diff logic
- [x] Unit tests for sandbox state machine transitions
- [x] Integration tests for API proxy routing
- [x] Integration tests for management API endpoints
- [x] End-to-end test: user request → sandbox provision → command execution → response
- [ ] Frontend component tests for critical UI flows (Vitest setup pending)

## 13. Documentation — P3

- [x] Architecture overview with diagrams
- [x] Deployment guide (Docker Compose + K3s)
- [x] Policy authoring guide with examples
- [x] API reference (OpenAPI/Swagger)
- [x] Operator runbook (troubleshooting, backup/restore)
- [x] Contributing guide
