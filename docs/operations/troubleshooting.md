# Troubleshooting Guide

This guide covers common issues encountered when operating Open Terminal Orchestrator and how to resolve them.

## Sandbox Issues

### Sandbox Stuck in WARMING State

A sandbox that remains in the `WARMING` state indicates the container failed to become ready within the expected timeframe.

**Diagnosis:**

1. Check the OpenShell gateway is reachable:
   ```bash
   curl -s http://<OPENSHELL_GATEWAY_HOST>:<PORT>/health
   ```

2. Verify the `openshell` CLI can communicate with the gateway:
   ```bash
   openshell sandbox list --gateway <GATEWAY_URL>
   ```

3. Check the sandbox startup logs for errors:
   ```bash
   docker compose logs oto-backend | grep "WARMING"
   ```

**Resolution:**

- Increase `SANDBOX_STARTUP_TIMEOUT` if the container image is large or the host is under load.
- Verify the container image specified in the policy is pullable from the configured registry.
- Restart the OpenShell gateway if it is unresponsive.
- Check that the gateway host has sufficient resources (CPU, memory, disk) to start new containers.

### Sandbox Won't Resume

When a suspended sandbox fails to resume, the user sees a timeout or error when attempting to reconnect.

**Diagnosis:**

1. Check the sandbox state in the database:
   ```sql
   SELECT id, state, updated_at FROM sandboxes WHERE user_id = '<USER_ID>';
   ```

2. Verify the gateway reports the container as available:
   ```bash
   openshell sandbox inspect <SANDBOX_ID> --gateway <GATEWAY_URL>
   ```

3. Check backend logs for resume errors:
   ```bash
   docker compose logs oto-backend | grep "resume"
   ```

**Resolution:**

- Increase `SANDBOX_RESUME_TIMEOUT` if the gateway is slow to restore suspended containers.
- Verify the gateway health endpoint returns a healthy status.
- If the underlying container was destroyed externally, the sandbox must be re-created. Open Terminal Orchestrator will handle this automatically on the next user connection if pool replenishment is enabled.

### High Cold-Start Latency

Users experience long waits when no pre-warmed sandbox is available.

**Diagnosis:**

1. Check current pool levels:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_API_KEY>" \
     http://localhost:8000/api/v1/sandboxes/pool/status
   ```

2. Measure image pull time on the gateway host:
   ```bash
   time docker pull <SANDBOX_IMAGE>
   ```

**Resolution:**

- Increase `POOL_WARMUP_SIZE` to maintain more pre-warmed sandboxes.
- Pre-pull the sandbox image on all gateway hosts to eliminate pull latency.
- Use a local or regional container registry to reduce pull times.
- Consider using smaller base images optimized for fast startup.

---

## Authentication Issues

### OIDC Login Fails

Users are redirected to the identity provider but authentication does not complete.

**Diagnosis:**

1. Verify the OIDC discovery URL is accessible:
   ```bash
   curl -s <OIDC_DISCOVERY_URL>/.well-known/openid-configuration
   ```

2. Check that redirect URIs match exactly (including scheme and trailing slashes):
   ```
   Expected: https://<YOUR_DOMAIN>/auth/callback
   ```

3. Review backend logs for OIDC errors:
   ```bash
   docker compose logs oto-backend | grep -i "oidc\|oauth"
   ```

**Resolution:**

- Ensure `OIDC_REDIRECT_URI` in your backend `.env` matches the redirect URI registered with your identity provider exactly.
- Verify `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET` are correct and have not been rotated.
- Confirm the discovery URL is reachable from the backend container (check DNS resolution and firewall rules).
- Check that the required scopes (`openid`, `profile`, `email`) are permitted by the identity provider.

### Local Auth Not Working

Email/password login through Supabase Auth returns errors or fails silently.

**Diagnosis:**

1. Test the Supabase connection:
   ```bash
   curl -s <VITE_SUPABASE_URL>/rest/v1/ \
     -H "apikey: <VITE_SUPABASE_ANON_KEY>"
   ```

2. Check browser console for Supabase client errors.

**Resolution:**

- Verify `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` are set correctly in the frontend `.env` file.
- Confirm the Supabase project is running and the Auth service is enabled.
- Check that the user exists in Supabase Auth and has confirmed their email if email confirmation is enabled.

---

## Database Issues

### Connection Refused

The backend cannot connect to PostgreSQL.

**Diagnosis:**

1. Verify PostgreSQL is running:
   ```bash
   pg_isready -h <DB_HOST> -p <DB_PORT>
   ```

2. Test the connection string directly:
   ```bash
   psql "<DATABASE_URL>"
   ```

3. If using Docker Compose, check the database container:
   ```bash
   docker compose ps oto-db
   docker compose logs oto-db
   ```

**Resolution:**

- Verify `DATABASE_URL` in the backend `.env` file is correct (host, port, database name, credentials).
- Ensure the database container is running: `docker compose up -d oto-db`.
- Check that the backend container can reach the database host (network configuration, Docker network).
- Verify PostgreSQL is accepting connections on the configured port and interface.

### Slow Queries

Dashboard or API responses are slower than expected.

**Diagnosis:**

1. Enable query logging in PostgreSQL:
   ```sql
   ALTER SYSTEM SET log_min_duration_statement = 500;
   SELECT pg_reload_conf();
   ```

2. Check for missing indexes:
   ```sql
   SELECT schemaname, tablename, indexname FROM pg_indexes
   WHERE schemaname = 'public' ORDER BY tablename;
   ```

3. Monitor active connections:
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
   ```

**Resolution:**

- Verify that all indexes from the migration files are present (especially on `sandboxes.user_id`, `sandboxes.state`, `audit_log.created_at`).
- Increase the connection pool size via `DB_POOL_SIZE` if connections are exhausted.
- Run `VACUUM ANALYZE` on heavily-written tables like `audit_log` and `sandboxes`.
- Consider adding `audit_log` retention policies to prevent unbounded table growth.

### Migration Errors

Migrations fail to apply.

**Diagnosis:**

1. Check which migrations have been applied:
   ```bash
   supabase db status
   ```

2. Review the failing migration SQL for syntax errors or conflicts.

**Resolution:**

- If a migration partially applied, you may need to manually fix the schema and mark the migration as complete.
- Ensure migrations are applied in order (they are timestamped for this reason).
- Check for conflicts with existing database objects (tables, indexes, policies).
- See the [Database Migrations Guide](../developer-guide/database-migrations.md) for more details.

---

## API Issues

### Proxy Returns 502 or 504

The API proxy to sandbox terminal endpoints returns gateway errors.

**Diagnosis:**

1. Check that the target sandbox is in `ACTIVE` state:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_API_KEY>" \
     http://localhost:8000/api/v1/sandboxes/<SANDBOX_ID>
   ```

2. Verify the sandbox's internal IP is reachable from the backend:
   ```bash
   docker compose exec oto-backend curl -s http://<SANDBOX_INTERNAL_IP>:<PORT>/health
   ```

3. Check proxy timeout configuration.

**Resolution:**

- Increase `PROXY_TIMEOUT` if the sandbox is healthy but responses are slow.
- Verify the sandbox's internal IP and port are correct in the database.
- Check that the backend container shares a network with the sandbox containers.
- If the sandbox process has crashed, destroy and re-create the sandbox.

### Management API Returns 401 or 403

Authenticated API requests are rejected.

**Diagnosis:**

1. Verify the API key is being sent correctly:
   ```bash
   curl -v -H "Authorization: Bearer <ADMIN_API_KEY>" \
     http://localhost:8000/api/v1/policies
   ```

2. Check that `ADMIN_API_KEY` is set in the backend environment.

**Resolution:**

- Ensure the `Authorization` header uses the `Bearer` scheme.
- Verify `ADMIN_API_KEY` in the backend `.env` matches the key you are sending.
- If using OIDC-based admin auth, confirm the user has admin privileges in the identity provider.
- Check that RLS policies in the database are not blocking the request at the data layer.

---

## Monitoring Issues

### /metrics Endpoint Not Accessible

The Prometheus metrics endpoint returns 401 or is unreachable.

**Diagnosis:**

1. Test with the metrics token:
   ```bash
   curl -s -H "Authorization: Bearer <METRICS_TOKEN>" \
     http://localhost:8000/metrics
   ```

2. Verify the endpoint is enabled in configuration.

**Resolution:**

- Set `METRICS_TOKEN` in the backend `.env` and use it in your Prometheus scrape configuration.
- If no token is configured, the endpoint may be disabled. Set `METRICS_ENABLED=true`.
- Ensure the backend is listening on the expected port and the `/metrics` path is not blocked by a reverse proxy.

### Alerts Not Firing

Configured alert rules are not triggering notifications.

**Diagnosis:**

1. Check the alert evaluation status:
   ```bash
   curl -s -H "Authorization: Bearer <ADMIN_API_KEY>" \
     http://localhost:8000/api/v1/system/alerts
   ```

2. Verify webhook endpoints are reachable from the backend.

**Resolution:**

- Check `ALERT_EVALUATION_INTERVAL` is set to a reasonable value (default: 60 seconds).
- Verify webhook URLs in the system configuration are correct and reachable.
- Check backend logs for webhook delivery errors.
- Ensure alert thresholds are correctly configured (they may be too high to trigger under current conditions).

---

## General Troubleshooting

### Checking Logs

Enable verbose logging for detailed diagnostics:

```bash
# Set debug logging in backend .env
LOG_LEVEL=debug

# View all service logs
docker compose logs -f

# View specific service logs
docker compose logs -f oto-backend
docker compose logs -f oto-db

# Filter for errors
docker compose logs oto-backend 2>&1 | grep -i "error\|exception\|traceback"
```

### Health Check Endpoints

Open Terminal Orchestrator exposes the following health check endpoints:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Backend health (returns 200 if the service is running) |
| `GET /health/db` | Database connectivity check |
| `GET /health/gateway` | OpenShell gateway connectivity check |
| `GET /metrics` | Prometheus metrics (requires `METRICS_TOKEN`) |

Use these endpoints for load balancer health checks and uptime monitoring:

```bash
# Quick health check
curl -sf http://localhost:8000/health && echo "OK" || echo "UNHEALTHY"

# Full system check
curl -s http://localhost:8000/health/db | jq .
curl -s http://localhost:8000/health/gateway | jq .
```

### Getting Help

If you are unable to resolve an issue using this guide:

1. Search existing [GitHub Issues](https://github.com/oto/oto/issues) for similar problems.
2. Collect diagnostic information: backend logs, database state, configuration (redact secrets).
3. Open a new issue with the diagnostic information and steps to reproduce.
