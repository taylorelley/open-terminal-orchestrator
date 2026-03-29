# ShellGuard Documentation

Welcome to the ShellGuard documentation. ShellGuard is an open-source orchestration layer that provides secure, per-user terminal sandboxes for [Open WebUI](https://github.com/open-webui/open-webui). It combines a React admin dashboard with a FastAPI backend to deliver policy-enforced sandbox isolation, real-time monitoring, and comprehensive audit logging.

---

## Quick Links

- [Getting Started](user-guide/getting-started.md) -- Set up ShellGuard in under 10 minutes
- [Dashboard Overview](user-guide/dashboard-overview.md) -- Navigate the admin interface
- [Managing Sandboxes](user-guide/managing-sandboxes.md) -- Lifecycle, pooling, and operations
- [Policy Engine Reference](architecture/policy-engine.md) -- YAML policy tiers and enforcement
- [API Reference](architecture/api-reference.md) -- Backend REST API documentation

---

## For Operators

Day-to-day guides for administrators and operators who manage ShellGuard through the dashboard.

| Document | Description |
|----------|-------------|
| [Getting Started](user-guide/getting-started.md) | Prerequisites, installation, and first login |
| [Dashboard Overview](user-guide/dashboard-overview.md) | Navigation, pages, and key metrics |
| [Managing Sandboxes](user-guide/managing-sandboxes.md) | Sandbox lifecycle, actions, pooling, and metrics |
| [Managing Users & Groups](user-guide/managing-users-groups.md) | User sync, groups, and policy assignment |
| [Managing Policies](user-guide/managing-policies.md) | Creating, editing, and assigning YAML policies |
| [Audit Log](user-guide/audit-log.md) | Searching, filtering, and exporting audit events |
| [Monitoring & Alerts](user-guide/monitoring-alerts.md) | Resource charts, alert rules, and webhooks |

## For Administrators

Deployment, configuration, and platform administration guides.

| Document | Description |
|----------|-------------|
| [Deployment Guide](admin-guide/deployment.md) | Production deployment with Docker Compose and Kubernetes |
| [Configuration Reference](admin-guide/configuration.md) | All environment variables and system settings |
| [Authentication & OIDC](admin-guide/authentication.md) | OIDC provider setup, Supabase Auth, and session management |
| [Database Administration](admin-guide/database.md) | PostgreSQL schema, migrations, backups, and RLS policies |
| [Security Hardening](admin-guide/security.md) | Network isolation, TLS, secret management, and best practices |
| [Upgrading](admin-guide/upgrading.md) | Version upgrade procedures and migration notes |

## Operations

Runbooks and operational procedures for production environments.

| Document | Description |
|----------|-------------|
| [Runbooks](operations/runbooks.md) | Step-by-step procedures for common operational tasks |
| [Troubleshooting](operations/troubleshooting.md) | Diagnosing and resolving common issues |
| [Backup & Recovery](operations/backup-recovery.md) | Database backup strategies and disaster recovery |
| [Scaling](operations/scaling.md) | Horizontal scaling, pool sizing, and resource planning |
| [Observability](operations/observability.md) | Logging, metrics export, and integration with monitoring stacks |

## Architecture & Reference

Technical architecture, API documentation, and design decisions.

| Document | Description |
|----------|-------------|
| [Architecture Overview](architecture/overview.md) | System components, data flow, and design principles |
| [Policy Engine](architecture/policy-engine.md) | YAML policy schema, tiers, resolution, and enforcement |
| [Sandbox Lifecycle](architecture/sandbox-lifecycle.md) | State machine, pooling strategy, and container management |
| [API Reference](architecture/api-reference.md) | Backend REST API endpoints, request/response schemas |
| [Database Schema](architecture/database-schema.md) | Tables, relationships, indexes, and RLS policies |
| [LiteLLM Integration](architecture/litellm-integration.md) | Inference routing and model provider configuration |

## For Developers

Guides for contributors and developers extending ShellGuard.

| Document | Description |
|----------|-------------|
| [Development Setup](developer-guide/development-setup.md) | Local environment, tooling, and dev workflow |
| [Frontend Architecture](developer-guide/frontend.md) | React app structure, components, hooks, and conventions |
| [Backend Architecture](developer-guide/backend.md) | FastAPI app structure, services, and middleware |
| [Testing](developer-guide/testing.md) | Running tests, writing tests, and CI pipeline |
| [Contributing](developer-guide/contributing.md) | Code style, PR process, and community guidelines |

## Releases

| Document | Description |
|----------|-------------|
| [Changelog](releases/changelog.md) | Version history and release notes |
| [Roadmap](releases/roadmap.md) | Planned features and milestones |

---

## License

ShellGuard is released under the MIT License. See [LICENSE](../LICENSE) for details.
