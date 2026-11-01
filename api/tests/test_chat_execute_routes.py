from unittest.mock import Mock
from uuid import UUID

import pandas as pd
from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import get_chat_service, require_approved_user
from api.services.chat import ChatResult, ChatService, ChatServiceError

USER_ID = "00000000-0000-0000-0000-000000000001"
OTHER_USER_ID = "00000000-0000-0000-0000-000000000009"
CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000002")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000003")


def _profile():
    return {
        "id": USER_ID,
        "email": "user@example.com",
        "name": "User",
        "role": "user",
        "status": "approved",
    }


def _client(service):
    app = create_app(
        Settings(
            web_origin="http://localhost:5173",
            session_secret="test-secret",
        )
    )
    app.dependency_overrides[get_chat_service] = lambda: service
    app.dependency_overrides[require_approved_user] = _profile
    return TestClient(app)


def _payload(sql=None):
    payload = {
        "conversation_id": str(CONVERSATION_ID),
        "request_id": str(REQUEST_ID),
    }
    if sql is not None:
        payload["sql"] = sql
    return payload


def _stored_messages(sql="SELECT total FROM sales", metadata=None):
    return [
        {
            "request_id": REQUEST_ID,
            "role": "user",
            "content": "Show revenue",
        },
        {
            "request_id": REQUEST_ID,
            "role": "assistant",
            "content": "SQL gerado para revisão.",
            "sql": sql,
            "error": None,
            "metadata": metadata or {},
        },
    ]


class StoredConversationRepository:
    def __init__(self, messages, owner_id=USER_ID):
        self.messages = messages
        self.owner_id = owner_id
        self.updated = []

    def get_messages(self, user_id, _conversation_id):
        return self.messages if user_id == self.owner_id else []

    def update_assistant_message(
        self,
        _user_id,
        _conversation_id,
        _request_id,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        self.updated.append(
            {
                "content": content,
                "sql": sql,
                "error": error,
                "metadata": metadata or {},
            }
        )


def _service(repository, database):
    return ChatService(
        repository,
        Mock(),
        database,
    )


def test_execute_ignores_client_sql_and_returns_bounded_results_and_chart():
    repository = StoredConversationRepository(
        _stored_messages(
            metadata={"grafico": {"tipo": "bar", "eixo_x": "month"}}
        )
    )
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"month": "Jan", "total": 12}]
    )
    client = _client(_service(repository, database))

    response = client.post(
        "/api/chat/execute",
        json=_payload(sql="DELETE FROM sales"),
    )

    assert response.status_code == 200
    assert response.json()["result"] == {
        "columns": ["month", "total"],
        "rows": [{"month": "Jan", "total": 12}],
        "row_count": 1,
        "truncated": False,
    }
    assert response.json()["chart"] == {
        "tipo": "bar",
        "eixo_x": "month",
    }
    database.execute_read_only_query.assert_called_once_with(
        "SELECT total FROM sales",
        {},
    )


def test_execute_exposes_supporting_insights_alongside_primary_result():
    repository = StoredConversationRepository(
        _stored_messages(
            metadata={
                "supporting_queries": [
                    {
                        "key": "kpi",
                        "title": "Indicadores do período",
                        "sql": "SELECT 2",
                        "parameters": {},
                    }
                ]
            }
        )
    )
    database = Mock()
    database.execute_read_only_query.side_effect = [
        pd.DataFrame([{"total": 12}]),
        pd.DataFrame([{"revenue": 12}]),
    ]
    client = _client(_service(repository, database))

    response = client.post("/api/chat/execute", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["rows"] == [{"total": 12}]
    assert body["insights"][0]["key"] == "kpi"
    assert body["insights"][0]["result"]["rows"] == [{"revenue": 12}]


def test_missing_or_foreign_stored_query_is_rejected_before_adapter_call():
    database = Mock()
    client = _client(
        _service(StoredConversationRepository([]), database)
    )

    response = client.post("/api/chat/execute", json=_payload())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "stored_query_not_found"
    database.execute_read_only_query.assert_not_called()

    foreign_client = _client(
        _service(
            StoredConversationRepository(
                _stored_messages(),
                owner_id=OTHER_USER_ID,
            ),
            database,
        )
    )
    foreign_response = foreign_client.post(
        "/api/chat/execute",
        json=_payload(),
    )

    assert foreign_response.status_code == 404
    assert foreign_response.json()["error"]["code"] == "stored_query_not_found"
    database.execute_read_only_query.assert_not_called()


def test_delete_sql_is_rejected_before_adapter_call():
    repository = StoredConversationRepository(
        _stored_messages(sql="DELETE FROM sales")
    )
    database = Mock()
    client = _client(_service(repository, database))

    response = client.post("/api/chat/execute", json=_payload())

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "sql_not_read_only"
    database.execute_read_only_query.assert_not_called()


def test_database_failure_returns_retryable_error():
    repository = StoredConversationRepository(_stored_messages())
    database = Mock()
    database.execute_read_only_query.side_effect = ConnectionError("offline")
    client = _client(_service(repository, database))

    response = client.post("/api/chat/execute", json=_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert repository.updated[-1]["error"] == "database_unavailable"
    assert repository.updated[-1]["metadata"]["retryable"] is True
    assert repository.updated[-1]["metadata"]["retry_kind"] == "execute"


def test_retry_route_uses_authenticated_owner_and_request_id():
    service = Mock()
    service.retry_request.return_value = ChatResult(
        conversation_id=CONVERSATION_ID,
        request_id=REQUEST_ID,
        status="review",
        content="SQL gerado para revisão.",
        sql="SELECT 1",
    )
    client = _client(service)

    response = client.post(
        "/api/chat/retry",
        json={
            "conversation_id": str(CONVERSATION_ID),
            "request_id": str(REQUEST_ID),
        },
    )

    assert response.status_code == 200
    assert response.json()["sql"] == "SELECT 1"
    service.retry_request.assert_called_once_with(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )


def test_retry_errors_use_the_documented_error_envelope():
    service = Mock()
    service.retry_request.side_effect = ChatServiceError(
        422,
        "request_not_retryable",
        "This request cannot be retried.",
    )
    client = _client(service)

    response = client.post(
        "/api/chat/retry",
        json={
            "conversation_id": str(CONVERSATION_ID),
            "request_id": str(REQUEST_ID),
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "request_not_retryable",
            "message": "This request cannot be retried.",
        }
    }


def test_cancel_route_marks_the_authenticated_request():
    service = Mock()
    client = _client(service)

    response = client.post("/api/chat/cancel", json=_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "cancelled"}
    service.cancel_request.assert_called_once_with(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )


def test_cancel_route_rejects_an_unknown_request():
    database = Mock()
    client = _client(
        _service(StoredConversationRepository([]), database)
    )

    response = client.post("/api/chat/cancel", json=_payload())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "request_not_found"
