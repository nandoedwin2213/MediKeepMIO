"""Clerk sign-in exchange: token verification and account resolution."""

import base64
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt

from app.core.config import settings
from app.core.utils.security import get_password_hash
from app.models.models import User
from app.services import clerk_auth

EXCHANGE_URL = "/api/v1/auth/clerk/exchange"
CONFIG_URL = "/api/v1/auth/clerk/config"
HOST = "example-app-12.clerk.accounts.dev"
PK = "pk_test_" + base64.b64encode(f"{HOST}$".encode()).decode().rstrip("=")
ORIGIN = "https://app.example.test"


def _key():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private.public_key()
        .public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    public = jwk.construct(public_pem, "RS256").to_dict()
    public.update(kid="kid-1", use="sig", alg="RS256")
    return pem, public


SIGNING_PEM, PUBLIC_JWK = _key()
OTHER_PEM, _ = _key()


def make_token(pem=SIGNING_PEM, **overrides):
    now = int(time.time())
    claims = {
        "sub": "user_clerk_1",
        "iss": f"https://{HOST}",
        "azp": ORIGIN,
        "iat": now,
        "nbf": now,
        "exp": now + 60,
        "sts": "active",
    }
    claims.update(overrides)
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": "kid-1"})


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return self._payload


@pytest.fixture
def clerk_user():
    return {
        "id": "user_clerk_1",
        "first_name": "Ana",
        "last_name": "Paz",
        "primary_email_address_id": "idn_1",
        "email_addresses": [
            {
                "id": "idn_1",
                "email_address": "Ana.Paz@Example.com",
                "verification": {"status": "verified"},
            }
        ],
    }


@pytest.fixture
def clerk_on(monkeypatch, clerk_user):
    monkeypatch.setattr(settings, "CLERK_PUBLISHABLE_KEY", PK)
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setattr(settings, "CLERK_AUTHORIZED_PARTIES", [])
    monkeypatch.setattr(settings, "APP_PUBLIC_URL", ORIGIN + "/")
    monkeypatch.setattr(settings, "ALLOW_USER_REGISTRATION", True)
    clerk_auth._jwks_cache.update(url=None, keys=[], fetched_at=0.0)
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(url)
        if url.endswith("/.well-known/jwks.json"):
            assert url == f"https://{HOST}/.well-known/jwks.json"
            return FakeResponse({"keys": [PUBLIC_JWK]})
        assert url == f"{clerk_auth.CLERK_API_URL}/users/{clerk_user['id']}"
        assert headers["Authorization"] == "Bearer sk_test_dummy"
        return FakeResponse(clerk_user)

    monkeypatch.setattr(clerk_auth.httpx, "get", fake_get)
    yield calls
    clerk_auth._jwks_cache.update(url=None, keys=[], fetched_at=0.0)


def test_frontend_api_host_decodes_publishable_key():
    assert clerk_auth.frontend_api_host(PK) == HOST
    assert clerk_auth.frontend_api_host("") is None
    assert clerk_auth.frontend_api_host("pk_test_!!!") is None
    assert clerk_auth.frontend_api_host("sk_test_abc") is None


def test_disabled_without_keys(client, monkeypatch):
    monkeypatch.setattr(settings, "CLERK_PUBLISHABLE_KEY", "")
    monkeypatch.setattr(settings, "CLERK_SECRET_KEY", "")
    assert client.get(CONFIG_URL).json()["enabled"] is False
    assert client.post(EXCHANGE_URL, json={"token": "x" * 40}).status_code == 404


def test_config_exposes_only_publishable_key(client, clerk_on):
    body = client.get(CONFIG_URL).json()
    assert body["enabled"] is True
    assert body["publishable_key"] == PK
    assert "sk_test_dummy" not in str(body)


def test_new_person_gets_patient_account_and_session(client, db_session, clerk_on):
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_new_user"] is True
    assert body["user"]["email"] == "ana.paz@example.com"
    assert body["user"]["role"] == "user"
    assert "access_token" in body
    created = db_session.query(User).filter(User.username == "ana.paz").one()
    assert created.sso_provider == "clerk"
    assert created.external_id == "user_clerk_1"
    assert created.full_name == "Ana Paz"


def test_existing_account_is_linked_by_verified_email(client, db_session, clerk_on):
    existing = User(
        username="anapaz",
        email="ana.paz@example.com",
        password_hash=get_password_hash("Secret123!"),
        full_name="Ana Paz",
        role="admin",
        auth_method="local",
    )
    db_session.add(existing)
    db_session.commit()

    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["is_new_user"] is False
    assert body["user"]["id"] == existing.id
    assert body["user"]["role"] == "admin"
    db_session.refresh(existing)
    assert existing.auth_method == "hybrid"
    assert existing.external_id == "user_clerk_1"
    assert db_session.query(User).count() == 1


def test_linked_account_found_by_clerk_id_after_email_change(
    client, db_session, clerk_on, clerk_user
):
    assert client.post(EXCHANGE_URL, json={"token": make_token()}).status_code == 200
    clerk_user["email_addresses"][0]["email_address"] = "new@example.com"
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 200
    assert response.json()["is_new_user"] is False
    assert db_session.query(User).count() == 1


def test_username_collision_gets_suffix(client, db_session, clerk_on):
    db_session.add(
        User(
            username="ana.paz",
            email="someone@else.com",
            password_hash=get_password_hash("Secret123!"),
            full_name="Other",
            role="user",
        )
    )
    db_session.commit()
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "ana.paz2"


@pytest.mark.parametrize(
    "token_factory",
    [
        lambda: make_token(pem=OTHER_PEM),
        lambda: make_token(exp=int(time.time()) - 120),
        lambda: make_token(iss="https://evil.clerk.accounts.dev"),
        lambda: make_token(azp="https://evil.example"),
        lambda: make_token(sts="pending"),
        lambda: "not-a-jwt-token-at-all-xxxxxxxx",
    ],
    ids=["bad-signature", "expired", "wrong-issuer", "wrong-azp", "pending", "garbage"],
)
def test_invalid_tokens_are_rejected(client, db_session, clerk_on, token_factory):
    response = client.post(EXCHANGE_URL, json={"token": token_factory()})
    assert response.status_code == 400
    assert db_session.query(User).count() == 0


def test_unverified_email_is_rejected(client, db_session, clerk_on, clerk_user):
    clerk_user["email_addresses"][0]["verification"]["status"] = "unverified"
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 400
    assert db_session.query(User).count() == 0


def test_registration_disabled_blocks_new_accounts(
    client, db_session, clerk_on, monkeypatch
):
    monkeypatch.setattr(settings, "ALLOW_USER_REGISTRATION", False)
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 403
    assert db_session.query(User).count() == 0


def test_inactive_account_is_refused(client, db_session, clerk_on):
    db_session.add(
        User(
            username="anapaz",
            email="ana.paz@example.com",
            password_hash=get_password_hash("Secret123!"),
            full_name="Ana Paz",
            role="user",
            is_active=False,
        )
    )
    db_session.commit()
    response = client.post(EXCHANGE_URL, json={"token": make_token()})
    assert response.status_code == 401
