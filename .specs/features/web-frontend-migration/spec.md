# Web Frontend Migration Specification

## Problem Statement

The Streamlit interface re-executes the whole script on every interaction. Login and query execution show duplicated forms and transient elements (reproduced in a real browser: 4 inputs before a login click, 6 during, 4 after). The interface also mixes rendering, session state, and business rules in a 1,130-line `app.py`, which makes UX changes risky. The product needs a separate frontend with its own state, backed by an API that reuses the existing `core/` and `database/` code.

## Goals

- [ ] Login, signup, chat, and query execution never render a duplicated or transient copy of any element (verified by an automated browser test that counts inputs during a login submit).
- [ ] Every current user-facing capability is available in the new UI: auth, private resumable conversations, SQL review/execute/retry, results/chart/CSV, history, shared queries, user administration, schema sync.
- [ ] The API enforces authorization, ownership, and read-only SQL on the server; the browser holds no tokens or credentials.
- [ ] Streamlit is removed only after an independent Verifier passes and the user approves the cutover.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Changing the LLM, prompt rules, or Ollama model | Not related to the UI problem |
| Persisting query result rows | Existing decision: results are re-fetched on execution |
| Token streaming of the model answer | Not needed to fix duplication; request/response is enough |
| Dark theme, i18n, mobile app | Not requested |
| Changing the PostgreSQL schema of existing tables | Repositories are reused as they are |
| Deployment infrastructure (containers, CI, hosting) | Separate decision; only local run commands are in scope |
| Write-capable SQL from the chat | Blocked by AD-003 |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Frontend framework | React + TypeScript + Vite SPA | Authenticated app behind an API; no SSR needed | y |
| Session mechanism | API-signed httpOnly SameSite=Lax cookie, 8 h lifetime | No token in browser storage | y |
| SQL execution policy | Read-only for every role | Chat currently permits writes; exposing that over HTTP is unsafe | y |
| Transition | Streamlit and the new app coexist until parity, then Streamlit is removed | Avoids an unusable app mid-migration | y |
| Result size | API returns at most 5,000 rows and a `truncated` flag | Unbounded JSON can freeze the browser; no limit exists today | n |
| Prompt length | 1 to 2,000 characters | Bounds model input and storage | n |
| Charts | Bar and line only, as today, rendered with Recharts | Parity with current behavior | n |
| Session expiry behavior | A 401 returns the user to login; unsent text in the composer is kept in memory only | Simple and predictable | n |
| Login failure | Email is kept, password is cleared, error shown inline | Standard behavior | n |
| Backend location | New `api/` package beside `core/` and `database/`; frontend in `web/` | Reuses repositories without moving files | n |
| Sync Database action | Available to every approved user, as today | Parity | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Stable authentication ⭐ MVP

**User Story**: As a user, I want to sign in, sign up, and sign out without any screen flicker or duplicated form so that the app feels reliable.

**Why P1**: The reported defect starts here.

**Acceptance Criteria**:

1. WHEN a user submits valid credentials THEN the system SHALL set a signed httpOnly SameSite=Lax session cookie and show the chat without the auth form being rendered more than once at any moment. <!-- WEB-01 -->
2. IF credentials are invalid THEN the system SHALL keep the form mounted, keep the email, clear the password, and show "Não foi possível entrar: <message>" inline. <!-- WEB-02 -->
3. IF the profile status is pending, rejected, or disabled THEN the system SHALL answer 403 with code `account_not_approved` and the UI SHALL show the matching status message with only a sign-out action. <!-- WEB-03 -->
4. WHEN a signup has a name, an email, a password of at least 8 characters, and a matching confirmation THEN the system SHALL create the account and a pending profile and show "Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin." <!-- WEB-04 -->
5. IF a signup field is empty, the password is shorter than 8 characters, or the confirmation differs THEN the system SHALL show the corresponding validation message and SHALL NOT call the API. <!-- WEB-05 -->
6. WHEN the user clicks Sair THEN the system SHALL clear the cookie and show the login screen. <!-- WEB-06 -->
7. IF a session cookie is missing, tampered with, or older than 8 hours THEN the system SHALL answer 401 and the UI SHALL show the login screen. <!-- WEB-07 -->
8. IF a non-GET request carries an Origin header outside the allowed list THEN the system SHALL answer 403. <!-- WEB-08 -->
9. The system SHALL read role and status from the database on every authenticated request. <!-- WEB-09 -->

**Independent Test**: Start API and web app, sign in with a stub account, and observe one auth form throughout; sign in with a wrong password and see the inline error.

---

### P1: Stable chat with SQL review ⭐ MVP

**User Story**: As an approved user, I want to ask a question, review the generated SQL, run it, and see results exactly once so that I can trust what is on screen.

**Why P1**: The second reported defect (duplicated elements on query execution).

**Acceptance Criteria**:

1. WHEN a user sends a prompt THEN the system SHALL persist it once and render exactly one user message and one assistant message for that request id. <!-- WEB-10 -->
2. WHILE a request is pending the system SHALL disable the composer and show a status indicator inside that request's assistant message without unmounting earlier messages. <!-- WEB-11 -->
3. WHERE review mode is on (default) the system SHALL show the generated SQL with "Executar SQL revisado" and "Cancelar revisão" and SHALL NOT execute it until the user confirms. <!-- WEB-12 -->
4. WHERE review mode is off the system SHALL execute the generated read-only SQL automatically after translation. <!-- WEB-13 -->
5. IF translation fails THEN the system SHALL store an error message with a retry action, and WHEN the user retries THEN the system SHALL reuse the original user message instead of creating a new one. <!-- WEB-14 -->
6. IF the translator returns text starting with "AVISO:" THEN the system SHALL show it as a warning and SHALL NOT offer execution. <!-- WEB-15 -->
7. IF the generated SQL is not a single read-only SELECT/WITH statement THEN the system SHALL answer 422 with code `sql_not_read_only`, store the error on the assistant message, and SHALL NOT call the database. <!-- WEB-16 -->
8. WHEN the user confirms execution THEN the system SHALL run the SQL stored for that request id inside a read-only transaction and SHALL ignore any SQL sent by the client. <!-- WEB-17 -->
9. WHEN a query returns rows THEN the system SHALL return the columns, up to 5,000 rows, the row count, and a `truncated` flag, and the UI SHALL show a notice when `truncated` is true. <!-- WEB-18 -->
10. WHEN the user chooses "Gerar Gráfico" and the suggested columns exist THEN the UI SHALL draw a bar or line chart; IF a column is missing THEN it SHALL show the warning "As colunas sugeridas pela IA para o gráfico não existem no resultado." <!-- WEB-19 -->
11. WHEN the user chooses CSV download THEN the UI SHALL download the displayed rows as UTF-8 CSV with a header row. <!-- WEB-20 -->
12. IF the Ollama service is unreachable THEN the system SHALL answer 502 with code `translator_unavailable`. <!-- WEB-21 -->
13. IF the database is unreachable during execution THEN the system SHALL answer 503 with code `database_unavailable` and store a retryable error. <!-- WEB-22 -->
14. IF a prompt is empty after trimming or longer than 2,000 characters THEN the system SHALL answer 422 and SHALL NOT persist a message. <!-- WEB-23 -->
15. IF the same request id and role is submitted twice THEN the system SHALL return the stored message and SHALL NOT insert a duplicate. <!-- WEB-24 -->

**Independent Test**: Send a prompt with the translator stubbed; observe one user and one assistant bubble, review controls, results after confirmation, and a single copy after a double-click on send.

---

### P1: Private resumable conversations ⭐ MVP

**User Story**: As a user, I want to resume my earlier conversations so that I keep context between visits.

**Why P1**: Already shipped in Streamlit; parity is required.

**Acceptance Criteria**:

1. WHEN a user sends the first prompt without an open conversation THEN the system SHALL create exactly one conversation owned by that user, titled from the prompt. <!-- WEB-25 -->
2. WHEN the user opens the conversation list THEN the system SHALL show the owner's conversations grouped as Hoje, Ontem, Últimos 7 dias, Últimos 30 dias, and Mais antigas by last activity in the browser timezone. <!-- WEB-26 -->
3. WHEN the user opens a conversation THEN the system SHALL restore prompts, SQL, and errors in original order without executing any SQL. <!-- WEB-27 -->
4. IF a user requests a conversation owned by someone else THEN the system SHALL answer 404. <!-- WEB-28 -->
5. WHEN the user favorites or unfavorites a conversation THEN the system SHALL persist the state and keep favorites out of the one-year expiry cleanup. <!-- WEB-29 -->
6. WHEN the user confirms deletion THEN the system SHALL delete the conversation, its messages, and linked history records; IF the user cancels THEN nothing SHALL change. <!-- WEB-30 -->
7. WHEN the translator is called THEN the system SHALL send at most the six most recent prior turns of that conversation as context. <!-- WEB-31 -->

**Independent Test**: Create two conversations as user A, reopen one, then request it as user B and receive 404.

---

### P2: Query history and shared queries

**User Story**: As a user, I want to rerun earlier queries and use shared queries so that I save effort.

**Why P2**: Existing capability, not part of the defect.

**Acceptance Criteria**:

1. WHEN the user opens the history THEN the system SHALL list only that user's records, pinned first, most recent next, limited to 20. <!-- WEB-32 -->
2. WHEN the user pins, unpins, or deletes a history record THEN the system SHALL change only that user's record. <!-- WEB-33 -->
3. WHEN the user reruns a history record THEN the system SHALL execute its stored SQL read-only and show the result in the active conversation. <!-- WEB-34 -->
4. WHEN the user searches the catalog THEN the system SHALL return matching shared queries with favorite state for that user. <!-- WEB-35 -->
5. WHEN the user runs a shared query with parameters THEN the system SHALL bind the values as SQL parameters and IF a required parameter is missing THEN it SHALL answer 422 naming the parameter. <!-- WEB-36 -->
6. WHERE the role is dev, dba, or admin the system SHALL allow creating, editing, and deleting shared queries; IF another role attempts it THEN the system SHALL answer 403. <!-- WEB-37 -->
7. IF a shared query is not a single read-only SELECT/WITH statement THEN the system SHALL answer 422 on create or update. <!-- WEB-38 -->

**Independent Test**: Run a shared query with a parameter, omit it once and see 422.

---

### P2: User administration and schema sync

**User Story**: As an admin, I want to approve users and manage roles, and any user can refresh the schema, so that access and prompts stay current.

**Why P2**: Existing capability.

**Acceptance Criteria**:

1. WHERE the role is admin the system SHALL list profiles and allow changing status (approved, rejected, disabled) and role (user, dev, admin); IF another role calls these endpoints THEN the system SHALL answer 403. <!-- WEB-39 -->
2. IF a change would remove the last approved admin THEN the system SHALL refuse it with 409. <!-- WEB-40 -->
3. WHEN a user chooses Sincronizar Banco THEN the system SHALL rebuild the translator schema context and clear catalog caches. <!-- WEB-41 -->

**Independent Test**: As admin, disable a user and see that user's next request return 403.

---

### P2: Usable layout

**User Story**: As a user, I want a clear, responsive layout so that the app is pleasant to use.

**Why P2**: The user asked for better UX/UI.

**Acceptance Criteria**:

1. The system SHALL show a sidebar (conversations, history, shared queries, administration) and a main chat column with the composer fixed at the bottom. <!-- WEB-42 -->
2. WHILE the viewport is narrower than 768 px the system SHALL collapse the sidebar behind a menu button. <!-- WEB-43 -->
3. The system SHALL give every input an associated label, make every action keyboard-operable, and announce request status through an aria-live region. <!-- WEB-44 -->
4. WHEN the composer has focus THEN Enter SHALL send and Shift+Enter SHALL insert a newline. <!-- WEB-45 -->

**Independent Test**: Resize to 360 px and operate the app with the keyboard only.

---

### P1: Safe cutover

**User Story**: As the owner, I want Streamlit removed only after the new app is verified so that I am never left without a working UI.

**Why P1**: The migration must be reversible until verified.

**Acceptance Criteria**:

1. WHEN the new app is verified THEN the system SHALL remove the Streamlit entry point, components, tests, theme config, and dependency only after the Verifier verdict is PASS and the user approves. <!-- WEB-46 -->
2. The system SHALL return errors as `{"error": {"code": string, "message": string}}` without stack traces, SQL text from other users, or secrets. <!-- WEB-47 -->
3. The system SHALL log each API request with method, path, status, and duration, and SHALL NOT log passwords, cookies, or result rows. <!-- WEB-48 -->
4. The system SHALL provide one documented command for the API and one for the web app. <!-- WEB-49 -->

**Independent Test**: Run `git grep -n streamlit` after cutover and find no runtime references.

---

## Edge Cases

- IF the user double-clicks send THEN the system SHALL create one user message because the client reuses one request id per submission.
- IF the browser loses the network after the request is sent THEN the retry SHALL reuse the same request id and SHALL NOT duplicate the message.
- IF two browser tabs use the same account THEN each tab SHALL show only data returned by its own requests and SHALL NOT share unsent composer text.
- WHEN a result contains NULL, NaN, dates, or Decimal values THEN the API SHALL serialize them as JSON null, ISO-8601 strings, and strings respectively.
- IF the conversation list is empty THEN the UI SHALL show an empty state with a "Nova conversa" action.
- IF storage is unavailable THEN the system SHALL answer 503 with code `storage_unavailable` and the UI SHALL show that the message was not saved.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| WEB-01 | P1: Stable authentication | Tasks | Pending |
| WEB-02 | P1: Stable authentication | Tasks | Pending |
| WEB-03 | P1: Stable authentication | Tasks | Pending |
| WEB-04 | P1: Stable authentication | Tasks | Pending |
| WEB-05 | P1: Stable authentication | Tasks | Pending |
| WEB-06 | P1: Stable authentication | Tasks | Pending |
| WEB-07 | P1: Stable authentication | Tasks | In Progress |
| WEB-08 | P1: Stable authentication | Tasks | In Progress |
| WEB-09 | P1: Stable authentication | Tasks | Pending |
| WEB-10 | P1: Stable chat | Tasks | Pending |
| WEB-11 | P1: Stable chat | Tasks | Pending |
| WEB-12 | P1: Stable chat | Tasks | Pending |
| WEB-13 | P1: Stable chat | Tasks | Pending |
| WEB-14 | P1: Stable chat | Tasks | Pending |
| WEB-15 | P1: Stable chat | Tasks | Pending |
| WEB-16 | P1: Stable chat | Tasks | Pending |
| WEB-17 | P1: Stable chat | Tasks | Pending |
| WEB-18 | P1: Stable chat | Tasks | In Progress |
| WEB-19 | P1: Stable chat | Tasks | Pending |
| WEB-20 | P1: Stable chat | Tasks | Pending |
| WEB-21 | P1: Stable chat | Tasks | Pending |
| WEB-22 | P1: Stable chat | Tasks | Pending |
| WEB-23 | P1: Stable chat | Tasks | In Progress |
| WEB-24 | P1: Stable chat | Tasks | Pending |
| WEB-25 | P1: Conversations | Tasks | Pending |
| WEB-26 | P1: Conversations | Tasks | Pending |
| WEB-27 | P1: Conversations | Tasks | Pending |
| WEB-28 | P1: Conversations | Tasks | Pending |
| WEB-29 | P1: Conversations | Tasks | Pending |
| WEB-30 | P1: Conversations | Tasks | Pending |
| WEB-31 | P1: Conversations | Tasks | Pending |
| WEB-32 | P2: History and shared queries | Tasks | Pending |
| WEB-33 | P2: History and shared queries | Tasks | Pending |
| WEB-34 | P2: History and shared queries | Tasks | Pending |
| WEB-35 | P2: History and shared queries | Tasks | Pending |
| WEB-36 | P2: History and shared queries | Tasks | Pending |
| WEB-37 | P2: History and shared queries | Tasks | Pending |
| WEB-38 | P2: History and shared queries | Tasks | Pending |
| WEB-39 | P2: Administration | Tasks | Pending |
| WEB-40 | P2: Administration | Tasks | Pending |
| WEB-41 | P2: Administration | Tasks | Pending |
| WEB-42 | P2: Layout | Tasks | Pending |
| WEB-43 | P2: Layout | Tasks | Pending |
| WEB-44 | P2: Layout | Tasks | Pending |
| WEB-45 | P2: Layout | Tasks | Pending |
| WEB-46 | P1: Cutover | Tasks | Pending |
| WEB-47 | P1: Cutover | Tasks | In Progress |
| WEB-48 | P1: Cutover | Tasks | In Progress |
| WEB-49 | P1: Cutover | Tasks | In Progress |

**Coverage:** 49 total, 49 mapped to tasks, 0 unmapped

---

## Success Criteria

- [ ] An automated browser test shows the number of `input` elements never exceeds its pre-click value during a login submit and during a chat send.
- [ ] Backend tests pass with fake repositories: `python3 -m pytest api -q`.
- [ ] Frontend unit tests, type check, lint, and build pass: `npm --prefix web run check`.
- [ ] Browser end-to-end tests pass: `npm --prefix web run e2e`.
- [ ] No code path executes SQL that did not pass read-only validation, proven by a test that a DELETE statement never reaches the database adapter.
- [ ] The independent Verifier verdict is PASS before Streamlit is removed.
