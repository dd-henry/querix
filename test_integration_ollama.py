import pytest
from core.translator import Translator

# Usamos um marcador (mark) customizado. Como testes com LLMs demoram, 
# é comum marcá-los para podermos rodar separadamente dos testes rápidos.
@pytest.mark.integration
def test_ollama_gera_sql_estruturado():
    """Testa se o Ollama consegue receber um prompt, entender o JSON e retornar SQL válido."""
    
    # 1. Configuração: Usamos um prompt de sistema bem enxuto, mas que exige o JSON.
    system_prompt = (
        "Você é um assistente de banco de dados. "
        "Retorne EXCLUSIVAMENTE um JSON com as chaves 'sql' e 'grafico'.\n\n"
        "=== CONTEXTO: ESQUEMA DO BANCO DE DADOS (DDLs) ===\n"
        "CREATE TABLE usuarios (id INT, nome VARCHAR(100), email VARCHAR(255), data_criacao TIMESTAMP);\n"
    )
    translator = Translator(system_prompt=system_prompt, model_name="qwen2.5-coder:7b")
    
    # 2. Execução: Bate no Ollama de verdade (pode demorar alguns segundos)
    resultado = translator.translate_to_sql("Liste todos os usuários cadastrados.")
    
    print("\n\n[DEBUG] === PROMPT (COM DDL) ENVIADO PARA A IA ===")
    print(system_prompt)
    print("====================================================\n")

    
    # 3. Validações (Comportamentais, não exatas)
    assert isinstance(resultado, dict), "O tradutor não devolveu um dicionário."
    assert "sql" in resultado, "O JSON retornado pelo Ollama não contém a chave 'sql'."
    assert "SELECT" in resultado["sql"].upper(), "A query gerada não parece ser um SELECT."
    assert "USUARIOS" in resultado["sql"].upper(), "A query gerada não parece estar buscando a tabela 'usuarios."