from unittest.mock import Mock
from uuid import UUID

import pandas as pd
import pytest

from api.services.chat import (
    ChatCancellationRegistry,
    ChatService,
    ChatServiceError,
)
from core.semantic_context import SemanticContextService

USER_ID = "00000000-0000-0000-0000-000000000001"
CONVERSATION_ID = UUID("00000000-0000-0000-0000-000000000002")
REQUEST_ID = UUID("00000000-0000-0000-0000-000000000003")


class MemoryConversationRepository:
    def __init__(self, messages=None):
        self.messages = list(messages or [])
        self.context_calls = []
        self.create_calls = []
        self.append_calls = []
        self.update_calls = []

    def get_messages(self, _user_id, _conversation_id):
        return self.messages

    def get_context(self, _user_id, _conversation_id, limit, exclude_request_id=None):
        self.context_calls.append((limit, exclude_request_id))
        return []

    def create_with_user_message(
        self,
        user_id,
        conversation_id,
        request_id,
        prompt,
    ):
        self.create_calls.append(
            (user_id, conversation_id, request_id, prompt)
        )
        self.messages.append(
            {
                "request_id": request_id,
                "role": "user",
                "content": prompt,
            }
        )

    def append_message(
        self,
        user_id,
        conversation_id,
        request_id,
        role,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        self.append_calls.append(
            (
                user_id,
                conversation_id,
                request_id,
                role,
                content,
                sql,
                error,
                metadata or {},
            )
        )
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
        user_id,
        conversation_id,
        request_id,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        self.update_calls.append(
            (
                user_id,
                conversation_id,
                request_id,
                content,
                sql,
                error,
                metadata or {},
            )
        )
        for message in self.messages:
            if (
                message["request_id"] == request_id
                and message["role"] == "assistant"
            ):
                message.update(
                    {
                        "content": content,
                        "sql": sql,
                        "error": error,
                        "metadata": metadata or {},
                    }
                )


class FakeTranslator:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def translate_to_sql(self, prompt, conversation_context):
        self.calls.append((prompt, conversation_context))
        if self.error is not None:
            raise self.error
        return self.response


class RepairTranslator(FakeTranslator):
    def __init__(self, repair_response):
        super().__init__()
        self.repair_response = repair_response
        self.repair_calls = []

    def repair_query(self, **kwargs):
        self.repair_calls.append(kwargs)
        return self.repair_response


def _service(
    repository,
    translator,
    database=None,
    history=None,
    semantic_context=None,
    cancellation_registry=None,
):
    return ChatService(
        repository,
        translator,
        database or Mock(),
        query_history_repository=history,
        semantic_context=semantic_context,
        cancellation_registry=cancellation_registry,
    )


def _user_message():
    return {
        "request_id": REQUEST_ID,
        "role": "user",
        "content": "Show revenue",
    }


def _assistant_message(**overrides):
    message = {
        "request_id": REQUEST_ID,
        "role": "assistant",
        "content": "SQL gerado para revisão.",
        "sql": "SELECT 1",
        "error": None,
        "metadata": {},
    }
    message.update(overrides)
    return message


def test_service_does_not_mutate_web_session_state():
    source = open(
        "api/services/chat.py",
        encoding="utf-8",
    ).read()

    assert "session_state" not in source


@pytest.mark.parametrize("prompt", ["   ", "x" * 2001])
def test_prompt_bounds_are_rejected_before_persistence(prompt):
    repository = MemoryConversationRepository()
    translator = FakeTranslator(response={"sql": "SELECT 1", "grafico": None})
    service = _service(repository, translator)

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            prompt,
        )

    assert error.value.status_code == 422
    assert error.value.code == "validation_error"
    assert repository.create_calls == []
    assert repository.append_calls == []
    assert translator.calls == []


def test_cancelled_request_stops_before_translation():
    repository = MemoryConversationRepository([_user_message()])
    translator = FakeTranslator(
        response={"sql": "SELECT 1", "grafico": None},
    )
    registry = ChatCancellationRegistry()
    registry.start(REQUEST_ID, USER_ID, CONVERSATION_ID)
    service = _service(
        repository,
        translator,
        cancellation_registry=registry,
    )

    service.cancel_request(USER_ID, CONVERSATION_ID, REQUEST_ID)

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.code == "request_cancelled"
    assert translator.calls == []


def test_cancellation_can_win_before_the_user_turn_is_persisted():
    registry = ChatCancellationRegistry()

    class CancellingRepository(MemoryConversationRepository):
        def get_messages(self, user_id, conversation_id):
            messages = super().get_messages(user_id, conversation_id)
            registry.cancel(REQUEST_ID, user_id, conversation_id)
            return messages

    repository = CancellingRepository()
    translator = FakeTranslator(
        response={"sql": "SELECT 1", "grafico": None},
    )
    service = _service(
        repository,
        translator,
        cancellation_registry=registry,
    )

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.code == "request_cancelled"
    assert repository.create_calls == []
    assert translator.calls == []


def test_cancellation_is_scoped_to_the_active_request_owner():
    repository = MemoryConversationRepository([_user_message()])
    registry = ChatCancellationRegistry()
    registry.start(REQUEST_ID, USER_ID, CONVERSATION_ID)
    service = _service(
        repository,
        FakeTranslator(response={"sql": "SELECT 1", "grafico": None}),
        cancellation_registry=registry,
    )

    with pytest.raises(ChatServiceError) as error:
        service.cancel_request(
            "00000000-0000-0000-0000-000000000009",
            CONVERSATION_ID,
            REQUEST_ID,
        )

    assert error.value.status_code == 409
    assert error.value.code == "request_not_active"
    assert not registry.is_cancelled(REQUEST_ID)


def test_request_id_collision_cannot_finish_another_owner_request():
    repository = MemoryConversationRepository()
    registry = ChatCancellationRegistry()
    registry.start(REQUEST_ID, USER_ID, CONVERSATION_ID)
    service = _service(
        repository,
        FakeTranslator(response={"sql": "SELECT 1", "grafico": None}),
        cancellation_registry=registry,
    )

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            "00000000-0000-0000-0000-000000000009",
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.code == "request_id_in_use"
    assert registry.is_active(REQUEST_ID, USER_ID, CONVERSATION_ID)


def test_completed_request_cannot_be_cancelled():
    repository = MemoryConversationRepository([_user_message()])
    service = _service(
        repository,
        FakeTranslator(response={"sql": "SELECT 1", "grafico": None}),
        cancellation_registry=ChatCancellationRegistry(),
    )

    with pytest.raises(ChatServiceError) as error:
        service.cancel_request(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert error.value.status_code == 409
    assert error.value.code == "request_not_active"


def test_cancellation_during_cached_lookup_does_not_return_cached_result():
    registry = ChatCancellationRegistry()

    class CancellingRepository(MemoryConversationRepository):
        def get_messages(self, user_id, conversation_id):
            messages = super().get_messages(user_id, conversation_id)
            registry.cancel(REQUEST_ID, user_id, conversation_id)
            return messages

    repository = CancellingRepository(
        [_user_message(), _assistant_message()]
    )
    service = _service(
        repository,
        FakeTranslator(response={"sql": "SELECT 1", "grafico": None}),
        cancellation_registry=registry,
    )

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.code == "request_cancelled"


def test_cancellation_after_database_response_skips_result_persistence():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    registry = ChatCancellationRegistry()
    database = Mock()

    def execute_and_cancel(_sql, _parameters):
        registry.cancel(REQUEST_ID, USER_ID, CONVERSATION_ID)
        return pd.DataFrame([{"total": 1}])

    database.execute_read_only_query.side_effect = execute_and_cancel
    service = _service(
        repository,
        FakeTranslator(),
        database=database,
        cancellation_registry=registry,
    )
    registry.start(REQUEST_ID, USER_ID, CONVERSATION_ID)

    with pytest.raises(ChatServiceError) as error:
        service.execute_stored_query(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
        )

    assert error.value.code == "request_cancelled"
    assert repository.update_calls == []


def test_translation_success_persists_once_and_limits_context():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={
            "sql": " SELECT count(*) FROM sales; ",
            "grafico": {"tipo": "bar"},
        }
    )
    service = _service(repository, translator)

    result = service.translate_prompt(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "  Show revenue  ",
    )

    assert result.status == "review"
    assert result.sql == "SELECT count(*) FROM sales"
    assert result.chart == {"tipo": "bar"}
    assert repository.create_calls == [
        (USER_ID, CONVERSATION_ID, REQUEST_ID, "Show revenue")
    ]
    assert repository.context_calls == [(6, None)]
    assert len(repository.append_calls) == 1
    assert repository.append_calls[0][3] == "assistant"
    assert translator.calls == [("Show revenue", [])]


def test_warning_is_persisted_without_a_query_or_execution():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={"sql": "AVISO: Não foi possível identificar a tabela.", "grafico": None}
    )
    database = Mock()
    service = _service(repository, translator, database)

    result = service.translate_prompt(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "Show something unknown",
    )

    assert result.status == "warning"
    assert result.content.startswith("AVISO:")
    assert result.sql is None
    database.execute_read_only_query.assert_not_called()
    assert repository.append_calls[-1][3] == "assistant"


def test_translator_failure_stores_a_retryable_error():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(error=ConnectionError("offline"))
    service = _service(repository, translator)

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.status_code == 502
    assert error.value.code == "translator_unavailable"
    assistant = repository.messages[-1]
    assert assistant["error"] == "translator_unavailable"
    assert assistant["metadata"] == {
        "retryable": True,
        "retry_kind": "translate",
    }


def test_invalid_generated_sql_is_stored_and_never_reaches_database():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={"sql": "DELETE FROM sales", "grafico": None}
    )
    database = Mock()
    service = _service(repository, translator, database)

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Delete sales",
        )

    assert error.value.status_code == 422
    assert error.value.code == "sql_not_read_only"
    assert repository.messages[-1]["error"] == "sql_not_read_only"
    database.execute_read_only_query.assert_not_called()


def test_multi_statement_generated_sql_is_rejected_before_database_call():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={"sql": "SELECT 1; SELECT 2", "grafico": None}
    )
    database = Mock()
    service = _service(repository, translator, database)

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "Show revenue",
        )

    assert error.value.code == "sql_not_read_only"
    database.execute_read_only_query.assert_not_called()


def test_unknown_plan_identifier_is_rejected_before_database_call():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={
            "sql": "SELECT missing FROM orders",
            "plan": {
                "intent": "list",
                "tables": ["orders"],
                "relationships": [],
                "dimensions": ["orders.missing"],
                "metrics": [],
                "filters": [],
                "grain": None,
                "assumptions": ["the requested column is available"],
            },
        }
    )
    database = Mock()
    metadata_source = Mock()
    metadata_source.get_schema_metadata.return_value = {
        "tables": [
            {
                "name": "orders",
                "columns": [{"name": "id", "data_type": "integer"}],
            }
        ],
        "relationships": [],
    }
    semantic_context = SemanticContextService(metadata_source)
    service = _service(
        repository,
        translator,
        database,
        semantic_context=semantic_context,
    )

    with pytest.raises(ChatServiceError) as error:
        service.translate_prompt(
            USER_ID,
            CONVERSATION_ID,
            REQUEST_ID,
            "List orders",
        )

    assert error.value.status_code == 422
    assert error.value.code == "query_plan_invalid"
    assert repository.messages[-1]["error"] == "query_plan_invalid"
    assert database.execute_read_only_query.call_count == 0


def test_invalid_stored_sql_is_rejected_before_database_call():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message(sql="UPDATE sales SET total = 0")]
    )
    database = Mock()
    service = _service(repository, FakeTranslator(), database)

    with pytest.raises(ChatServiceError) as error:
        service.execute_stored_query(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert error.value.status_code == 422
    assert error.value.code == "sql_not_read_only"
    database.execute_read_only_query.assert_not_called()


def test_stored_execution_is_read_only_bounded_and_records_history():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"total": 12}]
    )
    history = Mock()
    service = _service(repository, FakeTranslator(), database, history)

    result = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.status == "executed"
    assert result.result == {
        "columns": ["total"],
        "rows": [{"total": 12}],
        "row_count": 1,
        "truncated": False,
    }
    assert result.summary == "A consulta retornou 1 linha(s)."
    database.execute_read_only_query.assert_called_once_with("SELECT 1", {})
    history.record.assert_called_once_with(
        USER_ID,
        "Show revenue",
        "SELECT 1",
        "chat",
        {},
        session_id=CONVERSATION_ID,
    )
    assert repository.update_calls[-1][3] == "Aqui estão os resultados da consulta:"


def test_stored_execution_returns_supporting_insights_after_primary_result():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "parameters": {},
                    "supporting_queries": [
                        {
                            "key": "kpi",
                            "title": "Indicadores do período",
                            "sql": "SELECT 2",
                            "parameters": {},
                        },
                        {
                            "key": "top_products",
                            "title": "Produtos mais vendidos",
                            "sql": "SELECT 3",
                            "parameters": {},
                        },
                    ],
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.side_effect = [
        pd.DataFrame([{"total": 12}]),
        pd.DataFrame([{"faturamento": 12}]),
        pd.DataFrame([{"produto": "Picanha", "valor": 12}]),
    ]
    service = _service(repository, FakeTranslator(), database)

    result = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.result["rows"] == [{"total": 12}]
    assert [insight.key for insight in result.insights] == [
        "kpi",
        "top_products",
    ]
    assert result.insights[0].result["rows"] == [{"faturamento": 12}]
    assert result.insights[0].summary == "A consulta retornou 1 linha(s)."
    assert database.execute_read_only_query.call_count == 3


def test_stored_execution_preserves_zero_rows_and_adds_truthful_diagnostic():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "plan": {
                        "intent": "Comparar receita por região",
                        "tables": ["orders"],
                        "relationships": [],
                        "dimensions": ["region"],
                        "metrics": ["revenue"],
                        "filters": [],
                        "grain": "region",
                        "assumptions": ["revenue is the order total"],
                    }
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        columns=["region", "revenue"]
    )
    result = _service(repository, FakeTranslator(), database).execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.status == "executed"
    assert result.result["row_count"] == 0
    assert result.summary == "A consulta retornou 0 linha(s)."
    assert result.diagnostics == {
        "kind": "empty_result",
        "message": (
            "A consulta foi executada, mas não encontrou dados "
            "compatíveis com os filtros informados."
        ),
        "expected_columns": [],
    }
    assert "revenue" not in result.summary


def test_stored_execution_reports_missing_expected_metric_without_fabricating_it():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "plan": {
                        "intent": "Comparar receita por região",
                        "tables": ["orders"],
                        "relationships": [],
                        "dimensions": ["region"],
                        "metrics": ["revenue"],
                        "filters": [],
                        "grain": "region",
                        "assumptions": ["revenue is the order total"],
                    }
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"region": "Sul"}]
    )
    result = _service(repository, FakeTranslator(), database).execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.result["rows"] == [{"region": "Sul"}]
    assert result.diagnostics["kind"] == "missing_expected_columns"
    assert result.diagnostics["expected_columns"] == ["revenue"]
    assert result.summary == "A consulta retornou 1 linha(s)."
    assert "revenue" not in result.summary
    assert "999" not in result.summary


def test_supporting_failure_preserves_primary_result_with_warning():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "supporting_queries": [
                        {
                            "key": "kpi",
                            "title": "Indicadores do período",
                            "sql": "SELECT 2",
                            "parameters": {},
                        }
                    ]
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.side_effect = [
        pd.DataFrame([{"total": 12}]),
        ConnectionError("offline"),
    ]
    service = _service(repository, FakeTranslator(), database)

    result = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.status == "executed"
    assert result.result["rows"] == [{"total": 12}]
    assert result.insights[0].warning == (
        "Não foi possível calcular esta análise complementar."
    )


def test_empty_and_truncated_supporting_results_remain_truthful():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "supporting_queries": [
                        {
                            "key": "empty",
                            "title": "Sem resultados",
                            "sql": "SELECT 2",
                            "parameters": {},
                        },
                        {
                            "key": "large",
                            "title": "Resultado extenso",
                            "sql": "SELECT 3",
                            "parameters": {},
                        },
                    ]
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.side_effect = [
        pd.DataFrame([{"total": 12}]),
        pd.DataFrame(columns=["total"]),
        pd.DataFrame([{"total": value} for value in range(5_001)]),
    ]
    service = _service(repository, FakeTranslator(), database)

    result = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    empty, large = result.insights
    assert empty.result["row_count"] == 0
    assert empty.result["rows"] == []
    assert empty.summary == "A consulta retornou 0 linha(s)."
    assert large.result["row_count"] == 5_001
    assert len(large.result["rows"]) == 5_000
    assert large.result["truncated"] is True
    assert "resultado foi limitado" in large.summary


def test_invalid_supporting_query_is_reported_without_database_execution():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "supporting_queries": [
                        {
                            "key": "unsafe",
                            "title": "Unsafe",
                            "sql": "SELECT 1; SELECT 2",
                            "parameters": {},
                        }
                    ]
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.return_value = pd.DataFrame(
        [{"total": 12}]
    )
    service = _service(repository, FakeTranslator(), database)

    result = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.result["rows"] == [{"total": 12}]
    assert result.insights[0].warning is not None
    database.execute_read_only_query.assert_called_once_with("SELECT 1", {})


def test_repeating_stored_request_reuses_the_same_primary_and_insight_plan():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                metadata={
                    "supporting_queries": [
                        {
                            "key": "kpi",
                            "title": "Indicadores do período",
                            "sql": "SELECT 2",
                            "parameters": {},
                        }
                    ]
                },
            ),
        ]
    )
    database = Mock()
    database.execute_read_only_query.side_effect = [
        pd.DataFrame([{"total": 12}]),
        pd.DataFrame([{"revenue": 12}]),
        pd.DataFrame([{"total": 12}]),
        pd.DataFrame([{"revenue": 12}]),
    ]
    service = _service(repository, FakeTranslator(), database)

    first = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )
    second = service.execute_stored_query(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert second.result == first.result
    assert [
        (insight.key, insight.result, insight.summary)
        for insight in second.insights
    ] == [
        (insight.key, insight.result, insight.summary)
        for insight in first.insights
    ]
    assert len(repository.messages) == 2


def test_translation_persists_bound_parameters_for_known_analytical_query():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={
            "sql": (
                "SELECT total FROM vendas "
                "WHERE data_hora >= :period_start "
                "AND data_hora < :period_end"
            ),
            "parameters": {
                "period_start": "2026-08-01T00:00:00+00:00",
                "period_end": "2026-09-01T00:00:00+00:00",
            },
            "intent": "revenue_total",
            "grafico": None,
        }
    )
    service = _service(repository, translator)

    service.translate_prompt(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "Qual foi o total de vendas em agosto?",
    )

    metadata = repository.messages[-1]["metadata"]
    assert metadata["parameters"] == {
        "period_start": "2026-08-01T00:00:00+00:00",
        "period_end": "2026-09-01T00:00:00+00:00",
    }
    assert metadata["intent"] == "revenue_total"


def test_translation_persists_bounded_supporting_queries():
    repository = MemoryConversationRepository()
    translator = FakeTranslator(
        response={
            "sql": "SELECT 1",
            "grafico": None,
            "supporting_queries": [
                {
                    "key": "kpi",
                    "title": "Indicadores",
                    "sql": "SELECT 2",
                    "parameters": {},
                }
            ],
        }
    )
    service = _service(repository, translator)

    service.translate_prompt(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "Show revenue",
    )

    assert repository.messages[-1]["metadata"]["supporting_queries"] == [
        {
            "key": "kpi",
            "title": "Indicadores",
            "sql": "SELECT 2",
            "parameters": {},
        }
    ]


def test_database_failure_stores_a_retryable_error():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    database = Mock()
    database.execute_read_only_query.side_effect = ConnectionError("offline")
    service = _service(repository, FakeTranslator(), database)

    with pytest.raises(ChatServiceError) as error:
        service.execute_stored_query(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert error.value.status_code == 503
    assert error.value.code == "database_unavailable"
    assert repository.update_calls[-1][5] == "database_unavailable"
    assert repository.update_calls[-1][6]["retryable"] is True
    assert repository.update_calls[-1][6]["retry_kind"] == "execute"


def test_database_failure_is_repaired_once_and_updates_same_message():
    plan = {
        "intent": "List totals",
        "tables": ["orders"],
        "relationships": [],
        "dimensions": [],
        "metrics": ["total"],
        "filters": [],
        "grain": None,
        "assumptions": ["total is available"],
    }
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(metadata={"plan": plan}),
        ]
    )
    translator = RepairTranslator({"sql": "SELECT 2", "parameters": {}})
    database = Mock()
    database.execute_read_only_query.side_effect = [
        ConnectionError("missing column"),
        pd.DataFrame([{"total": 2}]),
    ]
    service = _service(repository, translator, database)

    result = service.execute_stored_query(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert result.status == "executed"
    assert result.sql == "SELECT 2"
    assert result.result["rows"] == [{"total": 2}]
    assert database.execute_read_only_query.call_count == 2
    assert len(translator.repair_calls) == 1
    assert len(repository.update_calls) == 1
    assert repository.update_calls[-1][2] == REQUEST_ID
    assert repository.update_calls[-1][4] == "SELECT 2"
    assert repository.update_calls[-1][5] is None
    assert repository.update_calls[-1][6]["repair_attempted"] is True
    assert repository.update_calls[-1][6]["repaired_from"] == "SELECT 1"
    assert translator.repair_calls[0]["database_error"] == "missing column"
    assert translator.repair_calls[0]["plan"] == plan


def test_invalid_repair_is_not_executed_and_remains_retryable():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    translator = RepairTranslator({"sql": "DELETE FROM orders"})
    database = Mock()
    database.execute_read_only_query.side_effect = ConnectionError("offline")
    service = _service(repository, translator, database)

    with pytest.raises(ChatServiceError) as error:
        service.execute_stored_query(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert error.value.code == "database_unavailable"
    assert database.execute_read_only_query.call_count == 1
    assert len(translator.repair_calls) == 1
    assert repository.update_calls[-1][4] == "SELECT 1"
    assert repository.update_calls[-1][2] == REQUEST_ID
    assert repository.update_calls[-1][6]["retryable"] is True
    assert repository.update_calls[-1][6]["retry_kind"] == "execute"
    assert repository.update_calls[-1][6]["repair_attempted"] is True


def test_failed_repair_is_bounded_to_one_database_retry():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    translator = RepairTranslator({"sql": "SELECT 2"})
    database = Mock()
    database.execute_read_only_query.side_effect = [
        ConnectionError("original failure"),
        ConnectionError("repair failure"),
    ]
    service = _service(repository, translator, database)

    with pytest.raises(ChatServiceError) as error:
        service.execute_stored_query(USER_ID, CONVERSATION_ID, REQUEST_ID)

    assert error.value.code == "database_unavailable"
    assert database.execute_read_only_query.call_count == 2
    assert len(translator.repair_calls) == 1
    assert repository.update_calls[-1][4] == "SELECT 2"
    assert repository.update_calls[-1][5] == "database_unavailable"
    assert repository.update_calls[-1][6]["repair_attempted"] is True
    assert repository.update_calls[-1][2] == REQUEST_ID
    assert repository.update_calls[-1][6]["retryable"] is True
    assert repository.update_calls[-1][6]["retry_kind"] == "execute"


def test_duplicate_request_returns_stored_message_without_translation_or_insert():
    repository = MemoryConversationRepository(
        [_user_message(), _assistant_message()]
    )
    translator = FakeTranslator(
        response={"sql": "SELECT 2", "grafico": None}
    )
    service = _service(repository, translator)

    result = service.translate_prompt(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
        "Show revenue again",
    )

    assert result.sql == "SELECT 1"
    assert result.status == "review"
    assert translator.calls == []
    assert repository.create_calls == []
    assert repository.append_calls == []
    assert repository.update_calls == []


def test_translation_retry_reuses_request_and_excludes_it_from_context():
    repository = MemoryConversationRepository(
        [
            _user_message(),
            _assistant_message(
                content="Não foi possível traduzir a pergunta.",
                sql=None,
                error="translator_unavailable",
                metadata={
                    "retryable": True,
                    "retry_kind": "translate",
                },
            ),
        ]
    )
    translator = FakeTranslator(
        response={"sql": "SELECT 3", "grafico": None}
    )
    service = _service(repository, translator)

    result = service.retry_request(
        USER_ID,
        CONVERSATION_ID,
        REQUEST_ID,
    )

    assert result.sql == "SELECT 3"
    assert repository.create_calls == []
    assert repository.append_calls == []
    assert repository.context_calls == [(6, REQUEST_ID)]
    assert repository.update_calls[-1][2] == REQUEST_ID
