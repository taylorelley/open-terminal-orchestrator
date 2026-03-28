# ShellGuard — TODO

Project completeness assessment against [PRD.md](./PRD.md).

**Legend:** `[x]` = done, `[-]` = partial, `[ ]` = not started
**Priority:** P0 = critical/blocking, P1 = high, P2 = medium, P3 = low

---

## Overall Status

| Area | Completion | Notes |
|------|-----------|-------|
| Frontend UI (Section 8) | 100% | All pages, components, routing implemented; lint/typecheck/build all pass |
| Database Schema (Section 10) | 100% | All tables, RLS, indexes, metric_snapshots in place |
| Backend Orchestrator (Section 5) | 100% | FastAPI scaffold complete |
| API Proxy (Section 9.1) | 100% | All proxy endpoints, auth, sandbox resolution, LiteLLM credential routing implemented |
| Management API (Section 9.2) | 100% | All CRUD + bulk + metrics + alerts + dry-run + resolve + version get + group members done |
| Policy Engine (Section 7) | 100% | Resolution, validation, application, hot-reload, recreation, diff, dry-run all done |
| Sandbox Lifecycle (Section 6) | 100% | Pool manager, openshell client, lifecycle automation, metric snapshots implemented |
| Integrations (Section 12) | 100% | GPU passthrough with device detection/scheduling; LiteLLM credential stripping/injection |
| Testing (Section 12) | ~95% | 236/236 backend tests pass; 14 frontend test files (45 tests) covering all pages + UI components |
| Deployment (Section 13) | 100% | Docker Compose, K3s, Alembic, TLS guide, CI/CD pipeline done |
| Documentation (Section 13) | 100% | Architecture, deployment, policy, API, runbook, contributing, security review done |
| Production Readiness | 100% | LICENSE, SECURITY.md, CI/CD, CLI tool, security review, package.json metadata all done |

---

## Remaining Work

### P0 — Critical / Blocking

- [x] **Fix build toolchain**: `npm install` done; `npm run build`, `npm run lint`, `npm run typecheck` all pass
- [x] **Fix backend test environment**: Installed missing `cffi` package; fixed dry-run test patch target; 236/236 pass
- [x] **Fix ESLint configuration**: Passes after `npm install` (0 errors, 3 pre-existing warnings)
- [x] **Fix TypeScript errors in test files**: All resolved after `npm install`

### P1 — High

- [x] **Add LICENSE file**: MIT License added
- [x] **Add SECURITY.md**: Vulnerability reporting process documented
- [x] **Security review**: Threat model, OWASP Top 10 assessment, dependency audit, RLS review in `docs/security-review.md`
- [x] **Fix `package.json` metadata**: Updated to `shellguard@0.1.0`
- [x] **CLI tool for policy management**: `shellguard-cli` with policy/sandbox/user subcommands in `backend/app/cli.py`

### P2 — Medium

- [x] **GPU passthrough implementation**: Device detection via `nvidia-smi`, GPU scheduler, NVIDIA runtime config, resource tracking
- [x] **LiteLLM credential routing**: Credential stripping/injection, model routing, provider configuration in `litellm_service.py`
- [x] **CI/CD pipeline**: `.github/workflows/ci.yml` with frontend + backend jobs
- [x] **Expand frontend test coverage**: All 8 pages tested (Dashboard, Login, AuditLog, Settings, UsersGroups + existing 3)

### P3 — Low

- [x] **Backend test failure**: Fixed (was caused by `cffi` missing + incorrect mock patch target)
- [x] **Frontend test for remaining UI components**: Badge, Modal, SlidePanel, Tabs, StatCard, EmptyState all tested

---

## Detailed Completion Checklist

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
- [x] `POST /admin/api/policies/{id}/dry-run` — test policy against OpenShell
- [x] `GET /admin/api/policies/assignments` — list all assignments
- [x] `PUT /admin/api/policies/assignments` — update assignments
- [x] `GET /admin/api/policies/{id}/versions/{v}` — get specific version
- [x] `GET /admin/api/policies/resolve/{uid}` — resolve effective policy for user

### Users & Groups
- [x] `POST /admin/api/users/sync` — sync users from Open WebUI
- [x] `GET /admin/api/users` — list users
- [x] `GET /admin/api/groups` — list groups
- [x] `POST /admin/api/groups` — create group
- [x] `PUT /admin/api/groups/{id}` — update group
- [x] `DELETE /admin/api/groups/{id}` — delete group
- [x] `PUT /admin/api/groups/{id}/members` — set group membership

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
- [x] Fix ESLint config — `npm install` done; linting passes
- [x] Fix TypeScript errors — all resolved after `npm install`

## 9. BYOC Sandbox Image — P1 (PRD Section 5.3)

- [x] Create `shellguard-sandbox/Dockerfile` (slim variant from `open-terminal:slim`)
- [x] Add health check (`curl -sf http://localhost:8000/health`)
- [x] Create `shellguard-sandbox/Dockerfile.full` (full variant from `open-terminal:latest`)
- [x] Register image with OpenShell as local BYOC source
- [x] Document image customization for additional tooling

## 10. Integrations — P2 (PRD Section 12)

- [x] Open WebUI integration (backend proxy mode, `X-Open-WebUI-User-Id` extraction, `X-API-Key` validation)
- [x] OpenShell CLI sandbox lifecycle (`openshell sandbox create/suspend/resume/destroy` via `openshell_client.py`)
- [x] OpenShell policy management (`policy set` and `policy get`)
- [x] OpenShell credential injection (`openshell provider create`)
- [x] LiteLLM Proxy inference routing — full credential stripping/injection, model routing, provider configuration via `litellm_service.py`
- [x] Prometheus metrics export endpoint (hardened with startup histograms, pool utilization, webhook counters)
- [x] Webhook notifications for lifecycle events
- [x] Syslog/SIEM forwarding for audit events
- [x] OpenTelemetry trace propagation (Open WebUI → orchestrator → sandbox)
- [x] Grafana dashboard template for Prometheus metrics
- [x] GPU passthrough — device detection via `nvidia-smi`, GPU scheduler, NVIDIA runtime config, resource tracking in `openshell_client.py`

## 11. Deployment — P2 (PRD Section 13)

- [x] `docker-compose.yml` — reference deployment (orchestrator + PostgreSQL + frontend)
- [x] `Dockerfile` — ShellGuard orchestrator container (multi-stage: Node + Python)
- [x] Kubernetes/K3s manifests for production deployment
- [x] Environment variable documentation and `.env.example`
- [x] Database initialization and migration scripts (Alembic for non-Supabase PostgreSQL)
- [x] TLS/reverse proxy configuration guide
- [x] CI/CD pipeline (`.github/workflows/ci.yml`) — frontend (lint, typecheck, build, test) + backend (pytest) jobs
- [x] Fix `package.json` metadata — updated to `shellguard@0.1.0`

## 12. Testing — P2

- [x] Set up test framework — pytest works; Vitest + RTL installed and running (14 test files, 45 tests)
- [x] Unit tests for policy validation and diff logic
- [x] Unit tests for sandbox state machine transitions
- [x] Integration tests for API proxy routing — 236/236 pass (fixed `cffi` dependency)
- [x] Integration tests for management API endpoints — 236/236 pass
- [x] End-to-end test: user request → sandbox provision → command execution → response — passes
- [x] Frontend component tests for critical UI flows — all 8 pages + 6 UI components tested (14 files, 45 tests)

## 13. Documentation — P3

- [x] Architecture overview with diagrams
- [x] Deployment guide (Docker Compose + K3s)
- [x] Policy authoring guide with examples
- [x] API reference (OpenAPI/Swagger)
- [x] Operator runbook (troubleshooting, backup/restore)
- [x] Contributing guide

## 14. Production Readiness — P1 (not in original PRD checklist)

- [x] Add LICENSE file (MIT)
- [x] Add SECURITY.md (vulnerability reporting process)
- [x] Security review — threat model, dependency audit, OWASP check in `docs/security-review.md`
- [x] CLI tool for policy management and diagnostics (`shellguard-cli` in `backend/app/cli.py`)
- [x] Populate `node_modules/` — `npm install` done; all frontend tooling works
