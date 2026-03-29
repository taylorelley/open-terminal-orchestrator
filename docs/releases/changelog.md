# Changelog

All notable changes to ShellGuard are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-03-28

### Added

- **Per-user sandbox isolation** -- each Open WebUI user receives a dedicated terminal sandbox with full process and filesystem isolation.
- **YAML policy engine** -- define security policies in YAML with three enforcement tiers (permissive, standard, strict) controlling command execution, filesystem access, and network rules.
- **Sandbox pool manager** -- automated lifecycle management with configurable pool warm-up, idle suspension, and automatic cleanup of destroyed sandboxes.
- **Admin dashboard** -- React single-page application providing a centralized interface for managing sandboxes, policies, users, groups, and system configuration.
- **Real-time monitoring with alerting** -- live dashboard metrics, resource utilization charts (via Recharts), and configurable alert rules with webhook notifications.
- **Audit logging with retention** -- comprehensive event logging for policy enforcement decisions, sandbox lifecycle transitions, and administrative actions, with configurable retention policies.
- **OIDC/SSO authentication** -- single sign-on support via OpenID Connect (Authlib) alongside local email/password authentication through Supabase Auth.
- **LiteLLM inference routing** -- integrated LiteLLM service for routing AI inference requests through sandboxed environments.
- **API proxy** -- Open Terminal compatible proxy layer that routes terminal traffic to the correct user sandbox with policy enforcement.
- **User sync from Open WebUI** -- automatic synchronization of user accounts from Open WebUI into ShellGuard for seamless identity management.
- **TLS and reverse proxy support** -- production-ready TLS termination and reverse proxy configuration for secure deployments.
- **Docker Compose deployment** -- complete Docker Compose configuration for single-command deployment of all ShellGuard services (backend, database, gateway).
- **Comprehensive API** -- dual API surface with a proxy API for terminal traffic and a management API for administrative operations, both documented via OpenAPI/Swagger.
- **Prometheus metrics** -- `/metrics` endpoint exposing sandbox pool sizes, request latencies, policy evaluation counts, and system health indicators.
- **OpenTelemetry tracing** -- distributed tracing support for debugging request flows across the backend and sandbox gateway.
