# ShellGuard API Reference

ShellGuard exposes two API surfaces:

1. **Proxy API** -- Open Terminal-compatible endpoints consumed by Open WebUI (root path)
2. **Management API** -- Admin endpoints for the dashboard and automation (`/admin/api/`)

An interactive Swagger UI is available at `/docs` when the backend is running.

## Authentication

### Proxy API Authentication

The proxy API identifies users via the `X-Open-WebUI-User-Id` header, which Open WebUI's backend proxy mode injects automatically. No additional authentication is required for this header-based flow.

### Management API Authentication

All `/admin/api/` endpoints (except `/admin/api/auth/config` and the OIDC flow) require admin authentication. Two methods are supported:

**API Key (header):**

```
Authorization: Bearer YOUR_ADMIN_API_KEY
```

**OIDC Session (cookie):**

After completing the OIDC login flow, a `sg_session` cookie is set automatically. Browser-based access via the admin UI uses this method.

The `AUTH_METHOD` environment variable controls which methods are enabled: `local` (API key only), `oidc` (SSO only), or `both`.

### API Key Management

```
POST   /admin/api/auth/keys          Create a new API key (returns raw key once)
GET    /admin/api/auth/keys          List all API keys (hashes not returned)
DELETE /admin/api/auth/keys/{key_id}  Revoke an API key
```

---

## Proxy API (Open Terminal Compatible)

These endpoints mirror the full Open Terminal REST API. Open WebUI connects to ShellGuard as if it were a standard Open Terminal instance. Each request is transparently routed to the calling user's sandbox. ShellGuard uses the [open-terminal](https://github.com/open-webui/open-terminal) Python package for sandbox communication, ensuring full compatibility with Open WebUI's terminal integration.

If the user has no sandbox, one is provisioned from the pre-warmed pool. If the sandbox is suspended, it is resumed (HTTP 202 with `Retry-After` header returned while warming).

### Command Execution

```
POST /api/execute
```

Execute a command in the user's sandbox.

**Headers:** `X-Open-WebUI-User-Id: <user-id>`

**Request body:** (forwarded to Open Terminal inside the sandbox)

```json
{
  "command": "ls -la /home/user"
}
```

### File Operations

```
GET    /api/files                    List files in the user's sandbox
GET    /api/files/{path}             Read a file
PUT    /api/files/{path}             Write a file
DELETE /api/files/{path}             Delete a file
POST   /api/files/upload             Upload a file
GET    /api/files/download/{path}    Download a file
POST   /api/files/move               Move or rename a file
POST   /api/files/mkdir              Create a directory
```

### Search

```
GET /api/search
```

Search files in the user's sandbox.

### Config and Metadata Discovery

```
GET /api/config     Feature/config discovery (used by Open WebUI)
GET /system         System information
GET /info           Environment metadata
```

### Port Detection and Service Proxy

```
GET  /api/ports                          Detect listening ports in the sandbox
ANY  /proxy/{port}/{path}                Reverse proxy to a service on an arbitrary port
```

The `/proxy/{port}/{path}` endpoint supports all HTTP methods (GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD) and forwards requests to the specified port inside the user's sandbox.

### Terminal Sessions

REST endpoints for managing PTY terminal sessions:

```
GET    /api/terminals                List active PTY sessions
POST   /api/terminals               Create a new PTY session
DELETE /api/terminals/{terminal_id}  Delete a PTY session
```

WebSocket endpoint for interactive PTY sessions:

```
WS /ws/terminal?user_id=<owui-user-id>
```

Bidirectional WebSocket relay to the user's sandbox Open Terminal PTY. Open WebUI connects here for interactive terminal sessions. User identity is passed via the `user_id` query parameter.

### Inference Proxy

These endpoints proxy OpenAI-compatible API calls through the user's sandbox, where inference routing rules from the applied policy take effect.

```
POST /v1/chat/completions     Proxy chat completions
POST /v1/completions          Proxy completions
GET  /v1/models               List available models
```

### Health

```
GET /health
```

Returns orchestrator health status. Always available (no authentication required).

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "connected"
  }
}
```

Returns HTTP 503 with `"status": "degraded"` if the database is unreachable.

---

## Management API

All endpoints below are prefixed with `/admin/api` and require admin authentication.

### Sandboxes

#### List Sandboxes

```
GET /admin/api/sandboxes
```

**Query parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `state` | string | (none) | Filter by state: POOL, WARMING, READY, ACTIVE, SUSPENDED, DESTROYED |
| `include_destroyed` | bool | false | Include destroyed sandboxes in results |
| `offset` | int | 0 | Pagination offset |
| `limit` | int | 50 | Page size (max 200) |

**Response:** Paginated list of sandbox objects.

```json
{
  "items": [...],
  "total": 15,
  "offset": 0,
  "limit": 50
}
```

#### Get Sandbox

```
GET /admin/api/sandboxes/{sandbox_id}
```

#### Suspend Sandbox

```
POST /admin/api/sandboxes/{sandbox_id}/suspend
```

Suspends an ACTIVE or READY sandbox. Returns 409 if the sandbox is in another state.

#### Resume Sandbox

```
POST /admin/api/sandboxes/{sandbox_id}/resume
```

Resumes a SUSPENDED sandbox. Returns 409 if not suspended.

#### Destroy Sandbox

```
DELETE /admin/api/sandboxes/{sandbox_id}
```

Destroys a sandbox. The sandbox is marked DESTROYED even if the OpenShell destroy call fails.

#### Update Sandbox Policy

```
POST /admin/api/sandboxes/{sandbox_id}/policy
```

**Request body:**

```json
{
  "policy_id": "uuid"
}
```

If the sandbox is ACTIVE or READY, the policy is applied immediately via OpenShell. Otherwise it is stored for application on next start.

#### Get Sandbox Logs

```
GET /admin/api/sandboxes/{sandbox_id}/logs
```

Returns paginated audit log entries for a specific sandbox.

#### Sandbox Terminal (WebSocket)

```
WS /admin/api/sandboxes/{sandbox_id}/terminal?token=ADMIN_API_KEY
```

Bidirectional WebSocket relay to a sandbox's terminal. Authentication is via query parameter since WebSocket connections cannot send custom headers.

#### Bulk Sandbox Actions

```
POST /admin/api/sandboxes/bulk
```

**Request body:**

```json
{
  "action": "suspend",
  "sandbox_ids": ["uuid1", "uuid2"]
}
```

Valid actions: `suspend`, `resume`, `destroy`.

**Response:**

```json
{
  "results": [
    {"sandbox_id": "uuid1", "status": "ok"},
    {"sandbox_id": "uuid2", "status": "error", "error": "..."}
  ],
  "succeeded": 1,
  "failed": 1
}
```

### Pool

#### Get Pool Status

```
GET /admin/api/pool
```

**Response:**

```json
{
  "total": 12,
  "active": 5,
  "ready": 2,
  "warming": 1,
  "suspended": 3,
  "pool": 1,
  "max_sandboxes": 20,
  "max_active": 10,
  "warmup_size": 2
}
```

#### Update Pool Configuration

```
PUT /admin/api/pool
```

**Request body:**

```json
{
  "value": {
    "warmup_size": 3,
    "max_sandboxes": 25,
    "max_active": 15
  }
}
```

### Policies

#### List Policies

```
GET /admin/api/policies
```

Returns all policies ordered by name.

#### Create Policy

```
POST /admin/api/policies
```

**Request body:**

```json
{
  "name": "my-policy",
  "tier": "standard",
  "description": "A custom policy",
  "yaml": "metadata:\n  name: my-policy\n  ..."
}
```

Returns 422 if the YAML fails validation.

#### Get Policy

```
GET /admin/api/policies/{policy_id}
```

#### Update Policy

```
PUT /admin/api/policies/{policy_id}
```

**Request body:**

```json
{
  "name": "updated-name",
  "tier": "elevated",
  "description": "Updated description",
  "yaml": "...",
  "changelog": "Added GPU access"
}
```

All fields are optional. If `yaml` changes, a new version is created and the patch version is auto-incremented. Dynamic changes are hot-reloaded; static changes schedule sandbox recreation.

#### Delete Policy

```
DELETE /admin/api/policies/{policy_id}
```

Returns 204 on success.

#### Validate Policy

```
POST /admin/api/policies/{policy_id}/validate
```

Validates the stored YAML of an existing policy.

```
POST /admin/api/policies/validate
```

Validates arbitrary YAML without saving:

```json
{
  "yaml": "metadata:\n  name: test\n  tier: restricted\n..."
}
```

#### List Policy Versions

```
GET /admin/api/policies/{policy_id}/versions
```

Returns all versions ordered by creation date (newest first).

#### Diff Policy Versions

```
GET /admin/api/policies/{policy_id}/diff?from_version=1.0.0&to_version=1.0.1
```

Returns a structured diff between two versions.

#### Policy Assignments

```
GET /admin/api/policies/assignments
```

**Query parameters:**

| Parameter | Description |
|---|---|
| `entity_type` | Filter by type: `user`, `group`, `role` |
| `entity_id` | Filter by entity ID |

```
PUT /admin/api/policies/assignments
```

Create or update a policy assignment:

```json
{
  "entity_type": "group",
  "entity_id": "GROUP_UUID",
  "policy_id": "POLICY_UUID",
  "priority": 50
}
```

### Users and Groups

#### List Users

```
GET /admin/api/users
```

Returns users synced from Open WebUI, ordered by username.

#### Sync Users

```
POST /admin/api/users/sync
```

Triggers a user sync from Open WebUI. Returns sync results (created, updated, deleted counts).

#### List Groups

```
GET /admin/api/groups
```

#### Create Group

```
POST /admin/api/groups
```

```json
{
  "name": "developers",
  "description": "Development team",
  "policy_id": "POLICY_UUID"
}
```

#### Update Group

```
PUT /admin/api/groups/{group_id}
```

#### Delete Group

```
DELETE /admin/api/groups/{group_id}
```

### Audit Log

#### Query Audit Log

```
GET /admin/api/audit
```

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| `category` | string | Filter: `enforcement`, `lifecycle`, `admin` |
| `event_type` | string | Filter by specific event type |
| `user_id` | UUID | Filter by user |
| `sandbox_id` | UUID | Filter by sandbox |
| `since` | ISO 8601 | Start of time range |
| `until` | ISO 8601 | End of time range |
| `offset` | int | Pagination offset |
| `limit` | int | Page size (max 200) |

#### Export Audit Log

```
GET /admin/api/audit/export
```

**Query parameters:** Same filters as the query endpoint, plus:

| Parameter | Default | Description |
|---|---|---|
| `format` | `json` | Export format: `csv`, `json`, or `jsonl` |

Returns a downloadable file (max 10,000 entries).

### System Configuration

#### List Configuration

```
GET /admin/api/config
```

#### Update Configuration

```
PUT /admin/api/config/{key}
```

```json
{
  "value": { ... }
}
```

#### System Health (detailed)

```
GET /admin/api/health
```

Returns database connectivity status and version.

#### Prometheus Metrics

```
GET /admin/api/metrics
```

Returns Prometheus-format metrics as `text/plain`.

### Metrics History

```
GET /admin/api/metrics/history
```

**Query parameters:**

| Parameter | Values | Description |
|---|---|---|
| `metric` | `cpu`, `memory`, `requests`, `errors`, `latency`, `startup` | Metric to retrieve |
| `range` | `1h`, `24h`, `7d`, `30d` | Time range |

### Webhooks

#### List Webhooks

```
GET /admin/api/webhooks
```

#### Create Webhook

```
POST /admin/api/webhooks
```

```json
{
  "url": "https://hooks.example.com/shellguard",
  "enabled": true,
  "event_filters": [
    {"category": "lifecycle", "event_type": "sandbox_destroyed"}
  ]
}
```

#### Update Webhook

```
PUT /admin/api/webhooks/{index}
```

#### Delete Webhook

```
DELETE /admin/api/webhooks/{index}
```

#### Test Webhook

```
POST /admin/api/webhooks/{index}/test
```

Sends a test event to verify webhook delivery.

### Alerts

#### Get Alert Rules

```
GET /admin/api/alerts
```

#### Update Alert Rules

```
PUT /admin/api/alerts
```

### Syslog

#### Test Syslog

```
POST /admin/api/syslog/test
```

Sends a test syslog message to verify configuration.

### Backup

```
POST /admin/api/backup
```

Exports all policies, policy versions, assignments, groups, and system configuration as a JSON archive. Returns a downloadable file.

### OIDC Authentication Flow

These endpoints do not require admin authentication (they are part of the login flow):

```
GET  /admin/api/auth/config           Returns auth method configuration
GET  /admin/api/auth/oidc/login       Redirects to OIDC provider
GET  /admin/api/auth/oidc/callback    Handles OIDC provider callback
GET  /admin/api/auth/session          Returns current session info
POST /admin/api/auth/oidc/logout      Clears session and returns provider logout URL
```
