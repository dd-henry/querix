import pytest

from api.config import Settings, SettingsError


def _environment(**overrides):
    values = {
        "WEB_ORIGIN": "http://localhost:5173",
        "SESSION_SECRET": "test-secret",
        "DATABASE_URL": "postgresql://db.example/ask_sql",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "anon-key",
    }
    values.update(overrides)
    return values


def test_settings_load_typed_values_and_bounded_defaults():
    settings = Settings.from_env(_environment())

    assert settings.web_origin == "http://localhost:5173"
    assert settings.session_max_age_seconds == 8 * 60 * 60
    assert settings.result_limit == 5_000
    assert settings.prompt_limit == 2_000
    assert settings.cookie_secure is False


def test_settings_require_session_secret_and_web_origin():
    with pytest.raises(SettingsError, match="SESSION_SECRET"):
        Settings.from_env(_environment(SESSION_SECRET=""))

    with pytest.raises(SettingsError, match="WEB_ORIGIN"):
        Settings.from_env(_environment(WEB_ORIGIN=""))


def test_settings_parse_production_cookie_security():
    assert Settings.from_env(_environment(COOKIE_SECURE="true")).cookie_secure is True
    assert Settings.from_env(_environment(COOKIE_SECURE="0")).cookie_secure is False
