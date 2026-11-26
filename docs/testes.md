# Testes do projeto Querix

Este documento apresenta os testes existentes no projeto, seus objetivos,
como executá-los e o que seus resultados permitem concluir. O código dos testes
é a fonte de referência para os cenários e as regras efetivamente verificadas.

## Visão geral

| Grupo | Ferramentas | Objetivo | Dependências externas |
|---|---|---|---|
| Backend e API | pytest, mocks e fixtures | Verificar regras, serviços, repositórios e contratos HTTP | Em geral simuladas nos testes sem marcação de integração |
| Frontend | Vitest, Testing Library e jsdom | Verificar componentes React, estado, interações e cliente HTTP | API simulada |
| Navegador (E2E) | Playwright e Chromium | Verificar fluxos de interface em um navegador, inclusive em tamanhos de tela diferentes | As respostas da API são simuladas nos cenários; o frontend é servido pelo Vite |
| Integração com LLM | pytest e Ollama | Verificar uma tradução usando um modelo real | Serviço Ollama e modelo local |
| Avaliação de consultas | pytest e módulo de benchmark | Verificar o cálculo de métricas sobre resultados fornecidos | O benchmark não chama banco nem modelo |

Os testes usam *assertions* para comparar o comportamento observado com o
esperado. *Mocks* substituem serviços por respostas controladas; *fixtures*
preparam dados e recursos para cada teste. Isso torna os cenários reproduzíveis,
mas não substitui a verificação de serviços reais.

## 1. Backend: regras, persistência e modelo de linguagem

Os arquivos `test_*.py` na raiz cobrem componentes internos:

| Arquivo | Exemplos do que é verificado |
|---|---|
| [`test_prompter.py`](../test_prompter.py) | Construção de prompts com esquema, DDLs e regras de negócio; contratos das etapas de planejamento e geração de SQL. |
| [`test_translator.py`](../test_translator.py) | Extração de JSON das respostas do modelo, tratamento de respostas inválidas, contexto das conversas, geração de SQL e resumos. |
| [`test_llm.py`](../test_llm.py) | Configuração de provedores e adaptação de mensagens e respostas, incluindo erros e novas tentativas com serviços simulados. |
| [`test_analytical_queries.py`](../test_analytical_queries.py) | Planejamento de perguntas por um fluxo genérico orientado ao esquema, sem regras SQL específicas de domínio inseridas no código. |
| [`test_temporal.py`](../test_temporal.py) | Interpretação de períodos e limites de datas, inclusive casos que atravessam anos. |
| [`test_postgres.py`](../test_postgres.py) | Configuração do adaptador, leituras com DataFrames simulados, transações somente de leitura e tratamento de falhas de conexão. |
| [`test_database_connections.py`](../test_database_connections.py) | Armazenamento criptografado da conexão do banco de destino e ausência da string de conexão no status retornado. |
| [`test_conversations.py`](../test_conversations.py) | Persistência e recuperação de conversas e mensagens, isolamento por usuário, idempotência e limite de contexto. |
| [`test_query_history.py`](../test_query_history.py) | Histórico vinculado ao usuário e à conversa, deduplicação, fixação e exclusão. |
| [`test_predefined_queries.py`](../test_predefined_queries.py) | Validação de SQL somente de leitura no catálogo, parâmetros, consultas e favoritos. |
| [`test_users.py`](../test_users.py) | Perfis, papéis e proteção contra remoção do último administrador. |

Esses testes utilizam, conforme o caso, `MagicMock`, `patch`, `monkeypatch`,
diretórios temporários e DataFrames sintéticos. Uma verificação com banco
simulado não demonstra que o PostgreSQL real está acessível ou que executará
todas as consultas corretamente.

## 2. API: rotas e serviços

Os testes em [`api/tests/`](../api/tests/) verificam a aplicação HTTP e suas
colaborações, em geral com dependências externas substituídas por objetos
simulados:

| Área | Arquivos | Exemplos do que é verificado |
|---|---|---|
| Aplicação e configuração | `test_app.py`, `test_config.py`, `test_dependencies.py` | Inicialização, health check, erros, origens permitidas, configurações e dependências autenticadas. |
| Autenticação e sessão | `test_auth_routes.py`, `test_service.py`, `test_session.py` | Cadastro, login, logout, perfis, cookies, sessões e tratamento de erros sem expor tokens. |
| Administração | `test_admin_routes.py` | Permissões, listagem de usuários, alteração de papel ou status e redefinição de senha. |
| Conexão e sincronização | `test_database_settings.py`, `test_sync_routes.py` | Permissões de configuração, teste antes de salvar a conexão, falhas e sincronização de esquema. |
| Chat | `test_chat_translate_routes.py`, `test_chat_execute_routes.py`, `test_chat_service.py` | Tradução, execução, modo de revisão, erros, cancelamento, progresso e isolamento das solicitações. |
| Conversas | `test_conversation_routes.py`, `test_conversation_item_routes.py`, `test_conversation_schemas.py` | Criação, listagem, restauração, favoritos, exclusão, autorização e formato das respostas. |
| Histórico e consultas compartilhadas | `test_history_routes.py`, `test_predefined_routes.py` | Escopo por usuário, parâmetros, execução, favoritos e operações de histórico. |
| Qualidade e segurança da consulta | `test_query_validation.py`, `test_schema_profile.py`, `test_result_quality.py`, `test_result_serializer.py` | Validação de identificadores e SQL, perfil do esquema, diagnósticos e serialização limitada dos resultados. |

Alguns testes combinam rotas ou serviços com repositórios concretos e adaptador
de banco simulado. Eles verificam o contrato entre camadas, não uma integração
com uma instância PostgreSQL real.

## 3. Frontend: componentes e estado

O Vitest executa os testes `*.test.ts` e `*.test.tsx` em
[`web/src/`](../web/src/), utilizando `jsdom` e Testing Library:

- **Aplicação e autenticação:** `App.test.tsx`, `AppShell.test.tsx`,
  `AuthProvider.test.tsx` e `AuthPage.test.tsx` verificam renderização, sessão,
  login, cadastro, erros e navegação acessível.
- **Cliente HTTP:** `api/client.test.ts` verifica requisições com credenciais,
  respostas, erros e comunicação com endpoints.
- **Chat:** `ChatWorkspace.test.tsx`, `MessageList.test.tsx` e
  `useChat.test.tsx` cobrem envio, progresso, cancelamento, mensagens,
  retomada, resultados, gráficos, exportação e cache em memória ao trocar de
  conversa.
- **Navegação e funcionalidades:** `AuthenticatedApp.test.tsx`,
  `ConversationSidebar.test.tsx`, `HistoryPanel.test.tsx` e
  `PredefinedQueriesPanel.test.tsx` verificam troca de painéis, conversas,
  histórico e consultas compartilhadas.
- **Administração e configurações:** `UserAdminPanel.test.tsx`,
  `DatabaseConnectionSettings.test.tsx` e `SyncDatabaseButton.test.tsx`
  verificam permissões, operações, mensagens de erro e prevenção de
  solicitações duplicadas.

Esses testes simulam a interface no `jsdom`: são úteis para comportamento e
acessibilidade, mas não reproduzem completamente a renderização visual de um
navegador.

## 4. Fluxos no navegador

Os testes em [`web/e2e/`](../web/e2e/) usam Playwright com Chromium:

- `auth.spec.ts`: login, cadastro, conta bloqueada e logout.
- `chat.spec.ts`: envio, revisão, repetição, gráfico, CSV e estabilidade da
  largura do chat com SQL extenso em diferentes tamanhos de tela.
- `parity.spec.ts`: navegação entre painéis, destaque da seção ativa,
  restauração e isolamento de conversas, sincronização e fluxos em celular.
- `smoke.spec.ts`: carregamento inicial da tela de autenticação.

O Playwright inicia o servidor Vite ou reutiliza um servidor existente em
`http://127.0.0.1:5173`, fora do CI, conforme
[`playwright.config.ts`](../web/playwright.config.ts). As respostas de API dos
cenários são interceptadas e simuladas: esses testes exercitam o navegador e a
interface, mas não comprovam a integração completa com backend, Supabase,
PostgreSQL ou LLM reais. Apesar de verificarem tamanhos de tela de celular,
utilizam o projeto Chromium configurado, não um dispositivo físico.

## 5. Integração real com Ollama

[`test_integration_ollama.py`](../test_integration_ollama.py) envia uma pergunta
ao Ollama usando o modelo `qwen2.5-coder:7b`. O teste verifica se a resposta é
um dicionário com SQL que contém `SELECT` e referência a `usuarios`. Ele usa
um esquema fornecido no próprio teste; não executa o SQL em um banco nem avalia
sua correção semântica completa.

O cenário possui a marca `integration` em [`pytest.ini`](../pytest.ini). É
necessário ter o Ollama acessível e o modelo disponível; por depender de um
modelo real, o resultado pode variar e a execução pode demorar. Configure o
provedor local quando necessário.

## 6. Avaliação de consultas e medições

[`evaluation/query_benchmark.py`](../evaluation/query_benchmark.py) agrega
resultados registrados pelo chamador: taxa de consultas executáveis, cobertura
de colunas esperadas, taxa de resultados vazios, latência média e atendimento
de limites de linhas. Os testes em
[`evaluation/test_query_benchmark.py`](../evaluation/test_query_benchmark.py)
verificam os cálculos com dados sintéticos e a validação de entradas.

O benchmark **não executa as perguntas, não mede a latência por conta própria
e não determina se os resultados respondem corretamente à pergunta**. Colunas
esperadas ou SQL executável não são prova de acurácia semântica. Para produzir
evidências empíricas, é necessário executar casos reais, registrar tempos com
um procedimento definido e comparar os resultados com referências corretas.
Os exemplos sintéticos não devem ser apresentados como medições reais.
Consulte [Avaliação de consultas analíticas](avaliacao_consultas.md) para o
contrato e as fórmulas.

## 7. Como executar

Execute os comandos na raiz do repositório, com as dependências do projeto
instaladas. Para Python, use o ambiente virtual com `pytest` instalado; para
frontend, são necessários Node.js e as dependências de `web/`. O Playwright
também precisa do navegador Chromium instalado (`npx playwright install
chromium`, executado em `web/`, quando necessário).

```bash
# Backend e API sem testes marcados como integração
venv/bin/python -m pytest -m "not integration" -q

# Teste de integração: requer Ollama e o modelo disponível
venv/bin/python -m pytest -m integration -q

# Todos os testes Python, incluindo integração
venv/bin/python -m pytest -q

# Apenas o contrato do benchmark
venv/bin/python -m pytest evaluation/test_query_benchmark.py -q

# Frontend: execução única
npm --prefix web test -- --run

# Navegador
npm --prefix web run e2e
```

Para executar um teste específico, por exemplo:

```bash
venv/bin/python -m pytest -v test_translator.py::test_clean_sql_response_json_perfeito
npm --prefix web test -- --run src/app/AuthenticatedApp.test.tsx
npm --prefix web run e2e -- --grep "active navigation item"
```

O comando `npm --prefix web run check` reúne verificação de tipos, lint e
testes Vitest; `npm --prefix web run build` também verifica tipos e produz o
build. Eles complementam os testes, mas não executam o Playwright. Para ver
mensagens impressas pelo pytest, acrescente `-s`.

## 8. Verificações manuais

[`teste_db.py`](../teste_db.py) tenta conectar ao banco configurado e
[`teste_ollama.py`](../teste_ollama.py) envia uma solicitação ao Ollama com o
modelo `qwen2.5-coder:7b`. São verificações manuais de infraestrutura, não
testes automatizados com asserções; dependem dos serviços reais e de sua
configuração local. Seus logs devem ser inspecionados para determinar o
resultado.

## 9. Registro de execução

Em 25/11/2026, no ambiente local:

| Execução | Resultado |
|---|---|
| pytest sem integração | 322 passaram; 1 teste de integração foi excluído. |
| Vitest | 121 passaram em 15 arquivos. |
| Playwright | 10 passaram e 6 falharam em 16 cenários. |

Entre as falhas do Playwright observadas, três cenários de autenticação
encontraram seletores de senha ambíguos; dois cenários de chat não encontraram
as mensagens esperadas e um cenário de navegação não encontrou o resultado
esperado. O teste de integração com Ollama não foi executado nessa
verificação.

Na execução enviada posteriormente, os 323 testes Python passaram, incluindo a
integração com Ollama, e os 121 testes Vitest passaram. As mesmas seis falhas
de navegador foram observadas.

Após corrigir seletores e simulações de API dos cenários de navegador, os 16
testes Playwright passaram em uma nova execução local. Esses resultados são
retratos de execuções específicas, não garantias para outros ambientes ou
serviços externos.
