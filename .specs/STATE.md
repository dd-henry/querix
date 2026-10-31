# Project State

## Decisions

### AD-001
- **Decision**: The interface moves from Streamlit to a React + TypeScript + Vite single-page app served against a FastAPI backend; Streamlit stays only until the new UI passes verification.
- **Reason**: Streamlit's full-script rerun produced duplicated forms and transient elements during login and query execution (reproduced: 4 → 6 → 4 inputs during a login submit, even after removing spinners).
- **Trade-off**: Two apps coexist during the migration and the API layer must be built and tested.
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

## Handoff

Feature: web-frontend-migration
Phase: 5 - Chat frontend
Current batch: T27 in Phase 5, resumed inline
Completed: Specification, design, tasks, dependency validation, execution-mode approval, Streamlit auth stabilization, T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14, T15, T16, T17, T18, T19, T20, T21, T22, T23, T24, T25, and T26
In progress: T27 in Phase 5
Next step: Build composer, SQL review, results, charts, and CSV in T27
Blockers: None
Uncommitted files: T26 implementation and test files, pending atomic commit
Branch: main
