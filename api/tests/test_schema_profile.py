from unittest.mock import Mock

import api.routes.sync as sync_route
from core.semantic_context import SemanticContextService


def _metadata():
    return {
        "tables": [
            {
                "name": "orders",
                "comment": "Business orders",
                "columns": [
                    {
                        "name": "id",
                        "data_type": "integer",
                        "is_nullable": "NO",
                        "is_primary_key": True,
                        "is_unique": True,
                    },
                    {
                        "name": "created_at",
                        "data_type": "timestamp without time zone",
                        "is_nullable": "NO",
                    },
                    {
                        "name": "amount",
                        "data_type": "numeric",
                        "is_nullable": "YES",
                    },
                ],
            },
            {
                "name": "customers",
                "columns": [
                    {
                        "name": "id",
                        "data_type": "integer",
                        "is_nullable": "NO",
                    }
                ],
            },
        ],
        "relationships": [
            {
                "table": "orders",
                "column": "customer_id",
                "foreign_table": "customers",
                "foreign_column": "id",
            }
        ],
        "rows": [{"id": 1, "amount": 999}],
    }


def test_profile_contains_structure_candidates_and_no_raw_rows():
    database = Mock()
    database.get_schema_metadata.return_value = _metadata()
    service = SemanticContextService(database)

    profile = service.get_profile()
    orders = profile.tables["orders"]

    assert set(profile.tables) == {"orders", "customers"}
    assert [column.name for column in orders.columns] == [
        "id",
        "created_at",
        "amount",
    ]
    assert orders.columns[0].name == "id"
    assert orders.columns[0].data_type == "integer"
    assert orders.columns[0].nullable is False
    assert orders.columns[2].name == "amount"
    assert orders.columns[2].data_type == "numeric"
    assert orders.columns[2].nullable is True
    assert orders.columns[0].is_primary_key is True
    assert orders.columns[0].is_unique is True
    assert orders.candidate_temporal_columns == ("created_at",)
    assert orders.candidate_numeric_columns == ("id", "amount")
    assert profile.relationships[0].foreign_table == "customers"
    assert "999" not in profile.to_prompt_context()
    assert "rows" not in profile.to_prompt_context()


def test_profile_accepts_empty_schema_without_relationships():
    database = Mock()
    database.get_schema_metadata.return_value = {
        "tables": [],
        "relationships": [],
    }
    service = SemanticContextService(database)

    profile = service.get_profile()

    assert profile.tables == {}
    assert profile.relationships == ()


def test_profile_accepts_tables_without_relationships_or_candidates():
    database = Mock()
    database.get_schema_metadata.return_value = {
        "tables": [
            {
                "name": "labels",
                "columns": [
                    {
                        "name": "label",
                        "data_type": "text",
                        "is_nullable": "YES",
                    }
                ],
            }
        ],
        "relationships": [],
    }

    profile = SemanticContextService(database).get_profile()

    assert profile.relationships == ()
    assert profile.tables["labels"].candidate_temporal_columns == ()
    assert profile.tables["labels"].candidate_numeric_columns == ()


def test_profile_cache_is_reused_and_invalidated():
    database = Mock()
    database.get_schema_metadata.return_value = _metadata()
    service = SemanticContextService(database)

    first = service.get_profile()
    second = service.get_profile()
    service.invalidate()
    third = service.get_profile()

    assert first is second
    assert third is not first
    assert database.get_schema_metadata.call_count == 2


def test_schema_sync_invalidates_semantic_context_cache(monkeypatch):
    semantic_context = Mock()
    semantic_context.return_value = semantic_context
    translator = Mock(return_value=object())
    catalog = Mock()
    monkeypatch.setattr(sync_route, "get_semantic_context", semantic_context)
    monkeypatch.setattr(sync_route, "get_translator", translator)
    monkeypatch.setattr(
        sync_route,
        "get_predefined_query_repository",
        catalog,
    )

    sync_route.synchronize_schema({"id": "profile"})

    semantic_context.cache_clear.assert_called_once_with()
    semantic_context.get_profile.assert_called_once_with()
