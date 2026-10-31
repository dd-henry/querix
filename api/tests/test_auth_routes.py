from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from starlette.responses import Response

from api.app import create_app
from api.auth.service import AuthServiceError, AuthUser
from api.auth.session import issue_session
from api.config import Settings
from api.routes.auth import SIGNUP_SUCCESS_MESSAGE, get_auth_service
from api.dependencies import get_user_repository


USER_ID = "00000000-0000-0000-0000-000000000001"


def _settings():
    return Settings(
        web_origin="http://localhost:5173",
        session_secret="test-secret",
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
    )


def _profile(status="approved"):
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": status,
    }


def _client(auth=None, repository=None, settings=None):
    app = create_app(settings or _settings())
    auth = auth or Mock()
    repository = repository or Mock()
    app.dependency_overrides[get_auth_service] = lambda: auth
    app.dependency_overrides[get_user_repository] = lambda: repository
    return TestClient(app), auth, repository


def test_login_sets_cookie_and_returns_approved_profile():
    auth = Mock()
    auth.sign_in.return_value = AuthUser(USER_ID, "user@example.com", True)
    repository = Mock()
    repository.get_profile.return_value = _profile()
    client, auth, repository = _client(auth, repository)

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json() == _profile()
    assert "ask_sql_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    auth.sign_in.assert_called_once_with("user@example.com", "password")
    repository.get_profile.assert_called_once_with(USER_ID)


def test_invalid_login_is_stateless_and_uses_safe_error():
    auth = Mock()
    auth.sign_in.side_effect = AuthServiceError(
        "auth_failed",
        "Authentication request failed.",
    )
    client, auth, repository = _client(auth)

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "auth_failed",
            "message": "Authentication request failed.",
        }
    }
    assert "set-cookie" not in response.headers
    repository.get_profile.assert_not_called()


@pytest.mark.parametrize("status", ["pending", "rejected", "disabled"])
def test_blocked_profiles_cannot_login(status):
    auth = Mock()
    auth.sign_in.return_value = AuthUser(USER_ID, "user@example.com", True)
    repository = Mock()
    repository.get_profile.return_value = _profile(status)
    client, _auth, _repository = _client(auth, repository)

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "password"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_not_approved"
    assert "set-cookie" not in response.headers


def test_signup_creates_pending_profile_and_returns_confirmation():
    auth = Mock()
    auth.sign_up.return_value = AuthUser(USER_ID, "new@example.com")
    repository = Mock()
    client, auth, repository = _client(auth, repository)

    response = client.post(
        "/api/auth/signup",
        json={
            "name": " New User ",
            "email": " new@example.com ",
            "password": "password",
            "password_confirmation": "password",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"message": SIGNUP_SUCCESS_MESSAGE}
    auth.sign_up.assert_called_once_with(
        "new@example.com",
        "password",
        "New User",
    )
    repository.create_pending_profile.assert_called_once_with(
        USER_ID,
        "new@example.com",
        "New User",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "",
            "email": "user@example.com",
            "password": "password",
            "password_confirmation": "password",
        },
        {
            "name": "User",
            "email": "",
            "password": "password",
            "password_confirmation": "password",
        },
        {
            "name": "User",
            "email": "user@example.com",
            "password": "short",
            "password_confirmation": "short",
        },
        {
            "name": "User",
            "email": "user@example.com",
            "password": "password",
            "password_confirmation": "different",
        },
    ],
)
def test_signup_validation_never_calls_auth_service(payload):
    client, auth, repository = _client()

    response = client.post("/api/auth/signup", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    auth.sign_up.assert_not_called()
    repository.create_pending_profile.assert_not_called()


def test_malformed_login_body_uses_validation_envelope():
    client, auth, _repository = _client()

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
        }
    }
    auth.sign_in.assert_not_called()


def test_logout_clears_cookie_and_me_requires_session():
    settings = _settings()
    client, _auth, repository = _client(settings=settings)
    repository.get_profile.return_value = _profile()

    missing = client.get("/api/auth/me")
    assert missing.status_code == 401

    session_response = Response()
    issue_session(session_response, USER_ID, settings)
    cookie = session_response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    client.cookies.set("ask_sql_session", cookie)

    current = client.get("/api/auth/me")
    assert current.status_code == 200
    assert current.json() == _profile()

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200
    assert "Max-Age=0" in logout.headers["set-cookie"]
