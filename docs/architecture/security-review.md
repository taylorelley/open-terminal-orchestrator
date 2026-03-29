# Open Terminal Orchestrator Security Review

**Date:** 2026-03-28
**Scope:** Full-stack security assessment of the Open Terminal Orchestrator admin dashboard, covering the FastAPI backend, React SPA frontend, Supabase integration, OpenShell CLI integration, and proxy API.

---

## 1. Threat Model

| Threat Category | Description | Severity | Key Attack Vectors |
|---|---|---|---|
| **Sandbox Escape** | A user breaks out of their terminal sandbox to access the host or other sandboxes. | Critical | Container breakout via kernel exploits, shared namespace misconfigurations, mounted host paths, privileged container settings. |
| **Policy Bypass** | An attacker circumvents security policies to execute disallowed operations within a sandbox. | High | Malformed YAML definitions that parse permissively, race conditions between policy updates and enforcement, policy version rollback attacks. |
| **Authentication Bypass** | Unauthorized access to the admin dashboard or management API. | Critical | API key exposure in logs/client code, session hijacking via XSS or insecure cookie settings, OIDC misconfiguration (missing audience validation, insecure redirect URIs, nonce reuse). |
| **SSRF** | The proxy API is abused to reach internal services not intended to be user-accessible. | High | Crafted sandbox target URLs that resolve to internal metadata endpoints (169.254.169.254), Supabase internal APIs, or other sandboxes. |
| **Injection Attacks** | Attacker-controlled input is interpreted as code or commands. | High | SQL injection via raw queries bypassing the ORM, command injection through openshell CLI arguments, stored XSS in the admin UI via user-supplied data (usernames, policy names). |
| **Privilege Escalation** | A non-admin user gains access to management API endpoints. | High | Missing or inconsistent auth middleware on API routes, JWT claim manipulation, API key scope confusion. |
| **Data Exfiltration** | Unauthorized access to data across sandbox boundaries or tampering with audit logs. | Medium | Cross-sandbox filesystem or network access, direct database access bypassing RLS, audit log deletion or modification by compromised admin accounts. |

### Sandbox Escape Details

The most critical threat for Open Terminal Orchestrator. Mitigations should include:

- Running sandboxes with a non-root user and minimal Linux capabilities (`--cap-drop=ALL`).
- Using seccomp profiles and AppArmor/SELinux to restrict syscalls.
- Avoiding shared PID, network, or IPC namespaces between sandboxes.
- Never mounting the Docker socket or host paths into sandbox containers.
- Keeping the host kernel patched against known container escape CVEs.

### Policy Bypass Details

YAML policy definitions must be validated strictly:

- Use a schema validator (e.g., JSON Schema over the parsed YAML) rather than relying on ad-hoc field checks.
- Apply policies atomically; do not allow a sandbox to operate in a window between policy update and enforcement.
- Version policies immutably; prevent rollback to deprecated or revoked versions without explicit admin action.

---

## 2. Dependency Audit Summary

### Python Dependencies

| Package | Purpose | Security Notes |
|---|---|---|
| FastAPI | HTTP framework | Actively maintained. Ensure Pydantic models validate all inputs. |
| SQLAlchemy (async) | ORM / database access | Use parameterized queries exclusively. Avoid `text()` with string interpolation. |
| authlib | OIDC / OAuth2 | Review OIDC provider configuration: validate `aud`, `iss`, `nonce`. Pin to a recent version. |
| httpx | HTTP client (proxy, outbound calls) | Potential SSRF vector. Validate and allowlist target URLs. Disable redirects to internal networks. |
| cryptography | Cryptographic operations | Keep updated; past CVEs in OpenSSL bindings. Avoid deprecated algorithms. |
| pyyaml | Policy YAML parsing | Always use `yaml.safe_load()`, never `yaml.load()`. The latter allows arbitrary code execution. |

### JavaScript Dependencies

| Package | Purpose | Security Notes |
|---|---|---|
| React 18 | UI framework | JSX auto-escapes output. Avoid `dangerouslySetInnerHTML`. |
| Supabase JS | Database / Auth / Realtime | Anon key is public by design; security relies on RLS policies being correct. |
| Vite 5 | Build tooling | Dev server should not be exposed in production. Ensure `.env` is not bundled. |
| Recharts | Charting | Low risk; renders SVG. Ensure data passed in is sanitized. |

### Recommended Actions

- Run `pip audit` on every CI build to catch known Python CVEs.
- Run `npm audit` on every CI build to catch known JS CVEs.
- Pin all dependency versions in lockfiles (`requirements.txt` / `package-lock.json`).
- Consider using Dependabot or Renovate for automated dependency update PRs.

---

## 3. OWASP Top 10 (2021) Assessment

| # | Category | Open Terminal Orchestrator Posture | Risk Level | Notes |
|---|---|---|---|---|
| A01 | **Broken Access Control** | RLS enabled on all tables. Admin auth middleware on API routes. API key validation for management endpoints. | Medium | Verify RLS policies cover all columns and operations (SELECT, INSERT, UPDATE, DELETE). Ensure no endpoints bypass the auth middleware. Test that non-admin JWTs are rejected by every management route. |
| A02 | **Cryptographic Failures** | Passwords hashed via Supabase Auth (bcrypt). OIDC tokens signed by the IdP. | Low | Enforce TLS on all connections (API, database, Supabase Realtime). Store API keys hashed, not in plaintext. Rotate keys periodically. |
| A03 | **Injection** | ORM parameterized queries via SQLAlchemy. Subprocess calls use argument lists (not `shell=True`). React JSX auto-escapes output. | Low | Audit all uses of `text()` in SQLAlchemy. Audit all `subprocess` calls to confirm no shell expansion. Verify no use of `dangerouslySetInnerHTML` in React. |
| A04 | **Insecure Design** | Per-user sandbox isolation. Policy-enforced restrictions. Audit logging of all lifecycle events. | Medium | Threat-model the proxy API carefully. Ensure sandbox-to-sandbox communication is blocked by default. Validate that destroyed sandboxes cannot be re-accessed. |
| A05 | **Security Misconfiguration** | Supabase manages database hardening. Vite build strips dev tooling. | Medium | Ensure Supabase dashboard access is restricted. Disable Supabase REST API for non-admin roles. Verify CORS is configured to allow only the admin UI origin. Review default Supabase settings (e.g., email confirmation, JWT expiry). |
| A06 | **Vulnerable and Outdated Components** | No automated dependency scanning currently in place. | High | Implement `pip audit` and `npm audit` in CI immediately. This is the highest-priority gap. |
| A07 | **Identification and Authentication Failures** | OIDC via authlib. Supabase Auth for frontend. API key auth for backend. | Medium | Enforce MFA for admin accounts. Set short JWT expiry (15 min) with refresh tokens. Validate OIDC `nonce` to prevent replay attacks. Rate-limit login endpoints. |
| A08 | **Software and Data Integrity Failures** | No current CI/CD pipeline security controls noted. | Medium | Sign container images for sandbox base images. Verify policy YAML integrity (e.g., checksums) before applying. Use lockfiles and verify their integrity in CI. |
| A09 | **Security Logging and Monitoring Failures** | Audit log table captures enforcement, lifecycle, and admin events. | Low | Ensure audit logs are append-only (no UPDATE/DELETE via RLS). Forward logs to an external SIEM. Alert on anomalous patterns (e.g., repeated auth failures, sandbox escape attempts). |
| A10 | **Server-Side Request Forgery (SSRF)** | Proxy API forwards requests to user sandboxes via httpx. | High | Allowlist sandbox IP ranges. Block requests to RFC 1918 addresses, link-local (169.254.x.x), and localhost. Disable HTTP redirects in the proxy client. Validate the target URL scheme (http/https only). |

---

## 4. RLS Policy Review

Row-Level Security is enabled on all Supabase tables with admin-only access enforced.

### Current State

- All tables have RLS enabled.
- Policies restrict access to authenticated users with an admin role.
- The Supabase anon key provides no data access without valid auth.

### Recommendations

| Area | Recommendation |
|---|---|
| **Audit log immutability** | Ensure the `audit_log` table has no UPDATE or DELETE policies, even for admins. Use a service-role key for inserts only. |
| **Policy version immutability** | The `policy_versions` table should disallow UPDATE. New versions should be INSERT-only. |
| **Sandbox isolation** | If non-admin users ever access the frontend, ensure sandbox rows are filtered by `user_id`. |
| **Testing** | Write integration tests that attempt unauthorized operations (e.g., non-admin SELECT, UPDATE on restricted tables) and assert they fail. |
| **Service role key** | Never expose the Supabase service role key to the frontend. It bypasses all RLS. Restrict it to backend server-side operations only. |

---

## 5. Network Boundary Analysis

```
                        +------------------+
                        |   External Users |
                        +--------+---------+
                                 |
                          TLS (HTTPS)
                                 |
                  +--------------+---------------+
                  |                               |
          +-------v--------+            +--------v--------+
          |   Admin UI     |            |   Proxy API     |
          |   (React SPA)  |            |   (FastAPI)     |
          +-------+--------+            +--------+--------+
                  |                               |
           Supabase API                  Internal Network
           (HTTPS)                                |
                  |                    +----------+----------+
          +-------v--------+          |                     |
          |   Supabase     |   +------v-------+   +--------v--------+
          |   (PostgreSQL, |   |  OpenShell   |   |   User          |
          |    Auth,       |   |  Gateway     |   |   Sandboxes     |
          |    Realtime)   |   +--------------+   |   (Containers)  |
          +----------------+                      +-----------------+
```

### Exposure Summary

| Component | Network Exposure | Trust Level |
|---|---|---|
| Admin UI (React SPA) | Public internet (static assets) | Untrusted |
| Proxy API (FastAPI) | Public internet (authenticated) | Semi-trusted (authenticated users only) |
| Supabase | Public internet (protected by RLS + Auth) | Semi-trusted |
| OpenShell Gateway | Internal network only | Trusted |
| User Sandboxes | Internal network only (accessed via proxy) | Untrusted (user-controlled) |

### Key Boundary Concerns

1. **Proxy API to Sandboxes:** The proxy must not allow users to reach internal services other than their own sandbox. Validate target addresses strictly.
2. **Sandboxes to Internal Network:** Sandboxes must have restricted egress. Block access to Supabase, the OpenShell gateway, and cloud metadata endpoints.
3. **Admin UI to Supabase:** The anon key is embedded in the frontend. Security depends entirely on RLS policies being correct and complete.

---

## 6. Recommendations

Prioritized by severity and effort.

### Critical (Address Immediately)

| # | Recommendation | Effort |
|---|---|---|
| 1 | **SSRF hardening in proxy API** -- Allowlist sandbox IP ranges, block RFC 1918/link-local/localhost, disable redirects in httpx. | Medium |
| 2 | **Verify `yaml.safe_load()` usage** -- Audit all YAML parsing to confirm `yaml.load()` is never used. A single instance allows arbitrary code execution. | Low |
| 3 | **Dependency scanning in CI** -- Add `pip audit` and `npm audit` to CI pipeline. Block merges on critical CVEs. | Low |
| 4 | **Audit subprocess calls** -- Confirm all openshell CLI invocations use argument lists, never `shell=True` or string interpolation into commands. | Low |

### High (Address Within 30 Days)

| # | Recommendation | Effort |
|---|---|---|
| 5 | **RLS integration tests** -- Write tests that assert unauthorized access patterns are blocked. Run on every migration change. | Medium |
| 6 | **Audit log immutability** -- Remove UPDATE/DELETE RLS policies on `audit_log`. Forward logs to an external store. | Low |
| 7 | **OIDC configuration review** -- Validate `aud`, `iss`, and `nonce` claims. Restrict redirect URIs to exact matches. | Low |
| 8 | **API key storage** -- Store API keys as bcrypt/argon2 hashes, not plaintext. Implement key rotation. | Medium |
| 9 | **Rate limiting** -- Add rate limits to authentication endpoints and the proxy API. | Medium |

### Medium (Address Within 90 Days)

| # | Recommendation | Effort |
|---|---|---|
| 10 | **Sandbox network egress controls** -- Implement network policies or firewall rules blocking sandbox access to internal services and cloud metadata. | High |
| 11 | **Container hardening** -- Enforce `--cap-drop=ALL`, seccomp profiles, and read-only root filesystems for sandboxes. | High |
| 12 | **MFA for admin accounts** -- Require multi-factor authentication for all admin users via Supabase Auth or the OIDC provider. | Medium |
| 13 | **Security headers** -- Add CSP, X-Content-Type-Options, X-Frame-Options, and Strict-Transport-Security headers to the API and static asset server. | Low |
| 14 | **Penetration testing** -- Commission an external penetration test focused on sandbox escape and proxy SSRF. | High |

### Low (Ongoing)

| # | Recommendation | Effort |
|---|---|---|
| 15 | **Automated dependency updates** -- Enable Dependabot or Renovate for both Python and JavaScript dependencies. | Low |
| 16 | **Security monitoring** -- Forward audit logs to a SIEM. Alert on repeated auth failures, sandbox lifecycle anomalies, and policy changes. | Medium |
| 17 | **Incident response plan** -- Document procedures for sandbox escape, data breach, and credential compromise scenarios. | Medium |

---

*This document should be reviewed and updated quarterly, or whenever significant architectural changes are made.*
