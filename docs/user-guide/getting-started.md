# Getting Started with Open Terminal Orchestrator

This guide walks you through installing Open Terminal Orchestrator, launching the stack, and connecting it to Open WebUI so that users get secure, isolated terminal sandboxes.

---

## Prerequisites

Before you begin, make sure you have:

- **Docker** v24 or later and **Docker Compose** v2.20 or later
- **OpenShell Gateway** -- the container runtime that provisions sandboxes (see [OpenShell docs](https://github.com/openshell/gateway))
- **Open WebUI** (optional for initial setup, required for production) -- the chat interface whose terminal sessions Open Terminal Orchestrator secures
- A machine with at least **2 CPU cores** and **4 GB RAM** for the Open Terminal Orchestrator stack itself (sandbox resources are separate)
- Ports **8080** (dashboard / API) and **5432** (PostgreSQL, if not using managed Supabase) available

---

## Step 1: Clone and Configure

Clone the repository and create your environment file:

```bash
git clone https://github.com/oto/open-terminal-orchestrator.git
cd open-terminal-orchestrator
cp .env.example .env
```

Open `.env` in your editor and set the following required variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENSHELL_GATEWAY` | URL of your OpenShell Gateway instance | `http://gateway:9090` |
| `ADMIN_API_KEY` | Secret key for admin API authentication | `sg-k_...` (generate a strong random string) |
| `VITE_SUPABASE_URL` | Supabase project URL (or local Supabase URL) | `http://localhost:54321` |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous/public key | `eyJhbGciOiJI...` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:password@db:5432/oto` |
| `JWT_SECRET` | Secret for signing JWT tokens | (generate a strong random string) |

Optional but recommended for production:

| Variable | Description | Default |
|----------|-------------|---------|
| `OIDC_ISSUER_URL` | OIDC provider issuer URL for SSO | _(disabled)_ |
| `OIDC_CLIENT_ID` | OIDC client ID | _(disabled)_ |
| `OIDC_CLIENT_SECRET` | OIDC client secret | _(disabled)_ |
| `LITELLM_API_BASE` | LiteLLM proxy URL for inference routing | _(disabled)_ |
| `LOG_LEVEL` | Application log level | `info` |
| `POOL_WARMUP_SIZE` | Number of pre-warmed sandbox containers | `3` |
| `MAX_SANDBOXES` | Maximum total sandbox containers | `50` |

---

## Step 2: Start the Stack

Launch all services with Docker Compose:

```bash
docker compose up -d
```

This starts:

- **oto-api** -- FastAPI backend on port 8080
- **oto-frontend** -- React dashboard (served by the API in production, or separate in dev)
- **postgres** -- PostgreSQL database (if using local Supabase)
- **supabase** -- Supabase services (auth, realtime, REST)

Verify the services are running:

```bash
docker compose ps
```

All services should show a status of `Up`. The database migrations run automatically on first startup.

---

## Step 3: Access the Admin Dashboard

Open your browser and navigate to:

```
http://localhost:8080
```

You will be presented with the login screen.

### First Login

On a fresh installation, create the initial admin account:

1. Click **Sign Up** on the login page.
2. Enter your email address and a strong password.
3. The first account created is automatically assigned the **admin** role.
4. After signing up, you are redirected to the dashboard.

> **Note:** Subsequent accounts are created with the **pending** role by default. An admin must promote them through the Users & Groups page.

---

## Step 4: Connect Open WebUI

To route Open WebUI terminal sessions through Open Terminal Orchestrator:

1. In your Open WebUI configuration, set the **terminal integration URL** to:

   ```
   http://oto:8080/api/v1/terminal
   ```

   Replace `oto` with the hostname or IP address if Open WebUI and Open Terminal Orchestrator are not on the same Docker network.

2. Open WebUI sends an `X-Open-WebUI-User-Id` header with each terminal request. Open Terminal Orchestrator uses this header to:
   - Identify the requesting user
   - Look up their policy assignment (user-specific, group, role, or system default)
   - Provision or reuse a sandbox matching that policy

3. If you are using OIDC, ensure both Open WebUI and Open Terminal Orchestrator are configured with the same identity provider so that user IDs are consistent.

### Docker Network Setup

If both services run via Docker Compose, add them to a shared network:

```yaml
# In your Open WebUI docker-compose.yml
services:
  open-webui:
    networks:
      - oto-net

networks:
  oto-net:
    external: true
```

Create the network if it does not exist:

```bash
docker network create oto-net
```

---

## Step 5: Verify the Integration

1. Open Open WebUI in your browser and start a new chat session.
2. Trigger a terminal session (e.g., ask the model to run a shell command).
3. Switch to the Open Terminal Orchestrator admin dashboard at `http://localhost:8080`.
4. Navigate to **Sandboxes** in the sidebar.
5. You should see a new sandbox in the **Active** tab with the user's ID, assigned policy, and resource metrics.

If the sandbox does not appear:

- Check the Open Terminal Orchestrator API logs: `docker compose logs oto-api`
- Verify the OpenShell Gateway is reachable from the Open Terminal Orchestrator container
- Confirm the `X-Open-WebUI-User-Id` header is being sent (check Open WebUI logs)
- See the [Troubleshooting guide](../operations/troubleshooting.md) for additional diagnostics

---

## What's Next

Now that Open Terminal Orchestrator is running and connected, explore these guides:

- [Dashboard Overview](dashboard-overview.md) -- Learn the admin interface
- [Managing Sandboxes](managing-sandboxes.md) -- Understand sandbox lifecycle and operations
- [Managing Users & Groups](managing-users-groups.md) -- Configure user access and group policies
- [Managing Policies](managing-policies.md) -- Create and assign YAML security policies
- [Deployment Guide](../admin-guide/deployment.md) -- Production deployment best practices
- [Configuration Reference](../admin-guide/configuration.md) -- Full list of environment variables and settings
