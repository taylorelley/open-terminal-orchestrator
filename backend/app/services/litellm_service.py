"""LiteLLM credential routing service.

Handles credential stripping from incoming inference requests,
provider credential injection for sandbox-bound requests, and
model management/provider configuration for LiteLLM Proxy integration.
"""

import logging
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)

# Headers that may carry credentials and must be stripped before
# forwarding to the sandbox LiteLLM instance.
_CREDENTIAL_HEADERS = frozenset({
    "authorization",
    "x-api-key",
    "api-key",
    "openai-api-key",
    "anthropic-api-key",
    "x-openai-api-key",
})


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider backend."""

    name: str
    api_base: str
    api_key: str = ""
    models: list[str] = field(default_factory=list)
    default_model: str = ""


@dataclass
class ModelRoute:
    """Maps a model alias to a provider and upstream model name."""

    alias: str
    provider: str
    upstream_model: str


class LiteLLMCredentialRouter:
    """Manages credential stripping/injection for LiteLLM proxy requests.

    When a user's inference request flows through ShellGuard:

    1. **Strip** — Remove any user-supplied API keys from the request
       headers so they never reach the sandbox.
    2. **Inject** — Add the operator-configured provider credentials
       appropriate for the user's policy tier and requested model.
    3. **Route** — Resolve the model alias to the correct upstream
       provider and model name.
    """

    def __init__(self) -> None:
        self._providers: dict[str, ProviderConfig] = {}
        self._routes: dict[str, ModelRoute] = {}

    def register_provider(self, config: ProviderConfig) -> None:
        """Register or update a provider configuration."""
        self._providers[config.name] = config
        logger.info("Registered LiteLLM provider: %s (%d models)", config.name, len(config.models))

    def remove_provider(self, name: str) -> bool:
        """Remove a provider. Returns True if it existed."""
        removed = self._providers.pop(name, None)
        if removed:
            # Remove routes that referenced this provider.
            self._routes = {
                alias: route
                for alias, route in self._routes.items()
                if route.provider != name
            }
            logger.info("Removed LiteLLM provider: %s", name)
        return removed is not None

    def register_route(self, route: ModelRoute) -> None:
        """Register a model alias route."""
        self._routes[route.alias] = route
        logger.info("Registered model route: %s -> %s/%s", route.alias, route.provider, route.upstream_model)

    def list_providers(self) -> list[ProviderConfig]:
        """Return all registered providers."""
        return list(self._providers.values())

    def list_models(self) -> list[str]:
        """Return all available model aliases."""
        return list(self._routes.keys())

    def strip_credentials(self, headers: dict[str, str]) -> dict[str, str]:
        """Remove credential headers from the request.

        Returns a new dict with credential-bearing headers removed so
        that user-supplied API keys never reach the sandbox.
        """
        return {
            k: v for k, v in headers.items()
            if k.lower() not in _CREDENTIAL_HEADERS
        }

    def inject_credentials(
        self,
        headers: dict[str, str],
        model: str | None = None,
    ) -> dict[str, str]:
        """Inject the appropriate provider credentials into request headers.

        If *model* is provided and maps to a known route, uses that
        route's provider credentials.  Otherwise falls back to the first
        registered provider.
        """
        provider: ProviderConfig | None = None

        if model and model in self._routes:
            route = self._routes[model]
            provider = self._providers.get(route.provider)

        if provider is None and self._providers:
            provider = next(iter(self._providers.values()))

        if provider is None:
            logger.debug("No LiteLLM provider configured — forwarding without credentials")
            return headers

        result = dict(headers)
        if provider.api_key:
            result["Authorization"] = f"Bearer {provider.api_key}"
        return result

    def resolve_model(self, model: str) -> tuple[str, str | None]:
        """Resolve a model alias to (upstream_model, api_base).

        Returns the original model name and None if no route is configured.
        """
        route = self._routes.get(model)
        if route is None:
            return model, None

        provider = self._providers.get(route.provider)
        if provider is None:
            return model, None

        return route.upstream_model, provider.api_base

    def transform_request_headers(
        self,
        headers: dict[str, str],
        model: str | None = None,
    ) -> dict[str, str]:
        """Full pipeline: strip user credentials, then inject operator credentials."""
        stripped = self.strip_credentials(headers)
        return self.inject_credentials(stripped, model=model)


# Module-level singleton.
litellm_router = LiteLLMCredentialRouter()
