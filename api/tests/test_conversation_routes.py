from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import (
    get_conversation_repository,
    require_approved_user,
)

USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000009"
SESSION_ID = "00000000-0000-0000-0000-000000000002"
REQUEST_ID = "00000000-0000-0000-0000-000000000003"


def _profile(user_id=USER_ID):
    return {
        "id": user_id,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": "approved",
    }


def _settings():
    return Settings(
        web_origin="http://localhost:5173",
        session_secret="test-secret",
    )


def _client(repository, profile=None):
    app = create_app(_settings())
    app.dependency_overrides[get_conversation_repository] = lambda: repository
    app.dependency_overrides[require_approved_user] = lambda: (
        profile or _profile()
    )
    return TestClient(app)


def _session(session_id, title, activity, favorite=False):
    return {
        "id": session_id,
        "title": title,
        "is_favorite": favorite,
        "created_at": activity,
        "last_activity": activity,
    }


class IdempotentRepository:
    def __init__(self):
        self.created = []

    def create_with_user_message(
        self,
        user_id,
        session_id,
        request_id,
        prompt,
    ):
        key = (str(session_id), str(request_id))
        if key not in {(item[1], item[2]) for item in self.created}:
            self.created.append((str(user_id), *key, prompt))


def test_list_conversations_is_owner_scoped_and_groups_by_timezone():
    repository = Mock()
    now = datetime.now(timezone.utc)
    repository.list_sessions_with_expired_count.return_value = (
        [
            _session(SESSION_ID, "Today", now),
            _session(
                "00000000-0000-0000-0000-000000000004",
                "Older",
                now - timedelta(days=31),
                favorite=True,
            ),
        ],
        1,
    )
    client = _client(repository)

    response = client.get("/api/conversations?timezone=UTC")

    assert response.status_code == 200
    payload = response.json()
    assert [group["key"] for group in payload["groups"]] == [
        "today",
        "yesterday",
        "last_7_days",
        "last_30_days",
        "older",
    ]
    assert payload["groups"][0]["conversations"][0]["title"] == "Today"
    assert payload["groups"][-1]["conversations"][0]["is_favorite"] is True
    assert payload["expired_count"] == 1
    repository.list_sessions_with_expired_count.assert_called_once_with(USER_ID)


def test_list_conversations_rejects_an_unknown_timezone():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([], 0)
    client = _client(repository)

    response = client.get("/api/conversations?timezone=Unknown/Zone")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Timezone is invalid.",
        }
    }


def test_create_conversation_trims_prompt_and_keeps_owner_scope():
    repository = Mock()
    client = _client(repository)

    response = client.post(
        "/api/conversations",
        json={
            "conversation_id": SESSION_ID,
            "request_id": REQUEST_ID,
            "prompt": "  Quantos clientes?  ",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "conversation_id": SESSION_ID,
        "request_id": REQUEST_ID,
    }
    repository.create_with_user_message.assert_called_once_with(
        USER_ID,
        UUID(SESSION_ID),
        UUID(REQUEST_ID),
        "Quantos clientes?",
    )


def test_repeated_request_id_delegates_to_idempotent_repository_contract():
    repository = IdempotentRepository()
    client = _client(repository)
    payload = {
        "conversation_id": SESSION_ID,
        "request_id": REQUEST_ID,
        "prompt": "Quantos clientes?",
    }

    first = client.post("/api/conversations", json=payload)
    second = client.post("/api/conversations", json=payload)

    assert first.status_code == second.status_code == 201
    assert repository.created == [
        (USER_ID, SESSION_ID, REQUEST_ID, "Quantos clientes?")
    ]


def test_empty_prompt_never_reaches_repository():
    repository = Mock()
    client = _client(repository)

    response = client.post(
        "/api/conversations",
        json={
            "conversation_id": SESSION_ID,
            "request_id": REQUEST_ID,
            "prompt": "   ",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    repository.create_with_user_message.assert_not_called()


def test_other_owner_is_used_for_a_separate_authenticated_request():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([], 0)
    client = _client(repository, _profile(OTHER_USER_ID))

    response = client.get("/api/conversations")

    assert response.status_code == 200
    repository.list_sessions_with_expired_count.assert_called_once_with(
        OTHER_USER_ID
    )
