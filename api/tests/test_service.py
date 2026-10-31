from types import SimpleNamespace

import pytest

from api.auth.service import (
    AuthConfigurationError,
    AuthServiceError,
    SupabaseAuthService,
)
from api.config import Settings


def _settings(**overrides):
    values = {
        "web_origin": "http://localhost:5173",
        "session_secret": "test-secret",
        "supabase_url": "https://example.supabase.co",
        "supabase_anon_key": "anon-key",
    }
    values.update(overrides)
    return Settings(**values)


class FakeAuth:
    def __init__(self, sign_in_response=None, sign_up_response=None):
        self.sign_in_response = sign_in_response
        self.sign_up_response = sign_up_response
        self.sign_in_payload = None
        self.sign_up_payload = None
        self.signed_out = False

    def sign_in_with_password(self, payload):
        self.sign_in_payload = payload
        if isinstance(self.sign_in_response, Exception):
            raise self.sign_in_response
        return self.sign_in_response

    def sign_up(self, payload):
        self.sign_up_payload = payload
        if isinstance(self.sign_up_response, Exception):
            raise self.sign_up_response
        return self.sign_up_response

    def sign_out(self):
        self.signed_out = True


class FakeClient:
    def __init__(self, auth):
        self.auth = auth


def test_login_returns_identity_without_exposing_supabase_tokens():
    auth = FakeAuth(
        sign_in_response=SimpleNamespace(
            user=SimpleNamespace(id="user-1", email="user@example.com"),
            session=SimpleNamespace(
                access_token="access-token",
                refresh_token="refresh-token",
            ),
        )
    )
    service = SupabaseAuthService(
        _settings(),
        client_factory=lambda _url, _key: FakeClient(auth),
    )

    user = service.sign_in(" user@example.com ", "password")

    assert user.id == "user-1"
    assert user.email == "user@example.com"
    assert user.session_present is True
    assert not hasattr(user, "access_token")
    assert auth.sign_in_payload == {
        "email": "user@example.com",
        "password": "password",
    }


def test_login_failure_is_a_typed_error():
    auth = FakeAuth(sign_in_response=RuntimeError("provider details"))
    service = SupabaseAuthService(
        _settings(),
        client_factory=lambda _url, _key: FakeClient(auth),
    )

    with pytest.raises(AuthServiceError) as error:
        service.sign_in("user@example.com", "wrong")

    assert error.value.code == "auth_failed"
    assert error.value.message == "Authentication request failed."
    assert "provider details" not in str(error.value)


def test_signup_returns_identity_and_strips_email():
    auth = FakeAuth(
        sign_up_response=SimpleNamespace(
            user=SimpleNamespace(id="user-2", email="new@example.com")
        )
    )
    service = SupabaseAuthService(
        _settings(),
        client_factory=lambda _url, _key: FakeClient(auth),
    )

    user = service.sign_up(" new@example.com ", "password", "New User")

    assert user.id == "user-2"
    assert user.email == "new@example.com"
    assert auth.sign_up_payload == {
        "email": "new@example.com",
        "password": "password",
    }


def test_signup_failure_and_missing_configuration_are_explicit():
    auth = FakeAuth(sign_up_response=RuntimeError("provider details"))
    service = SupabaseAuthService(
        _settings(),
        client_factory=lambda _url, _key: FakeClient(auth),
    )

    with pytest.raises(AuthServiceError) as signup_error:
        service.sign_up("new@example.com", "password", "New User")
    assert signup_error.value.code == "signup_failed"

    with pytest.raises(AuthConfigurationError, match="SUPABASE_URL"):
        SupabaseAuthService(_settings(supabase_url=None))


def test_each_operation_creates_a_fresh_client_and_signout_isolated():
    clients = []

    def client_factory(_url, _key):
        auth = FakeAuth(
            sign_in_response=SimpleNamespace(
                user=SimpleNamespace(id="user-1", email="user@example.com"),
                session=SimpleNamespace(),
            )
        )
        client = FakeClient(auth)
        clients.append(client)
        return client

    service = SupabaseAuthService(_settings(), client_factory=client_factory)

    service.sign_in("user@example.com", "password")
    service.sign_out()

    assert len(clients) == 2
    assert clients[0] is not clients[1]
    assert clients[1].auth.signed_out is True
