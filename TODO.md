# ShellGuard — TODO

Project completeness assessment against [PRD.md](./PRD.md).

**Legend:** `[x]` = done, `[-]` = partial, `[ ]` = not started
**Priority:** P0 = critical/blocking, P1 = high, P2 = medium, P3 = low

---

## Overall Status

| Area | Completion | Notes |
|------|-----------|-------|
| Frontend UI (Section 8) | 95% | All pages, components, routing implemented; lint/typecheck broken (missing node_modules) |
| Database Schema (Section 10) | 100% | All tables, RLS, indexes, metric_snapshots in place |
| Backend Orchestrator (Section 5) | 100% | FastAPI scaffold complete |
| API Proxy (Section 9.1) | 100% | All proxy endpoints, auth, sandbox resolution implemented |
| Management API (Section 9.2) | 100% | All CRUD + bulk + metrics + alerts + dry-run + resolve + version get + group members done |
| Policy Engine (Section 7) | 100% | Resolution, validation, application, hot-reload, recreation, diff, dry-run all done |
| Sandbox Lifecycle (Section 6) | 100% | Pool manager, openshell client, lifecycle automation, metric snapshots implemented |
| Integrations (Section 12) | ~85% | GPU passthrough is stub-only; LiteLLM is routing-only (no credential mgmt) |
| Testing (Section 12) | ~55% | 129/236 backend tests pass (106 error from cryptography dep); only 3 frontend test files |
| Deployment (Section 13) | ~90% | Docker Compose, K3s, Alembic, TLS guide done; no CI/CD pipeline; build toolchain broken |
| Documentation (Section 13) | ~90% | Architecture, deployment, policy, API, runbook, contributing done; no security review docs |
| Production Readiness | ~70% | Missing LICENSE, SECURITY.md, CI/CD, CLI tool, security review, package.json metadata |

---

## Remaining Work

### P0 — Critical / Blocking

- [ ] **Fix build toolchain**: Run `npm install` to populate `node_modules/`; verify `npm run build`, `npm run lint`, and `npm run typecheck` all pass
- [ ] **Fix backend test environment**: Resolve `cryptography`/`_cffi_backend` `pyo3_runtime.PanicException` causing 106 integration test errors
- [ ] **Fix ESLint configuration**: `eslint.config.js` imports `@eslint/js` which requires `npm install`; verify linting passes after install
- [ ] **Fix TypeScript errors in test files**: Frontend test files have missing type declarations for vitest, @testing-library/react, @testing-library/user-event; likely resolved by `npm install` but may need tsconfig adjustment

### P1 — High

- [ ] **Add LICENSE file**: PRD Q6 — choose Apache 2.0 or MIT before public release
- [ ] **Add SECURITY.md**: Vulnerability reporting process for open-source project
- [ ] **Security review**: PRD Phase 4 exit criterion — threat model, dependency audit, OWASP check
- [ ] **Fix `package.json` metadata**: Name is still `vite-react-typescript-starter@0.0.0`; update to `shellguard`
- [ ] **CLI tool for policy management**: PRD Phase 2 deliverable — standalone CLI for policy CRUD, sandbox diagnostics, user sync (not yet started)

### P2 — Medium

- [ ] **GPU passthrough implementation**: PRD Phase 4 — currently stub-only (`gpu_enabled` column + `--gpu` flag); needs device detection, NVIDIA runtime config, resource scheduling
- [ ] **LiteLLM credential routing**: PRD Section 12 — currently routing-only; needs credential stripping/injection, model management, provider configuration
- [ ] **CI/CD pipeline**: Add `.github/workflows/` with build, lint, typecheck, backend tests, frontend tests
- [ ] **Expand frontend test coverage**: Only 3 page tests exist (Policies, Monitoring, Sandboxes); Dashboard, Login, AuditLog, Settings, UsersGroups pages and UI components/hooks untested

### P3 — Low

- [ ] **Backend test failure**: 1 test fails (not just errors) — investigate and fix
- [ ] **Frontend test for remaining UI components**: Badge, Modal, SlidePanel, Tabs, StatCard, EmptyState, TerminalEmbed, layout components

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
- [ ] Fix ESLint config — `npm install` required; `@eslint/js` not in `node_modules/`
- [ ] Fix TypeScript errors — test files fail `tsc --noEmit` (missing type declarations)

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
- [-] LiteLLM Proxy inference routing — routing layer only (`/v1/chat/completions` forwarded to sandbox); no credential stripping/injection, model management, or provider configuration in ShellGuard
- [x] Prometheus metrics export endpoint (hardened with startup histograms, pool utilization, webhook counters)
- [x] Webhook notifications for lifecycle events
- [x] Syslog/SIEM forwarding for audit events
- [x] OpenTelemetry trace propagation (Open WebUI → orchestrator → sandbox)
- [x] Grafana dashboard template for Prometheus metrics
- [-] GPU passthrough — stub only (`gpu_enabled` column + `--gpu` CLI flag); no device detection, NVIDIA runtime config, or resource scheduling (PRD Phase 4, G9)

## 11. Deployment — P2 (PRD Section 13)

- [x] `docker-compose.yml` — reference deployment (orchestrator + PostgreSQL + frontend)
- [x] `Dockerfile` — ShellGuard orchestrator container (multi-stage: Node + Python)
- [x] Kubernetes/K3s manifests for production deployment
- [x] Environment variable documentation and `.env.example`
- [x] Database initialization and migration scripts (Alembic for non-Supabase PostgreSQL)
- [x] TLS/reverse proxy configuration guide
- [ ] CI/CD pipeline (`.github/workflows/`) — build, lint, typecheck, backend tests, frontend tests
- [ ] Fix `package.json` metadata — name is `vite-react-typescript-starter@0.0.0`, should be `shellguard`

## 12. Testing — P2

- [-] Set up test framework — pytest works; Vitest + RTL declared in `package.json` but `node_modules/` missing so frontend tests cannot run
- [x] Unit tests for policy validation and diff logic
- [x] Unit tests for sandbox state machine transitions
- [-] Integration tests for API proxy routing — tests exist but 106/236 error with `pyo3_runtime.PanicException` (`cryptography`/`_cffi_backend` conflict)
- [-] Integration tests for management API endpoints — same environment issue as above
- [-] End-to-end test: user request → sandbox provision → command execution → response — same environment issue
- [-] Frontend component tests for critical UI flows — only 3 page tests exist (Policies, Monitoring, Sandboxes); Dashboard, Login, AuditLog, Settings, UsersGroups untested

## 13. Documentation — P3

- [x] Architecture overview with diagrams
- [x] Deployment guide (Docker Compose + K3s)
- [x] Policy authoring guide with examples
- [x] API reference (OpenAPI/Swagger)
- [x] Operator runbook (troubleshooting, backup/restore)
- [x] Contributing guide

## 14. Production Readiness — P1 (not in original PRD checklist)

- [ ] Add LICENSE file (Apache 2.0 or MIT — PRD Q6)
- [ ] Add SECURITY.md (vulnerability reporting process)
- [ ] Security review — threat model, dependency audit, OWASP check (PRD Phase 4 exit criterion)
- [ ] CLI tool for policy management and diagnostics (PRD Phase 2 deliverable)
- [ ] Populate `node_modules/` — `npm install` has never been run; all frontend tooling is broken
