# ShellGuard Operator Runbook

## Troubleshooting

### Sandbox stuck in WARMING

**Symptoms:** Sandbox stays in WARMING state for more than `startup_timeout` (default 120s).

**Resolution:**
1. Check pool manager logs: `docker logs shellguard | grep WARMING`
2. The pool manager automatically destroys stuck sandboxes after `startup_timeout`
3. If stuck manually, call `DELETE /admin/api/sandboxes/{id}` to force destroy
4. Check OpenShell gateway connectivity: `curl http://openshell-gateway:6443/health`

### Database connection failures

**Symptoms:** Health endpoint returns `{"status": "degraded", "checks": {"database": "disconnected"}}`.

**Resolution:**
1. Verify PostgreSQL is running: `pg_isready -h localhost -p 5432`
2. Check `DATABASE_URL` environment variable format
3. Verify network connectivity between ShellGuard and PostgreSQL
4. Check PostgreSQL max connections (`max_connections` in postgresql.conf)

### Webhook delivery failures

**Symptoms:** Webhook events not reaching configured endpoints.

**Resolution:**
1. Check webhook config: `GET /admin/api/webhooks`
2. Test individual webhooks: `POST /admin/api/webhooks/{index}/test`
3. Check webhook delivery metrics in Prometheus: `shellguard_webhook_deliveries_total`
4. Verify the webhook URL is reachable from the ShellGuard container
5. Check for SSL/TLS certificate issues if using HTTPS webhooks

### Pool exhaustion

**Symptoms:** New sandbox requests return 503 or long wait times.

**Resolution:**
1. Check pool status: `GET /admin/api/pool`
2. Increase `POOL_MAX_SANDBOXES` or `POOL_MAX_ACTIVE` if resources allow
3. Reduce `IDLE_TIMEOUT` to reclaim unused sandboxes faster
4. Check for sandboxes stuck in WARMING that are consuming slots
5. Manually destroy unused sandboxes: `DELETE /admin/api/sandboxes/{id}`

### High memory/CPU usage

**Symptoms:** Resource metrics spiking on monitoring dashboard.

**Resolution:**
1. Identify heavy sandboxes via Monitoring > Resource Usage tab
2. Suspend idle sandboxes: `POST /admin/api/sandboxes/{id}/suspend`
3. Use bulk actions to suspend multiple sandboxes at once
4. Check if policy resource limits are properly configured

## Backup and Restore

### Creating a backup

```bash
curl -s -H "Authorization: Bearer $ADMIN_API_KEY" \
  http://localhost:8080/admin/api/backup \
  -o shellguard-backup-$(date +%Y%m%d).json
```

The backup includes: policies, policy versions, assignments, groups, and system configuration.

### Restoring from backup

Currently, restoration is manual:
1. Parse the backup JSON
2. Insert records via the Management API (POST /admin/api/policies, etc.)
3. Verify assignments and configuration

## Log Analysis

### Structured log format

ShellGuard uses JSON-structured logging. Key fields:
- `timestamp`: ISO 8601
- `level`: DEBUG, INFO, WARNING, ERROR
- `message`: Human-readable message
- `extra`: Additional context (sandbox_name, user_id, etc.)

### Useful log queries

```bash
# Find all sandbox lifecycle events
docker logs shellguard | jq 'select(.message | contains("sandbox"))'

# Find pool manager issues
docker logs shellguard | jq 'select(.message | contains("Pool"))'

# Find authentication failures
docker logs shellguard | jq 'select(.level == "WARNING" and (.message | contains("auth")))'
```

## Monitoring Alerts

Configure threshold alerts in the Monitoring > Alerts tab to get notified via webhooks when:
- CPU usage exceeds 80% (`cpu gt 80`)
- Available pool sandboxes drops below 2 (`pool_available lt 2`)
- Active sandboxes near max capacity (`active_sandboxes gt 8`)
