import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

from starlette.requests import Request
from starlette.responses import Response

from api.config import Settings

SESSION_COOKIE_NAME = "ask_sql_session"


class SessionError(Exception):
    """Raised when the session cookie cannot authenticate a request."""

    status_code = 401
    code = "auth_required"
    message = "Authentication required."

    def __init__(self):
        super().__init__(self.message)


@dataclass(frozen=True)
class SessionClaims:
    user_id: str
    issued_at: int
    expires_at: int


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)
    except (ValueError, binascii.Error) as exc:
        raise SessionError() from exc


def _claims_payload(claims: SessionClaims) -> bytes:
    return json.dumps(
        {
            "user_id": claims.user_id,
            "iat": claims.issued_at,
            "exp": claims.expires_at,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _signature(payload: bytes, secret: str) -> bytes:
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).digest()


def sign_session(
    user_id: str,
    secret: str,
    max_age_seconds: int,
    now: Optional[int] = None,
) -> tuple[str, SessionClaims]:
    issued_at = int(time.time()) if now is None else now
    claims = SessionClaims(
        user_id=user_id,
        issued_at=issued_at,
        expires_at=issued_at + max_age_seconds,
    )
    payload = _encode(_claims_payload(claims))
    signature = _encode(_signature(payload.encode("ascii"), secret))
    return f"{payload}.{signature}", claims


def verify_session(
    value: str,
    secret: str,
    now: Optional[int] = None,
) -> SessionClaims:
    current_time = int(time.time()) if now is None else now
    try:
        parts = value.split(".")
        if len(parts) != 2:
            raise SessionError()
        encoded_payload, encoded_signature = parts
        payload = _decode(encoded_payload)
        signature = _decode(encoded_signature)
    except (AttributeError, ValueError):
        raise SessionError()

    expected_signature = _signature(encoded_payload.encode("ascii"), secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise SessionError()

    try:
        data = json.loads(payload.decode("utf-8"))
        user_id = data["user_id"]
        issued_at = data["iat"]
        expires_at = data["exp"]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise SessionError() from exc

    if (
        not isinstance(user_id, str)
        or not user_id
        or type(issued_at) is not int
        or type(expires_at) is not int
        or issued_at > current_time
        or expires_at <= issued_at
        or expires_at <= current_time
    ):
        raise SessionError()

    return SessionClaims(
        user_id=user_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def issue_session(
    response: Response,
    user_id: str,
    settings: Settings,
    now: Optional[int] = None,
) -> SessionClaims:
    value, claims = sign_session(
        user_id,
        settings.session_secret,
        settings.session_max_age_seconds,
        now=now,
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=value,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return claims


def require_session(
    request: Request,
    settings: Settings,
    now: Optional[int] = None,
) -> SessionClaims:
    value = request.cookies.get(SESSION_COOKIE_NAME)
    if not value:
        raise SessionError()
    return verify_session(value, settings.session_secret, now=now)


def clear_session(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )
