import pandas as pd
import pytest
from unittest.mock import MagicMock

from database.predefined_queries import PredefinedQueryRepository


def test_validate_query_accepts_select_and_strips_trailing_semicolon():
    assert PredefinedQueryRepository.validate_query(" SELECT * FROM clientes; ", []) == "SELECT * FROM clientes"


@pytest.mark.parametrize("sql", ["DELETE FROM clientes", "SELECT 1; DROP TABLE clientes"])
def test_validate_query_rejects_non_read_only_sql(sql):
    with pytest.raises(ValueError, match="apenas SELECT ou WITH"):
        PredefinedQueryRepository.validate_query(sql, [])


def test_create_validates_and_persists_json_parameters():
    db = MagicMock()
    repository = PredefinedQueryRepository(db)

    repository.create(
        "Clientes ativos", "Lista ativos", "SELECT * FROM clientes WHERE status = :status",
        ["clientes"], "dba", [{"name": "status", "label": "Status"}],
    )

    params = db.execute_command.call_args.args[1]
    assert params["author"] == "dba"
    assert '"status"' in params["parameters"]


def test_list_returns_records_with_favorites():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame([{"id": 1, "name": "Clientes", "is_favorite": True}])
    repository = PredefinedQueryRepository(db)

    assert repository.list("user-id") == [{"id": 1, "name": "Clientes", "is_favorite": True}]
    assert db.execute_query.call_args.args[1]["user_id"] == "user-id"


def test_get_returns_record_with_favorite_state_for_user():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame(
        [{"id": 7, "name": "Clientes", "is_favorite": False}]
    )
    repository = PredefinedQueryRepository(db)

    assert repository.get("user-id", 7) == {
        "id": 7,
        "name": "Clientes",
        "is_favorite": False,
    }
    assert db.execute_query.call_args.args[1] == {
        "user_id": "user-id",
        "query_id": 7,
    }