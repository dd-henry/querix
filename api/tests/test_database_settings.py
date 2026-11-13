from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import api.routes.database_settings as database_settings_route
from api.app import create_app
from api.config import Settings
from api.dependencies import (
    get_database_connection_repository,
    require_approved_user,
)

USER_ID = "00000000-0000-0000-0000-000000000001"


def _profile(role="admin"):
    return {
        "id": USER_ID,
        "email": "admin@example.com",
        "name": "Admin",
        "role": role,
        "status": "approved",
    }


def _client(repository, role="admin"):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_database_connection_repository] = (
        lambda: repository
    )
    app.dependency_overrides[require_approved_user] = lambda: _profile(role)
    return TestClient(app)


def test_admin_can_read_status_without_receiving_a_secret():
    repository = Mock()
    repository.get_status.return_value = {
        "configured": True,
        "updated_at": "2026-11-12T12:00:00+00:00",
    }

    response = _client(repository).get("/api/settings/database")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "updated_at": "2026-11-12T12:00:00+00:00",
    }
    assert "connection_string" not in response.json()


def test_admin_tests_before_saving_and_gets_status(monkeypatch):
    repository = Mock()
    repository.get_status.return_value = {
        "configured": True,
        "updated_at": "2026-11-12T12:00:00+00:00",
    }
    target = Mock()
    target.test_connection.return_value = True
    target_class = Mock(return_value=target)
    target_class.validate_database_url = Mock(
        return_value="postgresql://target.example/analytics"
    )
    monkeypatch.setattr(database_settings_route, "PostgresAdapter", target_class)

    response = _client(repository).put(
        "/api/settings/database",
        json={"connection_string": "postgresql://user:pass@target.example/analytics"},
    )

    assert response.status_code == 200
    assert response.json()["configured"] is True
    target.test_connection.assert_called_once_with()
    repository.save.assert_called_once_with(
        "postgresql://target.example/analytics",
        USER_ID,
    )


def test_invalid_connection_string_is_rejected_before_target_test(monkeypatch):
    repository = Mock()
    target_class = Mock()
    target_class.validate_database_url.side_effect = ValueError("invalid")
    monkeypatch.setattr(database_settings_route, "PostgresAdapter", target_class)

    response = _client(repository).put(
        "/api/settings/database",
        json={"connection_string": "mysql://db.example/analytics"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    target_class.assert_not_called()
    repository.save.assert_not_called()


def test_failed_target_test_does_not_replace_previous_connection(monkeypatch):
    repository = Mock()
    target = Mock()
    target.test_connection.return_value = False
    target_class = Mock(return_value=target)
    target_class.validate_database_url = Mock(
        return_value="postgresql://target.example/analytics"
    )
    monkeypatch.setattr(database_settings_route, "PostgresAdapter", target_class)

    response = _client(repository).put(
        "/api/settings/database",
        json={"connection_string": "postgresql://user:pass@target.example/analytics"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_connection_failed"
    repository.save.assert_not_called()


@pytest.mark.parametrize("method", ["get", "put"])
def test_non_admin_cannot_read_or_write_target_connection(method):
    repository = Mock()
    client = _client(repository, role="user")
    kwargs = (
        {"json": {"connection_string": "postgresql://target.example/analytics"}}
        if method == "put"
        else {}
    )

    response = getattr(client, method)("/api/settings/database", **kwargs)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    repository.get_status.assert_not_called()
    repository.save.assert_not_called()
