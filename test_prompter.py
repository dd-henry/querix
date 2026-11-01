from datetime import date

from core.prompter import Prompter

def test_build_system_prompt_vazio(tmp_path):
    """Testa se o prompt base é gerado corretamente mesmo sem arquivos ou schema."""
    prompter = Prompter(context_dir=str(tmp_path))
    prompt = prompter.build_system_prompt()
    
    # Verifica se as instruções fundamentais estão presentes
    assert "Você é um Engenheiro de Dados Sênior" in prompt
    assert "intervalo inclusivo no início e exclusivo no fim" in prompt
    assert "Use somente tabelas, colunas e relacionamentos declarados" in prompt

    # Não deve ter as seções de contexto, pois passamos pastas vazias e schema vazio
    assert "=== CONTEXTO: ESQUEMA ATUAL" not in prompt
    assert "=== CONTEXTO: REGRAS DE NEGÓCIO ===" not in prompt


def test_build_system_prompt_nao_inventa_filtros_de_identificacao(tmp_path):
    prompter = Prompter(context_dir=str(tmp_path))

    prompt = prompter.build_system_prompt()

    assert "Não crie filtros por identificador" in prompt
    assert "quando o usuário não informar esse valor" in prompt
    assert (
        "Sem esse valor, não transforme a pergunta em busca de um registro individual"
        in prompt
    )


def test_build_system_prompt_inclui_estrategias_analiticas_genericas(tmp_path):
    prompter = Prompter(context_dir=str(tmp_path))

    prompt = prompter.build_system_prompt(
        reference_date=date(2026, 10, 31),
    )

    assert "coluna >= início AND coluna < fim" in prompt
    assert "Data de referência para períodos incompletos: 2026-10-31." in prompt
    assert "use o ano da data de referência fornecida" in prompt
    assert "não invente um filtro temporal" in prompt
    assert "supporting_queries" in prompt
    assert "Use no máximo três supporting_queries" in prompt
    assert "Nunca invente identificadores" in prompt
    assert (
        "Cada uma deve usar somente tabelas, colunas, tipos e relações presentes"
        in prompt
    )
    assert "Use parâmetros nomeados para períodos e filtros" in prompt
    for domain_identifier in (
        "vendas",
        "itens_venda",
        "produtos",
        "valor_total",
        "forma_pagamento",
        "concluida",
    ):
        assert domain_identifier not in prompt.lower()


def test_build_system_prompt_com_schema(tmp_path):
    """Testa se o schema lido do banco é anexado ao prompt."""
    prompter = Prompter(context_dir=str(tmp_path))
    mock_schema = "Tabela: clientes\n  - id (integer)"
    
    prompt = prompter.build_system_prompt(live_schema=mock_schema)
    assert "=== CONTEXTO: ESQUEMA ATUAL DO BANCO DE DADOS ===" in prompt
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


def test_build_stage_prompts_define_planning_and_sql_contracts(tmp_path):
    prompter = Prompter(context_dir=str(tmp_path))

    planner_prompt = prompter.build_planner_prompt(
        live_schema="Tabela: events\n  - created_at (timestamp)",
    )
    sql_prompt = prompter.build_sql_generation_prompt(
        live_schema="Tabela: events\n  - created_at (timestamp)",
    )

    assert "ETAPA 1: PLANEJAMENTO ANALÍTICO" in planner_prompt
    assert "intent, tables, relationships, dimensions, metrics" in planner_prompt
    assert "intent deve ser uma descrição curta e não vazia" in planner_prompt
    assert "ETAPA 2: GERAÇÃO SQL" in sql_prompt
    assert "supporting_queries e grafico" in sql_prompt
    assert (
        "Todo placeholder nomeado usado no SQL deve ter uma chave correspondente"
        in sql_prompt
    )
    assert "nunca gere placeholders sem valor" in sql_prompt
    assert "Tabela: events" in planner_prompt
    assert "Tabela: events" in sql_prompt