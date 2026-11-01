# Conversation Query Re-execution Specification

## Problem Statement

When a saved conversation is opened, the API returns the assistant message and
its stored SQL, but the web state does not expose an execution action for that
restored message. Users can read the conversation but cannot run the saved
query again to obtain current data.

## Goals

- Show a clear re-execution action for a restored assistant message that has
  stored SQL.
- Reuse the existing server-side stored-query execution route.
- Keep the conversation timeline stable and update the same assistant message
  with fresh results.
- Preserve the existing retry and read-only safety boundaries.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Sending raw SQL from the browser | The server already stores and validates the SQL. |
| Adding a new execution endpoint | `/api/chat/execute` already supports stored queries. |
| Persisting result rows in conversations | Results remain current, transient response data. |
| Re-executing a message without stored SQL | There is no safe query to execute. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Re-execution action | Use the existing `confirmExecution` callback and `/api/chat/execute` | It already sends only conversation and request identifiers and preserves idempotency. | yes |
| Restored successful message | Mark it as re-executable in client state when it has SQL and is not already retryable | The API omits result rows when loading a conversation, so the SQL is the durable signal. | yes |
| Failed restored execution | Keep the existing retry button as the single recovery action | Avoids two duplicate controls for the same failed operation. | yes |

**Open questions:** none.

## User Stories

### P1: Re-run a saved query

As a user, I want to re-execute a query from an opened conversation, so that
I can see current database results without asking the same question again.

### P1: Stable conversation

As a user, I want re-execution to update the existing assistant response, so
that the chat does not gain duplicate user or assistant messages.

## Acceptance Criteria

1. WHEN an opened conversation contains an assistant message with stored SQL
   and no retryable failure THEN the web UI SHALL display the SQL and a
   `Reexecutar consulta` action.
2. WHEN the user activates `Reexecutar consulta` THEN the client SHALL call
   `/api/chat/execute` with the stored conversation ID and request ID and SHALL
   not send raw SQL in the request body.
3. WHEN stored-query execution succeeds THEN the UI SHALL render the fresh
   result on the same assistant message and SHALL not add another timeline
   message.
4. IF stored-query execution fails THEN the UI SHALL preserve the existing
   message and expose the existing retry action without adding a duplicate
   timeline message.
5. WHEN an opened assistant message has no stored SQL THEN the UI SHALL not
   display a re-execution action.

## Edge Cases

- A restored assistant message with an execution failure remains retryable but
  does not show two equivalent recovery controls.
- Re-execution of a query with parameters uses the server-persisted parameters.
- A second click while execution is pending remains guarded by the existing
  active-request lock.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| CQR-01 | P1: Re-run a saved query | Execute | Implemented in T1 |
| CQR-02 | P1: Re-run a saved query | Execute | Implemented in T1 |
| CQR-03 | P1: Stable conversation | Execute | Implemented in T1 |
| CQR-04 | P1: Stable conversation | Execute | Implemented in T1 |
| CQR-05 | P1: Re-run a saved query | Execute | Implemented in T1 |

## Success Criteria

- Opening the conversation shown in the reported bug displays a `Reexecutar
  consulta` action.
- Clicking it executes the stored server-side query and renders fresh results
  in the original assistant message.
- The timeline keeps the same user/assistant message count.
