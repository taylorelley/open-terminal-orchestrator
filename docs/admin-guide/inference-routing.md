# Inference Routing

This document explains how Open Terminal Orchestrator manages LLM inference traffic flowing through user sandboxes, including credential security, model routing, and policy-based access control.

## Why Inference Routing Exists

Each Open Terminal Orchestrator sandbox runs an instance of Open Terminal, which provides a REST API for code execution, file management, and terminal access. AI agents operating inside these sandboxes — through Open WebUI's terminal integration — often need to call LLM APIs themselves (e.g., an agent writing code that invokes GPT-4 or Claude).

Without inference routing, operators face two bad options:

1. **Let agents use their own keys.** Users or agents supply API keys directly, bypassing any organisational controls over model access, spend, or audit.
2. **Bake keys into the sandbox image.** Embeds secrets in container images, which is insecure and makes rotation difficult.

Open Terminal Orchestrator's inference routing solves this by intercepting LLM API traffic at the proxy layer, stripping user-supplied credentials, and injecting operator-managed credentials based on policy.

## Architecture

The inference request flow has five stages:

```
Open WebUI
    │
    │  POST /v1/chat/completions
    │  X-Open-WebUI-User-Id: alice
    │  Authorization: Bearer <user-key>   ← user-supplied (untrusted)
    │  Body: { "model": "gpt-4o", ... }
    │
    ▼
┌──────────────────────────────────────────────┐
│           Open Terminal Orchestrator Proxy Layer              │
│                                              │
│  1. Resolve sandbox   ← lookup alice's       │
│                         active sandbox        │
│                                              │
│  2. Strip credentials ← remove Authorization,│
│                         x-api-key, etc.       │
│                                              │
│  3. Extract model     ← parse "gpt-4o" from  │
│                         JSON body             │
│                                              │
│  4. Resolve route     ← map "gpt-4o" to      │
│                         provider + upstream    │
│                         model name             │
│                                              │
│  5. Inject credentials← add operator's API    │
│                         key for that provider  │
└──────────────────┬───────────────────────────┘
                   │
                   │  Forwarded request with operator credentials
                   ▼
┌──────────────────────────────────────────────┐
│        Sandbox (alice's container)            │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  LiteLLM Proxy (:4000)                 │  │
│  │  Receives request with operator creds  │  │
│  │  Forwards to upstream LLM provider     │  │
│  └──────────────────┬─────────────────────┘  │
└─────────────────────┼────────────────────────┘
                      │
                      ▼
           ┌──────────────────┐
           │  Upstream LLM    │
           │  (OpenAI, etc.)  │
           └──────────────────┘
```

Open Terminal Orchestrator itself never makes LLM calls. It is a credential-routing proxy. The actual API call to the upstream provider happens inside the sandbox's LiteLLM instance.

## Components

### Credential Router (`litellm_service.py`)

The `LiteLLMCredentialRouter` is the core service. It is a module-level singleton (`litellm_router`) with four responsibilities:

**Provider registry** — Stores operator-configured LLM provider backends (name, API base URL, API key, available models).

**Model routes** — Maps model aliases to specific providers and upstream model names. For example, the alias `gpt-4o` might route to provider `openai-prod` with upstream model `gpt-4o-2024-08-06`.

**Credential stripping** — Removes credential-bearing headers from inbound requests before they reach the sandbox:

| Stripped Headers |
|---|
| `Authorization` |
| `X-Api-Key` |
| `Api-Key` |
| `OpenAI-Api-Key` |
| `Anthropic-Api-Key` |
| `X-OpenAI-Api-Key` |

**Credential injection** — Adds the appropriate provider's API key as a `Bearer` token in the `Authorization` header, selected based on the requested model's route.

### Proxy Endpoints (`proxy.py`)

Three endpoints handle inference traffic, all using the `_llm_proxy` handler:

| Endpoint | Description |
|---|---|
| `POST /v1/chat/completions` | OpenAI-compatible chat completions |
| `POST /v1/completions` | OpenAI-compatible text completions |
| `GET /v1/models` | List available models (uses standard proxy, no credential transform) |

The `_llm_proxy` handler:

1. Resolves the user's sandbox via `X-Open-WebUI-User-Id`.
2. Parses the request body to extract the `model` field.
3. Calls `litellm_router.transform_request_headers()` (strip then inject).
4. Forwards the transformed request to the sandbox's internal IP.

### Policy Integration

The `inference` section of a policy YAML controls which inference destinations are intercepted and how credentials are handled:

```yaml
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
```

These rules are enforced at the sandbox's network policy layer (L7 filtering). Traffic matching a route is redirected to the specified backend. Traffic to inference APIs not listed in the policy is blocked by the network `default: deny` rule.

See the [Policy Authoring Guide](../user-guide/managing-policies.md) for full syntax and examples.

## How Policies Control Model Access by Tier

The three policy tiers typically grant different levels of inference access:

### restricted

No inference routing. AI agents in restricted sandboxes cannot call external LLM APIs. The `inference.routes` list is empty, and network egress rules block API endpoints.

```yaml
inference:
  routes: []

network:
  egress:
    # Only package registries — no LLM API endpoints
    - destination: "pypi.org"
      methods: ["GET"]
  default: deny
```

### standard

Inference routed through the operator's LiteLLM Proxy. Agents can call LLM APIs, but only through managed infrastructure with operator-controlled credentials and model access.

```yaml
inference:
  routes:
    - match: "api.openai.com"
      backend: "http://litellm-proxy:4000"
      strip_credentials: true
      inject_credentials: true
```

The operator's LiteLLM Proxy configuration determines which models are actually available. A standard-tier user might only have access to cost-effective models (e.g., `gpt-4o-mini`) while elevated-tier users get access to larger models.

### elevated

Full inference routing with access to all configured providers and models, potentially including direct API access for specific trusted users.

```yaml
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
```

## Configuration

### Registering Providers

Providers are registered programmatically via the `LiteLLMCredentialRouter`:

```python
from app.services.litellm_service import litellm_router, ProviderConfig

litellm_router.register_provider(ProviderConfig(
    name="openai-prod",
    api_base="https://api.openai.com/v1",
    api_key="sk-...",
    models=["gpt-4o", "gpt-4o-mini"],
    default_model="gpt-4o-mini",
))
```

### Registering Model Routes

Model routes map aliases to specific providers:

```python
from app.services.litellm_service import litellm_router, ModelRoute

litellm_router.register_route(ModelRoute(
    alias="gpt-4o",
    provider="openai-prod",
    upstream_model="gpt-4o-2024-08-06",
))
```

### Admin UI

The LiteLLM Proxy URL is configurable in the admin UI under **Settings > Integrations > LiteLLM Proxy**. This sets the base URL that Open Terminal Orchestrator uses when configuring sandbox-level LiteLLM instances.

## Security Properties

**Credential isolation.** User-supplied API keys are stripped before reaching the sandbox. Users cannot bypass operator controls by injecting their own keys.

**Operator-controlled spend.** Since operator credentials are used for all inference, spend is centralised and auditable. Rate limits and budgets are managed at the provider level (e.g., via LiteLLM Proxy's built-in budget controls).

**Model access control.** Only models with registered routes are accessible. Unregistered model aliases pass through without credential injection, and will fail at the upstream provider if the sandbox has no direct API access (which `default: deny` network policy ensures).

**Audit trail.** All inference requests flow through Open Terminal Orchestrator's proxy layer and are logged in the audit log with user context, model requested, and timestamp.

**Hot-reload.** The `inference` section is a dynamic policy section. Changes to inference routes take effect immediately on running sandboxes without requiring recreation.

## Relationship to External LiteLLM Proxy

Open Terminal Orchestrator's `LiteLLMCredentialRouter` is not itself a LiteLLM Proxy instance. It is a lightweight credential-routing layer that sits in front of the per-sandbox LiteLLM instances. In a typical deployment, the architecture may include an external LiteLLM Proxy as the upstream backend:

```
Open Terminal Orchestrator Proxy  →  Sandbox LiteLLM  →  External LiteLLM Proxy  →  OpenAI / Anthropic / etc.
(cred routing)       (per-sandbox)        (org-wide, optional)       (upstream providers)
```

The external LiteLLM Proxy is optional. If sandboxes are configured to call upstream providers directly, Open Terminal Orchestrator's credential injection provides the API keys. If an external LiteLLM Proxy is used, it adds an additional layer of RBAC, priority queuing, caching, and budget management.
