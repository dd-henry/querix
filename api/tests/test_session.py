import pytest
from starlette.requests import Request
from starlette.responses import Response

from api.auth.session import (
    SESSION_COOKIE_NAME,
    SessionError,
    clear_session,
    issue_session,
    require_session,
    sign_session,
    verify_session,
)
from api.config import Settings


def _settings(**overrides):
    values = {
        "web_origin": "http://localhost:5173",
        "session_secret": "test-secret",
    }
    values.update(overrides)
    return Settings(**values)


def _request(cookie=None):
    headers = []
    if cookie is not None:
        headers.append(
            (
                b"cookie",
                f"{SESSION_COOKIE_NAME}={cookie}".encode("ascii"),
            )
        )
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "query_string": b"",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
        }
    )


def _cookie_value(response):
    return response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]


def test_issue_and_verify_session_contains_identity_and_expiry():
    response = Response()

    claims = issue_session(response, "user-123", _settings(), now=1_000)
    verified = verify_session(
        _cookie_value(response),
        "test-secret",
        now=1_001,
    )

    assert claims == verified
    assert verified.user_id == "user-123"
    assert verified.issued_at == 1_000
    assert verified.expires_at == 1_000 + 8 * 60 * 60
    assert require_session(
        _request(_cookie_value(response)),
        _settings(),
        now=1_001,
    ) == verified


def test_invalid_session_inputs_share_the_same_auth_error():
    response = Response()
    issue_session(response, "user-123", _settings(), now=1_000)
    valid_cookie = _cookie_value(response)
    tampered_cookie = f"{valid_cookie[:-1]}x"
    expired_value, _ = sign_session(
        "user-123",
        "test-secret",
        max_age_seconds=10,
        now=1_000,
    )

    requests = [
        _request(),
        _request("malformed"),
        _request(tampered_cookie),
        _request(expired_value),
    ]

    for request in requests:
        with pytest.raises(SessionError) as error:
            require_session(request, _settings(), now=1_010)
        assert error.value.status_code == 401
        assert error.value.code == "auth_required"


def test_session_cookie_has_required_security_attributes_and_can_clear():
    settings = _settings(cookie_secure=True)
    response = Response()

    issue_session(response, "user-123", settings, now=1_000)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie
    assert "Max-Age=28800" in cookie

    clear_session(response)
    cleared_cookie = response.raw_headers[-1][1].decode("latin-1")
    assert f"{SESSION_COOKIE_NAME}=" in cleared_cookie
    assert "Max-Age=0" in cleared_cookie
    assert "Path=/" in cleared_cookie
