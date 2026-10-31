from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import get_conversation_repository, require_approved_user
from database.conversations import ConversationRepository

USER_ID = "00000000-0000-0000-0000-000000000001"
SESSION_ID = "00000000-0000-0000-0000-000000000002"
REQUEST_ID = "00000000-0000-0000-0000-000000000003"
CREATED_AT = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)


def _profile():
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": "approved",
    }


def _session():
    return {
        "id": SESSION_ID,
        "title": "Revenue",
        "is_favorite": False,
        "created_at": CREATED_AT,
        "last_activity": CREATED_AT,
    }


def _messages():
    return [
        {
            "id": 1,
            "request_id": REQUEST_ID,
            "role": "user",
            "content": "Show revenue",
            "sql": None,
            "error": None,
            "metadata": {},
            "created_at": CREATED_AT,
        },
        {
            "id": 2,
            "request_id": REQUEST_ID,
            "role": "assistant",
            "content": "Here is the result.",
            "sql": "SELECT 1",
            "error": None,
            "metadata": {
                "retryable": True,
                "retry_kind": "execute",
            },
            "created_at": CREATED_AT,
        },
    ]


def _client(repository):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_conversation_repository] = lambda: repository
    app.dependency_overrides[require_approved_user] = _profile
    return TestClient(app)


def test_get_conversation_restores_ordered_messages_without_executing_sql():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([_session()], 0)
    repository.get_messages.return_value = _messages()
    client = _client(repository)

    response = client.get(f"/api/conversations/{SESSION_ID}")

    assert response.status_code == 200
    assert [message["role"] for message in response.json()["messages"]] == [
        "user",
        "assistant",
    ]
    assert response.json()["messages"][1]["sql"] == "SELECT 1"
    repository.get_messages.assert_called_once_with(
        USER_ID,
        UUID(SESSION_ID),
    )
    repository.set_favorite.assert_not_called()
    repository.delete.assert_not_called()


def test_foreign_or_unknown_conversation_returns_generic_not_found():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([], 0)
    client = _client(repository)

    response = client.get(f"/api/conversations/{SESSION_ID}")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Conversation not found.",
        }
    }
    assert SESSION_ID not in response.text


def test_favorite_and_unfavorite_are_owner_scoped():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([_session()], 0)
    client = _client(repository)

    favorite = client.patch(
        f"/api/conversations/{SESSION_ID}",
        json={"is_favorite": True},
    )
    unfavorite = client.patch(
        f"/api/conversations/{SESSION_ID}",
        json={"is_favorite": False},
    )

    assert favorite.status_code == unfavorite.status_code == 200
    assert favorite.json()["is_favorite"] is True
    assert unfavorite.json()["is_favorite"] is False
    assert repository.set_favorite.call_args_list == [
        ((USER_ID, UUID(SESSION_ID), True),),
        ((USER_ID, UUID(SESSION_ID), False),),
    ]


def test_delete_cancel_is_a_no_op_and_confirmation_deletes_owned_session():
    repository = Mock()
    repository.list_sessions_with_expired_count.return_value = ([_session()], 0)
    client = _client(repository)

    cancelled = client.delete(f"/api/conversations/{SESSION_ID}")
    confirmed = client.delete(
        f"/api/conversations/{SESSION_ID}?confirm=true",
    )

    assert cancelled.status_code == confirmed.status_code == 204
    repository.delete.assert_called_once_with(USER_ID, UUID(SESSION_ID))


def test_context_limit_is_preserved_by_the_repository_contract():
    repository = ConversationRepository(Mock())

    try:
        repository.get_context(USER_ID, SESSION_ID, limit=7)
    except ValueError as exc:
        assert "six" in str(exc)
    else:
        raise AssertionError("The repository must enforce the six-turn limit.")
