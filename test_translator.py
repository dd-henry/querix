import pytest
from unittest.mock import patch

from core.translator import Translator

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


def test_translate_to_sql_uses_deterministic_product_query_before_ollama(translator):
    with patch("core.translator.ollama.chat") as chat:
        resultado = translator.translate_to_sql(
            "Quais foram os produtos vendidos em agosto de 2026?"
        )

    assert resultado["intent"] == "product_sales"
    assert "SUM(iv.quantidade) AS quantidade" in resultado["sql"]
    assert "SUM(iv.subtotal) AS valor" in resultado["sql"]
    assert resultado["parameters"]["period_start"] == (
        "2026-08-01T00:00:00+00:00"
    )
    chat.assert_not_called()


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