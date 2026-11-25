<div align="center">

# Ask SQL

**Perguntas em linguagem natural. Consultas SQL. Dados para apoiar decisões.**

Uma aplicação web que utiliza modelos de linguagem para transformar perguntas
em consultas PostgreSQL e apresentar os resultados de forma interativa.

`React` · `TypeScript` · `FastAPI` · `PostgreSQL` · `Supabase Auth` · `LLM`

</div>

---

## Sumário

- [Visão geral](#visão-geral)
- [Funcionalidades](#funcionalidades)
- [Como funciona](#como-funciona)
- [Arquitetura](#arquitetura)
- [Decisões arquiteturais](#decisões-arquiteturais)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Executando localmente](#executando-localmente)
- [Configuração](#configuração)
- [Publicação com Docker e Dokploy](#publicação-com-docker-e-dokploy)
- [Testes e avaliação](#testes-e-avaliação)
- [Segurança, privacidade e limitações](#segurança-privacidade-e-limitações)
- [Documentação complementar](#documentação-complementar)

## Visão geral

Consultar dados em um banco relacional costuma exigir conhecimento de SQL, da
estrutura das tabelas e das regras de negócio. O Ask SQL procura reduzir essa
barreira: a pessoa descreve o que deseja saber e a aplicação utiliza um modelo
de linguagem (*LLM*) para planejar e gerar uma consulta SQL.

O SQL é produzido com base no esquema do banco consultado e em contextos
opcionais fornecidos pela organização. O resultado pode ser apresentado em
tabela, com resumo, gráfico e exportação CSV, conforme os dados e a resposta
gerada.

> **Exemplo:** “Quais foram as vendas do mês de agosto?” pode dar origem a uma
> consulta agregada sobre os dados disponíveis. A consulta e sua interpretação
> dependem do esquema, do contexto e do modelo configurado.

O projeto é uma ferramenta de apoio à análise, **não uma garantia de correção
dos resultados**. Consultas e conclusões devem ser revisadas, especialmente
quando utilizadas em decisões importantes.

## Funcionalidades

| Recurso | Descrição |
|---|---|
| Perguntas em linguagem natural | Tradução de perguntas para SQL usando Ollama, Gemini ou OpenRouter. |
| Revisão do SQL | Possibilidade de revisar a consulta antes de executá-la; a execução automática também pode ser escolhida. |
| Resultados | Exibição em tabela, resumo breve, gráficos quando aplicáveis e exportação CSV. |
| Conversas | Retomada de conversas, contexto de turnos anteriores e favoritos individuais. |
| Histórico | Listagem, fixação, exclusão e reexecução de consultas por usuário. |
| Consultas compartilhadas | Catálogo de consultas cadastradas com busca, favoritos individuais e parâmetros. |
| Administração | Aprovação de usuários, definição de papéis e configuração global do banco consultado. |
| Contexto adicional | Inclusão opcional de DDLs e regras de negócio para orientar o modelo. |

## Como funciona

```mermaid
sequenceDiagram
    actor U as Usuário
    participant W as Frontend React
    participant A as API FastAPI
    participant I as Banco interno
    participant D as Banco consultado
    participant L as Provedor LLM

    U->>W: Faz uma pergunta
    W->>A: Envia pergunta e contexto da conversa
    A->>I: Consulta e registra mensagens
    A->>D: Obtém esquema e relacionamentos
    A->>L: Envia contexto para planejamento
    L-->>A: Retorna plano analítico em JSON
    A->>A: Valida o plano contra o esquema
    A->>L: Solicita SQL para o plano validado
    L-->>A: Retorna SQL e metadados
    A-->>W: Apresenta SQL para revisão, quando habilitada
    U->>W: Autoriza execução
    W->>A: Solicita execução
    A->>D: Executa consulta em transação somente leitura
    D-->>A: Retorna dados
    A->>L: Solicita resumo do resultado
    A->>I: Registra consulta no histórico
    A-->>W: Retorna dados, resumo e avisos
    W-->>U: Exibe resultado e opções de exportação
```

O diagrama representa o caminho com revisão habilitada. Sem revisão, o fluxo
prossegue para a execução automaticamente. A aplicação também pode executar
consultas complementares, quando propostas e validadas, e tentar reparar uma
consulta após falha do banco.

### Etapas principais

1. **Contexto:** a API coleta o esquema do banco consultado e combina essas
   informações com instruções, data de referência, DDLs e regras opcionais.
2. **Planejamento:** o LLM retorna uma representação estruturada da intenção,
   tabelas, dimensões, métricas e filtros. O plano é validado contra o esquema.
3. **Geração:** o LLM recebe o plano e produz SQL e metadados. O sistema valida
   a forma do SQL antes de permitir sua execução.
4. **Revisão e execução:** o SQL pode ser revisado na interface e é executado
   pelo PostgreSQL em uma transação somente leitura.
5. **Apresentação:** os dados retornados são serializados e apresentados ao
   usuário. O LLM tenta produzir um resumo; se essa etapa falhar, a aplicação
   utiliza um resumo neutro baseado na quantidade de linhas.

O sistema utiliza até seis turnos anteriores concluídos da conversa como
contexto. Ao reabrir uma conversa, as mensagens e o SQL são recuperados, mas
as linhas dos resultados não são persistidas na conversa: é necessário
reexecutar a consulta para obter os dados atuais.

## Arquitetura

```mermaid
flowchart LR
    U[Usuário] --> W[Frontend<br/>React + TypeScript]
    W -->|HTTP / JSON| A[API<br/>FastAPI]
    A --> AUTH[Supabase Auth]
    A --> I[(PostgreSQL<br/>banco interno)]
    A --> C[Contexto e validação<br/>Prompter · Plano · Translator]
    C --> L[LLM<br/>Ollama · Gemini · OpenRouter]
    A --> D[(PostgreSQL<br/>banco consultado)]
    D -->|Esquema e relacionamentos| C
```

| Camada | Responsabilidade |
|---|---|
| **Interface** | Interação, estado da conversa, administração e apresentação de resultados. |
| **API** | Autenticação, autorização, orquestração do chat, rotas e contratos HTTP. |
| **Núcleo** | Construção de contexto, interpretação temporal, planejamento, validação e integração com LLM. |
| **Persistência** | Acesso PostgreSQL e repositórios para perfis, conversas, histórico, catálogo e configuração. |
| **Serviços externos** | Supabase Auth para identidade e um provedor de modelo de linguagem para tradução e resumo. |

### Dois papéis de banco de dados

- **Banco interno:** armazena perfis, conversas, histórico, consultas
  compartilhadas e a configuração cifrada da conexão consultada. É indicado
  por `DATABASE_URL` ou pelas variáveis `POSTGRES_*` e deve ser compatível com
  o projeto Supabase utilizado, incluindo o schema `auth`.
- **Banco consultado:** é o PostgreSQL cujos dados a aplicação analisa. Um
  administrador configura sua connection string na interface. Essa
  configuração é **global** e armazenada no banco interno.

São responsabilidades distintas, mas podem apontar para a mesma instância;
separá-las ajuda a limitar permissões e a evitar confusão entre dados da
aplicação e dados analisados. Alterar a conexão global afeta todos os usuários
que compartilham o mesmo banco interno.

## Decisões arquiteturais

As decisões abaixo descrevem a implementação atual e seus compromissos; não
representam resultados experimentais ou uma garantia de segurança.

### 1. Separar interface, API e núcleo de tradução

O frontend React concentra a experiência de uso; a API FastAPI expõe os fluxos
e aplica as regras de acesso; o núcleo concentra prompts, planejamento e
validação. Essa divisão facilita a evolução e os testes de cada parte, ao custo
de manter contratos explícitos entre frontend e backend.

### 2. Planejar antes de gerar SQL

Em vez de depender apenas de uma resposta SQL livre, o fluxo solicita primeiro
um plano estruturado e valida referências ao esquema. Isso torna a intenção mais
observável e permite apontar inconsistências antes da execução. Relações
inferidas entre colunas existentes podem gerar avisos; a validação não comprova
que a interpretação de negócio ou o resultado estão corretos.

### 3. Construir contexto a partir do esquema

Tabelas, colunas e relacionamentos são obtidos do banco consultado, sem um
gerador específico para um domínio de negócio. Arquivos opcionais em
`context/ddls/` (`.sql`) e `context/business_rules/` (`.md` ou `.txt`)
complementam o prompt. A qualidade da resposta continua dependendo da
qualidade do esquema, do contexto e do modelo.

### 4. Permitir diferentes provedores de LLM

Uma interface comum permite escolher Ollama, Gemini ou OpenRouter por
configuração, sem mudar o fluxo de uso. Isso permite comparar modelos locais e
serviços externos, mas introduz diferenças de latência, custo, disponibilidade,
privacidade e qualidade das respostas.

### 5. Isolar acesso a dados em adaptadores e repositórios

O adaptador PostgreSQL utiliza SQLAlchemy e pandas; repositórios organizam a
persistência por responsabilidade. Leituras e alterações usam métodos
separados, e valores são vinculados como parâmetros nas operações dos
repositórios. Para consultas executadas sobre o banco consultado, a aplicação
utiliza uma transação somente leitura.

### 6. Autenticar com Supabase e manter sessão na aplicação

O Supabase Auth valida a identidade; um perfil no banco interno determina papel
e status de aprovação. Após o login, a API emite um cookie de sessão assinado,
`HttpOnly` e `SameSite=Lax`; `Secure` deve ser habilitado em HTTPS. Conversas,
histórico e favoritos são vinculados ao UUID do usuário autenticado.

### 7. Preservar SQL e contexto, não as linhas retornadas

As mensagens, os metadados e o SQL permitem retomar conversas; as linhas dos
resultados não são guardadas na conversa. Ao reexecutar, o usuário obtém dados
atuais, que podem ser diferentes dos resultados anteriores.

## Estrutura do projeto

```text
ask-sql/
├── api/                 # Rotas, autenticação, contratos e serviços FastAPI
├── core/                # LLM, prompts, planos e validação
├── database/            # Adaptador PostgreSQL e repositórios
├── web/                 # Interface React, testes e configuração Vite
├── evaluation/          # Contrato e métricas para avaliação de consultas
├── docs/                # Documentação técnica complementar
├── context/             # DDLs e regras opcionais, quando fornecidos
├── docker-compose.yml   # Serviços da API e do frontend
├── requirements.txt     # Dependências Python da aplicação
└── pytest.ini           # Configuração e marcação dos testes
```

Os diretórios de `context/` são opcionais e podem ser criados conforme a
necessidade; seu conteúdo pode conter informações sensíveis do domínio.

## Executando localmente

### Pré-requisitos

- Python e um ambiente virtual. A imagem da API utiliza Python 3.12.
- Node.js e npm. A imagem de build do frontend utiliza Node.js 22.
- Um projeto Supabase com Auth e PostgreSQL para o banco interno.
- Um PostgreSQL acessível para consulta.
- Ollama acessível com o modelo escolhido **ou** credenciais de Gemini ou
  OpenRouter.

### 1. Instale as dependências

```bash
git clone https://github.com/dd-henry/querix.git
cd querix

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm --prefix web ci
```

Para executar os testes Python, é necessário que `pytest` esteja instalado no
ambiente; ele não está listado em `requirements.txt`.

### 2. Configure a API

Crie um arquivo `.env` na raiz, usando valores do seu ambiente:

```dotenv
WEB_ORIGIN=http://127.0.0.1:5173
SESSION_SECRET=substitua_por_um_segredo_aleatorio_forte
COOKIE_SECURE=false

DATABASE_URL=postgresql://usuario:senha@host:5432/banco_interno
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_ANON_KEY=sua_chave_anon

LLM_PROVIDER=local
OLLAMA_HOST=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5-coder:7b
```

Nunca versione `.env` ou compartilhe credenciais. O arquivo representa o banco
**interno**; a conexão do banco consultado é configurada posteriormente pela
interface. Opções adicionais estão em [Configuração](#configuração).

### 3. Prepare o banco interno

Antes do primeiro cadastro, o banco interno deve ter as tabelas da aplicação e
ser compatível com o projeto Supabase. Os repositórios oferecem métodos
`initialize()` com o DDL necessário, porém **não há uma migração central
automática para todos os repositórios**. O histórico e as conversas são
inicializados no primeiro uso do histórico; a configuração do banco consultado
também possui inicialização própria. Perfis e catálogo devem estar preparados
previamente.

Para uma **instalação nova e isolada**, com as permissões adequadas, é possível
inicializar os repositórios abaixo:

```bash
venv/bin/python - <<'PY'
from database.postgres import PostgresAdapter
from database.users import UserRepository
from database.conversations import ConversationRepository
from database.query_history import QueryHistoryRepository
from database.predefined_queries import PredefinedQueryRepository

db = PostgresAdapter()
UserRepository(db).initialize()
ConversationRepository(db).initialize()
QueryHistoryRepository(db).initialize()
PredefinedQueryRepository(db).initialize()
PY
```

Para um banco existente ou de produção, revise o DDL e faça backup antes de
aplicar mudanças. O usuário do banco interno precisa das permissões necessárias
para criar ou alterar tabelas e índices. A migração `must_change_password` faz
parte de `UserRepository.initialize()`; ela **não é aplicada automaticamente
no início da API**.

### 4. Inicie os serviços

Em um terminal:

```bash
venv/bin/uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

Em outro:

```bash
npm --prefix web run dev
```

Abra <http://127.0.0.1:5173>. O Vite encaminha `/api` para a API local na
porta `8000`. A documentação interativa da API fica em
<http://127.0.0.1:8000/docs>.

### 5. Crie o primeiro administrador e configure o banco consultado

1. Cadastre uma conta e confirme o e-mail conforme a configuração do Supabase.
2. Com o banco interno preparado, execute uma única vez:

   ```bash
   venv/bin/python bootstrap_admin.py email@empresa.com
   ```

   O comando promove o perfil informado somente se ainda não existir um
   administrador. Em um banco compartilhado, a operação afeta esse ambiente.
3. Entre na aplicação. Em **Configurações**, informe a connection string do
   banco consultado e use **Testar e salvar conexão**. A API testa a conexão
   antes de salvá-la.
4. Sincronize o esquema quando necessário e faça uma pergunta ou execute uma
   consulta compartilhada.

## Configuração

| Variável | Finalidade | Padrão / observação |
|---|---|---|
| `WEB_ORIGIN` | Origem permitida do frontend. | Obrigatória; deve corresponder à URL usada no navegador. |
| `SESSION_SECRET` | Assinatura dos cookies e derivação da chave que cifra a conexão consultada. | Obrigatória; mantenha privada e estável. |
| `COOKIE_SECURE` | Ativa o atributo `Secure` do cookie. | `false` na API; use `true` em HTTPS. |
| `SESSION_MAX_AGE_SECONDS` | Validade da sessão. | `28800` segundos. |
| `DATABASE_URL` | Conexão PostgreSQL interna. | Pode ser substituída por `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DBNAME`. |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Integração de autenticação. | Necessárias para login e cadastro. |
| `SUPABASE_SERVICE_ROLE_KEY` | Operação administrativa de reset de senha. | Opcional para os demais fluxos; somente no backend. |
| `LLM_PROVIDER` | Escolhe o provedor. | `local`, `google` ou `openrouter`; padrão `local`. |
| `OLLAMA_HOST`, `OLLAMA_MODEL` | Endereço e modelo do Ollama. | Modelo padrão: `qwen2.5-coder:7b`. |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | Credencial e modelo Gemini. | Chave necessária quando `LLM_PROVIDER=google`. |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | Credencial e modelo OpenRouter. | Chave necessária quando `LLM_PROVIDER=openrouter`. |
| `GEMINI_MAX_RETRIES`, `OPENROUTER_MAX_RETRIES` | Novas tentativas para falhas transitórias. | `2` para cada provedor. |
| `LLM_REQUEST_TIMEOUT_SECONDS` | Tempo máximo configurado para chamadas a Gemini e OpenRouter. | `180` segundos; não configura o timeout do cliente Ollama. |
| `RESULT_LIMIT`, `PROMPT_LIMIT` | Limites de linhas na resposta e tamanho do prompt. | `5000` e `2000`, respectivamente. |

Trocar `SESSION_SECRET` invalida os cookies existentes **e impede a leitura da
connection string cifrada com o segredo anterior**. Planeje a rotação e a
reconfiguração do banco consultado antes de alterar esse valor.

## Publicação com Docker e Dokploy

O [`docker-compose.yml`](docker-compose.yml) constrói dois serviços: `api`
(FastAPI) e `web` (build React servido por Nginx). O Nginx encaminha `/api`
para a API na rede interna. Ambos expõem `/health` para verificações básicas.
O frontend também disponibiliza a página pública `/documentacao.html`. Essa
página é uma captura estática do README e dos exemplos de código, mantida
separadamente; seus links de fonte apontam para o repositório no GitHub.

Para publicar no Dokploy:

1. Configure uma aplicação Compose apontando para este repositório e use a raiz
   como contexto de build.
2. Configure as variáveis no ambiente do serviço, incluindo `WEB_ORIGIN` com a
   URL HTTPS pública e `COOKIE_SECURE=true`. Mantenha segredos fora do Git.
3. Prepare ou migre o banco interno **antes** de disponibilizar uma versão que
   dependa de novas tabelas ou colunas.
4. Aponte o domínio ao serviço `web`, porta `80`, e execute o deploy.
5. Confirme o estado da aplicação, o login e a conexão consultada. Se usar um
   modelo externo, valide a configuração e o tratamento de dados com o provedor.

O endpoint `/health` confirma que a API está respondendo, mas não garante que
Supabase, bancos e LLM estejam disponíveis. O deploy automático depende da
configuração do provedor Git e do webhook no ambiente de hospedagem.

## Testes e avaliação

```bash
# Backend sem integração externa
venv/bin/pytest -m "not integration" -q

# Teste marcado de integração com Ollama
venv/bin/pytest -m integration -q

# Frontend: tipos, lint e testes unitários
npm --prefix web run check

# Build e testes de navegador
npm --prefix web run build
npm --prefix web run e2e
```

Os testes Python e do frontend usam mocks em grande parte dos fluxos. Os
testes Playwright usam principalmente respostas HTTP simuladas; eles não
substituem uma validação com bancos, Supabase e LLM reais. Testes de
integração dependem dos serviços externos correspondentes.

O módulo [`evaluation/query_benchmark.py`](evaluation/query_benchmark.py)
agrega métricas a partir de resultados previamente registrados, como taxa de
consultas executáveis, cobertura de colunas esperadas, resultados vazios e
latência. Ele **não executa consultas nem avalia automaticamente a correção
semântica**. Para o TCC, resultados e métricas devem ser coletados e relatados
com metodologia e evidências próprias.

## Segurança, privacidade e limitações

- **Acesso ao banco:** use uma conta com os menores privilégios necessários,
  preferencialmente somente leitura. Validação de SQL e transação somente
  leitura são camadas de proteção, não uma substituição para permissões,
  isolamento e controles no PostgreSQL.
- **Dados enviados ao modelo:** o contexto pode incluir esquema, regras de
  negócio e trechos da conversa. Para produzir o resumo, o resultado retornado
  também é enviado ao provedor configurado. Com serviços externos, considere
  políticas de privacidade, dados pessoais e requisitos da organização.
- **Resultados grandes:** `RESULT_LIMIT` limita as linhas serializadas na
  resposta, mas a consulta é carregada em um DataFrame antes desse corte. Isso
  não impede, por si só, consumo elevado de memória.
- **Precisão:** LLMs podem interpretar perguntas incorretamente, gerar SQL
  inadequado ou produzir resumos imprecisos. Revise consultas e resultados.
- **Senha:** o reset por administrador gera uma senha temporária para outro
  usuário e exige a chave `SUPABASE_SERVICE_ROLE_KEY`. O administrador não
  pode resetar a própria conta nesse fluxo. **Sessões anteriores não são
  invalidadas pelo reset**; avalie esse risco antes de usar o recurso.
- **Operação:** confirme migrações, permissões, backups e recuperação antes de
  implantar. O projeto não oferece garantia de disponibilidade apenas pelo
  fato de os testes isolados ou o health check passarem.

## Documentação complementar

- [Arquitetura e funcionamento](docs/arquitetura_e_funcionamento.md)
- [Estratégia de testes](docs/testes.md)
- [Avaliação de consultas analíticas](docs/avaliacao_consultas.md)
- [PostgreSQL MCP no VS Code](docs/postgres-mcp.md)
- Documentação interativa da API: `/docs`, com a API em execução.
