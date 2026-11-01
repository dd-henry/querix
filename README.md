# Ask-SQL 🤖

> Converse com seu banco de dados usando linguagem natural.

O **Ask-SQL** é uma ferramenta interativa que traduz perguntas em linguagem natural para consultas SQL, permitindo que você explore seus dados sem precisar escrever código SQL. A aplicação pode utilizar um modelo local via **Ollama**, o **Gemini** via Google AI Studio ou qualquer modelo compatível disponível no **OpenRouter**, conecta-se a um banco de dados **PostgreSQL** para executar as consultas e exibe os resultados de forma amigável.

## ✨ Recursos

*   **Tradução de Linguagem Natural para SQL:** Faça perguntas como "quantos usuários se cadastraram no último mês?" e obtenha a consulta SQL correspondente.
*   **Execução Direta no Banco de Dados:** Conecta-se ao seu banco de dados PostgreSQL para executar as consultas geradas.
*   **Consultas Compartilhadas:** Desenvolvedores e DBAs podem cadastrar, editar e excluir consultas somente de leitura para toda a equipe, com tags, parâmetros e favoritos por usuário.
*   **Histórico personalizado de consultas:** Cada usuário pode consultar, fixar, excluir e executar novamente consultas anteriores sem misturar dados entre contas.
*   **Conversas privadas e retomáveis:** Cada usuário aprovado pode iniciar conversas separadas, retomar sessões anteriores e favoritar as mais importantes.
*   **Arquitetura Modular:** Código organizado em componentes com responsabilidades claras, facilitando a manutenção e extensão.
*   **Engenharia de Prompt Avançada:** Utiliza o esquema atual, os relacionamentos, DDLs e regras de negócio para gerar planos sem SQL específico de um nicho.
*   **Suíte de Testes Abrangente:** Inclui testes unitários e de integração para garantir a qualidade e a confiabilidade do código.

## 🏗️ Arquitetura e Fluxo de Dados

O projeto é construído com uma arquitetura modular, garantindo que cada componente tenha uma única responsabilidade.

```mermaid
graph TD
    A[Usuário via React] --> B(web/);
    B --> N(FastAPI api/);
    N --> C{Prompter};
    D[Schema e relacionamentos do Banco] --> C;
    E[Regras de Negócio] --> C;
    C --> F{Translator (Ollama, Gemini ou OpenRouter)};
    F --> G[Consulta SQL Gerada];
    G --> H{Executor (Postgres)};
    H --> I[Resultados (DataFrame)];
    I --> B;
    B --> A;
```

1.  **Interface web (`web/`):** Frontend React + TypeScript + Vite. Mantém o estado do chat no navegador e chama a API por cookie de sessão.
2.  **API (`api/`):** Backend FastAPI que expõe autenticação, conversas, chat, histórico, consultas compartilhadas, administração e sincronização do schema.
3.  **Engenharia de Prompt (`core/prompter.py`):** Monta o "System Prompt" com estratégias analíticas genéricas, data de referência, regras de negócio, DDLs, tabelas, colunas e relacionamentos atuais. O código não contém SQL de um domínio específico.
4.  **Motor de Tradução (`core/translator.py`):** Comunica-se com o provedor LLM configurado em todas as perguntas, enviando o contexto da conversa e tratando a resposta estruturada sem interceptar vocabulário de negócio. O provedor é selecionado por `LLM_PROVIDER` (`local` para Ollama, `google` para Gemini ou `openrouter` para OpenRouter).
5.  **Banco de Dados (`database/postgres.py`):** Implementa a conexão com o PostgreSQL usando SQLAlchemy e entrega ao planejador tabelas, colunas, comentários e chaves estrangeiras do schema público.

## 🚀 Instalação e Configuração

Siga os passos abaixo para configurar o ambiente de desenvolvimento.

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-seu-repositorio>
    cd ask-sql
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as variáveis de ambiente:**
    Crie um arquivo `.env` na raiz do projeto e adicione as credenciais do seu banco de dados e a URL do Ollama.
    ```env
    DB_HOST=localhost
    DB_PORT=5432
    DB_USER=seu_usuario
    DB_PASSWORD=sua_senha
    DB_NAME=seu_banco
    OLLAMA_API_URL=http://localhost:11434
    LLM_PROVIDER=local
    OLLAMA_MODEL=qwen2.5-coder:7b
    GEMINI_MODEL=gemini-flash-latest
    GEMINI_MAX_RETRIES=2
    GEMINI_API_KEY=
    OPENROUTER_MODEL=openai/gpt-4o-mini
    OPENROUTER_MAX_RETRIES=2
    OPENROUTER_API_KEY=
    LLM_REQUEST_TIMEOUT_SECONDS=180
    ASK_SQL_USER=nome.do.usuario
    ASK_SQL_ROLE=viewer
    ```

`LLM_PROVIDER=local` mantém o fluxo atual com Ollama. Para testar o Gemini, use
`LLM_PROVIDER=google`, informe `GEMINI_API_KEY` e reinicie a API. A chave deve
permanecer somente no ambiente do backend, nunca no frontend ou em commits.
Falhas transitórias do Gemini recebem até `GEMINI_MAX_RETRIES` novas tentativas
com backoff; erros permanentes continuam sendo apresentados como falha do
provedor.

Para testar um modelo do OpenRouter, use `LLM_PROVIDER=openrouter`, informe
`OPENROUTER_API_KEY` e o identificador do modelo em `OPENROUTER_MODEL`. O
identificador usa o formato publicado pelo OpenRouter, como
`openai/gpt-4o-mini`. A chave permanece somente no ambiente do backend.
Cada chamada ao provedor usa 180 segundos por padrão; ajuste
`LLM_REQUEST_TIMEOUT_SECONDS` se o modelo ou a rede exigirem mais tempo.
Falhas transitórias respeitam o cabeçalho `Retry-After` do OpenRouter antes de
tentar novamente, evitando novas chamadas durante uma janela de rate limit.

Configure também o Supabase Auth:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_chave_anon_publica
```

O cadastro exige confirmação de email e cria um perfil `pending`. Um admin precisa aprová-lo antes do acesso. Os papéis são `user`, `dev` e `admin`; os status são `pending`, `approved`, `rejected` e `disabled`. A chave `SUPABASE_ANON_KEY` deve permanecer no backend, nunca no navegador.

## 🏃 Como Usar

### Frontend web React + API FastAPI

O frontend e a API são processos independentes. Em desenvolvimento, o Vite usa a porta `5173` e encaminha `/api` para a API na porta `8000`.

1. Configure no `.env` as variáveis da API:

```env
WEB_ORIGIN=http://127.0.0.1:5173
SESSION_SECRET=gere-um-segredo-aleatorio-com-mais-de-32-caracteres
DATABASE_URL=postgresql+psycopg2://usuario@127.0.0.1:5432/banco
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_chave_anon_publica
OLLAMA_API_URL=http://127.0.0.1:11434
LLM_PROVIDER=local
OLLAMA_MODEL=qwen2.5-coder:7b
GEMINI_MODEL=gemini-flash-latest
GEMINI_MAX_RETRIES=2
GEMINI_API_KEY=
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_MAX_RETRIES=2
OPENROUTER_API_KEY=
LLM_REQUEST_TIMEOUT_SECONDS=180
```

`DATABASE_URL` pode ser substituída pelos campos `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DBNAME`. Em desenvolvimento local, mantenha `COOKIE_SECURE=false`; ative-o somente quando a aplicação estiver atrás de HTTPS. Nunca coloque `SESSION_SECRET`, credenciais do banco ou a chave `service_role` do Supabase no frontend.

2. Inicie a API em um terminal:

```bash
venv/bin/uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

3. Instale as dependências do frontend uma vez e inicie-o em outro terminal:

```bash
npm --prefix web install
npm --prefix web run dev
```

Abra <http://127.0.0.1:5173>. O navegador conversa apenas com o frontend; o proxy do Vite encaminha as chamadas `/api` para `127.0.0.1:8000`, preservando o cookie de sessão.

Para validar o frontend:

```bash
npm --prefix web run check
npm --prefix web run build
npm --prefix web run e2e
```

Os testes E2E usam fixtures HTTP do Playwright e iniciam o servidor Vite automaticamente; a API real não precisa estar ativa para essa suíte.

### Conversas e histórico de consultas

Use **＋ Nova conversa** na barra lateral para começar um chat em branco. A conversa é salva quando você envia a primeira mensagem e recebe um título baseado nesse prompt. As conversas pertencem à sua conta; ao selecionar uma conversa salva, o chat restaura as mensagens, o SQL e os erros anteriores.

Os resultados das consultas, incluindo as linhas retornadas, não são salvos na conversa. O SQL de uma conversa reaberta é exibido, mas não é executado automaticamente. Use a ação de execução apresentada com o SQL para buscar resultados atuais.

O **Histórico de consultas** é separado das conversas: reúne consultas executadas e permite fixar, excluir ou executá-las novamente. Ao excluir uma conversa após confirmar, as mensagens e os registros do histórico vinculados a ela também são excluídos; registros antigos sem vínculo com uma conversa são preservados.

Você pode favoritar conversas para mantê-las. Conversas não favoritas sem atividade por um ano são removidas quando o histórico de conversas é aberto. A exclusão manual também exige confirmação.

## ✅ Estratégia de Testes

O projeto utiliza `pytest` para garantir a qualidade do código, com uma clara separação entre testes unitários e de integração.

### Testes Unitários
Valida a lógica interna dos componentes de forma isolada, usando *mocks* para simular dependências externas.


### Testes de Integração
Valida o fluxo completo, envolvendo a comunicação real com a API do Ollama.

### Benchmark de qualidade

O benchmark de consultas é genérico e trabalha apenas com perguntas, colunas
esperadas, restrições opcionais de linhas e resultados registrados. Ele mede
taxa de consultas executáveis, cobertura de colunas esperadas, taxa de
resultados vazios e latência sem embutir SQL ou depender de um banco de
produção. Consulte [`docs/avaliacao_consultas.md`](docs/avaliacao_consultas.md)
para o contrato e um exemplo.


### Executando os Testes

Graças às configurações no arquivo `pytest.ini`, você pode executar diferentes suítes de teste:

    ```bash
    pytest -v
    ```
    ```bash
    pytest -m "not integration" -v
    ```
    ```bash
    pytest -m "integration" -v
    ```

### Consultas compartilhadas

Consultas compartilhadas aparecem na barra lateral e são executadas diretamente com parâmetros vinculados pelo SQLAlchemy. O SQL cadastrado deve começar com `SELECT` ou `WITH` e não pode conter múltiplas instruções. Para cadastrar parâmetros, use JSON no formato:

```json
[{"name": "status", "label": "Status", "required": true}]
```

O SQL correspondente pode usar `:status`. Favoritos são individuais por UUID autenticado; a consulta e seus metadados são compartilhados com todos os usuários aprovados.

Para promover o primeiro admin, crie uma conta pela tela de cadastro, confirme o email e execute uma única vez:

```bash
./venv/bin/python bootstrap_admin.py email@empresa.com
```
