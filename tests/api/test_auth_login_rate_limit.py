"""Failed password logins are rate limited per client IP and per username."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.endpoints.auth import _failed_login_limiter
from app.core.http.auth_codes import AuthErrorCode
from tests.utils.user import create_random_user

LOGIN_URL = "/api/v1/auth/login"


def _login(client: TestClient, username: str, password: str):
    return client.post(LOGIN_URL, data={"username": username, "password": password})


class TestLoginRateLimit:
    def test_blocks_after_max_failures_even_with_correct_password(
        self, client: TestClient, db_session: Session, limiter_ceiling
    ):
        limiter_ceiling(_failed_login_limiter, 3)
        user_data = create_random_user(db_session)

        for _ in range(3):
            assert _login(client, user_data["username"], "wrong").status_code == 401

        response = _login(client, user_data["username"], user_data["password"])

        assert response.status_code == 429
        assert response.json()["error_code"] == AuthErrorCode.LOGIN_RATE_LIMITED
        assert int(response.headers["Retry-After"]) >= 1
        assert response.headers["X-RateLimit-Limit"] == "3"

    def test_successful_logins_are_not_counted(
        self, client: TestClient, db_session: Session, limiter_ceiling
    ):
        limiter_ceiling(_failed_login_limiter, 2)
        user_data = create_random_user(db_session)

        for _ in range(5):
            response = _login(client, user_data["username"], user_data["password"])
            assert response.status_code == 200

    def test_username_bucket_is_case_insensitive(
        self, client: TestClient, db_session: Session, limiter_ceiling
    ):
        limiter_ceiling(_failed_login_limiter, 2)
        user_data = create_random_user(db_session)
        username = user_data["username"]

        assert _login(client, username.upper(), "wrong").status_code == 401
        assert _login(client, username.lower(), "wrong").status_code == 401

        assert ("user", username.lower()) in _failed_login_limiter._requests
        assert _login(client, username, "wrong").status_code == 429

    def test_ip_bucket_blocks_other_usernames(
        self, client: TestClient, db_session: Session, limiter_ceiling
    ):
        limiter_ceiling(_failed_login_limiter, 2)
        user_data = create_random_user(db_session)

        assert _login(client, "nobody-1", "wrong").status_code == 401
        assert _login(client, "nobody-2", "wrong").status_code == 401

        response = _login(client, user_data["username"], user_data["password"])
        assert response.status_code == 429
