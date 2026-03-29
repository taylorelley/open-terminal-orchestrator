# ShellGuard Documentation

Welcome to the ShellGuard documentation. ShellGuard is an open-source orchestration layer that provides secure, per-user terminal sandboxes for [Open WebUI](https://github.com/open-webui/open-webui). It combines a React admin dashboard with a FastAPI backend to deliver policy-enforced sandbox isolation, real-time monitoring, and comprehensive audit logging.

---

## Quick Links

- [Getting Started](user-guide/getting-started.md) -- Set up ShellGuard in under 10 minutes
- [Configuration Reference](admin-guide/configuration-reference.md) -- All environment variables and settings
- [API Reference](architecture/api-reference.md) -- Proxy and management API endpoints
- [Troubleshooting](operations/troubleshooting.md) -- Diagnose and resolve common issues

---

## For Operators

Day-to-day guides for operators who manage ShellGuard through the admin dashboard.

| Document | Description |
|----------|-------------|
| [Getting Started](user-guide/getting-started.md) | Prerequisites, installation, and first login |
| [Dashboard Overview](user-guide/dashboard-overview.md) | Navigation, pages, and key metrics |
| [Managing Sandboxes](user-guide/managing-sandboxes.md) | Sandbox lifecycle, actions, pooling, and metrics |
| [Managing Policies](user-guide/managing-policies.md) | Creating, editing, and assigning YAML policies |
| [Managing Users & Groups](user-guide/managing-users-groups.md) | User sync, groups, and policy assignment |

## For Administrators

Deployment, configuration, and platform administration guides.

| Document | Description |
|----------|-------------|
| [Deployment](admin-guide/deployment.md) | Production deployment with Docker Compose and Kubernetes |
| [Configuration Reference](admin-guide/configuration-reference.md) | All environment variables and system settings |
| [Authentication](admin-guide/authentication.md) | OIDC/SSO setup, local auth, and API key management |
| [TLS & Reverse Proxy](admin-guide/tls-reverse-proxy.md) | TLS termination and reverse proxy configuration |
| [Inference Routing](admin-guide/inference-routing.md) | LiteLLM integration and model provider routing |
| [Monitoring & Alerting](admin-guide/monitoring-alerting.md) | Prometheus, Grafana, OpenTelemetry, webhooks, syslog |
| [Backup & Restore](admin-guide/backup-restore.md) | Database backup strategies and disaster recovery |

## Operations

Runbooks and procedures for production environments.

| Document | Description |
|----------|-------------|
| [Runbook](operations/runbook.md) | Step-by-step procedures for common operational tasks |
| [Troubleshooting](operations/troubleshooting.md) | Diagnosing and resolving common issues |

## Architecture & Reference

Technical architecture, API documentation, and security review.

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture/overview.md) | System components, data flow, and design principles |
| [API Reference](architecture/api-reference.md) | Proxy and management API endpoints with request/response schemas |
| [Security Review](architecture/security-review.md) | Threat model, compliance, and security architecture |

## For Developers

Guides for contributors extending ShellGuard.

| Document | Description |
|----------|-------------|
| [Development Setup](developer-guide/setup.md) | Local environment, tooling, and dev workflow |
| [Frontend Guide](developer-guide/frontend-guide.md) | React app structure, adding pages, components, and hooks |
| [Backend Guide](developer-guide/backend-guide.md) | FastAPI routes, services, models, and configuration |
| [Testing](developer-guide/testing.md) | Running tests, writing tests, and CI pipeline |
| [Database Migrations](developer-guide/database-migrations.md) | Supabase migration workflow, RLS patterns |

## Releases

| Document | Description |
|----------|-------------|
| [Changelog](releases/changelog.md) | Version history and release notes |

---

## Building the Documentation Site

The documentation can be built as a static site using [MkDocs](https://www.mkdocs.org/) with the [Material for MkDocs](https://squidfunnel.github.io/mkdocs-material/) theme.

### Prerequisites

```bash
pip install -r docs/requirements.txt
```

### Local Preview

```bash
mkdocs serve
```

This starts a local server at `http://localhost:8000` with live reload.

### Build Static Site

```bash
mkdocs build
```

The static site is generated in the `site/` directory, ready for deployment to any static hosting provider (GitHub Pages, Netlify, Cloudflare Pages, etc.).

### Deploy to GitHub Pages

```bash
mkdocs gh-deploy
```

This builds and pushes the site to the `gh-pages` branch automatically.

---

## License

ShellGuard is released under the MIT License. See [LICENSE](../LICENSE) for details.
