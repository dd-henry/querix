# Web Frontend Migration Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: activate it by name and follow its Execute flow and Critical Rules. Do not search for skill files by filesystem path. The skill is the source of truth for the per-task cycle, atomic commits, sub-agent delegation, Verifier, and discrimination sensor.

If the skill cannot be activated, stop and report the blocker. Do not proceed without it.

**Design**: `.specs/features/web-frontend-migration/design.md`  
**Specification**: `.specs/features/web-frontend-migration/spec.md`  
**Status**: In Progress

## Test Coverage Matrix

> Generated from the current repository, `README.md`, `docs/testes.md`, `pytest.ini`, the migration spec, and the planned toolchain. The frontend commands become executable in T7.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Existing Python core/database/repositories | unit | Existing behavior plus every migration-sensitive ownership, read-only, ordering, and failure edge case | `test_*.py` | `venv/bin/python -m pytest -m "not integration" -q` |
| API services and serializers | unit | All branches; 1:1 mapping to service acceptance criteria; every listed edge case | `api/tests/test_*.py` | `venv/bin/python -m pytest api/tests -q` |
| API routes and middleware | integration | Every route in scope: happy path, auth/role boundaries, validation, idempotency, external failure, and error envelope | `api/tests/test_routes_*.py` | `venv/bin/python -m pytest api/tests -q` |
| React API client, hooks, and components | unit | All state branches, validation paths, 401 handling, pending/error/retry states, and accessibility contracts | `web/src/**/*.test.ts(x)` | `npm --prefix web run test -- --run` |
| Browser workflows | e2e | Login/signup/logout, no duplicate DOM during transitions, chat review/execute/retry, conversation ownership, responsive layout, and parity panels | `web/e2e/*.spec.ts` | `npm --prefix web run e2e` |
| Configuration and documentation | none | Build/typecheck gate and manual command review | `web/package.json`, `README.md`, `.streamlit/config.toml` | `npm --prefix web run check` |

## Gate Check Commands

> Generated from the current Python test configuration and the planned frontend manifest. No current linter or formatter is configured for Python.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After a focused backend or frontend unit task | `venv/bin/python -m pytest api/tests -q` or `npm --prefix web run test -- --run` |
| API | After an API route or middleware task | `venv/bin/python -m pytest api/tests -q` |
| Frontend | After a frontend component or hook task | `npm --prefix web run check` |
| Full | After a vertical slice or E2E task | `venv/bin/python -m pytest -m "not integration" -q && npm --prefix web run check && npm --prefix web run e2e` |
| Build | Before cutover and after documentation/configuration changes | `venv/bin/python -m compileall -q api core database && npm --prefix web run build` |

**Co-located tests:** Every API service/route and frontend component/hook task includes its required tests in the same task. Tests are not deferred to a later task.

## Execution Plan

Phases run sequentially. Tasks within a phase follow the dependency arrows below. Cross-phase dependencies are declared in each task and are satisfied by the completed previous phase.

### Phase 1: API and frontend foundations

```text
T1 -> T2
T1 -> T3
T1 -> T4
T2 -> T5
T3 -> T5
T4 -> T5
T5 -> T6
```

T7 is independent of T1-T6 and creates the frontend workspace.

### Phase 2: Authentication vertical slice

```text
T8 -> T9 -> T10 -> T11 -> T12
```

### Phase 3: Core chat backend

```text
T13 -> T14
T13 -> T15
T13 -> T17
T16 -> T17
T17 -> T18
T17 -> T19
```

### Phase 4: Backend parity routes

T20-T23 are independent route families after the foundation.

### Phase 5: Chat frontend

```text
T25 -> T26 -> T27
T25 -> T27
```

### Phase 6: Parity frontend

```text
T28 -> T32
T29 -> T32
T30 -> T32
T31 -> T32
T32 -> T33
T28 -> T34
T29 -> T34
T30 -> T34
T31 -> T34
T32 -> T34
```

### Phase 7: Documentation and conditional cutover

```text
T33 -> T35
T34 -> T35
T35 -> T36 -> T37 -> T38 -> T39 -> T40 -> T41
```

T36-T41 are blocked until the independent Verifier returns PASS and the user explicitly approves removal of Streamlit.

## Task Breakdown

### Phase 1: API and frontend foundations

#### T1: Creating API runtime settings

**What**: Add typed API configuration for database, Supabase, web origin, session secret, cookie policy, result limit, and prompt limit.
**Where**: `api/config.py`
**Depends on**: None
**Reuses**: Environment names from `.env`, `core/auth.py`, and `requirements.txt`.
**Requirement**: WEB-07, WEB-18, WEB-23, WEB-49

**Done when**:

- [x] Missing `SESSION_SECRET` or `WEB_ORIGIN` fails startup with an explicit configuration error.
- [x] Defaults are bounded and match the spec: 8-hour session, 5,000 rows, 2,000 prompt characters.
- [x] Unit tests cover valid settings, missing secret, and boolean production cookie configuration.
- [x] Gate passes with the expected focused test count recorded in the commit: `venv/bin/pytest -q api/tests` → 3 passed.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(api): add typed runtime settings`

#### T2: Creating the FastAPI application shell

**What**: Create the application factory, JSON error envelope, request timing logs without secrets/rows, restricted CORS, and Origin protection for mutating requests.
**Where**: `api/app.py`
**Depends on**: T1
**Reuses**: Existing logging style and error propagation conventions.
**Requirement**: WEB-08, WEB-47, WEB-48, WEB-49

**Done when**:

- [x] `create_app()` returns a testable FastAPI instance without opening external connections at import time.
- [x] Validation, auth, forbidden, not-found, conflict, and unexpected errors use the documented envelope.
- [x] Disallowed mutating origins receive 403; allowed origins receive credentials-compatible CORS headers.
- [x] TestClient tests prove passwords, cookies, SQL, and result rows do not enter request logs.
- [x] Gate passes with 7 API tests: `venv/bin/pytest -q api/tests`.

**Tests**: integration
**Gate**: API
**Commit**: `feat(api): add fastapi application shell`

#### T3: Implementing signed session cookies

**What**: Implement issue, verify, expiry, and clear operations for the httpOnly session cookie.
**Where**: `api/auth/session.py`
**Depends on**: T1
**Reuses**: `auth_user` identity shape currently initialized in `app.py`.
**Requirement**: WEB-01, WEB-06, WEB-07

**Done when**:

- [x] A valid claim contains user ID, issued-at, and expiry.
- [x] Missing, malformed, tampered, and expired cookies all produce the same 401 error code.
- [x] The cookie is httpOnly, SameSite=Lax, Secure according to settings, and max-age is eight hours.
- [x] Unit tests cover valid, tampered, expired, missing, and clear paths.
- [x] Gate passes with 10 API tests: `venv/bin/pytest -q api/tests`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(auth): add signed session cookies`

#### T4: Adapting Supabase authentication for API requests

**What**: Add an operation-scoped Supabase auth adapter for login, signup, and logout without a shared mutable Streamlit client session.
**Where**: `api/auth/service.py`
**Depends on**: T1
**Reuses**: `SupabaseAuth` semantics from `core/auth.py`.
**Requirement**: WEB-01, WEB-04

**Done when**:

- [x] Valid login returns a user identity and session source data without exposing the Supabase token to route callers.
- [x] Missing Supabase configuration fails explicitly.
- [x] Supabase failures map to typed service errors instead of success-shaped values.
- [x] Unit tests cover login success/failure, signup success/failure, and client isolation.
- [x] Gate passes with 15 API tests: `venv/bin/pytest -q api/tests`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(auth): add api supabase adapter`

#### T5: Wiring authenticated profile and role dependencies

**What**: Provide repository factories, current-session dependency, approved-profile dependency, and role guards.
**Where**: `api/dependencies.py`
**Depends on**: T2, T3, T4
**Reuses**: `UserRepository`, `ConversationRepository`, `QueryHistoryRepository`, `PredefinedQueryRepository`, `PostgresAdapter`, `Prompter`, and `Translator`.
**Requirement**: WEB-03, WEB-09, WEB-28, WEB-37, WEB-39

**Done when**:

- [x] Every authenticated request reloads the profile by session user ID.
- [x] Pending, rejected, and disabled profiles produce `account_not_approved`.
- [x] Role guards distinguish user, dev/dba, and admin actions.
- [x] Unit/integration tests cover missing session, foreign profile, status guard, and role guard.
- [x] Gate passes with 22 API tests: `venv/bin/pytest -q api/tests`.

**Tests**: integration
**Gate**: API
**Commit**: `feat(api): add auth and repository dependencies`

#### T6: Adding authentication API routes

**What**: Implement login, signup, logout, and current-user routes with cookie mutation and profile status behavior.
**Where**: `api/routes/auth.py`
**Depends on**: T5
**Reuses**: `api/auth/service.py` and `api/auth/session.py`.
**Requirement**: WEB-01, WEB-02, WEB-03, WEB-04, WEB-05, WEB-06, WEB-07

**Done when**:

- [x] Successful login sets the cookie and returns the approved profile.
- [x] Invalid login keeps the API stateless and returns a safe error.
- [x] Signup validates server-side and creates a pending profile.
- [x] Logout clears the cookie; `/me` requires the cookie.
- [x] TestClient tests cover happy, invalid, pending, disabled, malformed input, and logout paths.
- [x] Gate passes with 34 API tests: `venv/bin/pytest -q api/tests`.

**Tests**: integration
**Gate**: API
**Commit**: `feat(auth): add authentication routes`

#### T7: Scaffolding the React frontend workspace

**What**: Create the React + TypeScript + Vite workspace with strict TypeScript, unit-test, lint/typecheck, build, and Playwright scripts.
**Where**: `web/`
**Depends on**: None
**Reuses**: Vite React TypeScript conventions; no existing JS workspace exists.
**Requirement**: WEB-49

**Done when**:

- [x] `npm --prefix web run check` runs typecheck, lint, and unit tests.
- [x] `npm --prefix web run build` produces a production bundle.
- [x] `npm --prefix web run e2e` has a configured browser project and local web-server contract.
- [x] The scaffold contains no Streamlit-specific code.
- [x] Gates pass: `npm --prefix web run check`, `npm --prefix web run build`, and `npm --prefix web run e2e -- --list`.

**Tests**: none
**Gate**: build
**Commit**: `build(web): scaffold react vite workspace`

### Phase 2: Authentication vertical slice

#### T8: Creating the typed frontend API client

**What**: Centralize credentialed fetches, JSON parsing, error envelopes, 401 callbacks, and typed auth methods.
**Where**: `web/src/api/client.ts`
**Depends on**: T7, T2
**Reuses**: API error envelope from T2.
**Requirement**: WEB-07, WEB-47

**Done when**:

- [x] Requests use `credentials: "include"` and never write tokens to browser storage.
- [x] Non-2xx responses become typed errors with code and message.
- [x] Unit tests cover JSON success, empty success, validation error, 401 callback, and malformed error payload.
- [x] Gate passes with 6 frontend tests: `npm --prefix web run check`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(web): add typed api client`

#### T9: Adding frontend auth state and routing

**What**: Add the auth provider and router that render exactly one public or authenticated branch based on `/api/auth/me`.
**Where**: `web/src/app/AuthProvider.tsx`
**Depends on**: T8, T6
**Reuses**: Typed API client and profile model.
**Requirement**: WEB-01, WEB-03, WEB-06, WEB-07

**Done when**:

- [x] Initial auth loading has one stable shell and no duplicate auth tree.
- [x] 401 transitions to the public branch and preserves only in-memory unsent text.
- [x] Pending/rejected/disabled profiles cannot render the chat branch.
- [x] Unit tests cover loading, authenticated, unauthenticated, and blocked-profile states.
- [x] Gate passes with 13 frontend tests: `npm --prefix web run check`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(web): add auth provider and route guards`

#### T10: Building login and signup forms

**What**: Implement controlled, labeled login/signup forms with client validation, password reset after failed login, and inline feedback.
**Where**: `web/src/features/auth/AuthPage.tsx`
**Depends on**: T9
**Reuses**: React controlled form behavior and auth client methods.
**Requirement**: WEB-02, WEB-04, WEB-05

**Done when**:

- [x] Invalid signup data never calls the API.
- [x] Failed login retains email, clears password, and displays the required prefix.
- [x] Submit buttons are disabled only for the active operation and cannot double-submit.
- [x] Component tests cover all validation branches and login/signup success/failure.
- [x] Gate passes with 21 frontend tests: `npm --prefix web run check`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(web): add authentication forms`

#### T11: Building the authenticated application shell

**What**: Add the main shell, sidebar slot, chat slot, sign-out action, responsive navigation button, and aria-live request status region.
**Where**: `web/src/app/AppShell.tsx`
**Depends on**: T10
**Reuses**: Profile role data and semantic HTML layout.
**Requirement**: WEB-42, WEB-43, WEB-44

**Done when**:

- [x] The shell has one sidebar and one main chat region.
- [x] The sidebar collapses below 768 px and is keyboard-operable.
- [x] Every shell action has an accessible name and status region is `aria-live`.
- [x] Component tests cover desktop, mobile, keyboard, and sign-out rendering.
- [x] Gate passes with 25 frontend tests: `npm --prefix web run check`.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add responsive application shell`

#### T12: Verifying authentication in the browser

**What**: Add Playwright coverage for successful login, invalid login, signup validation, logout, and duplicate-DOM detection during submit.
**Where**: `web/e2e/auth.spec.ts`
**Depends on**: T11, T6
**Reuses**: Local API/web test fixtures and the approved stub account.
**Requirement**: WEB-01, WEB-02, WEB-04, WEB-05, WEB-06

**Done when**:

- [x] The number of auth inputs never exceeds the pre-submit count during login.
- [x] Successful login shows the authenticated shell exactly once.
- [x] Invalid login keeps one form and clears only the password.
- [x] Logout returns to one login screen.
- [x] Gate passes with 128 Python, 26 frontend, and 5 browser tests:
  `venv/bin/python -m pytest -m "not integration" -q && npm --prefix web run check && npm --prefix web run e2e`.

**Tests**: e2e
**Gate**: Full
**Commit**: `test(web): cover authentication browser flow`

### Phase 3: Core chat backend

#### T13: Defining conversation API schemas

**What**: Add typed request/response models for profiles, conversations, messages, grouping metadata, and ownership-safe not-found responses.
**Where**: `api/schemas/conversations.py`
**Depends on**: T5
**Reuses**: Repository record fields from `database/conversations.py`.
**Requirement**: WEB-25, WEB-26, WEB-27, WEB-28

**Done when**:

- [x] Schemas represent ordered messages, SQL, errors, retry metadata, and favorites.
- [x] Unknown/foreign records cannot be represented as a successful response.
- [x] Unit tests cover required/optional fields and date serialization.
- [x] Gate passes with 38 API tests: `venv/bin/python -m pytest api/tests -q`.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(api): define conversation schemas`

#### T14: Adding conversation list and creation routes

**What**: Implement owner-scoped conversation listing with recency metadata and idempotent first-prompt creation.
**Where**: `api/routes/conversation_collection.py`
**Depends on**: T13, T5
**Reuses**: `ConversationRepository.list_sessions_with_expired_count` and `create_with_user_message`.
**Requirement**: WEB-25, WEB-26, WEB-29

**Done when**:

- [ ] First prompt creates one owned conversation and repeated request ID does not duplicate it.
- [ ] Results are grouped by browser-provided timezone metadata without changing persistence timestamps.
- [ ] Favorites are preserved and expiry cleanup remains owner-scoped.
- [ ] TestClient tests cover empty list, creation, duplicate request, grouping, and owner isolation.

**Tests**: integration
**Gate**: API
**Commit**: `feat(api): add conversation collection routes`

#### T15: Adding conversation detail and mutation routes

**What**: Implement message loading, favorite/unfavorite, and confirmed deletion for an owned conversation.
**Where**: `api/routes/conversation_item.py`
**Depends on**: T13, T5
**Reuses**: `ConversationRepository.get_messages`, `set_favorite`, and `delete`.
**Requirement**: WEB-27, WEB-28, WEB-29, WEB-30, WEB-31

**Done when**:

- [ ] Opening restores messages in order and never executes SQL.
- [ ] Foreign conversation IDs return 404 without leaking existence details.
- [ ] Deletion removes linked history through the repository contract.
- [ ] Tests cover detail, foreign access, favorite, delete confirmation, cancel/no-op, and context limit.

**Tests**: integration
**Gate**: API
**Commit**: `feat(api): add conversation item routes`

#### T16: Adding bounded result serialization

**What**: Convert pandas results to JSON-safe bounded payloads with columns, rows, row count, and truncation metadata.
**Where**: `api/serializers/results.py`
**Depends on**: T5
**Reuses**: DataFrame results returned by `PostgresAdapter`.
**Requirement**: WEB-18, WEB-19, WEB-20

**Done when**:

- [ ] Results are limited to 5,000 rows and expose `truncated`.
- [ ] Null-like, date, datetime, and Decimal values serialize deterministically.
- [ ] Unit tests cover empty, bounded, truncated, and special-value frames.

**Tests**: unit
**Gate**: quick
**Commit**: `feat(api): add bounded result serializer`

#### T17: Extracting the chat orchestration service

**What**: Move translation, idempotent message persistence, read-only validation, retry handling, and stored-query execution into an explicit service.
**Where**: `api/services/chat.py`
**Depends on**: T13, T16, T5
**Reuses**: `Translator`, `ConversationRepository`, `QueryHistoryRepository`, `PostgresAdapter`, and behavior in `app.py:310-425` and `app.py:863-1035`.
**Requirement**: WEB-10, WEB-11, WEB-12, WEB-13, WEB-14, WEB-15, WEB-16, WEB-17, WEB-18, WEB-21, WEB-22, WEB-23, WEB-24

**Done when**:

- [ ] Service methods have no Streamlit imports or session-state mutation.
- [ ] Prompt bounds, stable request IDs, six-turn context, warning responses, and retry reuse are explicit.
- [ ] Only stored read-only SQL reaches `execute_read_only_query`.
- [ ] Unit tests cover success, warning, translator failure, database failure, invalid SQL, duplicate request, and retry paths.

**Tests**: unit
**Gate**: Quick
**Commit**: `feat(api): extract chat orchestration service`

#### T18: Adding chat translation routes

**What**: Expose prompt submission and translation/review state through a credentialed API route.
**Where**: `api/routes/chat_translate.py`
**Depends on**: T17
**Reuses**: Chat service and conversation schemas.
**Requirement**: WEB-10, WEB-11, WEB-12, WEB-13, WEB-14, WEB-15, WEB-21, WEB-23, WEB-24

**Done when**:

- [ ] Empty/oversized prompts return 422 without persistence.
- [ ] Review mode returns stored SQL and no execution result.
- [ ] Warnings and translator failures use the documented response shape.
- [ ] TestClient tests cover double submit with one request ID, review on/off, warning, and translator outage.

**Tests**: integration
**Gate**: API
**Commit**: `feat(api): add chat translation route`

#### T19: Adding stored-query execution and retry routes

**What**: Expose explicit confirmation and retry operations that load SQL by request ID and never execute client-supplied SQL.
**Where**: `api/routes/chat_execute.py`
**Depends on**: T17
**Reuses**: Chat service and result serializer.
**Requirement**: WEB-14, WEB-16, WEB-17, WEB-18, WEB-19, WEB-20, WEB-22, WEB-24

**Done when**:

- [ ] Missing, foreign, or non-read-only stored SQL is rejected before the adapter call.
- [ ] Successful execution returns bounded results and chart metadata.
- [ ] Database failure stores a retryable assistant error.
- [ ] TestClient tests prove raw SQL in the request body is ignored and DELETE never reaches the adapter.

**Tests**: integration
**Gate**: Full
**Commit**: `feat(api): add stored query execution routes`

### Phase 4: Backend parity routes

#### T20: Adding query-history routes

**What**: Expose list, pin, unpin, delete, and stored-query rerun operations for the authenticated user.
**Where**: `api/routes/history.py`
**Depends on**: T5
**Reuses**: `QueryHistoryRepository` and stored-query chat execution.
**Requirement**: WEB-32, WEB-33, WEB-34

**Done when**:

- [ ] History is limited to 20, pinned first, and owner-scoped.
- [ ] Mutations cannot affect another user's record.
- [ ] Rerun uses stored read-only SQL and the active conversation.
- [ ] Route tests cover list, pin/unpin, delete, rerun, foreign ID, and database failure.

**Tests**: integration
**Gate**: Full
**Commit**: `feat(api): add query history routes`

#### T21: Adding shared-query routes

**What**: Expose catalog search, execution with bound parameters, favorites, and dev/dba/admin CRUD.
**Where**: `api/routes/predefined.py`
**Depends on**: T5
**Reuses**: `PredefinedQueryRepository.validate_query`, JSONB parameters, and role rules.
**Requirement**: WEB-35, WEB-36, WEB-37, WEB-38

**Done when**:

- [ ] Search returns shared rows with per-user favorite state.
- [ ] Required parameters are validated and bound; missing values return 422 naming the parameter.
- [ ] Unauthorized CRUD returns 403 and invalid SQL returns 422.
- [ ] Route tests cover search, parameter success/failure, favorite, CRUD role matrix, and invalid SQL.

**Tests**: integration
**Gate**: Full
**Commit**: `feat(api): add shared query routes`

#### T22: Adding administration routes

**What**: Expose admin-only profile listing and status/role mutations while preserving the last-approved-admin guard.
**Where**: `api/routes/admin.py`
**Depends on**: T5
**Reuses**: `UserRepository.list_profiles`, `set_status`, `set_role`, and last-admin protection.
**Requirement**: WEB-39, WEB-40

**Done when**:

- [ ] Non-admin callers receive 403 for every admin route.
- [ ] Admin can list and update allowed status/role values.
- [ ] Removing the last approved admin returns 409 and leaves data unchanged.
- [ ] Route tests cover role matrix, invalid values, success, and last-admin conflict.

**Tests**: integration
**Gate**: Full
**Commit**: `feat(api): add user administration routes`

#### T23: Adding schema synchronization route

**What**: Expose the existing schema refresh behavior through an approved-user route that rebuilds translator context and clears catalog caches.
**Where**: `api/routes/sync.py`
**Depends on**: T5
**Reuses**: `Prompter`, translator factory, and catalog cache invalidation currently at `app.py:1063-1068`.
**Requirement**: WEB-41

**Done when**:

- [ ] Approved users can trigger one explicit refresh.
- [ ] The refresh does not expose schema contents in the response.
- [ ] Failures return an explicit 503 error and do not claim success.
- [ ] Route tests cover approved, blocked, success, and failure paths.

**Tests**: integration
**Gate**: Full
**Commit**: `feat(api): add schema synchronization route`

### Phase 5: Chat frontend

#### T24: Building the conversation sidebar

**What**: Add the typed conversation query, grouped sidebar, new-conversation action, favorite/delete controls, and mobile drawer integration.
**Where**: `web/src/features/conversations/ConversationSidebar.tsx`
**Depends on**: T14, T15, T8
**Reuses**: Group labels and ownership semantics from `grouped_sessions` and conversation repositories.
**Requirement**: WEB-25, WEB-26, WEB-27, WEB-28, WEB-29, WEB-30, WEB-42, WEB-43

**Done when**:

- [ ] Empty, loading, error, selected, favorite, delete-confirmation, and mobile states are rendered.
- [ ] Conversation selection does not execute SQL automatically.
- [ ] Component tests cover grouping, owner-safe actions, and empty state.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add conversation sidebar`

#### T25: Building chat request state

**What**: Add the chat hook/store for stable request IDs, message updates, review state, retry, and pending status without unmounting prior messages.
**Where**: `web/src/features/chat/useChat.ts`
**Depends on**: T18, T19, T8
**Reuses**: API contracts and message models from T13/T17.
**Requirement**: WEB-10, WEB-11, WEB-12, WEB-13, WEB-14, WEB-15, WEB-23, WEB-24

**Done when**:

- [ ] One send creates one user message and one assistant request state.
- [ ] Double-click and network retry reuse the same request ID.
- [ ] Review confirmation/cancel and retry update only the target request.
- [ ] Unit tests cover pending, success, warning, failure, retry, review on/off, and duplicate submission.

**Tests**: unit
**Gate**: Quick
**Commit**: `feat(web): add chat request state`

#### T26: Rendering chat messages and status

**What**: Render user/assistant messages, pending status, errors, warnings, retry action, and aria-live updates exactly once.
**Where**: `web/src/features/chat/MessageList.tsx`
**Depends on**: T25
**Reuses**: Message shape from API schemas and current `components.py` content semantics.
**Requirement**: WEB-10, WEB-11, WEB-14, WEB-15, WEB-44

**Done when**:

- [ ] Stable React keys use request IDs and do not duplicate on state updates.
- [ ] Earlier messages remain mounted during pending requests.
- [ ] Retry buttons are disabled while the target request is pending.
- [ ] Component tests cover one-render-per-message, warning, error, retry, and live status.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add chat message rendering`

#### T27: Building composer, SQL review, results, charts, and CSV

**What**: Add keyboard-aware composer, review controls, bounded result table, bar/line chart rendering, missing-column warning, truncation notice, and CSV download.
**Where**: `web/src/features/chat/ChatWorkspace.tsx`
**Depends on**: T25, T26
**Reuses**: Current review/result/chart behavior from `components.py` and `app.py`.
**Requirement**: WEB-12, WEB-18, WEB-19, WEB-20, WEB-45

**Done when**:

- [ ] Enter submits and Shift+Enter inserts a newline.
- [ ] Review mode cannot execute before confirmation and cancel clears only review state.
- [ ] Results, truncation, chart success/failure, and UTF-8 CSV are rendered correctly.
- [ ] Component tests cover keyboard, disabled/pending, review, result, chart, and CSV paths.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add chat workspace controls`

### Phase 6: Parity frontend

#### T28: Building the history panel

**What**: Add history loading, pinned ordering, pin/unpin/delete actions, and stored-query rerun controls.
**Where**: `web/src/features/history/HistoryPanel.tsx`
**Depends on**: T20, T8
**Reuses**: Query-history API contract and active conversation state.
**Requirement**: WEB-32, WEB-33, WEB-34

**Done when**:

- [ ] Loading, empty, error, and populated states are accessible.
- [ ] Pin/delete mutations invalidate only the current user's list.
- [ ] Rerun uses the stored record and displays the result in chat.
- [ ] Component tests cover ordering, actions, and failure feedback.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add query history panel`

#### T29: Building the shared-query panel

**What**: Add catalog search, parameter form, favorite action, role-gated CRUD controls, and execution feedback.
**Where**: `web/src/features/predefined/PredefinedQueriesPanel.tsx`
**Depends on**: T21, T8
**Reuses**: Shared-query parameter and role contract.
**Requirement**: WEB-35, WEB-36, WEB-37, WEB-38

**Done when**:

- [ ] Search and empty states are rendered without duplicate requests.
- [ ] Required parameters are labeled and validated before execution.
- [ ] CRUD controls are absent for unauthorized roles and errors are inline.
- [ ] Component tests cover search, parameter validation, favorite, role gating, and execution.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add shared query panel`

#### T30: Building the user administration panel

**What**: Add admin-only profile table, status/role controls, validation, conflict feedback, and refresh behavior.
**Where**: `web/src/features/admin/UserAdminPanel.tsx`
**Depends on**: T22, T8
**Reuses**: Profile and role models.
**Requirement**: WEB-39, WEB-40

**Done when**:

- [ ] Non-admin users do not render the panel.
- [ ] Admin updates show success/failure without remounting unrelated chat state.
- [ ] Last-admin conflicts are presented as actionable errors.
- [ ] Component tests cover role gating, status/role update, validation, and 409 conflict.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): add user administration panel`

#### T31: Building schema synchronization control

**What**: Add the sync action, pending state, success toast, and explicit failure feedback.
**Where**: `web/src/features/settings/SyncDatabaseButton.tsx`
**Depends on**: T23, T8
**Reuses**: Sync route contract.
**Requirement**: WEB-41

**Done when**:

- [ ] The button cannot submit twice while syncing.
- [ ] Success invalidates translator/catalog queries and shows confirmation.
- [ ] Failure is visible and does not claim that sync completed.
- [ ] Component tests cover pending, success, and failure.

**Tests**: unit
**Gate**: Quick
**Commit**: `feat(web): add schema sync control`

#### T32: Integrating responsive accessibility layout

**What**: Compose sidebar, history/catalog/admin panels, chat workspace, mobile drawer, focus behavior, labels, and keyboard navigation into the authenticated shell.
**Where**: `web/src/app/AuthenticatedApp.tsx`
**Depends on**: T24, T26, T28, T29, T30, T31
**Reuses**: App shell and independently tested feature panels.
**Requirement**: WEB-42, WEB-43, WEB-44, WEB-45

**Done when**:

- [ ] Desktop and 360px layouts have no horizontal overflow.
- [ ] The composer remains usable at the bottom of the main column.
- [ ] Keyboard-only navigation reaches every action and focus moves predictably when panels open.
- [ ] Accessibility/component tests cover labels, tab order, mobile menu, and live status.

**Tests**: unit
**Gate**: Frontend
**Commit**: `feat(web): integrate authenticated app layout`

#### T33: Verifying chat transitions in the browser

**What**: Add E2E coverage for prompt send, review, execute, retry, results, CSV, chart, and duplicate-DOM detection.
**Where**: `web/e2e/chat.spec.ts`
**Depends on**: T27, T32
**Reuses**: API stubs and browser fixtures from T12.
**Requirement**: WEB-10, WEB-11, WEB-12, WEB-13, WEB-14, WEB-15, WEB-16, WEB-17, WEB-18, WEB-19, WEB-20, WEB-21, WEB-22, WEB-23, WEB-24

**Done when**:

- [ ] Double-clicking send produces one user message and one assistant request.
- [ ] Input and message counts do not increase during translation or execution.
- [ ] Review, retry, warning, error, result, chart, and CSV flows pass.
- [ ] The suite passes with the translator/database stubbed and with the API contract fixtures.

**Tests**: e2e
**Gate**: Full
**Commit**: `test(web): cover chat browser flow`

#### T34: Verifying feature parity in the browser

**What**: Add E2E coverage for conversation resume/ownership, history, shared queries, admin controls, schema sync, and responsive navigation.
**Where**: `web/e2e/parity.spec.ts`
**Depends on**: T28, T29, T30, T31, T32
**Reuses**: Browser fixtures and role-specific accounts.
**Requirement**: WEB-25, WEB-26, WEB-27, WEB-28, WEB-29, WEB-30, WEB-31, WEB-32, WEB-33, WEB-34, WEB-35, WEB-36, WEB-37, WEB-38, WEB-39, WEB-40, WEB-41, WEB-42, WEB-43, WEB-44, WEB-45

**Done when**:

- [ ] Each existing user-facing feature has one happy-path and one relevant failure/authorization assertion.
- [ ] Owner isolation is proven with two fixture users.
- [ ] Responsive and keyboard assertions pass at desktop and 360px viewports.

**Tests**: e2e
**Gate**: Full
**Commit**: `test(web): cover feature parity browser flow`

### Phase 7: Documentation and conditional cutover

#### T35: Documenting local API and web commands

**What**: Document environment variables, API start command, web start command, test commands, coexistence ports, and cutover prerequisites.
**Where**: `README.md`
**Depends on**: T33, T34
**Reuses**: Existing installation/testing sections.
**Requirement**: WEB-47, WEB-48, WEB-49

**Done when**:

- [ ] A contributor can start API and web independently using documented commands.
- [ ] The README states that Streamlit remains available until the Verifier PASS and owner approval.
- [ ] The README does not instruct users to expose cookies, Supabase secrets, or raw SQL.
- [ ] Manual documentation review is complete.

**Tests**: none
**Gate**: Build
**Commit**: `docs(migration): document api and web commands`

#### T36: Removing the Streamlit entry point after approval

**What**: Remove the legacy Streamlit application entry point only after the Verifier PASS and explicit user approval.
**Where**: `app.py`
**Depends on**: T35
**Reuses**: New API/web entry points and all migration validation evidence.
**Requirement**: WEB-46

**Done when**:

- [ ] User approval and Verifier PASS are recorded before the change.
- [ ] No documented start command points to `streamlit run app.py`.
- [ ] Full backend/frontend/E2E gates pass after removal.

**Tests**: none
**Gate**: Full
**Commit**: `refactor(cutover): remove streamlit entry point`

#### T37: Removing legacy Streamlit rendering components

**What**: Remove the obsolete Streamlit rendering module after the entry point is gone.
**Where**: `components.py`
**Depends on**: T36
**Reuses**: React components and API contracts that replaced its behavior.
**Requirement**: WEB-46

**Done when**:

- [ ] No runtime import references `components.py`.
- [ ] Frontend parity E2E remains green.
- [ ] `git grep -n streamlit` reports only approved historical/spec references, if any.

**Tests**: none
**Gate**: Full
**Commit**: `refactor(cutover): remove streamlit components`

#### T38: Removing legacy Streamlit application tests

**What**: Remove tests that exercise only the deleted Streamlit entry point after equivalent API/frontend coverage is green.
**Where**: `test_app.py`
**Depends on**: T37
**Reuses**: API and Playwright regression coverage.
**Requirement**: WEB-46

**Done when**:

- [ ] No unique acceptance criterion loses coverage.
- [ ] Remaining Python tests pass.
- [ ] The removed tests are listed in the cutover evidence.

**Tests**: none
**Gate**: Full
**Commit**: `test(cutover): remove streamlit app tests`

#### T39: Removing legacy Streamlit component tests

**What**: Remove Streamlit-only component tests after React component and E2E tests cover their behavior.
**Where**: `test_chat_ui.py`
**Depends on**: T38
**Reuses**: React unit and Playwright tests.
**Requirement**: WEB-46

**Done when**:

- [ ] Every removed UI assertion maps to a React unit or E2E test.
- [ ] The remaining Python test suite passes.
- [ ] No test imports Streamlit rendering code.

**Tests**: none
**Gate**: Full
**Commit**: `test(cutover): remove streamlit component tests`

#### T40: Removing Streamlit theme configuration

**What**: Remove the unused Streamlit theme configuration after the new web build is authoritative.
**Where**: `.streamlit/config.toml`
**Depends on**: T39
**Reuses**: React CSS and layout tests.
**Requirement**: WEB-46

**Done when**:

- [ ] The frontend build and browser suite pass without Streamlit configuration.
- [ ] No start or test command references the removed file.

**Tests**: none
**Gate**: Build
**Commit**: `refactor(cutover): remove streamlit theme config`

#### T41: Removing the Streamlit dependency and closing the cutover

**What**: Remove Streamlit from the Python dependency manifest and finalize documentation and state evidence.
**Where**: `requirements.txt`
**Depends on**: T40
**Reuses**: FastAPI and web commands documented in T35.
**Requirement**: WEB-46, WEB-49

**Done when**:

- [ ] `git grep -n streamlit` has no runtime dependency/import references.
- [ ] Python and frontend build/test gates pass from a clean environment.
- [ ] The Verifier writes `validation.md` with PASS and the migration state is closed.

**Tests**: none
**Gate**: Build
**Commit**: `refactor(cutover): remove streamlit dependency`

## Requirement Traceability

| Requirement range | Tasks |
| ----------------- | ----- |
| WEB-01..WEB-09 | T1-T12 |
| WEB-10..WEB-24 | T16-T19, T25-T27, T33 |
| WEB-25..WEB-31 | T13-T15, T24, T34 |
| WEB-32..WEB-38 | T20-T21, T28-T29, T34 |
| WEB-39..WEB-41 | T22-T23, T30-T31, T34 |
| WEB-42..WEB-45 | T11, T24, T26-T27, T32, T34 |
| WEB-46..WEB-49 | T2, T7, T8, T35-T41 |

**Coverage**: 49 total, 49 mapped to tasks, 0 unmapped.

## Pre-Approval Cross-Checks

### Granularity check

Each task has one primary deliverable: one module, route family, component, browser spec, documentation file, or cutover file. No task combines unrelated backend and frontend changes.

### Diagram-definition cross-check

The arrows in each phase diagram represent every same-phase `Depends on` edge. Cross-phase dependencies are intentionally declared in task bodies and are satisfied by the preceding phase; the validator checks that no dependency points forward.

### Test co-location validation

| Task family | Matrix requirement | Task field | Result |
| ----------- | ------------------ | ----------- | ------ |
| API settings/services/serializers | unit | `Tests: unit` | ✅ |
| API app/routes | integration | `Tests: integration` | ✅ |
| React client/hooks/components | unit | `Tests: unit` | ✅ |
| Browser specs | e2e | `Tests: e2e` | ✅ |
| Config/docs/cutover deletion | none | `Tests: none` | ✅ |
