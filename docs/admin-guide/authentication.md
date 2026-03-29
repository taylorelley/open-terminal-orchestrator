# Authentication

Open Terminal Orchestrator supports multiple authentication methods to secure the admin dashboard and management API. This guide covers setup and best practices for each method.

---

## Overview

| Method | Use Case | Transport |
|--------|----------|-----------|
| **Local credentials** (Supabase email/password) | Development, small deployments | Browser session (JWT) |
| **OIDC / SSO** | Production, enterprise deployments | Browser session (JWT via OIDC) |
| **API key** (`ADMIN_API_KEY`) | Automation, CI/CD, scripts | `Authorization: Bearer <key>` header |

All methods ultimately produce a session managed by Supabase Auth. The frontend stores the JWT in memory and refreshes it automatically. Row-Level Security (RLS) policies on the database enforce that only authenticated admin users can access data.

---

## Local Authentication (Supabase Email/Password)

Local authentication uses Supabase's built-in email/password provider. This is the simplest method and is suitable for development or small teams.

### Setup

1. **Create a Supabase project** at [supabase.com](https://supabase.com) or self-host Supabase using the official Docker Compose stack.

2. **Enable the email provider** in the Supabase dashboard under **Authentication > Providers > Email**. Ensure the following settings:
   - "Enable Email Signup" is turned on.
   - "Confirm email" can be disabled for development; enable it in production.
   - "Secure email change" should be enabled.

3. **Set the frontend environment variables** in your `.env` file:

   ```bash
   VITE_SUPABASE_URL=https://your-project.supabase.co
   VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
   ```

4. **Create the first admin user.** Navigate to the Open Terminal Orchestrator login page and use the signup form, or create the user directly in the Supabase dashboard under **Authentication > Users**.

5. **Restrict signups** (recommended for production). After creating admin accounts, disable public signups in the Supabase dashboard under **Authentication > Settings > User Signups** or by setting the `GOTRUE_DISABLE_SIGNUP=true` environment variable in a self-hosted Supabase instance.

### How It Works

1. The user enters their email and password on the `/login` page.
2. The `AuthContext` calls `supabase.auth.signInWithPassword()`.
3. Supabase returns a JWT access token and a refresh token.
4. The frontend stores the session in memory. The Supabase client automatically refreshes the token before expiry.
5. All subsequent API calls include the JWT in the `Authorization` header.

---

## OIDC / SSO

For production deployments, configure an external identity provider (IdP) via OpenID Connect. Supabase supports any OIDC-compliant provider. Below are examples for two common self-hosted providers.

### General OIDC Setup

1. **Register a client** in your identity provider with the following settings:

   | Parameter | Value |
   |-----------|-------|
   | Client type | Confidential |
   | Redirect URI | `https://<your-supabase-url>/auth/v1/callback` |
   | Post-logout redirect URI | `https://<your-oto-domain>/login` |
   | Scopes | `openid email profile` |

2. **Configure Supabase** with the OIDC provider details. In the Supabase dashboard, go to **Authentication > Providers** and add a new provider (or use the generic OIDC option). You will need:

   - **Client ID** -- from your IdP client registration.
   - **Client Secret** -- from your IdP client registration.
   - **Issuer / Discovery URL** -- the OpenID Connect discovery endpoint (e.g., `https://idp.example.com/.well-known/openid-configuration`).

3. **Rebuild the frontend** so that the login page picks up the new provider.

### Authentik Example

[Authentik](https://goauthentik.io/) is an open-source identity provider.

1. In Authentik, go to **Applications > Providers > Create** and select **OAuth2/OpenID Connect**.

2. Fill in the provider settings:

   ```
   Name:             Open Terminal Orchestrator
   Authorization URL: (auto-filled)
   Client type:       Confidential
   Client ID:         oto-dashboard
   Client Secret:     (generated)
   Redirect URIs:     https://<supabase-url>/auth/v1/callback
   Scopes:            openid email profile
   Signing Key:       authentik Self-signed Certificate
   ```

3. Create an **Application** linked to the provider and assign it to the appropriate users or groups.

4. In Supabase, add a new OIDC provider:

   ```
   Provider name:    Authentik
   Client ID:        oto-dashboard
   Client Secret:    <from step 2>
   Issuer URL:       https://authentik.example.com/application/o/oto/
   ```

5. The discovery URL is: `https://authentik.example.com/application/o/oto/.well-known/openid-configuration`

### Keycloak Example

[Keycloak](https://www.keycloak.org/) is a widely deployed open-source identity and access management solution.

1. In Keycloak, create a new **Client** under your realm:

   ```
   Client ID:          oto-dashboard
   Client Protocol:    openid-connect
   Access Type:        confidential
   Valid Redirect URIs: https://<supabase-url>/auth/v1/callback
   ```

2. After saving, go to the **Credentials** tab and copy the **Secret**.

3. In Supabase, add a new OIDC provider:

   ```
   Provider name:    Keycloak
   Client ID:        oto-dashboard
   Client Secret:    <from step 2>
   Issuer URL:       https://keycloak.example.com/realms/your-realm
   ```

4. The discovery URL is: `https://keycloak.example.com/realms/your-realm/.well-known/openid-configuration`

### Mapping Roles

By default, any user who authenticates via OIDC receives access to the Open Terminal Orchestrator dashboard. To restrict access, configure your IdP to include a `role` or `groups` claim in the ID token and add a Supabase Auth hook or RLS policy to enforce it.

---

## API Key Authentication

The `ADMIN_API_KEY` environment variable enables token-based authentication for the Open Terminal Orchestrator management API. This is intended for automation, scripts, and CI/CD pipelines -- not for interactive dashboard use.

### Setup

1. Generate a strong random key:

   ```bash
   openssl rand -base64 32
   ```

2. Set it in your `.env` file:

   ```bash
   ADMIN_API_KEY=sg-admin-AbCdEfGhIjKlMnOpQrStUvWxYz012345
   ```

3. Restart the Open Terminal Orchestrator backend.

### Usage

Include the API key in the `Authorization` header:

```bash
curl -H "Authorization: Bearer sg-admin-AbCdEfGhIjKlMnOpQrStUvWxYz012345" \
     https://oto.example.com/api/v1/admin/sandboxes
```

### Scope

API key authentication grants full admin access to all management endpoints under `/api/v1/admin/`. It does not grant access to the frontend dashboard (which requires a browser session).

When `ADMIN_API_KEY` is empty or unset, API-key authentication is disabled entirely and all management endpoints require a valid Supabase session.

---

## Session Management

### Token Lifecycle

- **Access tokens** expire after 1 hour (configurable in Supabase under `JWT_EXPIRY`).
- **Refresh tokens** are long-lived and rotate on each use.
- The Supabase client in the frontend handles token refresh automatically and transparently.

### Session Storage

Sessions are stored in memory only. Closing the browser tab ends the session. The refresh token is stored in an HTTP-only cookie by Supabase when using PKCE flow.

### Logout

Calling `supabase.auth.signOut()` invalidates the refresh token on the server and clears the local session. The frontend redirects to `/login`.

### Concurrent Sessions

A user can have multiple active sessions (e.g., different browsers or tabs). Each session has its own access/refresh token pair. Revoking a session only affects that specific token pair.

---

## Best Practices

### General

- **Use OIDC/SSO in production.** Local email/password auth is convenient for development but lacks MFA, centralized user management, and audit trails provided by enterprise IdPs.
- **Restrict signups.** After creating your admin accounts, disable public registration in Supabase.
- **Enable email confirmation** for local auth to prevent unauthorized account creation.

### API Keys

- **Rotate API keys regularly.** Change `ADMIN_API_KEY` at least quarterly.
- **Use separate keys per integration.** If multiple systems call the Open Terminal Orchestrator API, issue distinct keys by deploying separate Open Terminal Orchestrator instances or implementing a key management layer.
- **Never log API keys.** Ensure your reverse proxy and application logs redact `Authorization` headers.
- **Disable when not needed.** If no automation requires API access, leave `ADMIN_API_KEY` empty to close the attack surface.

### Network Security

- **Always use HTTPS** in production. Terminate TLS at your reverse proxy (Nginx, Caddy, Traefik).
- **Restrict CORS origins.** Replace the default `["*"]` in `CORS_ORIGINS` with your actual dashboard domain.
- **Place the Supabase instance behind a firewall** and only expose the required endpoints to the Open Terminal Orchestrator frontend.

### Monitoring

- Monitor failed login attempts via the Supabase Auth logs.
- Set up alerts for unusual API key usage patterns (high request rates, requests from unexpected IPs).
- Review the Open Terminal Orchestrator audit log for `admin.login` and `admin.api_key_auth` events.
