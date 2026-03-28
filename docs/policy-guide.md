# ShellGuard Policy Authoring Guide

This document covers how to write, assign, and manage security policies in ShellGuard.

## Overview

Policies are YAML documents that define what a sandbox is allowed to do. They control four enforcement domains:

- **Network** -- Outbound HTTP/HTTPS egress rules (Layer 7)
- **Filesystem** -- Which paths are readable and writable
- **Process** -- Privilege escalation and syscall restrictions
- **Inference** -- Routing of AI model API traffic through managed backends

Policies are versioned. Each update creates a new version. Dynamic sections (network, inference) are hot-reloaded on running sandboxes. Static sections (filesystem, process) require sandbox recreation on the next idle cycle.

## YAML Policy Format

```yaml
metadata:
  name: my-policy
  description: "Human-readable description of the policy."
  tier: standard          # restricted | standard | elevated
  version: "1.0.0"       # Semver, auto-incremented on update
  changelog: "Initial version"

network:
  egress:
    - destination: "pypi.org"
      methods: ["GET"]
    - destination: "api.github.com"
      methods: ["GET", "POST"]
  default: deny           # deny all traffic not matching a rule

filesystem:
  writable:
    - /home/user
    - /tmp
  readable:
    - /home/user
    - /tmp
    - /usr
    - /lib
    - /etc/ssl/certs
  default: deny           # deny access to paths not listed

process:
  allow_sudo: false
  allow_ptrace: false
  blocked_syscalls:
    - mount
    - umount
    - reboot
    - kexec_load

inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
    - match: "api.anthropic.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true

gpu:
  enabled: false
  devices: []
```

### Section Reference

#### metadata

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Unique policy name (alphanumeric + hyphens) |
| `description` | No | Human-readable description |
| `tier` | Yes | One of: `restricted`, `standard`, `elevated` |
| `version` | Auto | Semantic version string, auto-incremented on updates |
| `changelog` | No | Description of changes for this version |

#### network

| Field | Description |
|---|---|
| `egress` | List of allowed outbound destinations |
| `egress[].destination` | Hostname or wildcard pattern (e.g., `*.github.com`) |
| `egress[].methods` | Allowed HTTP methods (e.g., `["GET"]`, `["GET", "POST"]`) |
| `default` | Default action for unmatched traffic: `deny` (recommended) or `allow` |

#### filesystem

| Field | Description |
|---|---|
| `writable` | List of paths the sandbox can write to |
| `readable` | List of paths the sandbox can read from (superset of writable is common) |
| `default` | Default action for unlisted paths: `deny` (recommended) or `allow` |

#### process

| Field | Description |
|---|---|
| `allow_sudo` | Whether `sudo` is permitted (`true`/`false`) |
| `allow_ptrace` | Whether ptrace (debugging/tracing) is permitted |
| `blocked_syscalls` | List of Linux syscalls to block (e.g., `mount`, `reboot`) |

#### inference

| Field | Description |
|---|---|
| `routes` | List of inference API routing rules |
| `routes[].match` | Destination hostname to intercept |
| `routes[].backend` | URL of the managed inference proxy (e.g., LiteLLM) |
| `routes[].strip_credentials` | Remove original API key from the request |
| `routes[].inject_credentials` | Add managed credentials for the backend |

#### gpu

| Field | Description |
|---|---|
| `enabled` | Whether GPU passthrough is enabled |
| `devices` | List of GPU device IDs, or `["all"]` for all available GPUs |

## Tier System

ShellGuard uses three predefined tiers as a classification system. Tiers are metadata labels that help administrators categorize policies; enforcement comes from the policy content, not the tier label.

### restricted

The most locked-down tier. Suitable for untrusted users or default assignments.

Typical characteristics:
- Network egress limited to package registries only (PyPI, npm)
- Filesystem writes limited to `/home/user` and `/tmp`
- No sudo, no ptrace
- Dangerous syscalls blocked
- No inference routing

### standard

For trusted regular users. Adds access to code hosting and inference routing.

Typical characteristics:
- Network egress includes package registries plus GitHub, GitLab
- Additional writable paths (e.g., `/shared/projects`)
- No sudo, no ptrace
- Inference traffic routed through LiteLLM Proxy

### elevated

For administrators and power users. Broad access with full inference routing.

Typical characteristics:
- Wide network egress with wildcard patterns, including write methods (POST, PUT, PATCH)
- Broad filesystem access including shared datasets
- Sudo permitted
- Full inference routing
- GPU access available

## Assignment Precedence

Policies are assigned at four levels. When resolving the effective policy for a user, ShellGuard checks each level in order and uses the first match:

```
1. User-level override      (highest priority)
2. Group-level assignment
3. Role-level default
4. System default            (lowest priority)
```

**User-level override** -- An explicit policy assigned directly to one user. Use this for exceptions (e.g., granting a specific user elevated access temporarily).

**Group-level assignment** -- A policy assigned to a ShellGuard group. Users in that group inherit the policy. This is the primary mechanism for managing policies in multi-user deployments.

**Role-level default** -- A policy mapped to an Open WebUI role (`admin`, `user`, `pending`). All users with that role get this policy unless overridden at the group or user level.

**System default** -- The fallback policy configured in ShellGuard system settings. Applied when no other assignment matches.

### Viewing Effective Policy

Use the management API to see which policy resolves for a given user:

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
     http://localhost:8080/admin/api/policies/resolve/USER_ID
```

The admin UI also shows the resolved effective policy with inheritance trace on the Users page.

## Worked Examples

### Example 1: Restrictive Default for All Users

Create a restricted policy and assign it as the system default.

**Policy YAML (restricted.yaml):**

```yaml
metadata:
  name: restricted
  description: "Default policy for all users. Package registries only."
  tier: restricted
  version: "1.0.0"

network:
  egress:
    - destination: "pypi.org"
      methods: ["GET"]
    - destination: "files.pythonhosted.org"
      methods: ["GET"]
    - destination: "registry.npmjs.org"
      methods: ["GET"]
  default: deny

filesystem:
  writable:
    - /home/user
    - /tmp
  readable:
    - /home/user
    - /tmp
    - /usr
    - /lib
    - /etc/ssl/certs
  default: deny

process:
  allow_sudo: false
  allow_ptrace: false
  blocked_syscalls:
    - mount
    - umount
    - reboot
    - kexec_load

inference:
  routes: []
```

Create via API:

```bash
curl -X POST http://localhost:8080/admin/api/policies \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "restricted",
    "tier": "restricted",
    "description": "Default policy for all users.",
    "yaml": "..."
  }'
```

Assign as role-level default for the `user` role:

```bash
curl -X PUT http://localhost:8080/admin/api/policies/assignments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "role",
    "entity_id": "user",
    "policy_id": "POLICY_UUID",
    "priority": 10
  }'
```

### Example 2: Developer Group with GitHub Access

Create a standard policy for developers who need Git access and inference routing.

**Policy YAML (developer.yaml):**

```yaml
metadata:
  name: developer
  description: "Developers. GitHub access and inference routing."
  tier: standard
  version: "1.0.0"

network:
  egress:
    - destination: "pypi.org"
      methods: ["GET"]
    - destination: "files.pythonhosted.org"
      methods: ["GET"]
    - destination: "registry.npmjs.org"
      methods: ["GET"]
    - destination: "api.github.com"
      methods: ["GET"]
    - destination: "github.com"
      methods: ["GET"]
  default: deny

filesystem:
  writable:
    - /home/user
    - /tmp
    - /shared/projects
  readable:
    - /home/user
    - /tmp
    - /shared/projects
    - /usr
    - /lib
    - /etc/ssl/certs
  default: deny

process:
  allow_sudo: false
  allow_ptrace: false

inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
```

Then create a group, assign the policy to it, and add users:

```bash
# Create the group
curl -X POST http://localhost:8080/admin/api/groups \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "developers", "description": "Dev team", "policy_id": "POLICY_UUID"}'

# Assign users to group via the admin UI or API
```

### Example 3: Temporary Elevated Access for One User

Override a single user's policy to elevated for a specific task, without changing their group assignment.

```bash
curl -X PUT http://localhost:8080/admin/api/policies/assignments \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "user",
    "entity_id": "USER_UUID",
    "policy_id": "ELEVATED_POLICY_UUID",
    "priority": 100
  }'
```

Since user-level overrides have the highest precedence, this takes effect immediately. Dynamic sections (network, inference) are hot-reloaded. Remove the override to revert to the group/role default.

## Policy Validation

Policies are validated against the expected schema before being saved. You can validate a policy without saving it:

```bash
# Validate existing policy
curl http://localhost:8080/admin/api/policies/POLICY_UUID/validate \
  -H "Authorization: Bearer YOUR_API_KEY"

# Validate arbitrary YAML
curl -X POST http://localhost:8080/admin/api/policies/validate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"yaml": "metadata:\n  name: test\n  tier: restricted\nnetwork:\n  default: deny"}'
```

## Version History

Every policy update creates a new version. You can list versions and diff between them:

```bash
# List versions
curl http://localhost:8080/admin/api/policies/POLICY_UUID/versions \
  -H "Authorization: Bearer YOUR_API_KEY"

# Diff two versions
curl "http://localhost:8080/admin/api/policies/POLICY_UUID/diff?from_version=1.0.0&to_version=1.0.1" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

The admin UI provides a visual diff view for comparing policy versions side by side.
