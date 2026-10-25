import json
from unittest.mock import MagicMock

import pandas as pd
import pytest

from database.conversations import ConversationRepository


@pytest.fixture
def db():
    fake = MagicMock()
    fake.execute_command.return_value = 0
    return fake


def test_initialize_creates_owned_session_and_message_tables(db):
    ConversationRepository(db).initialize()

    statements = [call.args[0] for call in db.execute_command.call_args_list]
    assert any("ask_sql_conversation_sessions" in sql for sql in statements)
    assert any("ask_sql_conversation_messages" in sql for sql in statements)
    assert any("UNIQUE (session_id, request_id, role)" in sql for sql in statements)


def test_create_with_user_message_is_atomic_and_keeps_full_prompt(db):
    repository = ConversationRepository(db)

    repository.create_with_user_message(
        "user-id", "session-id", "request-id", "  Quantos clientes?  "
    )

    sql, parameters = db.execute_command.call_args.args
    assert "WITH created AS" in sql
    assert "INSERT INTO ask_sql_conversation_messages" in sql
    assert parameters == {
        "session_id": "session-id",
        "user_id": "user-id",
        "request_id": "request-id",
        "title": "Quantos clientes?",
        "prompt": "Quantos clientes?",
    }


def test_create_with_user_message_rejects_empty_prompt(db):
    with pytest.raises(ValueError, match="prompt"):
        ConversationRepository(db).create_with_user_message(
            "user-id", "session-id", "request-id", "  "
        )

    db.execute_command.assert_not_called()


def test_append_message_is_owner_scoped_and_idempotent(db):
    repository = ConversationRepository(db)

    repository.append_message(
        "user-id",
        "session-id",
        "request-id",
        "assistant",
        "Resultado pronto",
        sql="SELECT 1",
        metadata={"chart": None},
    )

    sql, parameters = db.execute_command.call_args.args
    assert "ON CONFLICT (session_id, request_id, role) DO NOTHING" in sql
    assert "s.user_id = CAST(:user_id AS uuid)" in sql
    assert parameters["metadata"] == json.dumps({"chart": None})


def test_append_message_rejects_invalid_role(db):
    with pytest.raises(ValueError, match="role"):
        ConversationRepository(db).append_message(
            "user-id", "session-id", "request-id", "system", "message"
        )

    db.execute_command.assert_not_called()


def test_update_assistant_message_replaces_same_owned_turn(db):
    repository = ConversationRepository(db)

    repository.update_assistant_message(
        "user-id",
        "session-id",
        "request-id",
        "Resultado pronto",
        sql="SELECT 1",
        metadata={"retryable": False},
    )

    sql, parameters = db.execute_command.call_args.args
    assert "UPDATE ask_sql_conversation_messages m" in sql
    assert "m.request_id = CAST(:request_id AS uuid)" in sql
    assert "m.role = 'assistant'" in sql
    assert "s.user_id = CAST(:user_id AS uuid)" in sql
    assert parameters == {
        "user_id": "user-id",
        "session_id": "session-id",
        "request_id": "request-id",
        "content": "Resultado pronto",
        "sql": "SELECT 1",
        "error": None,
        "metadata": json.dumps({"retryable": False}, ensure_ascii=False),
    }


def test_update_assistant_message_rejects_user_role(db):
    with pytest.raises(ValueError, match="assistant"):
        ConversationRepository(db).update_assistant_message(
            "user-id", "session-id", "request-id", "message", role="user"
        )

    db.execute_command.assert_not_called()


def test_list_sessions_expires_only_owned_non_favorites_then_lists(db):
    db.execute_query.return_value = pd.DataFrame([{"id": "session-id"}])
    repository = ConversationRepository(db)

    assert repository.list_sessions("user-id") == [{"id": "session-id"}]

    expiry_sql, expiry_parameters = db.execute_command.call_args.args
    assert "is_favorite = FALSE" in expiry_sql
    assert "last_activity <= NOW() - INTERVAL '1 year'" in expiry_sql
    assert expiry_parameters == {"user_id": "user-id"}
    list_sql, list_parameters = db.execute_query.call_args.args
    assert "WHERE user_id = CAST(:user_id AS uuid)" in list_sql
    assert "ORDER BY is_favorite DESC, last_activity DESC" in list_sql
    assert list_parameters == {"user_id": "user-id"}


def test_list_sessions_with_expired_count_reports_removed_sessions(db):
    db.execute_command.return_value = 2
    db.execute_query.return_value = pd.DataFrame([{"id": "active-1"}])
    repository = ConversationRepository(db)

    sessions, expired_count = repository.list_sessions_with_expired_count("user-id")

    assert sessions == [{"id": "active-1"}]
    assert expired_count == 2
    expiry_sql, expiry_parameters = db.execute_command.call_args.args
    assert "DELETE FROM ask_sql_conversation_sessions" in expiry_sql
    assert "RETURNING" not in expiry_sql
    assert expiry_parameters == {"user_id": "user-id"}


def test_get_messages_returns_ordered_owner_scoped_records(db):
    expected = [{"id": 1, "role": "user"}, {"id": 2, "role": "assistant"}]
    db.execute_query.return_value = pd.DataFrame(expected)

    assert ConversationRepository(db).get_messages("user-id", "session-id") == expected

    sql, parameters = db.execute_query.call_args.args
    assert "ORDER BY m.id" in sql
    assert "s.user_id = CAST(:user_id AS uuid)" in sql
    assert parameters == {"user_id": "user-id", "session_id": "session-id"}


def test_get_context_returns_recent_turns_in_chronological_order(db):
    rows = [
        {
            "prompt": f"Question {index}",
            "assistant_content": f"Answer {index}",
            "assistant_sql": f"SELECT {index}",
            "assistant_error": None,
        }
        for index in range(6, 0, -1)
    ]
    db.execute_query.return_value = pd.DataFrame(rows)

    context = ConversationRepository(db).get_context("user-id", "session-id")

    assert len(context) == 12
    assert context[0] == {"role": "user", "content": "Question 1"}
    assert context[1]["role"] == "assistant"
    assert json.loads(context[1]["content"]) == {
        "message": "Answer 1",
        "sql": "SELECT 1",
        "error": None,
    }
    sql, parameters = db.execute_query.call_args.args
    assert "LIMIT :limit" in sql
    assert "s.user_id = CAST(:user_id AS uuid)" in sql
    assert parameters == {
        "user_id": "user-id",
        "session_id": "session-id",
        "limit": 6,
        "exclude_request_id": None,
    }


def test_get_context_rejects_limit_above_six(db):
    with pytest.raises(ValueError, match="six"):
        ConversationRepository(db).get_context("user-id", "session-id", limit=7)

    db.execute_query.assert_not_called()


def test_get_context_can_exclude_the_turn_being_retried(db):
    db.execute_query.return_value = pd.DataFrame()

    ConversationRepository(db).get_context(
        "user-id", "session-id", exclude_request_id="retry-id"
    )

    sql, parameters = db.execute_query.call_args.args
    assert "u.request_id IS DISTINCT FROM CAST(:exclude_request_id AS uuid)" in sql
    assert parameters["exclude_request_id"] == "retry-id"


def test_set_favorite_updates_only_owned_session(db):
    ConversationRepository(db).set_favorite("user-id", "session-id", True)

    sql, parameters = db.execute_command.call_args.args
    assert "WHERE id = CAST(:session_id AS uuid)" in sql
    assert "AND user_id = CAST(:user_id AS uuid)" in sql
    assert parameters == {
        "user_id": "user-id",
        "session_id": "session-id",
        "favorite": True,
    }


def test_delete_removes_only_owned_session(db):
    ConversationRepository(db).delete("user-id", "session-id")

    sql, parameters = db.execute_command.call_args.args
    assert "DELETE FROM ask_sql_conversation_sessions" in sql
    assert "ask_sql_query_history" not in sql
    assert "WHERE id = CAST(:session_id AS uuid)" in sql
    assert "AND user_id = CAST(:user_id AS uuid)" in sql
    assert parameters == {"user_id": "user-id", "session_id": "session-id"}


def test_repository_surfaces_storage_errors(db):
    db.execute_command.side_effect = RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        ConversationRepository(db).initialize()
