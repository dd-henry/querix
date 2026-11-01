from unittest.mock import Mock

import api.routes.sync as sync_route
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import get_current_profile, require_approved_user

USER_ID = "00000000-0000-0000-0000-000000000001"


def _profile(status="approved"):
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": status,
    }


def _client(status="approved"):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    if status == "approved":
        app.dependency_overrides[require_approved_user] = lambda: _profile(
            status
        )
    else:
        app.dependency_overrides[get_current_profile] = lambda: _profile(
            status
        )
    return TestClient(app)


def test_approved_user_can_sync_without_receiving_schema_contents(
    monkeypatch,
):
    translator = Mock(return_value=object())
    catalog = Mock()
    monkeypatch.setattr(sync_route, "get_translator", translator)
    monkeypatch.setattr(
        sync_route,
        "get_predefined_query_repository",
        catalog,
    )
    client = _client()

    response = client.post("/api/schema/sync")

    assert response.status_code == 200
    assert response.json() == {"status": "synchronized"}
    assert "schema" not in response.json()
    translator.cache_clear.assert_called_once_with()
    catalog.cache_clear.assert_called_once_with()
    translator.assert_called_once()


def test_non_approved_user_cannot_sync(monkeypatch):
    translator = Mock()
    catalog = Mock()
    monkeypatch.setattr(sync_route, "get_translator", translator)
    monkeypatch.setattr(
        sync_route,
        "get_predefined_query_repository",
        catalog,
    )
    client = _client(status="pending")

    response = client.post("/api/schema/sync")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_not_approved"
    assert translator.call_count == 0
    translator.cache_clear.assert_not_called()
    catalog.cache_clear.assert_not_called()


def test_sync_failure_returns_503_without_success_response(monkeypatch):
    translator = Mock(side_effect=RuntimeError("database offline"))
    catalog = Mock()
    monkeypatch.setattr(sync_route, "get_translator", translator)
    monkeypatch.setattr(
        sync_route,
        "get_predefined_query_repository",
        catalog,
    )
    client = _client()

    response = client.post("/api/schema/sync")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "schema_sync_failed",
            "message": "The database schema could not be synchronized.",
        }
    }
    assert response.json().get("status") != "synchronized"
    translator.cache_clear.assert_called_once_with()
    catalog.cache_clear.assert_called_once_with()
