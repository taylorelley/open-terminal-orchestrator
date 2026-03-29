# Open Terminal Orchestrator Operator Runbook

This document covers operational procedures, troubleshooting, backup/restore, and log analysis for Open Terminal Orchestrator.

## Health Checks

### Quick Health Check

```bash
curl http://localhost:8080/health
```

Expected response:

```json
{"status": "healthy", "version": "0.1.0", "checks": {"database": "connected"}}
```

### Detailed Health Check (authenticated)

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/health
```

### Pool Status

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/pool
```

Check that:
- `pool` count is at or near `warmup_size`
- `total` is below `max_sandboxes`
- `active` is below `max_active`

---

## Troubleshooting

### Sandbox Stuck in WARMING

**Symptoms:** A sandbox remains in WARMING state beyond the `startup_timeout` (default 120 seconds). Users see 202 responses that never resolve.

**Diagnosis:**

1. Check the sandbox record:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/sandboxes?state=WARMING
```

2. Check Open Terminal Orchestrator backend logs for OpenShell errors:

```bash
# Docker Compose
docker compose logs oto | grep -i "warming\|openshell\|sandbox create"

# K3s
kubectl -n oto logs deployment/oto | grep -i "warming\|openshell"
```

3. Check OpenShell gateway status:

```bash
curl http://OPENSHELL_GATEWAY:6443/health
```

**Common causes and fixes:**

| Cause | Fix |
|---|---|
| OpenShell gateway unreachable | Verify `OPENSHELL_GATEWAY` env var and network connectivity |
| Image pull failure | Verify `DEFAULT_IMAGE_TAG` exists in the registry; check OpenShell logs |
| Resource exhaustion on K3s | Check node resources: `kubectl top nodes` |
| Policy validation failure | Check audit log for policy application errors |

**Resolution:** If the sandbox cannot recover, destroy it manually:

```bash
curl -X DELETE -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/sandboxes/SANDBOX_UUID
```

The pool manager will create a replacement pre-warmed sandbox automatically.

### Database Connection Failures

**Symptoms:** Health endpoint returns `{"status": "degraded", "checks": {"database": "disconnected"}}`. All management API calls return 500 errors. Proxy requests may still work for sandboxes already resolved and cached.

**Diagnosis:**

1. Check database container/pod status:

```bash
# Docker Compose
docker compose ps oto-db
docker compose logs oto-db

# K3s
kubectl -n oto get pods -l app=oto-db
kubectl -n oto logs statefulset/oto-db
```

2. Test database connectivity directly:

```bash
# Docker Compose
docker compose exec oto-db pg_isready -U oto

# K3s
kubectl -n oto exec statefulset/oto-db -- pg_isready -U oto
```

3. Check the `DATABASE_URL` environment variable matches the actual database host, port, user, and password.

**Common causes and fixes:**

| Cause | Fix |
|---|---|
| Database container crashed | `docker compose restart oto-db` or delete the pod to let K3s reschedule |
| Disk full on database volume | Expand the volume or clean up old audit logs |
| Connection limit exceeded | Increase `max_connections` in PostgreSQL config; check for connection leaks |
| Password mismatch | Verify `SG_DB_PASS` / `DATABASE_URL` match the database credentials |

### Webhook Delivery Failures

**Symptoms:** Configured webhooks are not receiving events. No external notifications for sandbox lifecycle changes.

**Diagnosis:**

1. List configured webhooks:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/webhooks
```

2. Test a specific webhook:

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/webhooks/0/test
```

3. Check backend logs for delivery errors:

```bash
docker compose logs oto | grep -i "webhook"
```

**Common causes and fixes:**

| Cause | Fix |
|---|---|
| Webhook URL unreachable | Verify URL and network access from the Open Terminal Orchestrator container |
| TLS certificate errors | Ensure the webhook endpoint's certificate is trusted |
| Webhook disabled | Check `enabled` field in webhook config |
| Event filter too restrictive | Review `event_filters` -- an empty list matches all events |

### Pool Exhaustion

**Symptoms:** New users cannot get sandboxes. Pre-warmed pool is empty. Existing users experience long waits.

**Diagnosis:**

1. Check pool status:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/pool
```

2. If `total` equals `max_sandboxes`, the pool is full. Check how many sandboxes are SUSPENDED vs ACTIVE:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/sandboxes?state=SUSPENDED"
```

**Remediation:**

- **Destroy idle suspended sandboxes** to free capacity:

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     http://localhost:8080/admin/api/sandboxes/bulk \
     -d '{"action": "destroy", "sandbox_ids": ["uuid1", "uuid2"]}'
```

- **Increase pool limits** if the infrastructure supports it:

```bash
curl -X PUT -H "Authorization: Bearer YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     http://localhost:8080/admin/api/pool \
     -d '{"value": {"max_sandboxes": 30, "max_active": 15, "warmup_size": 3}}'
```

- **Reduce idle/suspend timeouts** to reclaim sandboxes faster (set `IDLE_TIMEOUT` and `SUSPEND_TIMEOUT` environment variables and restart).

### Sandbox Policy Not Taking Effect

**Symptoms:** A user's sandbox does not reflect the expected policy (e.g., network rules not applied).

**Diagnosis:**

1. Check policy assignments for the user:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/policies/assignments?entity_type=user&entity_id=USER_UUID"
```

2. Check the sandbox's assigned policy:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/sandboxes/SANDBOX_UUID
```

3. If a policy was updated, check whether the changes were dynamic or static:
   - Dynamic (network, inference): Should be hot-reloaded. Check audit log for hot-reload events.
   - Static (filesystem, process): Requires sandbox recreation. Check if the sandbox is flagged for recreation.

---

## Backup and Restore

### Configuration Backup

Open Terminal Orchestrator provides a built-in backup endpoint that exports all policies, policy versions, assignments, groups, and system configuration:

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/backup \
     -o "oto-backup-$(date +%Y%m%dT%H%M%SZ).json"
```

The backup JSON includes:
- All policies with their YAML definitions
- Full policy version history
- All policy assignments
- All groups
- All system configuration entries

Schedule this regularly (e.g., via cron):

```bash
0 2 * * * curl -s -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8080/admin/api/backup \
  -o /backups/oto/oto-backup-$(date +\%Y\%m\%dT\%H\%M\%SZ).json
```

### Full Database Backup

For a complete backup including audit logs, sandbox records, and metric snapshots:

```bash
# Docker Compose
docker compose exec oto-db \
  pg_dump -U oto oto > oto-full-$(date +%Y%m%d).sql

# K3s
kubectl -n oto exec statefulset/oto-db -- \
  pg_dump -U oto oto > oto-full-$(date +%Y%m%d).sql
```

### Restore

To restore a full database backup:

```bash
# Docker Compose
cat oto-full-YYYYMMDD.sql | \
  docker compose exec -T oto-db psql -U oto oto

# K3s
cat oto-full-YYYYMMDD.sql | \
  kubectl -n oto exec -i statefulset/oto-db -- psql -U oto oto
```

After restoring, restart the Open Terminal Orchestrator backend to reload configuration from the database.

---

## Log Analysis

### Backend Logs

Open Terminal Orchestrator logs to stdout in structured format. The log level is controlled by the `LOG_LEVEL` environment variable (default: `info`).

```bash
# Docker Compose
docker compose logs -f oto

# K3s
kubectl -n oto logs -f deployment/oto
```

### Key Log Patterns

| Pattern | Meaning |
|---|---|
| `openshell suspend failed` | OpenShell API error during sandbox suspension |
| `openshell resume failed` | OpenShell API error during sandbox resume |
| `openshell destroy failed` | OpenShell API error during sandbox destruction (sandbox marked destroyed anyway) |
| `Failed to apply policy` | Policy could not be applied to a running sandbox |
| `Terminal WebSocket error` | Error in the admin terminal WebSocket relay |

### Audit Log Queries

Use the management API to query structured audit events:

```bash
# All enforcement events in the last 24 hours
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit?category=enforcement&since=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)"

# Policy denials for a specific user
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit?event_type=policy_deny&user_id=USER_UUID"

# All admin actions
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit?category=admin"
```

### Audit Log Export

For external analysis or compliance reporting:

```bash
# Export as JSON
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit/export?format=json&since=2026-01-01T00:00:00Z" \
     -o audit-export.json

# Export as CSV
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit/export?format=csv" \
     -o audit-export.csv

# Export as JSONL (for streaming ingestion)
curl -H "Authorization: Bearer YOUR_API_KEY" \
     "http://localhost:8080/admin/api/audit/export?format=jsonl" \
     -o audit-export.jsonl
```

Maximum export size is 10,000 entries per request. Use time-range filters to export in batches if needed.

### Prometheus Metrics

Open Terminal Orchestrator exposes Prometheus-compatible metrics:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/metrics
```

If `METRICS_TOKEN` is set, the public `/metrics` endpoint can be scraped without the admin API key by using the metrics token as a bearer token.

### Syslog Integration

Test syslog forwarding:

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/syslog/test
```

Configure syslog forwarding in the system settings to send audit events to your SIEM.

---

## Operational Procedures

### Scaling the Pool

When user count increases, adjust pool parameters:

1. Increase `max_sandboxes` and `max_active` via the pool API or environment variables.
2. Increase `warmup_size` to reduce cold-start latency for new users.
3. Ensure the K3s cluster has sufficient resources (CPU, memory, storage).

### Rotating API Keys

1. Generate a new API key:

```bash
curl -X POST -H "Authorization: Bearer CURRENT_KEY" \
     "http://localhost:8080/admin/api/auth/keys?label=new-primary"
```

2. Update all clients to use the new key.
3. Revoke the old key:

```bash
curl -X DELETE -H "Authorization: Bearer NEW_KEY" \
     http://localhost:8080/admin/api/auth/keys/OLD_KEY_ID
```

### Emergency: Destroy All Sandboxes

In an emergency, destroy all active sandboxes:

1. List all non-destroyed sandboxes.
2. Use the bulk action endpoint to destroy them.
3. The pool manager will recreate pre-warmed sandboxes automatically once the situation stabilizes.

### Audit Retention

Audit logs are retained for 90 days by default (`AUDIT_RETENTION_DAYS`). The retention cleanup runs every 24 hours (`AUDIT_RETENTION_INTERVAL`). Export audit data before it expires if long-term retention is required.
