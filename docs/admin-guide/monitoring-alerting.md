# Monitoring and Alerting

ShellGuard exposes Prometheus metrics, supports OpenTelemetry distributed tracing, and provides a built-in alerting system with webhook notifications. This guide covers setup and configuration for production observability.

---

## Prometheus Metrics

### Endpoint

ShellGuard exposes metrics in Prometheus exposition format at:

```
GET /metrics
```

### Authentication

The endpoint is optionally protected by a bearer token. Set `METRICS_TOKEN` in your `.env` file:

```bash
METRICS_TOKEN=prom-secret-token
```

When set, Prometheus must include the token in its scrape configuration:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: shellguard
    scheme: https
    bearer_token: prom-secret-token
    static_configs:
      - targets: ["shellguard.example.com:443"]
    metrics_path: /metrics
    scrape_interval: 15s
```

When `METRICS_TOKEN` is empty, the endpoint is unauthenticated.

### Available Metrics

#### Sandbox Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `shellguard_sandboxes_total` | gauge | `state` | Total number of sandboxes by state (`pool`, `warming`, `ready`, `active`, `suspended`, `destroyed`) |
| `shellguard_sandboxes_created_total` | counter | `image` | Cumulative number of sandboxes created, labeled by container image |
| `shellguard_sandboxes_destroyed_total` | counter | `reason` | Cumulative number of sandboxes destroyed, labeled by reason (`idle_timeout`, `suspend_timeout`, `admin`, `error`, `policy`) |
| `shellguard_sandbox_startup_duration_seconds` | histogram | `image` | Time from container creation to READY state |
| `shellguard_sandbox_resume_duration_seconds` | histogram | -- | Time from SUSPENDED to ACTIVE state |
| `shellguard_sandbox_session_duration_seconds` | histogram | -- | Duration of user sessions (ACTIVE state) |

#### Pool Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `shellguard_pool_ready_count` | gauge | -- | Number of sandboxes currently in READY state in the warm pool |
| `shellguard_pool_target_size` | gauge | -- | Configured `POOL_WARMUP_SIZE` target |
| `shellguard_pool_max_sandboxes` | gauge | -- | Configured `POOL_MAX_SANDBOXES` limit |
| `shellguard_pool_max_active` | gauge | -- | Configured `POOL_MAX_ACTIVE` limit |
| `shellguard_pool_utilization_ratio` | gauge | -- | Ratio of active sandboxes to `POOL_MAX_ACTIVE` (0.0 -- 1.0) |
| `shellguard_pool_queue_length` | gauge | -- | Number of sandbox requests waiting in the queue |

#### HTTP Request Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `shellguard_http_requests_total` | counter | `method`, `path`, `status` | Total HTTP requests handled |
| `shellguard_http_request_duration_seconds` | histogram | `method`, `path` | Request latency in seconds |
| `shellguard_proxy_requests_total` | counter | `status` | Total requests proxied to sandbox containers |
| `shellguard_proxy_request_duration_seconds` | histogram | -- | Proxy request latency in seconds |

#### Policy Enforcement Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `shellguard_policy_enforcements_total` | counter | `policy`, `action`, `result` | Total policy enforcement events. `action` is the enforced action (e.g., `block_command`, `restrict_network`). `result` is `allowed` or `denied`. |
| `shellguard_policy_evaluation_duration_seconds` | histogram | -- | Time spent evaluating policy rules |

#### Audit Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `shellguard_audit_events_total` | counter | `event_type` | Total audit log events by type |
| `shellguard_audit_log_size` | gauge | -- | Current number of rows in the audit log table |

---

## Grafana Dashboard

ShellGuard ships with a pre-built Grafana dashboard.

### Importing the Dashboard

1. Locate the dashboard JSON file in the repository:

   ```
   deploy/grafana/shellguard-dashboard.json
   ```

2. In Grafana, go to **Dashboards > Import** and upload the JSON file or paste its contents.

3. Select your Prometheus data source when prompted.

### Dashboard Panels

The dashboard includes the following panels:

- **Sandbox Overview** -- Current sandbox counts by state (stacked bar chart).
- **Pool Utilization** -- Active sandboxes vs. maximum capacity over time.
- **Pool Queue** -- Pending sandbox requests in the queue.
- **Request Rate** -- HTTP requests per second by status code.
- **Request Latency** -- p50, p90, and p99 request latency.
- **Proxy Latency** -- Latency of proxied requests to sandbox containers.
- **Policy Enforcement** -- Allowed vs. denied policy events over time.
- **Sandbox Lifecycle** -- Creation, suspension, and destruction rates.
- **Startup Time** -- Sandbox startup duration histogram.
- **Audit Events** -- Audit log event rate by type.

### Customization

The dashboard uses Grafana template variables for the Prometheus data source and job name. Adjust these in **Dashboard Settings > Variables** if your Prometheus job is named differently.

---

## OpenTelemetry Tracing

ShellGuard supports distributed tracing via OpenTelemetry for debugging request flows across the system.

### Configuration

Enable tracing with the following environment variables:

```bash
OTEL_ENABLED=true
OTEL_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=shellguard
```

| Variable | Description |
|----------|-------------|
| `OTEL_ENABLED` | Set to `true` to enable trace export. Default: `false`. |
| `OTEL_ENDPOINT` | OTLP gRPC endpoint. This is typically an OpenTelemetry Collector, Jaeger (with OTLP receiver), or Grafana Tempo. |
| `OTEL_SERVICE_NAME` | Service name attached to all spans. Default: `shellguard`. |

### Instrumented Operations

The following operations generate trace spans:

- **HTTP requests** -- Each incoming request creates a root span with method, path, and status code attributes.
- **Sandbox lifecycle** -- Create, suspend, resume, and destroy operations are traced end-to-end, including communication with the OpenShell gateway.
- **Policy evaluation** -- Policy rule evaluation is traced with the policy name and result.
- **Database queries** -- Supabase/PostgreSQL queries appear as child spans (when debug-level tracing is enabled).
- **Proxy requests** -- Requests forwarded to sandbox containers include upstream latency.

### Backend Setup Examples

**Jaeger (all-in-one):**

```yaml
# docker-compose.yml
jaeger:
  image: jaegertracing/all-in-one:1.53
  ports:
    - "16686:16686"   # Jaeger UI
    - "4317:4317"     # OTLP gRPC
  environment:
    COLLECTOR_OTLP_ENABLED: "true"
```

**Grafana Tempo:**

```yaml
tempo:
  image: grafana/tempo:2.3.1
  command: ["-config.file=/etc/tempo.yaml"]
  ports:
    - "4317:4317"     # OTLP gRPC
    - "3200:3200"     # Tempo API
```

---

## Alert Rules

ShellGuard's dashboard (the **Monitoring** page in the admin UI) includes a built-in alert configuration system.

### Configuring Alerts

Navigate to **Monitoring > Alerts** in the ShellGuard dashboard. Each alert rule has the following settings:

| Setting | Description |
|---------|-------------|
| **Name** | Human-readable name for the alert (e.g., "High CPU Usage"). |
| **Metric** | The metric to monitor (e.g., CPU usage, memory usage, disk usage, pool utilization, active sandboxes). |
| **Threshold** | The value that triggers the alert. Units depend on the metric (percentage for CPU/memory/disk, count for sandboxes). |
| **Comparison** | `greater_than`, `less_than`, `equal_to`. |
| **Evaluation interval** | How often the alert condition is checked. Default: 60 seconds. Minimum: 10 seconds. |
| **For duration** | How long the condition must be true before the alert fires. Prevents alerts on transient spikes. Default: 5 minutes. |
| **Severity** | `info`, `warning`, `critical`. Affects notification routing. |

### Recommended Alert Thresholds

| Alert | Metric | Threshold | Severity | Rationale |
|-------|--------|-----------|----------|-----------|
| High CPU | Per-sandbox CPU | > 90% for 5 min | warning | Sandbox may be running a resource-intensive process |
| Critical CPU | Per-sandbox CPU | > 95% for 2 min | critical | Potential runaway process; may need policy intervention |
| High memory | Per-sandbox memory | > 85% for 5 min | warning | Approaching OOM kill threshold |
| Critical memory | Per-sandbox memory | > 95% for 1 min | critical | OOM kill imminent |
| Disk usage | Per-sandbox disk | > 80% for 10 min | warning | User data volume filling up |
| Pool exhaustion | Pool utilization ratio | > 0.9 for 5 min | critical | Almost all sandbox slots are in use |
| Pool queue backup | Pool queue length | > 5 for 2 min | warning | Users are waiting for sandbox availability |
| Startup failures | Startup timeout rate | > 10% over 15 min | critical | Infrastructure issue affecting container creation |

### Alert States

- **OK** -- Condition is not met.
- **Pending** -- Condition is met but has not exceeded the "for duration" threshold.
- **Firing** -- Alert is active and notifications have been sent.
- **Resolved** -- Alert was firing but the condition is no longer met. A resolution notification is sent.

---

## Webhook Notifications

Alerts can trigger HTTP webhook notifications to integrate with external systems like Slack, PagerDuty, Microsoft Teams, or custom endpoints.

### Configuring Webhooks

Navigate to **Monitoring > Alerts > Notification Channels** in the ShellGuard dashboard.

| Setting | Description |
|---------|-------------|
| **Name** | Display name for the channel (e.g., "Ops Slack Channel"). |
| **URL** | The webhook endpoint URL. |
| **Method** | HTTP method. Default: `POST`. |
| **Headers** | Optional custom headers (e.g., `Authorization`, `Content-Type`). JSON key-value pairs. |
| **Template** | Notification body template. Supports variable substitution (see below). |
| **Severity filter** | Only send notifications for alerts at or above this severity. |
| **Send resolved** | Whether to send a notification when the alert resolves. Default: `true`. |

### Webhook Payload

The default webhook payload is JSON:

```json
{
  "status": "firing",
  "alert_name": "High CPU Usage",
  "severity": "warning",
  "metric": "cpu_usage",
  "current_value": 92.5,
  "threshold": 90,
  "sandbox_id": "sb_abc123",
  "user": "john@example.com",
  "fired_at": "2026-03-29T14:30:00Z",
  "message": "CPU usage at 92.5% (threshold: 90%) for sandbox sb_abc123"
}
```

### Slack Example

```
URL:     https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX
Method:  POST
Headers: {"Content-Type": "application/json"}
Template:
{
  "text": "[{{severity}}] {{alert_name}}: {{message}}"
}
```

### PagerDuty Example

```
URL:     https://events.pagerduty.com/v2/enqueue
Method:  POST
Headers: {"Content-Type": "application/json"}
Template:
{
  "routing_key": "your-pagerduty-integration-key",
  "event_action": "{{#if resolved}}resolve{{else}}trigger{{/if}}",
  "dedup_key": "shellguard-{{alert_name}}",
  "payload": {
    "summary": "{{message}}",
    "severity": "{{severity}}",
    "source": "shellguard"
  }
}
```

---

## Syslog Forwarding

ShellGuard can forward audit log events to an external syslog receiver for integration with SIEM systems (Splunk, Elastic SIEM, QRadar, etc.).

### Configuration

Configure syslog forwarding in the ShellGuard dashboard under **Settings > Integrations > Syslog**.

| Setting | Description |
|---------|-------------|
| **Enabled** | Toggle syslog forwarding on or off. |
| **Protocol** | `tcp`, `udp`, or `tls`. Use `tls` in production. |
| **Host** | Syslog receiver hostname or IP (e.g., `siem.example.com`). |
| **Port** | Syslog receiver port. Common values: `514` (UDP), `6514` (TLS). |
| **Facility** | Syslog facility. Default: `local0`. |
| **Format** | `rfc5424` (structured) or `rfc3164` (legacy). Default: `rfc5424`. |
| **TLS CA certificate** | CA certificate for verifying the syslog server (when using TLS). |
| **Event filter** | Which audit event types to forward. Default: all events. |

### Syslog Message Format (RFC 5424)

```
<134>1 2026-03-29T14:30:00.000Z shellguard shellguard - audit [meta policy="default-policy" action="block_command" user="john@example.com" sandbox="sb_abc123"] Policy enforcement: command blocked by default-policy
```

### Forwarded Event Types

The following audit event types can be forwarded:

- `sandbox.created` -- A new sandbox was created.
- `sandbox.activated` -- A sandbox transitioned to ACTIVE.
- `sandbox.suspended` -- A sandbox was suspended (idle timeout or manual).
- `sandbox.destroyed` -- A sandbox was destroyed.
- `policy.enforced` -- A policy rule was evaluated and enforced.
- `policy.created` / `policy.updated` / `policy.deleted` -- Policy lifecycle events.
- `admin.login` -- Admin user logged in.
- `admin.api_key_auth` -- API key authentication was used.
- `admin.config_changed` -- System configuration was modified.
- `user.synced` -- User was synced from Open WebUI.

### Integration with Common SIEM Platforms

**Splunk:** Configure a TCP/TLS syslog input on your Splunk Heavy Forwarder or Universal Forwarder. Set the source type to `syslog` and create an index for ShellGuard events.

**Elastic SIEM:** Use a Filebeat syslog input module or Logstash syslog input plugin to ingest events into Elasticsearch. Create an index pattern and detection rules for policy enforcement events.

**QRadar:** Add a syslog log source in QRadar pointing to the ShellGuard server. Map event types to QRadar categories using a custom DSM or the Universal DSM.

---

## Troubleshooting

### Metrics endpoint returns 401

Verify that the `METRICS_TOKEN` value in your `.env` file matches the `bearer_token` in your Prometheus scrape config. Tokens are compared in constant time and are case-sensitive.

### No traces appearing

1. Confirm `OTEL_ENABLED=true` is set and the backend was restarted after the change.
2. Verify the `OTEL_ENDPOINT` is reachable from the ShellGuard container: `curl -v http://otel-collector:4317`.
3. Check ShellGuard logs for OTLP export errors (set `LOG_LEVEL=debug` temporarily).

### Alerts not firing

1. Verify the alert rule is enabled and the evaluation interval has elapsed.
2. Check the "for duration" -- the condition must persist for this period.
3. Verify the notification channel URL is correct and the target service is reachable.
4. Check the ShellGuard logs for webhook delivery errors.

### Syslog messages not arriving

1. Verify network connectivity between ShellGuard and the syslog receiver (check firewalls and security groups).
2. If using TLS, confirm the CA certificate is correct and the syslog server's certificate is valid.
3. Try switching to UDP/TCP temporarily to rule out TLS issues.
4. Check ShellGuard logs for syslog connection errors.
