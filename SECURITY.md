# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Open Terminal Orchestrator, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email your report to **security@openterminalorchestrator.dev** with:
   - A description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment
   - Any suggested fixes (optional)

### What to Expect

- **Acknowledgement** within 48 hours of your report.
- **Initial assessment** within 5 business days.
- **Resolution timeline** communicated once the issue is triaged.
- **Credit** in the release notes (unless you prefer to remain anonymous).

### Scope

The following are in scope for security reports:

- Authentication and authorization bypass
- Sandbox escape or isolation failures
- Policy enforcement bypass
- SQL injection, XSS, SSRF, or other injection attacks
- Sensitive data exposure (credentials, API keys, PII)
- Privilege escalation
- Denial of service via resource exhaustion

### Out of Scope

- Vulnerabilities in upstream dependencies (report these to the respective projects)
- Issues requiring physical access to the host
- Social engineering attacks
- Rate limiting or brute force without demonstrated impact

## Security Best Practices for Operators

- Always deploy Open Terminal Orchestrator behind a TLS-terminating reverse proxy.
- Rotate `ADMIN_API_KEY` and `OPEN_WEBUI_API_KEY` regularly.
- Enable Row-Level Security (RLS) on all Supabase tables (enabled by default).
- Restrict network access to the management API to trusted networks.
- Review audit logs regularly for anomalous activity.
- Keep all dependencies up to date.
