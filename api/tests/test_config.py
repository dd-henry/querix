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
    assert settings.llm.provider == "local"
    assert settings.llm.model_name == "qwen2.5-coder:7b"


def test_settings_require_session_secret_and_web_origin():
    with pytest.raises(SettingsError, match="SESSION_SECRET"):
        Settings.from_env(_environment(SESSION_SECRET=""))

    with pytest.raises(SettingsError, match="WEB_ORIGIN"):
        Settings.from_env(_environment(WEB_ORIGIN=""))


def test_settings_parse_production_cookie_security():
    assert Settings.from_env(_environment(COOKIE_SECURE="true")).cookie_secure is True
    assert Settings.from_env(_environment(COOKIE_SECURE="0")).cookie_secure is False


def test_settings_support_google_provider_without_exposing_the_key():
    settings = Settings.from_env(
        _environment(
            LLM_PROVIDER="google",
            GEMINI_API_KEY="test-key",
            GEMINI_MODEL="gemini-test",
            GEMINI_MAX_RETRIES="4",
        )
    )

    assert settings.llm.provider == "google"
    assert settings.llm.model_name == "gemini-test"
    assert settings.llm.gemini_api_key == "test-key"
    assert settings.llm.gemini_max_retries == 4


def test_settings_require_google_api_key_when_cloud_provider_is_selected():
    with pytest.raises(SettingsError, match="GEMINI_API_KEY"):
        Settings.from_env(_environment(LLM_PROVIDER="google"))
