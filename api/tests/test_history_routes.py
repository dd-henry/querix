from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pandas as pd
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import (
    get_chat_service,
    get_query_history_repository,
    require_approved_user,
)
from api.services.chat import ChatService

USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000009"
CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000002")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000003")
CREATED_AT = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)


def _profile():
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": "approved",
    }


def _record(history_id=41, owner_id=USER_ID, is_pinned=False):
    return {
        "id": history_id,
        "owner_id": owner_id,
        "prompt": "Show revenue",
        "sql": "SELECT total FROM sales",
        "parameters": {},
        "source": "chat",
        "session_id": None,
        "is_pinned": is_pinned,
        "created_at": CREATED_AT,
    }


class MemoryHistoryRepository:
    def __init__(self, records):
        self.records = {record["id"]: record for record in records}
        self.list_calls = []
        self.pin_calls = []
        self.delete_calls = []
        self.record_calls = []

    def list(self, user_id, limit=20):
        self.list_calls.append((user_id, limit))
        return [
            {
                key: value
                for key, value in record.items()
                if key != "owner_id"
            }
            for record in self.records.values()
            if record["owner_id"] == user_id
        ][:limit]

    def get(self, user_id, history_id):
        record = self.records.get(history_id)
        if record is None or record["owner_id"] != user_id:
            return None
        return {
            key: value
            for key, value in record.items()
            if key != "owner_id"
        }

    def set_pinned(self, user_id, history_id, pinned):
        self.pin_calls.append((user_id, history_id, pinned))
        self.records[history_id]["is_pinned"] = pinned

    def delete(self, user_id, history_id):
        self.delete_calls.append((user_id, history_id))
        self.records.pop(history_id, None)

    def record(
        self,
        user_id,
        prompt,
        sql,
        source="chat",
        parameters=None,
        session_id=None,
    ):
        self.record_calls.append(
            (user_id, prompt, sql, source, parameters, session_id)
        )


class MemoryConversationRepository:
    def __init__(self):
        self.messages = []
        self.updated = []

    def get_messages(self, _user_id, _conversation_id):
        return self.messages

    def create_with_user_message(
        self,
        _user_id,
        _conversation_id,
        request_id,
        prompt,
    ):
        self.messages.append(
            {
                "request_id": request_id,
                "role": "user",
                "content": prompt,
            }
        )

    def append_message(
        self,
        _user_id,
        _conversation_id,
        request_id,
        role,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        self.messages.append(
            {
                "request_id": request_id,
                "role": role,
                "content": content,
                "sql": sql,
                "error": error,
                "metadata": metadata or {},
            }
        )

    def update_assistant_message(
        self,
        _user_id,
        _conversation_id,
        request_id,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        self.updated.append(
            {
                "request_id": request_id,
                "content": content,
                "sql": sql,
                "error": error,
                "metadata": metadata or {},
            }
        )

    def get_context(self, *_args, **_kwargs):
        return []


def _client(history, service=None):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_query_history_repository] = lambda: history
    app.dependency_overrides[require_approved_user] = _profile
    if service is not None:
        app.dependency_overrides[get_chat_service] = lambda: service
    return TestClient(app)


def _rerun_payload():
    return {
        "conversation_id": str(CONVERSATION_ID),
        "request_id": str(REQUEST_ID),
    }


def test_history_is_limited_to_twenty_and_owner_scoped():
    history = MemoryHistoryRepository(
        [
            _record(41, is_pinned=True),
            _record(42, is_pinned=False),
            _record(43, owner_id=OTHER_USER_ID),
        ]
    )
    client = _client(history)

    response = client.get("/api/history")

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [41, 42]
    assert response.json()["records"][0]["is_pinned"] is True
    assert history.list_calls == [(USER_ID, 20)]


def test_pin_unpin_and_delete_are_owner_scoped():
    history = MemoryHistoryRepository([_record()])
    client = _client(history)

    pinned = client.patch(
        "/api/history/41",
        json={"is_pinned": True},
    )
    unpinned = client.patch(
        "/api/history/41",
        json={"is_pinned": False},
    )
    deleted = client.delete("/api/history/41")

    assert pinned.status_code == unpinned.status_code == deleted.status_code == 200
    assert pinned.json()["is_pinned"] is True
    assert unpinned.json()["is_pinned"] is False
    assert history.pin_calls == [
        (USER_ID, 41, True),
        (USER_ID, 41, False),
    ]
    assert history.delete_calls == [(USER_ID, 41)]


def test_foreign_history_mutation_returns_404_without_mutation():
    history = MemoryHistoryRepository([_record(owner_id=OTHER_USER_ID)])
    client = _client(history)

    response = client.patch(
        "/api/history/41",
        json={"is_pinned": True},
    )

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "not_found",
        "message": "History record not found.",
    }
    assert history.pin_calls == []


def test_rerun_uses_stored_sql_in_the_active_conversation():
    history = MemoryHistoryRepository([_record()])
    conversations = MemoryConversationRepository()
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"total": 12}]
    )
    service = ChatService(
        conversations,
        Mock(),
        database,
        query_history_repository=history,
    )
    client = _client(history, service)

    response = client.post(
        "/api/history/41/rerun",
        json=_rerun_payload(),
    )

    assert response.status_code == 200
    assert response.json()["result"]["rows"] == [{"total": 12}]
    database.execute_read_only_query.assert_called_once_with(
        "SELECT total FROM sales",
        {},
    )
    assert conversations.messages[0]["content"] == "Show revenue"
    assert conversations.messages[1]["sql"] == "SELECT total FROM sales"


def test_foreign_history_rerun_returns_404_before_database_call():
    history = MemoryHistoryRepository([_record(owner_id=OTHER_USER_ID)])
    database = Mock()
    service = ChatService(
        MemoryConversationRepository(),
        Mock(),
        database,
        query_history_repository=history,
    )
    client = _client(history, service)

    response = client.post(
        "/api/history/41/rerun",
        json=_rerun_payload(),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "history_not_found"
    database.execute_read_only_query.assert_not_called()


def test_history_rerun_database_failure_is_retryable():
    history = MemoryHistoryRepository([_record()])
    conversations = MemoryConversationRepository()
    database = Mock()
    database.execute_read_only_query.side_effect = ConnectionError("offline")
    service = ChatService(
        conversations,
        Mock(),
        database,
        query_history_repository=history,
    )
    client = _client(history, service)

    response = client.post(
        "/api/history/41/rerun",
        json=_rerun_payload(),
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert conversations.updated[-1]["error"] == "database_unavailable"
    assert conversations.updated[-1]["metadata"]["retryable"] is True
