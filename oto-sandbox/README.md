# Open Terminal Orchestrator Sandbox Image

Custom BYOC (Bring Your Own Container) images for Open Terminal Orchestrator sandboxes, built on Open Terminal.

## Variants

| Variant | Base Image | Tag | Use Case |
|---------|-----------|-----|----------|
| **Slim** | `open-terminal:slim` | `oto-sandbox:slim` | Default. Minimal attack surface, fast startup. |
| **Full** | `open-terminal:latest` | `oto-sandbox:full` | When sandboxes need pre-installed tooling (language runtimes, data science libraries). |

## Building

```bash
# Build slim variant (default)
./register.sh

# Build full variant
./register.sh full
```

Or manually:

```bash
docker build -t oto-sandbox:slim -f Dockerfile .
docker build -t oto-sandbox:full -f Dockerfile.full .
```

## Registering with OpenShell

Create a sandbox from the built image:

```bash
openshell sandbox create \
  --from oto-sandbox:slim \
  --name my-sandbox \
  --policy policy.yaml
```

Or build directly from the directory context:

```bash
openshell sandbox create \
  --from ./oto-sandbox/ \
  --name my-sandbox \
  --policy policy.yaml
```

## Health Check

Both variants include a Docker HEALTHCHECK that probes `http://localhost:8000/health` every 10 seconds. The Open Terminal Orchestrator pool manager uses this to determine sandbox readiness before assigning sandboxes to users.

## Customization

To add additional tooling, extend either Dockerfile. For example, to add Python and Node.js to the full variant:

```dockerfile
FROM oto-sandbox:full

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip nodejs npm \
  && rm -rf /var/lib/apt/lists/*
```

Build with a custom tag and update `default_image_tag` in your Open Terminal Orchestrator configuration (Settings > Sandbox Image Tag).

## Configuration

The default image tag is configured via:

- **Environment variable:** `DEFAULT_IMAGE_TAG=oto-sandbox:slim`
- **Admin UI:** Settings > Sandbox Image Tag
- **Database:** `system_config` table, key `default_image_tag`
