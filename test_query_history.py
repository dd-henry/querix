import pandas as pd
import pytest
from unittest.mock import MagicMock

from database.conversations import ConversationRepository
from database.query_history import QueryHistoryRepository


def test_record_persists_user_and_query():
    db = MagicMock()
    QueryHistoryRepository(db).record("user-id", "Quantos clientes?", "SELECT count(*) FROM clientes")

    params = db.execute_command.call_args.args[1]
    assert params == {
        "user_id": "user-id",
        "prompt": "Quantos clientes?",
        "sql": "SELECT count(*) FROM clientes",
        "parameters": "{}",
        "source": "chat",
        "session_id": None,
    }
    assert "WHERE NOT EXISTS" in db.execute_command.call_args.args[0]
    assert "session_id IS NOT DISTINCT FROM CAST(:session_id AS uuid)" in db.execute_command.call_args.args[0]


def test_record_normalizes_trailing_semicolon():
    db = MagicMock()
    QueryHistoryRepository(db).record("user-id", "Clientes", " SELECT * FROM clientes; ")

    assert db.execute_command.call_args.args[1]["sql"] == "SELECT * FROM clientes"


def test_record_rejects_unknown_source():
    with pytest.raises(ValueError, match="Origem de histórico"):
        QueryHistoryRepository(MagicMock()).record("user-id", "", "SELECT 1", "other")


def test_list_returns_only_repository_records():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame([{"id": 1, "prompt": "Clientes"}])

    assert QueryHistoryRepository(db).list("user-id") == [{"id": 1, "prompt": "Clientes"}]
    assert db.execute_query.call_args.args[1]["user_id"] == "user-id"


def test_set_pinned_is_scoped_to_user():
    db = MagicMock()
    QueryHistoryRepository(db).set_pinned("user-id", 3, True)

    params = db.execute_command.call_args.args[1]
    assert params == {"user_id": "user-id", "history_id": 3, "pinned": True}


def test_delete_is_scoped_to_user():
    db = MagicMock()
    QueryHistoryRepository(db).delete("user-id", 3)

    params = db.execute_command.call_args.args[1]
    assert params == {"user_id": "user-id", "history_id": 3}


def test_initialize_adds_nullable_session_foreign_key_with_cascade():
    db = MagicMock()
    QueryHistoryRepository(db).initialize()

    statements = [call.args[0] for call in db.execute_command.call_args_list]
    session_column = next(sql for sql in statements if "ADD COLUMN IF NOT EXISTS session_id" in sql)
    create_table = next(sql for sql in statements if "CREATE TABLE IF NOT EXISTS ask_sql_query_history" in sql)
    assert "UUID" in session_column
    assert "NOT NULL" not in session_column
    assert "DEFAULT" not in session_column
    assert "REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE" in session_column
    assert "session_id UUID REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE" in create_table
    deduplication = next(sql for sql in statements if "WITH ranked AS" in sql)
    assert "PARTITION BY user_id, session_id, sql, parameters" in deduplication


def test_session_delete_uses_nullable_history_cascade_for_linked_records():
    db = MagicMock()
    QueryHistoryRepository(db).initialize()
    ConversationRepository(db).delete("user-id", "session-id")

    statements = [call.args[0] for call in db.execute_command.call_args_list]
    session_column = next(
        sql for sql in statements if "ADD COLUMN IF NOT EXISTS session_id" in sql
    )
    session_delete = statements[-1]

    assert "NOT NULL" not in session_column
    assert "REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE" in session_column
    assert "DELETE FROM ask_sql_conversation_sessions" in session_delete
    assert "ask_sql_query_history" not in session_delete
    assert "user_id = CAST(:user_id AS uuid)" in session_delete


def test_record_links_query_to_session_without_changing_legacy_records():
    db = MagicMock()
    QueryHistoryRepository(db).record(
        "user-id", "Quantos clientes?", "SELECT count(*) FROM clientes",
        session_id="session-id",
    )

    sql, params = db.execute_command.call_args.args
    assert "session_id" in sql
    assert params["session_id"] == "session-id"


def test_same_query_is_deduplicated_within_session_not_across_sessions():
    db = MagicMock()
    repository = QueryHistoryRepository(db)

    repository.record("user-id", "Clientes", "SELECT 1", session_id="session-a")
    first_params = db.execute_command.call_args.args[1]
    repository.record("user-id", "Clientes", "SELECT 1", session_id="session-b")
    second_params = db.execute_command.call_args.args[1]

    assert first_params["session_id"] == "session-a"
    assert second_params["session_id"] == "session-b"
    assert "session_id IS NOT DISTINCT FROM CAST(:session_id AS uuid)" in db.execute_command.call_args.args[0]


def test_list_includes_session_linkage():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame(
        [{"id": 1, "session_id": "session-id"}]
    )

    assert QueryHistoryRepository(db).list("user-id") == [
        {"id": 1, "session_id": "session-id"}
    ]
    assert "session_id" in db.execute_query.call_args.args[0]