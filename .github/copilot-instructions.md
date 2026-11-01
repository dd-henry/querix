# Instruções para Copilot neste repositório

## Comandos

- Instalar dependências: `pip install -r requirements.txt`
- Iniciar a API: `venv/bin/uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload`
- Executar toda a suíte: `pytest -v`
- Executar somente testes sem integração externa: `pytest -m "not integration" -v`
- Executar testes de integração com o Ollama: `pytest -m integration -v`
- Executar um teste específico: `pytest -v test_translator.py::test_clean_sql_response_json_perfeito`

Os testes de integração dependem de serviços externos locais, como Ollama e/ou PostgreSQL. Os testes unitários isolam essas dependências com mocks. Não há comando de lint configurado no projeto.

## Arquitetura

- O fluxo de perguntas é: `database/postgres.py` lê o esquema atual → `core/prompter.py` combina esse esquema com DDLs e regras de negócio opcionais em `context/ddls/` e `context/business_rules/` → `core/translator.py` envia o prompt ao provedor configurado em `LLM_PROVIDER` (`local`/Ollama ou `google`/Gemini) e interpreta o JSON → a aplicação apresenta o SQL para revisão e executa-o no PostgreSQL.
- `database/base.py` define a interface do adaptador; `database/postgres.py` implementa a conexão SQLAlchemy e entrega resultados como DataFrames pandas.
- `api/auth/service.py` integra o Supabase Auth. `database/users.py` mantém perfis e papéis (`user`, `dev`, `admin`) com estados de aprovação. O catálogo de consultas compartilhadas e os favoritos ficam em `database/predefined_queries.py`; o histórico isolado por usuário fica em `database/query_history.py`. Esses repositórios inicializam suas tabelas e índices no PostgreSQL.

## Convenções específicas

- Preserve a separação de responsabilidades: fluxo e estado da API em `api/`, componentes de interface em `web/`, integrações de LLM/autenticação em `core/` e persistência em repositórios de `database/`.
- Repositórios recebem o adaptador de banco no construtor; use `execute_query` para leituras e `execute_command` para alterações. Para valores SQL, use parâmetros nomeados do SQLAlchemy, não interpolação de strings.
- Consultas compartilhadas são somente leitura: `PredefinedQueryRepository.validate_query` aceita SQL iniciado por `SELECT` ou `WITH`, sem múltiplas instruções; parâmetros são armazenados como JSONB e vinculados na execução. Não confunda essa regra do catálogo com o fluxo de SQL gerado pelo chat.
- O histórico e os favoritos devem permanecer vinculados ao UUID do usuário autenticado. Ao alterar operações desses repositórios, preserve o escopo do usuário nas consultas e mutações.
- Testes unitários de persistência usam `MagicMock` para o adaptador e DataFrames sintéticos para respostas de leitura. O teste real do Ollama é marcado com `@pytest.mark.integration`; o Gemini é mockado nos testes unitários.
- Para trabalho spec-driven, a skill TLC está disponível em `.claude/skills/tlc-spec-driven/SKILL.md` e também em `.cursor/skills/` e `.windsurf/skills/`. Use-a quando o ambiente carregar essa skill; não presuma que Copilot a invoque automaticamente.
- A configuração do PostgreSQL MCP no VS Code está documentada em `docs/postgres-mcp.md`; use o servidor em modo restrito e nunca leia ou exponha credenciais do `.env.mcp`.

Consulte `README.md`, `docs/arquitetura_e_funcionamento.md` e `docs/testes.md` para detalhes do fluxo, configuração e cobertura.
