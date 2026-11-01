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
