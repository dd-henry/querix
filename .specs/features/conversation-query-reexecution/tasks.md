# Conversation Query Re-execution Tasks

## Execution Protocol

Implement one task at a time. Each task is tested, gated, marked done, and
committed before the next task begins.

**Design**: `.specs/features/conversation-query-reexecution/design.md`
**Status**: Done

## Test Coverage Matrix

> Generated from `README.md`, `docs/testes.md`, `web/package.json`, and existing
> frontend tests. No project lint command is configured.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Chat state and UI | unit | Restored SQL marker, action visibility, identifier-only execution, same-message update, failure retry, and no-SQL absence | `web/src/features/chat/*.test.tsx` | `npm --prefix web run check` |
| Conversation resume | e2e | Open saved conversation, reexecute, current result, stable message count | `web/e2e/parity.spec.ts` | `npm --prefix web run e2e` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After state/UI unit task | `npm --prefix web run check` |
| Full | After E2E task | `npm --prefix web run check && npm --prefix web run e2e` |
| Build | Final task | `npm --prefix web run check && npm --prefix web run build && npm --prefix web run e2e` |

## Execution Plan

### Phase 1: Restored query action

```text
T1
```

### Phase 2: Browser verification and documentation

```text
T1 -> T2
```

### Phase 3: Closing restored failure coverage

```text
T1 -> T2 -> T3
```

## Task Breakdown

### T1: Exposing restored query re-execution

**Status**: Done

**What**: Mark restored assistant messages with stored SQL as re-executable
and render an action that reuses the existing stored-query execution callback.
Add unit coverage for visibility, identifier-only execution, same-message
updates, retry failure behavior, and no-SQL messages.
**Where**: `web/src/features/chat/useChat.ts`,
`web/src/features/chat/ChatWorkspace.tsx`,
`web/src/features/chat/useChat.test.tsx`,
`web/src/features/chat/ChatWorkspace.test.tsx`
**Depends on**: None
**Requirement**: CQR-01, CQR-02, CQR-03, CQR-04, CQR-05

**Done when**:

- [x] Restored successful messages with SQL expose `reexecuteAvailable`.
- [x] The action displays the stored SQL and invokes the existing execute
      callback with the original request ID.
- [x] Successful execution replaces the same assistant message with results.
- [x] Failed execution keeps the message retryable without duplicate controls.
- [x] Messages without SQL do not display the action.

**Tests**: unit
**Gate**: quick

### T2: Covering conversation resume end to end

**Status**: Done

**What**: Extend the conversation-resume browser scenario to execute the
restored query and verify current results and stable message count. Document
the restored-query action in the architecture guide.
**Where**: `web/e2e/parity.spec.ts`, `docs/arquitetura_e_funcionamento.md`
**Depends on**: T1
**Requirement**: CQR-01, CQR-02, CQR-03

**Done when**:

- [x] The E2E scenario opens a saved conversation and sees the
      `Reexecutar consulta` action.
- [x] The E2E scenario mocks execution, sees the fresh result, and confirms
      one user and one assistant message remain.
- [x] Documentation states that reopened SQL can be reexecuted.

**Tests**: e2e
**Gate**: build

### T3: Covering restored execution failures

**Status**: Done

**What**: Add focused unit coverage for a restored query that fails during
execution, including retry visibility, stable message identity, and the
existing pending-request guard.
**Where**: `web/src/features/chat/useChat.test.tsx`,
`web/src/features/chat/ChatWorkspace.test.tsx`
**Depends on**: T2
**Requirement**: CQR-04

**Done when**:

- [x] A restored execution failure remains on the same assistant message,
      becomes retryable, and keeps the timeline at two messages.
- [x] The failed restored message shows `Tentar novamente` and not
      `Reexecutar consulta`.
- [x] A second restored execution click while pending does not issue another
      execute request.

**Tests**: unit
**Gate**: quick
