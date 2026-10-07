"""Clerk sign-in: verify a Clerk session token and resolve it to a MediKeep user.

Clerk only proves who the person is (verified email, Google). Roles, patients and
all medical data stay in MediKeep; the user receives the usual MediKeep session.
"""

import base64
import re
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.sso.exceptions import SSOAuthenticationError, SSORegistrationBlockedError
from app.core.config import settings
from app.core.http.auth_codes import AuthErrorCode
from app.core.logging.config import get_logger
from app.crud.user import user as user_crud
from app.models.models import User

logger = get_logger(__name__, "sso")

PROVIDER = "clerk"
CLERK_API_URL = "https://api.clerk.com/v1"
_JWKS_TTL_SECONDS = 3600
_HTTP_TIMEOUT = 10.0
_LEEWAY_SECONDS = 10

_jwks_lock = threading.Lock()
_jwks_cache: Dict = {"url": None, "keys": [], "fetched_at": 0.0}


def frontend_api_host(publishable_key: str) -> Optional[str]:
    """Decode the Clerk Frontend API host embedded in a publishable key."""
    match = re.fullmatch(r"pk_(test|live)_([A-Za-z0-9+/=_-]+)", publishable_key or "")
    if not match:
        return None
    encoded = match.group(2)
    try:
        decoded = base64.b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    host = decoded.rstrip("$")
    if not re.fullmatch(r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}", host):
        return None
    return host


def is_enabled() -> bool:
    return bool(
        settings.CLERK_SECRET_KEY and frontend_api_host(settings.CLERK_PUBLISHABLE_KEY)
    )


def _issuer() -> str:
    return f"https://{frontend_api_host(settings.CLERK_PUBLISHABLE_KEY)}"


def _authorized_parties() -> List[str]:
    parties = [p.rstrip("/") for p in settings.CLERK_AUTHORIZED_PARTIES if p]
    if not parties and settings.APP_PUBLIC_URL:
        parsed = urlparse(settings.APP_PUBLIC_URL)
        if parsed.scheme and parsed.netloc:
            parties = [f"{parsed.scheme}://{parsed.netloc}"]
    return parties


def _fail(message: str) -> SSOAuthenticationError:
    return SSOAuthenticationError(
        message, error_code=AuthErrorCode.SSO_AUTHENTICATION_FAILED
    )


def _fetch_jwks(force: bool = False) -> List[Dict]:
    url = f"{_issuer()}/.well-known/jwks.json"
    with _jwks_lock:
        fresh = time.time() - _jwks_cache["fetched_at"] < _JWKS_TTL_SECONDS
        if not force and fresh and _jwks_cache["url"] == url and _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        try:
            response = httpx.get(url, timeout=_HTTP_TIMEOUT)
            response.raise_for_status()
            keys = response.json().get("keys", [])
        except (httpx.HTTPError, ValueError) as exc:
            raise _fail("Could not reach the sign-in provider") from exc
        _jwks_cache.update(url=url, keys=keys, fetched_at=time.time())
        return keys


def _signing_key(kid: Optional[str]) -> Dict:
    for force in (False, True):
        for key in _fetch_jwks(force=force):
            if key.get("kid") == kid:
                return key
    raise _fail("Unknown signing key")


def verify_session_token(token: str) -> Dict:
    """Validate a Clerk session JWT (signature, issuer, expiry, azp) and return claims."""
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _fail("Invalid session token") from exc
    if header.get("alg") != "RS256":
        raise _fail("Invalid session token")

    try:
        claims = jwt.decode(
            token,
            _signing_key(header.get("kid")),
            algorithms=["RS256"],
            issuer=_issuer(),
            options={
                "verify_aud": False,
                "require_exp": True,
                "leeway": _LEEWAY_SECONDS,
            },
        )
    except JWTError as exc:
        raise _fail("Invalid session token") from exc

    if not claims.get("sub"):
        raise _fail("Invalid session token")
    if claims.get("sts") not in (None, "active"):
        raise _fail("Session is not active")

    parties = _authorized_parties()
    azp = (claims.get("azp") or "").rstrip("/")
    if parties and azp not in parties:
        logger.warning(
            "Clerk token rejected: unexpected authorized party",
            extra={"category": "security", "event": "clerk_azp_rejected", "azp": azp},
        )
        raise _fail("Invalid session token")
    return claims


def fetch_clerk_user(clerk_user_id: str) -> Dict:
    """Read the verified primary email and name from the Clerk Backend API."""
    try:
        response = httpx.get(
            f"{CLERK_API_URL}/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
            timeout=_HTTP_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _fail("Could not reach the sign-in provider") from exc

    if data.get("banned") or data.get("locked"):
        raise _fail("This account is blocked")

    primary_id = data.get("primary_email_address_id")
    email = None
    for address in data.get("email_addresses") or []:
        verified = (address.get("verification") or {}).get("status") == "verified"
        if address.get("id") == primary_id and verified:
            email = (address.get("email_address") or "").strip().lower()
    if not email:
        raise _fail("A verified email address is required")

    name = " ".join(
        part for part in (data.get("first_name"), data.get("last_name")) if part
    ).strip()
    return {"id": data.get("id") or clerk_user_id, "email": email, "name": name}


def _unique_username(db: Session, email: str) -> str:
    base = re.sub(r"[^a-z0-9._-]", "", email.split("@")[0].lower())[:40] or "user"
    candidate, suffix = base, 1
    while user_crud.get_by_username(db, username=candidate):
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def resolve_user(db: Session, profile: Dict) -> Dict:
    """Find the MediKeep account for a Clerk identity: by Clerk id, then by verified
    email (linking it), otherwise create a regular patient account."""
    now = datetime.utcnow()
    linked = user_crud.get_by_external_id(
        db, external_id=profile["id"], sso_provider=PROVIDER
    )
    if linked:
        linked.last_sso_login = now
        db.commit()
        return {"user": linked, "is_new_user": False, "auth_method": "sso"}

    existing = (
        db.query(User)
        .filter(func.lower(User.email) == profile["email"])
        .order_by(User.id)
        .first()
    )
    if existing:
        if existing.external_id and existing.sso_provider not in (None, PROVIDER):
            logger.warning(
                "Clerk sign-in replaced a previous SSO link",
                extra={
                    "category": "security",
                    "event": "clerk_link_replaced",
                    "user_id": existing.id,
                    "previous_provider": existing.sso_provider,
                },
            )
        existing.external_id = profile["id"]
        existing.sso_provider = PROVIDER
        existing.last_sso_login = now
        if existing.auth_method == "local":
            existing.auth_method = "hybrid"
            existing.account_linked_at = now
        db.commit()
        logger.info(
            "Clerk identity linked to existing account by verified email",
            extra={"category": "sso", "event": "clerk_linked", "user_id": existing.id},
        )
        return {"user": existing, "is_new_user": False, "auth_method": "sso"}

    if not settings.ALLOW_USER_REGISTRATION:
        raise SSORegistrationBlockedError(
            "New user registration is currently disabled. "
            "Please contact an administrator to create an account.",
            error_code=AuthErrorCode.REGISTRATION_DISABLED,
        )

    new_user = user_crud.create_from_sso(
        db,
        email=profile["email"],
        username=_unique_username(db, profile["email"]),
        full_name=profile["name"] or profile["email"].split("@")[0],
        external_id=profile["id"],
        sso_provider=PROVIDER,
    )
    logger.info(
        "New user created via Clerk",
        extra={
            "category": "sso",
            "event": "clerk_user_created",
            "user_id": new_user.id,
        },
    )
    return {"user": new_user, "is_new_user": True, "auth_method": "sso"}
