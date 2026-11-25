from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.routes.auth import get_auth_service
from api.auth.service import AuthServiceError
from api.dependencies import get_user_repository, require_approved_user
from database.users import UserRepository

USER_ID = "00000000-0000-0000-0000-000000000001"
TARGET_ID = "00000000-0000-0000-0000-000000000002"
CREATED_AT = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)


def _profile(role="admin"):
    return {
        "id": USER_ID,
        "email": "admin@example.com",
        "name": "Admin",
        "role": role,
        "status": "approved",
    }


def _user():
    return {
        "id": TARGET_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": "pending",
        "created_at": CREATED_AT,
        "approved_at": None,
        "disabled_at": None,
    }


def _client(repository, role="admin", auth=None):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_user_repository] = lambda: repository
    app.dependency_overrides[require_approved_user] = lambda: _profile(role)
    if auth is not None:
        app.dependency_overrides[get_auth_service] = lambda: auth
    return TestClient(app)


def test_admin_can_list_profiles_and_change_status_and_role():
    repository = Mock()
    repository.list_profiles.return_value = [_user()]
    client = _client(repository)

    listed = client.get("/api/admin/users")
    status = client.patch(
        f"/api/admin/users/{TARGET_ID}/status",
        json={"status": "approved"},
    )
    role = client.patch(
        f"/api/admin/users/{TARGET_ID}/role",
        json={"role": "dev"},
    )

    assert listed.status_code == 200
    assert listed.json()["profiles"][0]["email"] == "user@example.com"
    assert status.status_code == 200
    assert status.json() == {"id": TARGET_ID, "status": "approved"}
    assert role.status_code == 200
    assert role.json() == {"id": TARGET_ID, "role": "dev"}
    repository.list_profiles.assert_called_once_with()
    repository.set_status.assert_called_once_with(
        UUID(TARGET_ID),
        "approved",
        USER_ID,
    )
    repository.set_role.assert_called_once_with(
        UUID(TARGET_ID),
        "dev",
        USER_ID,
    )


def test_admin_lists_profiles_with_mixed_nullable_datetimes():
    database = Mock()
    database.execute_query.return_value = pd.DataFrame(
        [
            {**_user(), "approved_at": CREATED_AT, "disabled_at": None},
            {
                **_user(),
                "id": USER_ID,
                "approved_at": None,
                "disabled_at": CREATED_AT,
            },
        ]
    )
    client = _client(UserRepository(database))

    response = client.get("/api/admin/users")

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert profiles[0]["approved_at"] is not None
    assert profiles[0]["disabled_at"] is None
    assert profiles[1]["approved_at"] is None
    assert profiles[1]["disabled_at"] is not None


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/admin/users", None),
        (
            "patch",
            f"/api/admin/users/{TARGET_ID}/status",
            {"status": "approved"},
        ),
        (
            "patch",
            f"/api/admin/users/{TARGET_ID}/role",
            {"role": "dev"},
        ),
    ],
)
def test_non_admin_cannot_call_any_admin_route(method, path, payload):
    repository = Mock()
    client = _client(repository, role="user")

    if payload is None:
        response = getattr(client, method)(path)
    else:
        response = getattr(client, method)(path, json=payload)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    repository.list_profiles.assert_not_called()
    repository.set_status.assert_not_called()
    repository.set_role.assert_not_called()


@pytest.mark.parametrize(
    ("path", "payload", "method_name"),
    [
        (
            f"/api/admin/users/{TARGET_ID}/status",
            {"status": "pending"},
            "set_status",
        ),
        (
            f"/api/admin/users/{TARGET_ID}/role",
            {"role": "dba"},
            "set_role",
        ),
    ],
)
def test_invalid_admin_values_are_rejected_before_repository(
    path,
    payload,
    method_name,
):
    repository = Mock()
    client = _client(repository)

    response = client.patch(path, json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    getattr(repository, method_name).assert_not_called()


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            f"/api/admin/users/{TARGET_ID}/status",
            {"status": "disabled"},
        ),
        (
            f"/api/admin/users/{TARGET_ID}/role",
            {"role": "dev"},
        ),
    ],
)
def test_last_admin_conflict_returns_409_without_database_mutation(
    path,
    payload,
):
    database = Mock()
    database.execute_query.return_value = pd.DataFrame([{"admin_count": 1}])
    repository = UserRepository(database)
    client = _client(repository)

    response = client.patch(path, json=payload)

    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "last_admin_conflict",
        "message": "The last approved admin cannot be removed.",
    }
    assert database.execute_command.call_count == 0


def test_admin_reset_password_returns_temporary_password_and_flags_user():
    repository = Mock()
    repository.get_profile.return_value = _user()
    auth = Mock()
    client = _client(repository, auth=auth)

    response = client.post(f"/api/admin/users/{TARGET_ID}/reset-password")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == TARGET_ID
    assert len(body["temporary_password"]) >= 8
    auth.set_password.assert_called_once_with(TARGET_ID, body["temporary_password"])
    repository.set_must_change_password.assert_called_once_with(
        UUID(TARGET_ID),
        True,
    )


def test_admin_reset_password_reverts_flag_when_supabase_fails():
    repository = Mock()
    repository.get_profile.return_value = _user()
    auth = Mock()
    auth.set_password.side_effect = AuthServiceError(
        "auth_not_configured",
        "Configure SUPABASE_SERVICE_ROLE_KEY to reset passwords.",
    )
    client = _client(repository, auth=auth)

    response = client.post(f"/api/admin/users/{TARGET_ID}/reset-password")

    assert response.status_code == 503
    assert repository.set_must_change_password.call_args_list[-1].args == (
        UUID(TARGET_ID),
        False,
    )


def test_admin_cannot_reset_own_password_and_non_admin_is_forbidden():
    repository = Mock()
    auth = Mock()
    own = _client(repository, auth=auth).post(
        f"/api/admin/users/{USER_ID}/reset-password"
    )
    forbidden = _client(repository, role="user", auth=auth).post(
        f"/api/admin/users/{TARGET_ID}/reset-password"
    )

    assert own.status_code == 422
    assert forbidden.status_code == 403
    auth.set_password.assert_not_called()
