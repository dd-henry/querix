from unittest.mock import Mock
from uuid import UUID

from fastapi.testclient import TestClient

from api.app import create_app
from api.config import Settings
from api.dependencies import (
    get_chat_service,
    require_approved_user,
)
from api.services.chat import ChatResult, ChatServiceError

USER_ID = "00000000-0000-0000-0000-000000000001"
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


def _result(**overrides):
    values = {
        "conversation_id": CONVERSATION_ID,
        "request_id": REQUEST_ID,
        "status": "review",
        "content": "SQL gerado para revisão.",
        "sql": "SELECT 1",
    }
    values.update(overrides)
    return ChatResult(**values)


def _payload(prompt="Show revenue", review_mode=True):
    return {
        "conversation_id": str(CONVERSATION_ID),
        "request_id": str(REQUEST_ID),
        "prompt": prompt,
        "review_mode": review_mode,
    }


def test_review_mode_returns_stored_sql_without_result_or_execution():
    service = Mock()
    service.translate_prompt.return_value = _result()
    client = _client(service)

    response = client.post("/api/chat/translate", json=_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "review"
    assert response.json()["sql"] == "SELECT 1"
    assert response.json()["result"] is None
    service.translate_prompt.assert_called_once_with(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "Show revenue",
        review_mode=True,
    )
    service.execute_stored_query.assert_not_called()


def test_review_mode_off_executes_the_stored_request():
    service = Mock()
    service.translate_prompt.return_value = _result(status="translated")
    service.execute_stored_query.return_value = _result(
        status="executed",
        content="Aqui estão os resultados da consulta:",
        result={
            "columns": ["total"],
            "rows": [{"total": 12}],
            "row_count": 1,
            "truncated": False,
        },
    )
    client = _client(service)

    response = client.post(
        "/api/chat/translate",
        json=_payload(review_mode=False),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "executed"
    assert response.json()["result"]["rows"] == [{"total": 12}]
    service.execute_stored_query.assert_called_once_with(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )


def test_warning_response_has_no_execution_result():
    service = Mock()
    service.translate_prompt.return_value = _result(
        status="warning",
        content="AVISO: Não foi possível identificar a tabela.",
        sql=None,
    )
    client = _client(service)

    response = client.post(
        "/api/chat/translate",
        json=_payload(review_mode=False),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "warning"
    assert response.json()["content"].startswith("AVISO:")
    assert response.json()["result"] is None
    service.execute_stored_query.assert_not_called()


def test_translator_failure_uses_error_envelope():
    service = Mock()
    service.translate_prompt.side_effect = ChatServiceError(
        502,
        "translator_unavailable",
        "The translator service is unavailable.",
    )
    client = _client(service)

    response = client.post("/api/chat/translate", json=_payload())

    assert response.status_code == 502
    assert response.json() == {
        "error": {
            "code": "translator_unavailable",
            "message": "The translator service is unavailable.",
        }
    }


def test_empty_and_oversized_prompts_are_rejected_without_service_call():
    service = Mock()
    client = _client(service)

    empty = client.post(
        "/api/chat/translate",
        json=_payload(prompt="   "),
    )
    oversized = client.post(
        "/api/chat/translate",
        json=_payload(prompt="x" * 2001),
    )

    assert empty.status_code == oversized.status_code == 422
    assert empty.json()["error"]["code"] == "validation_error"
    assert oversized.json()["error"]["code"] == "validation_error"
    service.translate_prompt.assert_not_called()


def test_double_submit_keeps_the_same_request_id_for_idempotent_service():
    service = Mock()
    service.translate_prompt.return_value = _result()
    client = _client(service)

    first = client.post("/api/chat/translate", json=_payload())
    second = client.post("/api/chat/translate", json=_payload())

    assert first.status_code == second.status_code == 200
    assert service.translate_prompt.call_args_list == [
        (
            (USER_ID, CONVERSATION_ID, REQUEST_ID, "Show revenue"),
            {"review_mode": True},
        ),
        (
            (USER_ID, CONVERSATION_ID, REQUEST_ID, "Show revenue"),
            {"review_mode": True},
        ),
    ]
