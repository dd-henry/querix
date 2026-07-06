import pytest
from core.prompter import Prompter

def test_build_system_prompt_vazio(tmp_path):
    """Testa se o prompt base é gerado corretamente mesmo sem arquivos ou schema."""
    prompter = Prompter(context_dir=str(tmp_path))
    prompt = prompter.build_system_prompt()
    
    # Verifica se as instruções fundamentais estão presentes
    assert "Você é um Engenheiro de Dados Sênior" in prompt
    assert "EXTRACT(MONTH FROM coluna)" in prompt
    
    # Não deve ter as seções de contexto, pois passamos pastas vazias e schema vazio
    assert "=== CONTEXTO: ESQUEMA ATUAL" not in prompt
    assert "=== CONTEXTO: REGRAS DE NEGÓCIO ===" not in prompt

def test_build_system_prompt_com_schema(tmp_path):
    """Testa se o schema lido do banco é anexado ao prompt."""
    prompter = Prompter(context_dir=str(tmp_path))
    mock_schema = "Tabela: clientes\n  - id (integer)"
    
    prompt = prompter.build_system_prompt(live_schema=mock_schema)
    assert "=== CONTEXTO: ESQUEMA ATUAL DO BANCO DE DADOS (Extraído do PostgreSQL) ===" in prompt
    assert "Tabela: clientes" in prompt

def test_build_system_prompt_com_arquivos_locais(tmp_path):
    """Testa a leitura correta de diretórios DDL e Regras de Negócio."""
    # Criando pastas falsas e arquivos de teste
    ddl_dir = tmp_path / "ddls"
    ddl_dir.mkdir(parents=True)
    (ddl_dir / "tabelas.sql").write_text("CREATE TABLE teste (id INT);", encoding="utf-8")
    
    rules_dir = tmp_path / "business_rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "regra1.md").write_text("Sempre considere o faturamento em Reais.", encoding="utf-8")
    
    prompter = Prompter(context_dir=str(tmp_path))
    prompt = prompter.build_system_prompt()
    
    assert "CREATE TABLE teste (id INT);" in prompt
    assert "Sempre considere o faturamento em Reais." in prompt