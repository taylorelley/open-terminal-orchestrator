"""OIDC client service for admin SSO authentication.

Handles discovery, authorization code exchange, ID token validation,
and session JWT creation/verification. Supports Authentik, Keycloak,
and any standard OpenID Connect provider.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass, field

import httpx
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

from app.config import settings

logger = logging.getLogger(__name__)

# Session JWT validity (seconds).
SESSION_LIFETIME = 8 * 3600  # 8 hours


@dataclass
class OIDCMetadata:
    """Cached OIDC provider metadata from discovery endpoint."""

    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str
    jwks_uri: str
    end_session_endpoint: str = ""
    issuer: str = ""
    fetched_at: float = 0.0


@dataclass
class OIDCUserInfo:
    """Extracted user identity from OIDC ID token / userinfo."""

    sub: str
    email: str = ""
    name: str = ""
    groups: list[str] = field(default_factory=list)


class OIDCClient:
    """OIDC client that wraps discovery, token exchange, and validation."""

    def __init__(self) -> None:
        self._metadata: OIDCMetadata | None = None
        self._jwks: dict | None = None
        self._jwks_fetched_at: float = 0.0
        # Cache TTL for discovery and JWKS (seconds).
        self._cache_ttl = 3600

    @property
    def is_configured(self) -> bool:
        """Return True if OIDC settings are present."""
        return bool(settings.oidc_issuer and settings.oidc_client_id)

    @property
    def _session_secret(self) -> str:
        """Return the secret used to sign session JWTs."""
        if settings.oidc_session_secret:
            return settings.oidc_session_secret
        # Derive a deterministic secret from client_secret so it survives restarts.
        if settings.oidc_client_secret:
            return hashlib.sha256(
                f"oto-session:{settings.oidc_client_secret}".encode()
            ).hexdigest()
        return "oto-dev-secret"

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def _fetch_metadata(self) -> OIDCMetadata:
        """Fetch and cache OIDC discovery metadata."""
        now = time.monotonic()
        if self._metadata and (now - self._metadata.fetched_at) < self._cache_ttl:
            return self._metadata

        url = f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        self._metadata = OIDCMetadata(
            authorization_endpoint=data["authorization_endpoint"],
            token_endpoint=data["token_endpoint"],
            userinfo_endpoint=data.get("userinfo_endpoint", ""),
            jwks_uri=data["jwks_uri"],
            end_session_endpoint=data.get("end_session_endpoint", ""),
            issuer=data["issuer"],
            fetched_at=now,
        )
        logger.info("OIDC discovery metadata fetched", extra={"issuer": data["issuer"]})
        return self._metadata

    async def _fetch_jwks(self) -> dict:
        """Fetch and cache the JWKS key set."""
        now = time.monotonic()
        if self._jwks and (now - self._jwks_fetched_at) < self._cache_ttl:
            return self._jwks

        meta = await self._fetch_metadata()
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(meta.jwks_uri)
            resp.raise_for_status()
            self._jwks = resp.json()
            self._jwks_fetched_at = now

        return self._jwks

    # ------------------------------------------------------------------
    # Authorization URL
    # ------------------------------------------------------------------

    async def get_authorize_url(self, state: str, nonce: str) -> str:
        """Build the OIDC authorization URL for the browser redirect."""
        meta = await self._fetch_metadata()
        redirect_uri = settings.oidc_redirect_uri or self._default_redirect_uri()
        params = {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": redirect_uri,
            "scope": settings.oidc_scopes,
            "state": state,
            "nonce": nonce,
        }
        qs = "&".join(f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items())
        return f"{meta.authorization_endpoint}?{qs}"

    # ------------------------------------------------------------------
    # Token exchange
    # ------------------------------------------------------------------

    async def exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for tokens."""
        meta = await self._fetch_metadata()
        redirect_uri = settings.oidc_redirect_uri or self._default_redirect_uri()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.oidc_client_id,
            "client_secret": settings.oidc_client_secret,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                meta.token_endpoint,
                data=payload,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # ID token validation
    # ------------------------------------------------------------------

    async def validate_id_token(self, id_token: str, nonce: str | None = None) -> OIDCUserInfo:
        """Validate an OIDC ID token and extract user info.

        Verifies signature, issuer, audience, expiry, and optional nonce.
        """
        jwks_data = await self._fetch_jwks()
        key_set = JsonWebKey.import_key_set(jwks_data)

        claims = jwt.decode(id_token, key_set)
        claims.validate()

        # Verify issuer
        meta = await self._fetch_metadata()
        if claims.get("iss") != meta.issuer:
            raise ValueError(f"Invalid issuer: {claims.get('iss')}")

        # Verify audience
        aud = claims.get("aud")
        if isinstance(aud, list):
            if settings.oidc_client_id not in aud:
                raise ValueError("Client ID not in audience")
        elif aud != settings.oidc_client_id:
            raise ValueError(f"Invalid audience: {aud}")

        # Verify nonce if provided
        if nonce and claims.get("nonce") != nonce:
            raise ValueError("Nonce mismatch")

        # Extract user info
        groups: list[str] = []
        raw_groups = claims.get("groups", claims.get("roles", []))
        if isinstance(raw_groups, list):
            groups = [str(g) for g in raw_groups]

        return OIDCUserInfo(
            sub=claims["sub"],
            email=claims.get("email", ""),
            name=claims.get("name", claims.get("preferred_username", "")),
            groups=groups,
        )

    # ------------------------------------------------------------------
    # Session JWT helpers
    # ------------------------------------------------------------------

    def create_session_token(self, user_info: OIDCUserInfo) -> str:
        """Create a signed session JWT for the authenticated admin."""
        now = int(time.time())
        payload = {
            "sub": user_info.sub,
            "email": user_info.email,
            "name": user_info.name,
            "groups": user_info.groups,
            "iat": now,
            "exp": now + SESSION_LIFETIME,
            "iss": "oto",
        }
        header = {"alg": "HS256"}
        return jwt.encode(header, payload, self._session_secret).decode("utf-8")

    def verify_session_token(self, token: str) -> OIDCUserInfo | None:
        """Verify an Open Terminal Orchestrator session JWT. Returns None if invalid."""
        try:
            claims = jwt.decode(token, self._session_secret)
            claims.validate()
            if claims.get("iss") != "oto":
                return None
            return OIDCUserInfo(
                sub=claims["sub"],
                email=claims.get("email", ""),
                name=claims.get("name", ""),
                groups=claims.get("groups", []),
            )
        except (JoseError, ValueError, KeyError):
            return None

    # ------------------------------------------------------------------
    # Logout URL
    # ------------------------------------------------------------------

    async def get_logout_url(self, id_token_hint: str | None = None) -> str | None:
        """Return the OIDC provider logout URL, or None if not supported."""
        meta = await self._fetch_metadata()
        if not meta.end_session_endpoint:
            return None
        url = meta.end_session_endpoint
        if id_token_hint:
            url += f"?id_token_hint={id_token_hint}"
        return url

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def generate_state() -> str:
        """Generate a random state parameter."""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_nonce() -> str:
        """Generate a random nonce."""
        return secrets.token_urlsafe(24)

    @staticmethod
    def _default_redirect_uri() -> str:
        """Derive a default redirect URI from server settings."""
        return f"http://localhost:{settings.port}/admin/api/auth/oidc/callback"


# Module-level singleton.
oidc_client = OIDCClient()
