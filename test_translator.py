import pytest
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