import pandas as pd
import pytest
from unittest.mock import MagicMock

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


def test_initialize_adds_session_column_without_deleting_existing_history():
    db = MagicMock()
    QueryHistoryRepository(db).initialize()

    statements = [call.args[0] for call in db.execute_command.call_args_list]
    migration = next(sql for sql in statements if "ADD COLUMN IF NOT EXISTS session_id" in sql)
    assert "REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE" in migration
    assert not any("DELETE FROM ask_sql_query_history" in sql for sql in statements)


def test_record_keeps_sessions_separate():
    db = MagicMock()
    repository = QueryHistoryRepository(db)
    repository.record("user-id", "Clientes", "SELECT 1", session_id="session-a")
    repository.record("user-id", "Clientes", "SELECT 1", session_id="session-b")

    first, second = db.execute_command.call_args_list
    assert first.args[1]["session_id"] == "session-a"
    assert second.args[1]["session_id"] == "session-b"
    assert "session_id IS NOT DISTINCT FROM CAST(:session_id AS uuid)" in second.args[0]


def test_get_is_scoped_to_user_and_returns_none_for_missing_record():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame()
    assert QueryHistoryRepository(db).get("user-id", 3) is None
    sql, params = db.execute_query.call_args.args
    assert "user_id = CAST(:user_id AS uuid)" in sql
    assert params == {"user_id": "user-id", "history_id": 3}