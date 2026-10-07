"""Subscriptions paid through PayPhone."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api import deps
from app.core.http.error_handling import (
    BusinessLogicException,
    NotFoundException,
    ServiceUnavailableException,
)
from app.crud.activity_log import activity_log
from app.models.activity_log import EntityType
from app.models.billing import Subscription
from app.models.models import User
from app.services import billing

router = APIRouter()


class CheckoutRequest(BaseModel):
    plan: str = Field(..., max_length=30)


class ConfirmRequest(BaseModel):
    id: int = Field(..., ge=1)
    client_transaction_id: str = Field(..., min_length=1, max_length=64)


@router.get("/plans")
def list_plans() -> Any:
    """Public: plans and prices shown on the landing page."""
    return {
        "currency": billing.CURRENCY,
        "configured": billing.payphone_configured(),
        "plans": billing.get_plans(),
    }


@router.get("/me")
def my_subscription(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    return billing.access_status(db, current_user)


@router.post("/checkout")
async def checkout(
    body: CheckoutRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    plan = billing.find_plan(body.plan)
    if plan is None:
        raise NotFoundException(message="Unknown plan", request=request)
    try:
        return await run_in_threadpool(billing.start_checkout, db, current_user, plan)
    except billing.BillingNotConfigured:
        raise ServiceUnavailableException(
            message="Payments are not configured yet", request=request
        )
    except billing.BillingError:
        raise ServiceUnavailableException(
            message="The payment provider is not available", request=request
        )


@router.post("/confirm")
async def confirm(
    body: ConfirmRequest,
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    try:
        sub = await run_in_threadpool(
            billing.confirm_payment,
            db,
            current_user,
            body.id,
            body.client_transaction_id,
        )
    except LookupError:
        raise NotFoundException(message="Payment not found", request=request)
    except billing.BillingNotConfigured:
        raise ServiceUnavailableException(
            message="Payments are not configured yet", request=request
        )
    except billing.BillingError:
        raise BusinessLogicException(
            message="The payment could not be confirmed", request=request
        )
    activity_log.log_activity(
        db=db,
        action="subscription_payment",
        entity_type=EntityType.USER,
        description=f"Subscription {sub.plan} payment {sub.status}",
        user_id=current_user.id,
        metadata={"plan": sub.plan, "status": sub.status},
    )
    return {
        "subscription": billing.serialize(sub),
        **billing.access_status(db, current_user),
    }


@router.get("/admin/subscriptions")
def list_subscriptions(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_admin_user),
) -> Any:
    rows = (
        db.query(Subscription, User.email)
        .join(User, User.id == Subscription.user_id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .limit(300)
        .all()
    )
    return {"items": [{**billing.serialize(s), "email": email} for s, email in rows]}


def require_subscription(
    request: Request,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_user),
) -> None:
    """Router dependency: premium (metabolic programme) endpoints need a paid plan."""
    if not billing.has_access(db, current_user):
        raise deps.MedicalRecordsAPIException(
            error_code="SUBSCRIPTION_REQUIRED",
            http_status_code=402,
            message="An active subscription is required",
            request=request,
        )
