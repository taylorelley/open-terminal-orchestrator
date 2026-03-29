# ShellGuard Sandbox — Slim Variant
# Minimal Open Terminal image for OpenShell policy-enforced sandboxes.

FROM ghcr.io/open-webui/open-terminal:slim

LABEL org.opencontainers.image.title="ShellGuard Sandbox"
LABEL org.opencontainers.image.description="Open Terminal in OpenShell sandbox"
LABEL org.opencontainers.image.source="https://github.com/taylorelley/shellguard"

# Health check for pool manager readiness probes
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

# Configuration for Open Terminal inside the sandbox.
# OPEN_TERMINAL_API_KEY is injected at container creation time by openshell_client.
ENV OPEN_TERMINAL_PORT=8000

# Inherit entrypoint from base image (open-terminal run).
