# Configuração da conexão do banco consultado

**Status:** in design
**Priority:** P1

## Problem Statement

O Ask-SQL depende de uma connection string configurada na `.env` para consultar
o banco de dados. Isso impede que um administrador troque ou configure o banco
consultado pela interface do sistema. A aplicação também usa o banco definido
em `DATABASE_URL` para persistir perfis, conversas e histórico, então essa
persistência interna não pode depender da tela de configuração do banco-alvo.

## Out of Scope

| Item | Motivo |
| --- | --- |
| Substituir ou remover a conexão do banco interno da aplicação | A autenticação, os perfis, as conversas e o histórico continuam dependentes dela. |
| Conexões diferentes por usuário | A decisão desta entrega é uma conexão global administrada por `admin`. |
| Suporte a bancos que não sejam PostgreSQL | O adaptador e o fluxo atual são específicos de PostgreSQL. |
| Exibir, recuperar ou editar parcialmente uma credencial já salva | A connection string completa nunca deve voltar ao navegador. |
| Gerenciar múltiplos ambientes ou múltiplos bancos simultâneos | A entrega cobre um único banco-alvo ativo. |

## Assumptions & Open Questions

| Assumption / Open question | Chosen default | Rationale |
| --- | --- | --- |
| O banco interno da aplicação continuará configurado por ambiente | `DATABASE_URL` permanece a conexão de persistência interna | Sem uma persistência estável, o sistema não consegue autenticar usuários nem guardar histórico. |
| Escopo da configuração do banco consultado | Uma configuração global para todos os usuários aprovados | O usuário escolheu administração global e não configuração por usuário. |
| Formato de entrada | Uma connection string PostgreSQL completa | O usuário escolheu connection string only, evitando duplicar campos e combinações de credenciais. |
| Proteção da credencial persistida | Cifrar no banco interno usando uma chave derivada de `SESSION_SECRET` | A credencial precisa sobreviver a reinícios sem ficar armazenada em texto puro. |
| Momento de ativação | Testar com `SELECT 1` antes de salvar e invalidar o cache após salvar | Evita ativar credenciais inválidas e garante que novas consultas usem a conexão aprovada. |
| Configuração ausente | A aplicação continua disponível, mas operações que precisam do banco-alvo retornam `503 database_not_configured` | O admin precisa conseguir abrir a tela e configurar a conexão sem erro de inicialização global. |
| Open questions: none | None | As decisões de escopo, proprietário e formato foram confirmadas pelo usuário. |

## User Stories

### P1: Administrar o banco consultado

Como administrador, quero abrir Configurações, informar uma connection string
PostgreSQL e ativá-la sem editar a `.env`, para que o Ask-SQL consulte o banco
correto.

**Acceptance Criteria**:

1. WHEN an approved admin opens the Configurações panel THEN the system SHALL show a connection-string form and a status indicating whether a target database is configured.
2. WHEN an approved admin submits a PostgreSQL connection string THEN the system SHALL execute `SELECT 1` against that connection before storing it.
3. WHEN the connection test succeeds THEN the system SHALL store the connection as the single global target and return status `configured` without returning the submitted connection string.
4. IF the connection test fails THEN the system SHALL return HTTP `503` with error code `database_connection_failed` and SHALL leave the previously stored target unchanged.
5. IF a non-admin calls the target-connection read or write endpoint THEN the system SHALL return HTTP `403` with error code `forbidden`.

### P1: Operar sem connection string do banco-alvo na `.env`

Como operador, quero iniciar a aplicação sem uma connection string do banco
consultado na `.env`, para configurar esse banco depois pela tela.

**Acceptance Criteria**:

1. IF no target connection is stored THEN the system SHALL keep the health endpoint and internal application persistence available.
2. IF no target connection is stored and an approved user requests schema synchronization or query execution THEN the system SHALL return HTTP `503` with error code `database_not_configured`.
3. WHEN a target connection is stored THEN schema inspection, chat execution, history rerun, and predefined-query execution SHALL use that target while profiles, conversations, and query history remain stored through the internal application database.

### P1: Proteger a credencial

Como administrador, quero que a credencial não seja exposta pela aplicação,
para que uma connection string salva não vire um segredo no frontend ou nos
logs.

**Acceptance Criteria**:

1. The system SHALL store the target connection in encrypted form and SHALL never persist the submitted connection string as plaintext.
2. The system SHALL never include the target connection string in API responses, browser state, or application log messages.
3. WHEN the admin saves a new target connection THEN the system SHALL invalidate cached schema, translator, and target-adapter state before the next target operation.

## Requirement Traceability

| ID | Story | Acceptance criteria | Verification |
| --- | --- | --- | --- |
| DCS-001 | Administrar o banco consultado | P1.1 | API/UI tests |
| DCS-002 | Administrar o banco consultado | P1.2 | Repository/service tests |
| DCS-003 | Administrar o banco consultado | P1.3 | API tests |
| DCS-004 | Administrar o banco consultado | P1.4 | API/repository tests |
| DCS-005 | Administrar o banco consultado | P1.5 | API tests |
| DCS-006 | Operar sem connection string do banco-alvo na `.env` | P2.1 | API tests |
| DCS-007 | Operar sem connection string do banco-alvo na `.env` | P2.2 | API tests |
| DCS-008 | Operar sem connection string do banco-alvo na `.env` | P2.3 | Dependency/service tests |
| DCS-009 | Proteger a credencial | P3.1 | Repository tests |
| DCS-010 | Proteger a credencial | P3.2 | API/logging tests |
| DCS-011 | Proteger a credencial | P3.3 | Dependency/cache tests |
