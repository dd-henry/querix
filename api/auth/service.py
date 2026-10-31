from dataclasses import dataclass
from typing import Callable, Optional

from supabase import create_client

from api.config import Settings


class AuthConfigurationError(RuntimeError):
    """Raised when Supabase configuration is not available."""


class AuthServiceError(RuntimeError):
    """Raised when an authentication operation cannot be completed."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class AuthUser:
    """User identity safe for API route callers."""

    id: str
    email: Optional[str]
    session_present: bool = False


ClientFactory = Callable[[str, str], object]


class SupabaseAuthService:
    """Perform each Supabase operation with an isolated client."""

    def __init__(
        self,
        settings: Settings,
        client_factory: ClientFactory = create_client,
    ):
        if not settings.supabase_url or not settings.supabase_anon_key:
            raise AuthConfigurationError(
                "Configure SUPABASE_URL and SUPABASE_ANON_KEY."
            )
        self._url = settings.supabase_url
        self._anon_key = settings.supabase_anon_key
        self._client_factory = client_factory

    def _new_client(self):
        return self._client_factory(self._url, self._anon_key)

    @staticmethod
    def _user_identity(user: object) -> AuthUser:
        user_id = getattr(user, "id", None)
        email = getattr(user, "email", None)
        if not isinstance(user_id, str) or not user_id:
            raise AuthServiceError(
                "auth_invalid_response",
                "Authentication service returned an invalid user.",
            )
        if email is not None and not isinstance(email, str):
            email = None
        return AuthUser(id=user_id, email=email)

    def sign_in(self, email: str, password: str) -> AuthUser:
        client = self._new_client()
        try:
            response = client.auth.sign_in_with_password(
                {"email": email.strip(), "password": password}
            )
        except Exception as exc:
            raise AuthServiceError(
                "auth_failed",
                "Authentication request failed.",
            ) from exc

        user = getattr(response, "user", None)
        session = getattr(response, "session", None)
        if user is None or session is None:
            raise AuthServiceError(
                "auth_invalid_response",
                "Authentication service returned an incomplete response.",
            )
        identity = self._user_identity(user)
        return AuthUser(
            id=identity.id,
            email=identity.email,
            session_present=True,
        )

    def sign_up(self, email: str, password: str, name: str) -> AuthUser:
        client = self._new_client()
        try:
            response = client.auth.sign_up(
                {"email": email.strip(), "password": password}
            )
        except Exception as exc:
            raise AuthServiceError(
                "signup_failed",
                "Signup request failed.",
            ) from exc

        user = getattr(response, "user", None)
        if user is None:
            raise AuthServiceError(
                "auth_invalid_response",
                "Authentication service returned an incomplete response.",
            )
        identity = self._user_identity(user)
        return AuthUser(
            id=identity.id,
            email=identity.email,
            session_present=getattr(response, "session", None) is not None,
        )

    def sign_out(self) -> None:
        client = self._new_client()
        try:
            client.auth.sign_out()
        except Exception as exc:
            raise AuthServiceError(
                "signout_failed",
                "Signout request failed.",
            ) from exc
