"""Authentication routes for admin SSO and local (SQLite) auth.

Provides OIDC login redirect, callback, logout, session info endpoints,
and local email/password authentication for environments without Supabase.
These endpoints do NOT require the ``require_admin`` dependency since
they are part of the authentication flow itself.
"""

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AdminUser
from app.services.audit_service import log_admin
from app.services.oidc import oidc_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/api/auth", tags=["auth"])

# Cookie name for the session JWT.
_SESSION_COOKIE = "sg_session"

# Cookie name for the OIDC state/nonce (short-lived, used during login flow).
_STATE_COOKIE = "sg_oidc_state"


def _source_ip(request: Request) -> str:
    """Extract the client IP from the request."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/config")
async def auth_config() -> dict:
    """Return the authentication configuration (public, no auth required).

    The frontend uses this to decide which login options to show.
    """
    return {
        "auth_method": settings.auth_method,
        "oidc_configured": oidc_client.is_configured,
    }


@router.get("/oidc/login")
async def oidc_login() -> RedirectResponse:
    """Redirect the user to the OIDC provider's authorization endpoint."""
    if not oidc_client.is_configured:
        return RedirectResponse("/login?error=oidc_not_configured", status_code=302)

    state = oidc_client.generate_state()
    nonce = oidc_client.generate_nonce()
    authorize_url = await oidc_client.get_authorize_url(state, nonce)

    response = RedirectResponse(authorize_url, status_code=302)
    # Store state + nonce in a short-lived cookie for CSRF verification.
    response.set_cookie(
        _STATE_COOKIE,
        f"{state}:{nonce}",
        httponly=True,
        samesite="lax",
        max_age=600,  # 10 minutes
        secure=False,  # Set True behind TLS reverse proxy
    )
    return response


@router.get("/oidc/callback")
async def oidc_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OIDC provider callback after user authentication."""
    ip = _source_ip(request)

    if error:
        logger.warning("OIDC callback error", extra={"error": error, "ip": ip})
        log_admin(db, "oidc_login_failed", details={"error": error}, source_ip=ip)
        return RedirectResponse("/login?error=oidc_denied", status_code=302)

    if not code or not state:
        log_admin(db, "oidc_login_failed", details={"error": "missing_code_or_state"}, source_ip=ip)
        return RedirectResponse("/login?error=oidc_invalid", status_code=302)

    # Verify state against cookie.
    state_cookie = request.cookies.get(_STATE_COOKIE, "")
    if ":" not in state_cookie:
        log_admin(db, "oidc_login_failed", details={"error": "missing_state_cookie"}, source_ip=ip)
        return RedirectResponse("/login?error=oidc_invalid", status_code=302)

    expected_state, nonce = state_cookie.split(":", 1)
    if state != expected_state:
        log_admin(db, "oidc_login_failed", details={"error": "state_mismatch"}, source_ip=ip)
        return RedirectResponse("/login?error=oidc_invalid", status_code=302)

    try:
        # Exchange authorization code for tokens.
        token_data = await oidc_client.exchange_code(code)
        id_token = token_data.get("id_token", "")
        if not id_token:
            raise ValueError("No id_token in token response")

        # Validate ID token and extract user info.
        user_info = await oidc_client.validate_id_token(id_token, nonce=nonce)
    except Exception as exc:
        logger.warning("OIDC token validation failed", extra={"error": str(exc), "ip": ip})
        log_admin(db, "oidc_login_failed", details={"error": str(exc)}, source_ip=ip)
        return RedirectResponse("/login?error=oidc_failed", status_code=302)

    # Create an Open Terminal Orchestrator session JWT.
    session_token = oidc_client.create_session_token(user_info)

    log_admin(
        db,
        "oidc_login_success",
        details={"sub": user_info.sub, "email": user_info.email, "name": user_info.name},
        source_ip=ip,
    )

    response = RedirectResponse("/admin", status_code=302)
    response.set_cookie(
        _SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
        secure=False,  # Set True behind TLS reverse proxy
    )
    # Clear the state cookie.
    response.delete_cookie(_STATE_COOKIE)
    return response


@router.get("/session")
async def session_info(request: Request) -> JSONResponse:
    """Return current session information.

    If the user has a valid session cookie, return their identity.
    Otherwise return an unauthenticated status.
    """
    token = request.cookies.get(_SESSION_COOKIE, "")
    if token:
        user_info = oidc_client.verify_session_token(token)
        if user_info:
            return JSONResponse({
                "authenticated": True,
                "method": "oidc",
                "sub": user_info.sub,
                "email": user_info.email,
                "name": user_info.name,
                "groups": user_info.groups,
            })

    return JSONResponse({
        "authenticated": False,
        "method": None,
    })


@router.post("/oidc/logout")
async def oidc_logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Clear the session cookie and optionally redirect to OIDC logout."""
    ip = _source_ip(request)

    token = request.cookies.get(_SESSION_COOKIE, "")
    user_info = oidc_client.verify_session_token(token) if token else None

    if user_info:
        log_admin(
            db,
            "oidc_logout",
            details={"sub": user_info.sub, "email": user_info.email},
            source_ip=ip,
        )

    # Get the provider logout URL if available.
    logout_url = await oidc_client.get_logout_url() if oidc_client.is_configured else None

    response = JSONResponse({
        "status": "ok",
        "logout_url": logout_url,
    })
    response.delete_cookie(_SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# Local (SQLite) authentication helpers & endpoints
# ---------------------------------------------------------------------------

# Signing key for local JWTs — derived from the OIDC session secret or
# a random value generated at startup.
_LOCAL_SECRET = settings.oidc_session_secret or secrets.token_hex(32)

# Token lifetime: 8 hours.
_LOCAL_TOKEN_TTL = 8 * 3600


def _hash_password(password: str) -> str:
    """Return a salted SHA-256 hash of *password*."""
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{digest}"


def _verify_password(password: str, stored: str) -> bool:
    """Check *password* against a hash produced by ``_hash_password``."""
    salt, digest = stored.split(":", 1)
    expected = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return hmac.compare_digest(digest, expected)


def _create_local_token(user_id: str, email: str) -> str:
    """Create a simple HMAC-signed JWT-like token for local auth."""
    header = urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload_data = {
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + _LOCAL_TOKEN_TTL,
    }
    payload = urlsafe_b64encode(json.dumps(payload_data).encode()).rstrip(b"=").decode()
    signature_input = f"{header}.{payload}".encode()
    sig = hmac.new(_LOCAL_SECRET.encode(), signature_input, hashlib.sha256).hexdigest()
    return f"{header}.{payload}.{sig}"


def _verify_local_token(token: str) -> dict | None:
    """Verify a local auth token.  Returns the payload dict or None."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header, payload, sig = parts
    expected_sig = hmac.new(
        _LOCAL_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    # Pad base64 back.
    padded = payload + "=" * (-len(payload) % 4)
    try:
        data = json.loads(urlsafe_b64decode(padded))
    except Exception:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


@router.post("/local/signup")
async def local_signup(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Register a local admin user (only when no admin users exist yet)."""
    body = await request.json()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not email or not password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)

    try:
        # Only allow signup when no admin users exist.
        existing = (await db.execute(select(AdminUser).limit(1))).scalars().first()
        if existing is not None:
            return JSONResponse(
                {"error": "An admin user already exists. Use login instead."}, status_code=409
            )

        user = AdminUser(
            id=uuid.uuid4(),
            email=email,
            password_hash=_hash_password(password),
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()

        ip = _source_ip(request)
        log_admin(db, "local_signup", details={"email": email}, source_ip=ip)

        token = _create_local_token(str(user.id), email)
        return JSONResponse({"token": token, "user": {"id": str(user.id), "email": email}})
    except Exception:
        logger.exception("local_signup failed for %s", email)
        return JSONResponse({"error": "Signup failed. Check server logs for details."}, status_code=500)


@router.post("/local/login")
async def local_login(request: Request, db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Authenticate with a local admin email/password."""
    body = await request.json()
    email = body.get("email", "").strip()
    password = body.get("password", "")

    if not email or not password:
        return JSONResponse({"error": "Email and password are required"}, status_code=400)

    user = (
        await db.execute(select(AdminUser).where(AdminUser.email == email))
    ).scalars().first()

    if user is None or not _verify_password(password, user.password_hash):
        ip = _source_ip(request)
        log_admin(db, "local_login_failed", details={"email": email}, source_ip=ip)
        return JSONResponse({"error": "Invalid email or password"}, status_code=401)

    ip = _source_ip(request)
    log_admin(db, "local_login_success", details={"email": email}, source_ip=ip)

    token = _create_local_token(str(user.id), email)
    return JSONResponse({"token": token, "user": {"id": str(user.id), "email": email}})


@router.get("/local/session")
async def local_session(request: Request) -> JSONResponse:
    """Validate a local auth token and return user info."""
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        return JSONResponse({"authenticated": False, "method": None})

    payload = _verify_local_token(token)
    if not payload:
        return JSONResponse({"authenticated": False, "method": None})

    return JSONResponse({
        "authenticated": True,
        "method": "local",
        "sub": payload["sub"],
        "email": payload["email"],
        "name": payload.get("email", ""),
        "groups": [],
    })
