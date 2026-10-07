"""PayPhone subscriptions: checkout, confirmation and premium gating."""

from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.models.billing import Subscription
from app.services import billing

RECIPES = "/api/v1/metabolic/recipes"


@pytest.fixture
def payphone(monkeypatch):
    monkeypatch.setattr(settings, "PAYPHONE_TOKEN", "test-token")
    monkeypatch.setattr(settings, "PAYPHONE_STORE_ID", "store-1")
    monkeypatch.setattr(settings, "APP_PUBLIC_URL", "https://app.example.com")
    monkeypatch.setattr(settings, "BILLING_REQUIRED", True)
    calls = []
    replies = {}

    def fake_post(path, body):
        calls.append((path, body))
        return replies[path](body)

    monkeypatch.setattr(billing, "_post", fake_post)
    replies["/api/button/Prepare"] = lambda body: {
        "paymentId": 777,
        "payWithCard": "https://pay.payphonetodoesposible.com/Anonymous?paymentId=777",
    }
    return calls, replies


def _approve(amount=None):
    def reply(body):
        return {
            "statusCode": 3,
            "transactionStatus": "Approved",
            "transactionId": body["id"],
            "clientTransactionId": body["clientTxId"],
            "amount": 1999 if amount is None else amount,
            "lastDigits": "4242",
        }

    return reply


def _checkout(client, headers, plan="monthly"):
    res = client.post("/api/v1/billing/checkout", json={"plan": plan}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def test_plans_are_public(client):
    res = client.get("/api/v1/billing/plans")
    assert res.status_code == 200
    data = res.json()
    assert data["currency"] == "USD"
    assert [p["id"] for p in data["plans"]] == ["monthly", "quarterly", "yearly"]
    assert data["configured"] is False


def test_not_enforced_until_payphone_configured(client, user_token_headers):
    me = client.get("/api/v1/billing/me", headers=user_token_headers).json()
    assert me["required"] is False and me["has_access"] is True
    assert client.get(RECIPES, headers=user_token_headers).status_code == 200
    res = client.post(
        "/api/v1/billing/checkout", json={"plan": "monthly"}, headers=user_token_headers
    )
    assert res.status_code == 503


def test_premium_blocked_without_subscription(
    client, payphone, user_token_headers, admin_token_headers
):
    res = client.get(RECIPES, headers=user_token_headers)
    assert res.status_code == 402
    assert client.get(RECIPES, headers=admin_token_headers).status_code == 200
    me = client.get("/api/v1/billing/me", headers=user_token_headers).json()
    assert me["required"] is True and me["has_access"] is False


def test_checkout_and_confirm_activates(
    client, db_session, payphone, user_token_headers
):
    calls, replies = payphone
    out = _checkout(client, user_token_headers)
    assert out["redirect_url"].startswith("https://pay.payphonetodoesposible.com/")
    path, body = calls[0]
    assert path == "/api/button/Prepare"
    assert body["amount"] == body["amountWithoutTax"] == 1999
    assert body["storeId"] == "store-1"
    assert body["responseUrl"] == "https://app.example.com/billing/response"
    sub = db_session.query(Subscription).one()
    assert sub.status == "pending"
    assert client.get(RECIPES, headers=user_token_headers).status_code == 402

    replies["/api/button/V2/Confirm"] = _approve()
    res = client.post(
        "/api/v1/billing/confirm",
        json={"id": 777, "client_transaction_id": out["client_transaction_id"]},
        headers=user_token_headers,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["subscription"]["status"] == "active"
    assert data["has_access"] is True
    db_session.refresh(sub)
    assert sub.period_end - sub.period_start >= timedelta(days=28)
    assert "test-token" not in str(sub.provider_response)
    assert client.get(RECIPES, headers=user_token_headers).status_code == 200

    # Confirming twice is idempotent and does not call PayPhone again.
    client.post(
        "/api/v1/billing/confirm",
        json={"id": 777, "client_transaction_id": out["client_transaction_id"]},
        headers=user_token_headers,
    )
    assert [c[0] for c in calls].count("/api/button/V2/Confirm") == 1


def test_amount_mismatch_is_rejected(client, payphone, user_token_headers):
    _, replies = payphone
    out = _checkout(client, user_token_headers)
    replies["/api/button/V2/Confirm"] = _approve(amount=1)
    res = client.post(
        "/api/v1/billing/confirm",
        json={"id": 777, "client_transaction_id": out["client_transaction_id"]},
        headers=user_token_headers,
    )
    assert res.json()["subscription"]["status"] == "rejected"
    assert client.get(RECIPES, headers=user_token_headers).status_code == 402


def test_cancelled_payment(client, payphone, user_token_headers):
    _, replies = payphone
    out = _checkout(client, user_token_headers)
    replies["/api/button/V2/Confirm"] = lambda body: {
        "statusCode": 2,
        "transactionStatus": "Canceled",
        "clientTransactionId": body["clientTxId"],
    }
    res = client.post(
        "/api/v1/billing/confirm",
        json={"id": 777, "client_transaction_id": out["client_transaction_id"]},
        headers=user_token_headers,
    )
    assert res.json()["subscription"]["status"] == "cancelled"


def test_cannot_confirm_someone_elses_payment(
    client, payphone, user_token_headers, admin_token_headers
):
    out = _checkout(client, user_token_headers)
    res = client.post(
        "/api/v1/billing/confirm",
        json={"id": 777, "client_transaction_id": out["client_transaction_id"]},
        headers=admin_token_headers,
    )
    assert res.status_code == 404


def test_unknown_plan(client, payphone, user_token_headers):
    res = client.post(
        "/api/v1/billing/checkout", json={"plan": "gold"}, headers=user_token_headers
    )
    assert res.status_code == 404


def test_renewal_extends_from_current_period_end(
    client, db_session, payphone, test_user, user_token_headers
):
    _, replies = payphone
    end = datetime(2099, 1, 31, 12, 0)
    db_session.add(
        Subscription(
            user_id=test_user.id,
            plan="monthly",
            months=1,
            amount_cents=1999,
            currency="USD",
            status="active",
            provider="payphone",
            client_transaction_id="SILHO-existing",
            period_start=end - timedelta(days=31),
            period_end=end,
        )
    )
    db_session.commit()
    out = _checkout(client, user_token_headers, plan="quarterly")
    replies["/api/button/V2/Confirm"] = _approve(amount=4999)
    data = client.post(
        "/api/v1/billing/confirm",
        json={"id": 778, "client_transaction_id": out["client_transaction_id"]},
        headers=user_token_headers,
    ).json()
    assert data["subscription"]["period_start"].startswith("2099-01-31")
    assert data["subscription"]["period_end"].startswith("2099-04-30")


def test_admin_lists_subscriptions(
    client, payphone, user_token_headers, admin_token_headers
):
    _checkout(client, user_token_headers)
    assert (
        client.get(
            "/api/v1/billing/admin/subscriptions", headers=user_token_headers
        ).status_code
        == 403
    )
    items = client.get(
        "/api/v1/billing/admin/subscriptions", headers=admin_token_headers
    ).json()["items"]
    assert items[0]["email"] == "test@example.com"


def test_add_months_clamps_day():
    assert billing.add_months(datetime(2027, 1, 31), 1) == datetime(2027, 2, 28)
    assert billing.add_months(datetime(2027, 11, 15), 3) == datetime(2028, 2, 15)


def test_invalid_plan_env_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "BILLING_PLANS", "not json")
    assert billing.get_plans()[0]["id"] == "monthly"
    monkeypatch.setattr(
        settings,
        "BILLING_PLANS",
        '[{"id": "monthly", "months": 1, "amount_cents": 2500}]',
    )
    assert billing.get_plans() == [{"id": "monthly", "months": 1, "amount_cents": 2500}]
