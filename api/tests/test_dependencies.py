from unittest.mock import Mock

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from starlette.responses import Response

from api.app import create_app
from api.auth.session import issue_session
from api.config import Settings
from api.dependencies import (
    get_conversation_repository,
    get_current_profile,
    get_db_adapter,
    get_predefined_query_repository,
    get_query_history_repository,
    get_user_repository,
    require_approved_user,
    require_roles,
)
from database.conversations import ConversationRepository
from database.postgres import PostgresAdapter
from database.predefined_queries import PredefinedQueryRepository
from database.query_history import QueryHistoryRepository
from database.users import UserRepository


USER_ID = "00000000-0000-0000-0000-000000000001"


def _settings():
    return Settings(
        web_origin="http://localhost:5173",
        session_secret="test-secret",
    )


def _authenticated_client(app, settings):
    response = Response()
    issue_session(response, USER_ID, settings)
    client = TestClient(app)
    client.cookies.set(
        "ask_sql_session",
        response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1],
    )
    return client


def _profile(status="approved", role="user"):
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": role,
        "status": status,
    }


def _app_with_profile(profile):
    settings = _settings()
    app = create_app(settings)
    repository = Mock()
    repository.get_profile.return_value = profile
    app.dependency_overrides[get_user_repository] = lambda: repository

    @app.get("/profile")
    def profile_route(current=Depends(get_current_profile)):
        return current

    @app.get("/approved")
    def approved_route(current=Depends(require_approved_user)):
        return current

    @app.get("/admin")
    def admin_route(current=Depends(require_roles("admin"))):
        return current

    @app.get("/builder")
    def builder_route(current=Depends(require_roles("dev", "dba", "admin"))):
        return current

    return app, settings, repository


def test_authenticated_profile_is_reloaded_for_each_request():
    app, settings, repository = _app_with_profile(_profile())
    client = _authenticated_client(app, settings)

    first = client.get("/profile")
    second = client.get("/profile")

    assert first.status_code == 200
    assert second.status_code == 200
    assert repository.get_profile.call_count == 2
    assert repository.get_profile.call_args_list[0].args == (USER_ID,)
    assert repository.get_profile.call_args_list[1].args == (USER_ID,)


def test_missing_session_and_missing_profile_are_not_accepted():
    app, settings, _repository = _app_with_profile(None)
    client = TestClient(app)

    missing_session = client.get("/profile")
    assert missing_session.status_code == 401
    assert missing_session.json()["error"]["code"] == "auth_required"

    client = _authenticated_client(app, settings)
    missing_profile = client.get("/profile")
    assert missing_profile.status_code == 403
    assert missing_profile.json()["error"]["code"] == "account_not_approved"


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("pending", "Sua conta aguarda aprovação."),
        ("rejected", "Sua solicitação de acesso foi rejeitada."),
        ("disabled", "Sua conta está desativada."),
    ],
)
def test_non_approved_statuses_share_the_account_guard(status, message):
    app, settings, _repository = _app_with_profile(_profile(status=status))
    response = _authenticated_client(app, settings).get("/approved")

    assert response.status_code == 403
    assert response.json() == {
        "error": {"code": "account_not_approved", "message": message}
    }


def test_role_guard_allows_expected_roles_and_rejects_other_roles():
    user_app, user_settings, _repository = _app_with_profile(
        _profile(role="user")
    )
    user_client = _authenticated_client(user_app, user_settings)

    assert user_client.get("/admin").status_code == 403
    assert user_client.get("/builder").status_code == 403

    dba_app, dba_settings, _repository = _app_with_profile(_profile(role="dba"))
    assert _authenticated_client(dba_app, dba_settings).get(
        "/builder"
    ).status_code == 200

    admin_app, admin_settings, _repository = _app_with_profile(
        _profile(role="admin")
    )
    admin_client = _authenticated_client(admin_app, admin_settings)
    assert admin_client.get("/admin").status_code == 200


def test_repository_factories_reuse_the_lazy_database_adapter():
    get_db_adapter.cache_clear()
    get_user_repository.cache_clear()
    get_conversation_repository.cache_clear()
    get_query_history_repository.cache_clear()
    get_predefined_query_repository.cache_clear()

    database = get_db_adapter()

    assert isinstance(database, PostgresAdapter)
    assert get_user_repository().db is database
    assert isinstance(get_user_repository(), UserRepository)
    assert isinstance(get_conversation_repository(), ConversationRepository)
    assert isinstance(get_query_history_repository(), QueryHistoryRepository)
    assert isinstance(
        get_predefined_query_repository(),
        PredefinedQueryRepository,
    )
