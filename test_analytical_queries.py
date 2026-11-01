from unittest.mock import patch

from core.translator import Translator


def test_domain_questions_share_the_same_llm_planning_path():
    translator = Translator(system_prompt="schema context", model_name="test")
    responses = [
        '{"sql":"SELECT product_name FROM inventory"}',
        '{"sql":"SELECT customer_name FROM customers"}',
    ]

    with patch(
        "core.translator.ollama.chat",
        side_effect=[
            {"message": {"content": responses[0]}},
            {"message": {"content": responses[1]}},
        ],
    ) as chat:
        first = translator.translate_to_sql("Quais produtos foram vendidos?")
        second = translator.translate_to_sql("Quais clientes estão ativos?")

    assert first["sql"] == "SELECT product_name FROM inventory"
    assert second["sql"] == "SELECT customer_name FROM customers"
    assert chat.call_count == 2


def test_empty_question_is_not_intercepted_by_domain_logic():
    translator = Translator(system_prompt="schema context", model_name="test")

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT 1"}'}},
    ) as chat:
        result = translator.translate_to_sql("")

    assert result["sql"] == "SELECT 1"
    assert chat.call_count == 1


def test_period_parameters_are_not_injected_before_ollama():
    translator = Translator(system_prompt="schema context", model_name="test")

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": '{"sql":"SELECT created_at FROM events"}'}},
    ) as chat:
        result = translator.translate_to_sql("Quais eventos ocorreram em agosto?")

    assert result == {"sql": "SELECT created_at FROM events", "supporting_queries": []}
    assert chat.call_args.kwargs["messages"][-1] == {
        "role": "user",
        "content": "Quais eventos ocorreram em agosto?",
    }


def test_year_only_question_does_not_receive_a_python_month():
    translator = Translator(system_prompt="schema context", model_name="test")

    with patch(
        "core.translator.ollama.chat",
        return_value={
            "message": {
                "content": '{"sql":"SELECT COUNT(*) FROM events","parameters":{}}'
            }
        },
    ):
        result = translator.translate_to_sql("Quantos eventos ocorreram em 2025?")

    assert result["parameters"] == {}
    assert result["sql"] == "SELECT COUNT(*) FROM events"


def test_model_can_return_a_generic_schema_grounded_supporting_query():
    translator = Translator(system_prompt="schema context", model_name="test")

    with patch(
        "core.translator.ollama.chat",
        return_value={
            "message": {
                "content": (
                    '{"sql":"SELECT category, COUNT(*) FROM records GROUP BY category",'
                    '"supporting_queries":[{"key":"trend","title":"Monthly trend",'
                    '"sql":"SELECT month, COUNT(*) FROM records GROUP BY month",'
                    '"parameters":{}}]}'
                )
            }
        },
    ):
        result = translator.translate_to_sql("Mostre categorias e uma leitura complementar.")

    assert result["supporting_queries"] == [
        {
            "key": "trend",
            "title": "Monthly trend",
            "sql": "SELECT month, COUNT(*) FROM records GROUP BY month",
            "parameters": {},
        }
    ]


def test_model_sql_shape_is_preserved_without_domain_rewriting():
    translator = Translator(system_prompt="schema context", model_name="test")
    sql = "SELECT region, AVG(score) AS average_score FROM assessments GROUP BY region"

    with patch(
        "core.translator.ollama.chat",
        return_value={"message": {"content": f'{{"sql":"{sql}"}}'}},
    ):
        result = translator.translate_to_sql("Compare o desempenho por região.")

    assert result["sql"] == sql
