"""PayPhone subscriptions: plans, checkout (Prepare), confirmation and access rules."""

import json
import uuid
from calendar import monthrange
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging.config import get_logger
from app.models.billing import Subscription
from app.models.models import User
from app.services.metabolic_dashboard import is_professional

logger = get_logger(__name__, "app")

PAYPHONE_API_URL = "https://pay.payphonetodoesposible.com"
PAYPHONE_APPROVED = 3
PAYPHONE_CANCELLED = 2
CURRENCY = "USD"
DEFAULT_PLANS: List[Dict[str, Any]] = [
    {"id": "monthly", "months": 1, "amount_cents": 1999},
    {"id": "quarterly", "months": 3, "amount_cents": 4999},
    {"id": "yearly", "months": 12, "amount_cents": 17999},
]


class BillingError(Exception):
    """Raised when PayPhone cannot be reached or rejects a request."""


class BillingNotConfigured(BillingError):
    """Raised when PayPhone credentials or the public URL are missing."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_plans() -> List[Dict[str, Any]]:
    raw = (settings.BILLING_PLANS or "").strip()
    if not raw:
        return [dict(p) for p in DEFAULT_PLANS]
    try:
        parsed = json.loads(raw)
        plans = [
            {
                "id": str(p["id"])[:30],
                "months": int(p["months"]),
                "amount_cents": int(p["amount_cents"]),
            }
            for p in parsed
        ]
        if plans and all(p["months"] > 0 and p["amount_cents"] > 0 for p in plans):
            return plans
    except (ValueError, KeyError, TypeError):
        pass
    logger.warning("Invalid BILLING_PLANS, using defaults")
    return [dict(p) for p in DEFAULT_PLANS]


def find_plan(plan_id: str) -> Optional[Dict[str, Any]]:
    return next((p for p in get_plans() if p["id"] == plan_id), None)


def payphone_configured() -> bool:
    return bool(
        settings.PAYPHONE_TOKEN
        and settings.PAYPHONE_STORE_ID
        and settings.APP_PUBLIC_URL
    )


def billing_enforced() -> bool:
    return settings.BILLING_REQUIRED and payphone_configured()


def is_exempt(user: User) -> bool:
    return is_professional(user)


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def active_subscription(
    db: Session, user_id: int, now: Optional[datetime] = None
) -> Optional[Subscription]:
    now = now or utcnow()
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user_id,
            Subscription.status == "active",
            Subscription.period_end > now,
        )
        .order_by(Subscription.period_end.desc())
        .first()
    )


def has_access(db: Session, user: User) -> bool:
    if not billing_enforced() or is_exempt(user):
        return True
    return active_subscription(db, user.id) is not None


def serialize(sub: Subscription) -> Dict[str, Any]:
    return {
        "id": sub.id,
        "plan": sub.plan,
        "months": sub.months,
        "amount_cents": sub.amount_cents,
        "currency": sub.currency,
        "status": sub.status,
        "period_start": sub.period_start.isoformat() if sub.period_start else None,
        "period_end": sub.period_end.isoformat() if sub.period_end else None,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


def access_status(db: Session, user: User) -> Dict[str, Any]:
    active = active_subscription(db, user.id)
    history = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        .limit(12)
        .all()
    )
    exempt = is_exempt(user)
    return {
        "configured": payphone_configured(),
        "required": billing_enforced() and not exempt,
        "exempt": exempt,
        "has_access": has_access(db, user),
        "active": serialize(active) if active else None,
        "history": [serialize(s) for s in history],
    }


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.PAYPHONE_TOKEN}",
        "Content-Type": "application/json",
    }


def _post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = httpx.post(
            f"{PAYPHONE_API_URL}{path}", json=body, headers=_headers(), timeout=20
        )
    except httpx.HTTPError as exc:
        raise BillingError("PayPhone unreachable") from exc
    try:
        data = response.json()
    except ValueError:
        data = {}
    if response.status_code >= 400:
        logger.warning(
            "PayPhone request failed",
            extra={"path": path, "status": response.status_code},
        )
        raise BillingError(f"PayPhone error {response.status_code}")
    return data if isinstance(data, dict) else {}


def start_checkout(db: Session, user: User, plan: Dict[str, Any]) -> Dict[str, Any]:
    if not payphone_configured():
        raise BillingNotConfigured("PayPhone is not configured")
    client_tx = f"SILHO-{uuid.uuid4().hex[:24]}"
    base = settings.APP_PUBLIC_URL.rstrip("/")
    body = {
        "amount": plan["amount_cents"],
        "amountWithoutTax": plan["amount_cents"],
        "amountWithTax": 0,
        "tax": 0,
        "currency": CURRENCY,
        "clientTransactionId": client_tx,
        "storeId": settings.PAYPHONE_STORE_ID,
        "reference": f"SILHO {plan['id']}",
        "responseUrl": f"{base}/billing/response",
        "cancellationUrl": f"{base}/billing/response?cancelled=1",
    }
    if user.email:
        body["email"] = user.email
    sub = Subscription(
        user_id=user.id,
        plan=plan["id"],
        months=plan["months"],
        amount_cents=plan["amount_cents"],
        currency=CURRENCY,
        status="pending",
        client_transaction_id=client_tx,
    )
    db.add(sub)
    db.flush()
    data = _post("/api/button/Prepare", body)
    redirect_url = data.get("payWithCard") or data.get("payWithPayPhone")
    if not redirect_url:
        sub.status = "error"
        db.commit()
        raise BillingError("PayPhone returned no payment link")
    sub.provider_transaction_id = str(data.get("paymentId") or "") or None
    db.commit()
    return {"redirect_url": redirect_url, "client_transaction_id": client_tx}


def confirm_payment(
    db: Session, user: User, payment_id: int, client_tx: str
) -> Subscription:
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.client_transaction_id == client_tx,
            Subscription.user_id == user.id,
        )
        .first()
    )
    if sub is None:
        raise LookupError("subscription not found")
    if sub.status in ("active", "cancelled", "rejected"):
        return sub
    if not payphone_configured():
        raise BillingNotConfigured("PayPhone is not configured")
    data = _post(
        "/api/button/V2/Confirm", {"id": int(payment_id), "clientTxId": client_tx}
    )
    status_code = data.get("statusCode")
    approved = (
        status_code == PAYPHONE_APPROVED
        and str(data.get("clientTransactionId")) == client_tx
        and int(data.get("amount") or 0) == sub.amount_cents
    )
    sub.provider_transaction_id = str(data.get("transactionId") or payment_id)
    sub.provider_response = {
        k: data.get(k)
        for k in (
            "statusCode",
            "transactionStatus",
            "transactionId",
            "authorizationCode",
            "amount",
            "currency",
            "cardBrand",
            "lastDigits",
            "date",
            "message",
        )
        if k in data
    }
    if approved:
        current = active_subscription(db, user.id)
        start = max(utcnow(), current.period_end) if current else utcnow()
        sub.period_start = start
        sub.period_end = add_months(start, sub.months)
        sub.status = "active"
    elif status_code == PAYPHONE_CANCELLED:
        sub.status = "cancelled"
    else:
        sub.status = "rejected"
    db.commit()
    db.refresh(sub)
    return sub
