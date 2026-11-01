from datetime import date

import pytest
from unittest.mock import patch

from core.query_plan import QueryPlan
from core.query_validation import QueryValidationError
from core.temporal import TemporalInterpreter
from core.translator import Translator
from core.translator import TranslationStageError

# Fixture é um recurso do pytest para criar instâncias reutilizáveis
@pytest.fixture
def translator():
    return Translator(system_prompt="Prompt Falso", model_name="test_model")

def test_clean_sql_response_json_perfeito(translator):
    """Testa se o extrator consegue ler um JSON perfeitamente formatado."""
    fake_llm_response = '{"sql": "SELECT * FROM users", "grafico": null}'
    
    resultado = translator._clean_sql_response(fake_llm_response)
    
    assert resultado["sql"] == "SELECT * FROM users"
    assert resultado["grafico"] is None

def test_clean_sql_response_com_sujeira_markdown(translator):
    """Testa se o extrator ignora a 'tagarelice' da IA antes e depois do JSON."""
    fake_llm_response = '''
    Claro! Aqui está o resultado da sua solicitação:
    ```json
    {"sql": "SELECT count(1) FROM vendas", "grafico": {"tipo": "bar"}}
    ```
    Espero ter ajudado!
    '''
    
    resultado = translator._clean_sql_response(fake_llm_response)
    
    assert resultado["sql"] == "SELECT count(1) FROM vendas"
    assert resultado["grafico"]["tipo"] == "bar"

def test_clean_sql_response_deve_falhar_json_invalido(translator):
    """Testa se o sistema levanta erro quando a IA gera um JSON quebrado (faltando aspas, etc)."""
    fake_invalid_response = '{"sql": "SELECT * FROM users, "grafico": null}' # Faltando aspas no users
    
    with pytest.raises(ValueError, match="O modelo não retornou um JSON válido"):
        translator._clean_sql_response(fake_invalid_response)


def test_clean_sql_response_normalizes_supporting_queries(translator):
    resultado = translator._clean_sql_response(
        '{"sql":"SELECT 1","grafico":null,"supporting_queries":['
        '{"key":"kpi","title":"Indicadores","sql":"SELECT 2",'
        '"parameters":{"period_start":"2026-10-01"}}]}'
    )

    assert resultado["supporting_queries"] == [
        {
            "key": "kpi",
            "title": "Indicadores",
            "sql": "SELECT 2",
            "parameters": {"period_start": "2026-10-01"},
        }
    ]


@pytest.mark.parametrize(
    "supporting_queries",
    [
        '[{"key":"kpi","title":"Indicadores"}]',
        '[{"key":"kpi","title":"Indicadores","sql":"SELECT 2"},'
        '{"key":"kpi","title":"Duplicado","sql":"SELECT 3"}]',
    ],
)
def test_clean_sql_response_discards_malformed_supporting_queries(
    translator,
    supporting_queries,
):
    resultado = translator._clean_sql_response(
        '{"sql":"SELECT 1","grafico":null,"supporting_queries":'
        f"{supporting_queries}}}"
    )

    assert resultado["sql"] == "SELECT 1"
    assert resultado["supporting_queries"] == []


def test_translate_to_sql_passes_context_before_current_question(translator):
    context = [
        {"role": "user", "content": "Quantos clientes?"},
        {
            "role": "assistant",
            "content": '{"message":"São 12 clientes.","sql":"SELECT count(*) FROM clientes"}',
        },
        {"role": "user", "content": "E quantos estão ativos?"},
        {"role": "assistant", "content": '{"sql":"SELECT count(*) FROM clientes WHERE ativo"}'},
    ]

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT 8"}'}},
    ) as chat:
        translator.translate_to_sql("E quantos inativos?", context)

    assert chat.call_args.kwargs["messages"] == [
        {"role": "system", "content": "Prompt Falso"},
        *context,
        {"role": "user", "content": "E quantos inativos?"},
    ]


def test_translate_to_sql_dispatches_former_domain_question_to_ollama(translator):
    with patch(
        "core.translator.ollama.chat",
        return_value={
            "message": {
                "content": (
                    '{"sql":"SELECT product_name, SUM(quantity) AS total '
                    'FROM inventory GROUP BY product_name"}'
                )
            }
        },
    ) as chat:
        resultado = translator.translate_to_sql(
            "Quais produtos foram vendidos em agosto de 2026?"
        )

    assert resultado["sql"].startswith("SELECT product_name")
    assert "intent" not in resultado
    assert chat.call_count == 1


def test_translate_to_sql_preserves_two_message_request_without_context(translator):
    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT 1"}'}},
    ) as chat:
        translator.translate_to_sql("Quantos clientes?")

    assert chat.call_args.kwargs["messages"] == [
        {"role": "system", "content": "Prompt Falso"},
        {"role": "user", "content": "Quantos clientes?"},
    ]


def test_translate_to_sql_preserves_two_message_request_with_empty_context(translator):
    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT 1"}'}},
    ) as chat:
        translator.translate_to_sql("Quantos clientes?", [])

    assert len(chat.call_args.kwargs["messages"]) == 2


def test_translate_to_sql_limits_context_to_latest_six_turns(translator):
    context = []
    for index in range(1, 8):
        context.extend(
            [
                {"role": "user", "content": f"Question {index}"},
                {"role": "assistant", "content": f'{{"sql":"SELECT {index}"}}'},
            ]
        )

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT 8"}'}},
    ) as chat:
        translator.translate_to_sql("Next question", context)

    messages = chat.call_args.kwargs["messages"]
    assert len(messages) == 14
    assert messages[1] == {"role": "user", "content": "Question 2"}
    assert messages[-2] == {"role": "assistant", "content": '{"sql":"SELECT 7"}'}
    assert messages[-1] == {"role": "user", "content": "Next question"}


def test_translate_to_sql_surfaces_ollama_failure(translator):
    with patch(
        "core.translator.ollama.chat",
        side_effect=ConnectionError("Ollama unavailable"),
    ):
        with pytest.raises(RuntimeError, match="Ollama unavailable"):
            translator.translate_to_sql("Quantos clientes?")


def _staged_translator(**kwargs):
    return Translator(
        system_prompt="legacy prompt",
        model_name="test_model",
        planner_prompt="planner prompt",
        sql_generation_prompt="sql prompt",
        **kwargs,
    )


def test_plan_question_normalizes_typed_plan():
    translator = _staged_translator()
    planner_payload = (
        '{"intent":"ranking","tables":["orders"],'
        '"relationships":["orders.customer_id -> customers.id"],'
        '"dimensions":["customers.name"],"metrics":["SUM(orders.amount)"],'
        '"filters":[{"column":"orders.created_at","operator":">=","value":"2025-01-01"}],'
        '"grain":"customer","assumptions":["amount is additive"]}'
    )

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": planner_payload}},
    ):
        plan = translator.plan_question(
            "Ranking de clientes",
            temporal_interpretation=TemporalInterpreter().interpret(
                "em janeiro",
                reference_date=date(2025, 1, 15),
            ),
        )

    assert isinstance(plan, QueryPlan)
    assert plan.intent == "ranking"
    assert plan.tables == ("orders",)
    assert plan.relationships == ("orders.customer_id -> customers.id",)
    assert plan.dimensions == ("customers.name",)
    assert plan.metrics == ("SUM(orders.amount)",)
    assert plan.filters[0]["operator"] == ">="
    assert plan.grain == "customer"
    assert plan.assumptions == ("amount is additive",)


def test_plan_question_ignores_empty_optional_plan_entries():
    payload = (
        '{"intent":"list","tables":["events"],'
        '"relationships":[""],"dimensions":["created_at",""],'
        '"metrics":[""],"filters":[],"grain":null,'
        '"assumptions":["no aggregation requested"]}'
    )

    translator = _staged_translator()
    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": payload}},
    ):
        plan = translator.plan_question("Liste eventos")

    assert plan.relationships == ()
    assert plan.dimensions == ("created_at",)
    assert plan.metrics == ()


def test_plan_question_retries_malformed_planner_response():
    translator = _staged_translator()
    valid_payload = (
        '{"intent":"list","tables":["events"],"relationships":[],'
        '"dimensions":["created_at"],"metrics":[],"filters":[],'
        '"grain":null,"assumptions":["no aggregation requested"]}'
    )

    with patch(
        "core.translator.ollama.chat",
        side_effect=[
            {"message": {"content": '{"intent":"","tables":[]}'}},
            {"message": {"content": valid_payload}},
        ],
    ) as chat:
        plan = translator.plan_question("Liste eventos")

    assert plan.tables == ("events",)
    assert chat.call_count == 2
    assert (
        "CORREÇÃO OBRIGATÓRIA"
        in chat.call_args_list[1].kwargs["messages"][0]["content"]
    )


def test_translate_to_sql_retries_plan_rejected_by_schema_validation():
    validation_calls = []

    def validate(plan):
        validation_calls.append(plan)
        if len(validation_calls) == 1:
            raise QueryValidationError(
                "unknown_column",
                "Unknown column in query plan: total_vendas.",
            )

    translator = _staged_translator(plan_validator=validate)
    invalid_payload = (
        '{"intent":"ranking","tables":["events"],"relationships":[],'
        '"dimensions":["created_at"],"metrics":["SUM(total_vendas)"],'
        '"filters":[],"grain":"day","assumptions":["metric is additive"]}'
    )
    valid_payload = (
        '{"intent":"ranking","tables":["events"],"relationships":[],'
        '"dimensions":["created_at"],"metrics":["COUNT(*)"],'
        '"filters":[],"grain":"day","assumptions":["count rows"]}'
    )

    with patch(
        "core.translator.ollama.chat",
        side_effect=[
            {"message": {"content": invalid_payload}},
            {"message": {"content": valid_payload}},
            {
                "message": {
                    "content": (
                        '{"sql":"SELECT created_at, COUNT(*) FROM events '
                        'GROUP BY created_at"}'
                    )
                }
            },
        ],
    ) as chat:
        result = translator.translate_to_sql("Liste eventos")

    assert result["sql"].startswith("SELECT created_at")
    assert len(validation_calls) == 2
    assert chat.call_count == 3
    assert (
        "total_vendas"
        in chat.call_args_list[1].kwargs["messages"][0]["content"]
    )


def test_translate_to_sql_sends_normalized_plan_and_temporal_hint():
    translator = _staged_translator()
    plan_payload = (
        '{"intent":"trend","tables":["events"],"relationships":[],'
        '"dimensions":["created_at"],"metrics":["COUNT(*)"],"filters":[],'
        '"grain":"day","assumptions":["created_at defines the period"]}'
    )
    sql_payload = '{"sql":"SELECT created_at, COUNT(*) FROM events GROUP BY created_at"}'

    with patch(
        "core.translator.ollama.chat",
        side_effect=[
            {"message": {"content": plan_payload}},
            {"message": {"content": sql_payload}},
        ],
    ) as chat:
        result = translator.translate_to_sql("Eventos de janeiro")

    assert result["sql"].startswith("SELECT created_at")
    assert chat.call_count == 2
    sql_stage_prompt = chat.call_args_list[1].kwargs["messages"][0]["content"]
    assert '"tables": ["events"]' in sql_stage_prompt
    expected_year = date.today().year
    assert f'"start": "{expected_year}-01-01"' in sql_stage_prompt
    assert f'"end": "{expected_year}-02-01"' in sql_stage_prompt


def test_sql_generation_runs_only_after_the_plan_validator():
    validation_events = []

    def validate(plan):
        validation_events.append(plan)

    translator = _staged_translator(plan_validator=validate)
    plan_payload = (
        '{"intent":"trend","tables":["events"],"relationships":[],'
        '"dimensions":["created_at"],"metrics":["COUNT(*)"],"filters":[],'
        '"grain":"day","assumptions":["created_at defines the period"]}'
    )
    sql_payload = '{"sql":"SELECT created_at, COUNT(*) FROM events GROUP BY created_at"}'

    def chat_response(*_args, **_kwargs):
        if len(validation_events) == 0:
            return {"message": {"content": plan_payload}}
        return {"message": {"content": sql_payload}}

    with patch(
        "core.translator.ollama.chat",
        side_effect=chat_response,
    ):
        result = translator.translate_to_sql("Eventos de janeiro")

    assert result["sql"].startswith("SELECT created_at")
    assert len(validation_events) == 1
    assert isinstance(validation_events[0], QueryPlan)


def test_planning_rejects_empty_assumptions():
    translator = _staged_translator()
    with patch(
        "core.translator.ollama.chat",
        return_value={
            "message": {
                "content": (
                    '{"intent":"list","tables":["events"],'
                    '"relationships":[],"dimensions":[],"metrics":[],'
                    '"filters":[],"grain":null,"assumptions":[]}'
                )
            }
        },
    ):
        with pytest.raises(TranslationStageError, match="must not be empty"):
            translator.plan_question("Liste eventos")


@pytest.mark.parametrize(
    ("stage", "response"),
    [
        ("planning", '{"intent":"missing"}'),
        ("sql_generation", '{"sql":'),
    ],
)
def test_staged_translation_returns_retryable_typed_errors(stage, response):
    translator = _staged_translator()
    plan = QueryPlan(
        intent="list",
        tables=("events",),
        relationships=(),
        dimensions=("created_at",),
        metrics=(),
        filters=(),
        grain=None,
        assumptions=("no aggregation requested",),
    )

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": response}},
    ):
        with pytest.raises(TranslationStageError) as error:
            if stage == "planning":
                translator.plan_question("Liste eventos")
            else:
                translator.translate_plan_to_sql(plan, "Liste eventos")

    assert error.value.stage == stage
    assert error.value.retryable is True