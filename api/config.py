import os
from dataclasses import dataclass, field
from typing import Mapping, Optional

from dotenv import load_dotenv


class SettingsError(RuntimeError):
    """Raised when required API configuration is missing or invalid."""


def _required(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name, "").strip()
    if not value:
        raise SettingsError(f"{name} must be configured.")
    return value


def _boolean(environ: Mapping[str, str], name: str, default: bool) -> bool:
    value = environ.get(name)
    if value is None or not value.strip():
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{name} must be a boolean.")


def _positive_integer(
    environ: Mapping[str, str], name: str, default: int
) -> int:
    value = environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer.") from exc
    if parsed <= 0:
        raise SettingsError(f"{name} must be greater than zero.")
    return parsed


@dataclass(frozen=True)
class Settings:
    """Typed runtime configuration for the API."""

    web_origin: str
    session_secret: str = field(repr=False)
    database_url: Optional[str] = None
    postgres_host: Optional[str] = None
    postgres_port: str = "5432"
    postgres_user: Optional[str] = None
    postgres_password: Optional[str] = field(default=None, repr=False)
    postgres_dbname: Optional[str] = None
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = field(default=None, repr=False)
    session_max_age_seconds: int = 8 * 60 * 60
    cookie_secure: bool = False
    result_limit: int = 5_000
    prompt_limit: int = 2_000

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "Settings":
        if environ is None:
            load_dotenv()
            environ = os.environ

        return cls(
            web_origin=_required(environ, "WEB_ORIGIN"),
            session_secret=_required(environ, "SESSION_SECRET"),
            database_url=environ.get("DATABASE_URL") or None,
            postgres_host=environ.get("POSTGRES_HOST") or None,
            postgres_port=environ.get("POSTGRES_PORT", "5432"),
            postgres_user=environ.get("POSTGRES_USER") or None,
            postgres_password=environ.get("POSTGRES_PASSWORD") or None,
            postgres_dbname=environ.get("POSTGRES_DBNAME") or None,
            supabase_url=environ.get("SUPABASE_URL") or None,
            supabase_anon_key=environ.get("SUPABASE_ANON_KEY") or None,
            session_max_age_seconds=_positive_integer(
                environ, "SESSION_MAX_AGE_SECONDS", 8 * 60 * 60
            ),
            cookie_secure=_boolean(environ, "COOKIE_SECURE", False),
            result_limit=_positive_integer(environ, "RESULT_LIMIT", 5_000),
            prompt_limit=_positive_integer(environ, "PROMPT_LIMIT", 2_000),
        )


def get_settings() -> Settings:
    """Load API settings from the process environment."""

    return Settings.from_env()
