from datetime import datetime, timezone
from unittest.mock import Mock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import (
    get_db_adapter,
    get_predefined_query_repository,
    require_approved_user,
)

USER_ID = "00000000-0000-0000-0000-000000000001"
CREATED_AT = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)


def _profile(role="user"):
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": role,
        "status": "approved",
    }


def _query(query_id=7):
    return {
        "id": query_id,
        "name": "Revenue",
        "description": "Revenue by month",
        "sql": "SELECT total FROM sales WHERE status = :status",
        "tags": ["sales"],
        "author": "dba@example.com",
        "parameters": [
            {"name": "status", "label": "Status", "required": True}
        ],
        "updated_at": CREATED_AT,
        "is_favorite": True,
    }


def _payload(sql=None):
    return {
        "name": "Revenue",
        "description": "Revenue by month",
        "sql": sql or "SELECT total FROM sales",
        "tags": [" sales ", ""],
        "parameters": [],
    }


def _client(repository, database=None, role="user"):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_predefined_query_repository] = (
        lambda: repository
    )
    app.dependency_overrides[require_approved_user] = lambda: _profile(role)
    if database is not None:
        app.dependency_overrides[get_db_adapter] = lambda: database
    return TestClient(app)


def test_search_returns_owner_favorite_state_and_trimmed_search():
    repository = Mock()
    repository.list.return_value = [_query()]
    client = _client(repository)

    response = client.get("/api/predefined-queries?search=%20revenue%20")

    assert response.status_code == 200
    assert response.json()["queries"][0]["is_favorite"] is True
    assert response.json()["queries"][0]["parameters"][0]["name"] == "status"
    repository.list.assert_called_once_with(USER_ID, search="revenue")


def test_favorite_mutation_is_authenticated_user_scoped():
    repository = Mock()
    repository.get.return_value = _query()
    client = _client(repository)

    response = client.patch(
        "/api/predefined-queries/7/favorite",
        json={"is_favorite": False},
    )

    assert response.status_code == 200
    assert response.json() == {"id": 7, "is_favorite": False}
    repository.toggle_favorite.assert_called_once_with(USER_ID, 7, False)


def test_execute_binds_parameters_and_returns_bounded_results():
    repository = Mock()
    repository.get.return_value = _query()
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"total": 12}]
    )
    client = _client(repository, database)

    response = client.post(
        "/api/predefined-queries/7/execute",
        json={"parameters": {"status": "paid"}},
    )

    assert response.status_code == 200
    assert response.json()["result"]["rows"] == [{"total": 12}]
    database.execute_read_only_query.assert_called_once_with(
        "SELECT total FROM sales WHERE status = :status",
        {"status": "paid"},
    )


def test_missing_required_parameter_returns_422_naming_parameter():
    repository = Mock()
    repository.get.return_value = _query()
    database = Mock()
    client = _client(repository, database)

    response = client.post(
        "/api/predefined-queries/7/execute",
        json={"parameters": {}},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "missing_parameter",
            "message": "Missing required parameter: status.",
        }
    }
    database.execute_read_only_query.assert_not_called()


@pytest.mark.parametrize("role", ["dev", "dba", "admin"])
def test_builder_roles_can_create_update_and_delete(role):
    repository = Mock()
    client = _client(repository, role=role)

    created = client.post(
        "/api/predefined-queries",
        json=_payload(),
    )
    updated = client.patch(
        "/api/predefined-queries/7",
        json=_payload(),
    )
    deleted = client.delete("/api/predefined-queries/7")

    assert created.status_code == 201
    assert created.json() == {"status": "created"}
    assert updated.status_code == 200
    assert updated.json() == {"status": "updated"}
    assert deleted.status_code == 200
    assert deleted.json() == {"status": "deleted"}
    repository.create.assert_called_once_with(
        "Revenue",
        "Revenue by month",
        "SELECT total FROM sales",
        ["sales"],
        "user@example.com",
        [],
    )
    repository.update.assert_called_once_with(
        7,
        "Revenue",
        "Revenue by month",
        "SELECT total FROM sales",
        ["sales"],
        [],
    )
    repository.delete.assert_called_once_with(7)


def test_regular_user_cannot_create_shared_query():
    repository = Mock()
    client = _client(repository, role="user")

    response = client.post(
        "/api/predefined-queries",
        json=_payload(),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    repository.create.assert_not_called()


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/predefined-queries", _payload()),
        ("patch", "/api/predefined-queries/7", _payload()),
        ("delete", "/api/predefined-queries/7", None),
    ],
)
def test_regular_user_cannot_use_any_catalog_mutation(
    method,
    path,
    payload,
):
    repository = Mock()
    client = _client(repository, role="user")

    if payload is None:
        response = getattr(client, method)(path)
    else:
        response = getattr(client, method)(path, json=payload)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
    repository.create.assert_not_called()
    repository.update.assert_not_called()
    repository.delete.assert_not_called()


@pytest.mark.parametrize("method", ["post", "patch"])
def test_invalid_sql_is_rejected_before_create_or_update(method):
    repository = Mock()
    client = _client(repository, role="admin")

    response = getattr(client, method)(
        "/api/predefined-queries"
        if method == "post"
        else "/api/predefined-queries/7",
        json=_payload(sql="DELETE FROM sales"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sql_not_read_only"
    repository.create.assert_not_called()
    repository.update.assert_not_called()


def test_execute_rejects_non_read_only_stored_sql():
    repository = Mock()
    stored_query = _query()
    stored_query["sql"] = "DELETE FROM sales"
    repository.get.return_value = stored_query
    database = Mock()
    client = _client(repository, database)

    response = client.post(
        "/api/predefined-queries/7/execute",
        json={"parameters": {"status": "paid"}},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sql_not_read_only"
    database.execute_read_only_query.assert_not_called()
