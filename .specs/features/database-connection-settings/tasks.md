# Configuração da conexão do banco consultado Tasks

**Spec:** `.specs/features/database-connection-settings/spec.md`
**Design:** `.specs/features/database-connection-settings/design.md`
**Status:** implementing

## Test Coverage Matrix

> Generated from [README.md](/Users/ddhenry/Documents/dev/ask-sql/README.md),
> `docs/testes.md`, existing pytest/Vitest tests, and this feature spec.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Encryption/repository | unit | Save, decrypt, status-only response, and unchanged value on failed test | `test_database_connections.py` | `venv/bin/pytest -q test_database_connections.py` |
| API routes/dependencies | unit | Every new endpoint: admin success, non-admin denial, missing target, invalid input, failed test, and cache invalidation | `api/tests/test_database_settings.py`, `api/tests/test_dependencies.py` | `venv/bin/pytest -q api/tests/test_database_settings.py api/tests/test_dependencies.py` |
| Frontend API client | unit | Typed request paths, payloads, and response/error behavior | `web/src/api/client.test.ts` | `npm --prefix web test -- --run src/api/client.test.ts` |
| Frontend component/integration | unit | Initial status, save success, duplicate-submit guard, and failure feedback | `web/src/features/settings/DatabaseConnectionSettings.test.tsx`, `web/src/app/AuthenticatedApp.test.tsx` | `npm --prefix web test -- --run src/features/settings/DatabaseConnectionSettings.test.tsx src/app/AuthenticatedApp.test.tsx` |
| Build/configuration | none | Type-check and production build | `web/`, `requirements.txt`, docs | `venv/bin/pytest -q && npm --prefix web run build` |

## Gate Check Commands

> Generated from the project commands in the repository instructions.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Backend or frontend unit task | `venv/bin/pytest -q <focused tests> && npm --prefix web test -- --run <focused tests>` |
| Full | Route/adapter integration task | `venv/bin/pytest -q api/tests test_database_connections.py test_postgres.py` |
| Build | Final task or docs/config task | `venv/bin/pytest -q && npm --prefix web run build` |

## Execution Plan

```text
T1 -> T2 -> T3 -> T4 -> T5 -> T6 -> T7 -> T8 -> T9
```

## Task Breakdown

### Phase 1: Backend foundation

#### T1: Add explicit PostgreSQL target adapter construction ✅

**Depends on**: none
**Where**: `database/postgres.py`, `test_postgres.py`
**Tests**: Unit tests cover explicit URL construction, accepted PostgreSQL URL forms, and rejection of unsupported URLs.
**Gate**: Quick: `venv/bin/pytest -q test_postgres.py`
- **Done when:** `PostgresAdapter` can be constructed from a validated explicit target URL without reading a target URL from the environment, while existing environment-based tests remain green.

#### T2: Persist encrypted global target connection ✅

**Depends on**: T1
**Where**: `database/database_connections.py`, `test_database_connections.py`, `requirements.txt`
**Tests**: Unit tests cover encrypted storage, decryption, status without secret, and lazy table initialization.
**Gate**: Quick: `venv/bin/pytest -q test_database_connections.py`
- **Done when:** The repository stores one encrypted target connection in the internal database, returns status without plaintext, and decrypts only for server-side target resolution.

### Phase 2: Backend API and wiring

#### T3: Add admin-only target connection API ✅

**Depends on**: T2
**Where**: `api/routes/database_settings.py`, `api/schemas/database_settings.py`, `api/tests/test_database_settings.py`
**Tests**: Route tests cover status, successful test-and-save, invalid input, failed test preserving prior state, and non-admin `403`.
**Gate**: Full: `venv/bin/pytest -q api/tests/test_database_settings.py`
- **Done when:** `GET` and `PUT /api/settings/database` implement the specified status, authorization, validation, test-before-save, and error contracts.

#### T4: Route target operations through the configured adapter ✅

**Depends on**: T3
**Where**: `api/dependencies.py`, `api/routes/predefined.py`, `api/routes/sync.py`, `api/app.py`, `api/tests/test_dependencies.py`, `api/tests/test_sync_routes.py`, `api/tests/test_predefined_routes.py`
**Tests**: Tests cover missing target `503`, cache invalidation, and successful target dependency wiring without changing internal repository wiring.
**Gate**: Full: `venv/bin/pytest -q api/tests`
- **Done when:** Schema sync, chat service construction, and predefined-query execution use the configured target; internal repositories still use `get_db_adapter`; missing target returns `database_not_configured`.

#### T5: Use target adapter for history and chat execution ✅

**Depends on**: T4
**Where**: `api/dependencies.py`, `api/tests/test_chat_service.py`, `api/tests/test_history_routes.py`
**Tests**: Existing chat/history execution tests are updated only where the dependency boundary changes and assert target execution while persistence uses the internal repositories.
**Gate**: Full: `venv/bin/pytest -q api/tests/test_chat_service.py api/tests/test_history_routes.py`
- **Done when:** Chat execution, supporting queries, and history reruns execute through the target adapter and retain existing user-scoped persistence behavior.

### Phase 3: Frontend

#### T6: Add typed settings client methods ✅

**Depends on**: T3
**Where**: `web/src/api/client.ts`, `web/src/api/client.test.ts`
**Tests**: Client tests assert the exact GET path, PUT payload, and typed response handling.
**Gate**: Quick: `npm --prefix web test -- --run src/api/client.test.ts`
- **Done when:** The frontend can read target status and save a connection string through the existing API client.

#### T7: Build and integrate the admin connection settings panel ✅

**Depends on**: T6
**Where**: `web/src/features/settings/DatabaseConnectionSettings.tsx`, `web/src/features/settings/DatabaseConnectionSettings.test.tsx`, `web/src/app/AuthenticatedApp.tsx`, `web/src/app/AuthenticatedApp.test.tsx`, `web/src/styles.css`
**Tests**: Component tests cover status loading, save success, duplicate-submit prevention, failure feedback, and admin-only rendering.
**Gate**: Build: `npm --prefix web test -- --run && npm --prefix web run build`
- **Done when:** Admins see a connection-string form in Configurações, the secret is not echoed, save feedback is explicit, and existing schema synchronization remains available.

### Phase 4: Documentation and final verification

#### T8: Document internal and target database configuration ✅

**Depends on**: T7
**Where**: `README.md`
**Tests**: none (documentation only).
**Gate**: Build: `venv/bin/pytest -q && npm --prefix web run build`
- **Done when:** Deployment documentation states that `DATABASE_URL` is internal, target configuration is performed in the admin UI, and missing target behavior is documented.

### Verification fix

#### T9: Harden target failure handling and verification evidence ✅

**Depends on**: T8
**Where**: `database/postgres.py`, `api/dependencies.py`, target settings and operation tests
**Tests**: Secret-safe connection failure logging, corrupt configuration mapping, exact `SELECT 1` ordering, prior-value preservation, cache invalidation, and missing-target endpoint responses.
**Gate**: Full: `venv/bin/pytest -q`
- **Done when:** Target connection failures never log the connection string, corrupt encrypted configuration returns the documented API error, and the feature's required endpoint behavior and side effects have direct assertions.

## Traceability

| Task | Requirements |
| --- | --- |
| T1 | DCS-002 |
| T2 | DCS-009 |
| T3 | DCS-001, DCS-003, DCS-004, DCS-005, DCS-010 |
| T4 | DCS-006, DCS-007, DCS-011 |
| T5 | DCS-008 |
| T6 | DCS-001, DCS-003 |
| T7 | DCS-001, DCS-010 |
| T8 | DCS-006 |
| T9 | DCS-002, DCS-004, DCS-007, DCS-010, DCS-011 |
