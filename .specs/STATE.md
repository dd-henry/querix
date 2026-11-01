# Project State

## Decisions

### AD-001
- **Decision**: The authoritative interface is a React + TypeScript + Vite single-page app served against a FastAPI backend; the legacy Streamlit interface was removed after the new UI passed verification and received owner approval.
- **Reason**: Streamlit's full-script rerun produced duplicated forms and transient elements during login and query execution (reproduced: 4 → 6 → 4 inputs during a login submit, even after removing spinners).
- **Trade-off**: The project no longer carries a second UI runtime, but the React and API gates must remain green.
- **Scope**: Whole project; `api/` (backend), `web/` (frontend), existing `core/` and `database/` reused.
- **Date**: 2026-10-31
- **Status**: active

### AD-002
- **Decision**: The API owns authentication and issues a signed httpOnly, SameSite=Lax session cookie; Supabase is used only on the server with a fresh client per login/signup call.
- **Reason**: Keeps tokens out of browser storage and removes the shared Supabase client session state that exists today.
- **Trade-off**: Requires a `SESSION_SECRET`, an Origin check on mutating requests, and a DB profile lookup on every request.
- **Scope**: `api/` auth, session, and dependencies.
- **Date**: 2026-10-31
- **Status**: active

### AD-003
- **Decision**: Every SQL execution exposed through the API is read-only (`execute_read_only_query` plus read-only validation), and clients never send raw SQL to execute; chat and history execute the SQL stored server-side and the catalog executes stored SQL with bound parameters.
- **Reason**: The current chat path uses `execute_query`, which allows writes; behind an HTTP API that becomes a remote write endpoint.
- **Trade-off**: Generated INSERT/UPDATE/DELETE statements can no longer be executed from the chat.
- **Scope**: `api/services/chat.py`, history, and catalog routes.
- **Date**: 2026-10-31
- **Status**: active

### AD-004
- **Decision**: Analytical query generation uses an in-process semantic context layer enriched with staged planning, validation, bounded repair, and result diagnostics.
- **Reason**: A structured semantic boundary improves schema accuracy and query recoverability without introducing a separately deployed service.
- **Trade-off**: Complex questions may require additional local model calls and therefore higher latency.
- **Scope**: `core/`, `api/services/chat.py`, `database/`, `web/src/features/chat/`, and `evaluation/`.
- **Date**: 2026-11-01
- **Status**: active

## Handoff

Feature: web-frontend-migration
Phase: 7 - Documentation and cutover complete
Current batch: T36-T41 completed after verifier PASS and owner approval
Completed: Specification, design, tasks, dependency validation, execution-mode approval, T1-T41, legacy Streamlit removal, and final backend/frontend/E2E gates
In progress: None
Next step: None
Blockers: None
Uncommitted files: None
Branch: main
