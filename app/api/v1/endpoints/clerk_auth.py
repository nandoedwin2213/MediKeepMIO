"""Sign-in through Clerk (email and Google), exchanged for a MediKeep session."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.endpoints.sso import _check_user_active, _complete_sso_login
from app.auth.sso.exceptions import SSOAuthenticationError, SSORegistrationBlockedError
from app.core.config import settings
from app.core.http.auth_codes import AuthErrorCode
from app.core.http.error_handling import MedicalRecordsAPIException
from app.core.logging.config import get_logger
from app.core.logging.helpers import log_endpoint_error, log_security_event
from app.core.utils.client_ip import get_client_ip
from app.core.utils.rate_limit import SlidingWindowRateLimiter
from app.services import clerk_auth

logger = get_logger(__name__, "sso")
router = APIRouter(prefix="/auth/clerk", tags=["clerk"])

_exchange_limiter = SlidingWindowRateLimiter(
    max_requests=settings.SSO_RATE_LIMIT_ATTEMPTS,
    window_seconds=settings.SSO_RATE_LIMIT_WINDOW_MINUTES * 60,
)


class ClerkExchangeRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=8192)


@router.get("/config")
async def get_clerk_config():
    enabled = clerk_auth.is_enabled()
    return {
        "enabled": enabled,
        "publishable_key": settings.CLERK_PUBLISHABLE_KEY if enabled else None,
        "registration_enabled": settings.ALLOW_USER_REGISTRATION,
    }


@router.post("/exchange")
def exchange_clerk_session(
    req: Request, request: ClerkExchangeRequest, db: Session = Depends(deps.get_db)
):
    """Verify a Clerk session token and return a MediKeep session for that person."""
    if not clerk_auth.is_enabled():
        raise HTTPException(status_code=404, detail="Clerk sign-in is not configured")

    client_ip = get_client_ip(req)
    if not _exchange_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many sign-in attempts. Please try again later.",
            headers=_exchange_limiter.rate_limit_headers(client_ip),
        )

    try:
        claims = clerk_auth.verify_session_token(request.token)
        profile = clerk_auth.fetch_clerk_user(claims["sub"])
        result = clerk_auth.resolve_user(db, profile)
        _check_user_active(result["user"], "clerk_login_rejected_inactive", req)
        return _complete_sso_login(
            result,
            req,
            db,
            log_event_name="clerk_token_created",
            activity_description=f"User logged in via Clerk: {result['user'].username}",
        )
    except SSORegistrationBlockedError as e:
        log_security_event(
            logger, "clerk_registration_blocked", req, "Clerk registration blocked"
        )
        raise HTTPException(
            status_code=403,
            detail="Registration is currently disabled. Please contact an administrator.",
            headers={
                "X-Error-Code": e.error_code or AuthErrorCode.REGISTRATION_DISABLED
            },
        )
    except SSOAuthenticationError as e:
        log_security_event(
            logger,
            "clerk_authentication_failed",
            req,
            "Clerk authentication failed",
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail=e.message,
            headers={
                "X-Error-Code": e.error_code or AuthErrorCode.SSO_AUTHENTICATION_FAILED
            },
        )
    except (MedicalRecordsAPIException, HTTPException):
        raise
    except Exception as e:
        log_endpoint_error(logger, req, "Unexpected error in Clerk exchange", e)
        raise HTTPException(
            status_code=500,
            detail="Sign-in failed",
            headers={"X-Error-Code": AuthErrorCode.SSO_AUTHENTICATION_FAILED},
        )
