# Chat UX and Interaction Stability Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: activate it by name and follow its Execute flow and Critical Rules. Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, Verifier, and discrimination sensor).

If the skill cannot be activated, stop and tell the user.

---

**Design**: `.specs/features/chat-ux-stability/design.md`
**Status**: In Progress

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `README.md`, `docs/testes.md`, `pytest.ini`; no project-specific agent instructions, linter, formatter, or build configuration was found.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Conversation repository / data access | unit | Every repository operation; owner isolation, duplicate request, expiry/favorite, deletion, ordering, persistence failure, and each applicable spec edge case | `test_conversations.py` | `python3 -m pytest test_conversations.py -q` |
| Query-history repository | unit | Existing behavior plus session-scoped de-duplication, legacy null-session behavior, and linked-record deletion | `test_query_history.py` | `python3 -m pytest test_query_history.py -q` |
| SQL translator | unit | No-context compatibility, ordered prior-turn context, maximum six turns, and Ollama failure behavior | `test_translator.py` | `python3 -m pytest test_translator.py -q` |
| Streamlit components and application flow | unit | 1:1 coverage of CHAT-01 through CHAT-08 and CHAT-19 through CHAT-23; prompt/result/error rendered once; pending/retry, session navigation, roles, preserved tools, and authentication feedback | `test_chat_ui.py` | `python3 -m pytest test_chat_ui.py -q` |
| Documentation | none | Manual review for consistency with implemented behavior | `README.md`, `docs/arquitetura_e_funcionamento.md`, `docs/testes.md` | No documentation test command is configured |

## Gate Check Commands

> Generated from codebase - confirm before Execute.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | After a task with focused unit tests | `python3 -m pytest -m "not integration" -q` |
| Full | After application integration or phase completion | `python3 -m pytest -m "not integration" -q` |
| Build | After the final code phase or documentation-only task | `python3 -m compileall -q app.py components.py core database test_*.py && python3 -m pytest -m "not integration" -q` |

No linter or formatter is configured in the repository. The integration marker is excluded because its Ollama dependency is external; feature tests use mocks and run without a database or Ollama service.

---

## Execution Plan

Phases run in order. Tasks execute sequentially within each phase. A phase boundary orders work but does not imply an unlisted task dependency.

### Phase 1: Conversation persistence

```text
T1 → T2
```

### Phase 2: Translation and chat rendering

```text
T3    T4
```

T3 and T4 are independent and execute in listed order.

### Phase 3: Application integration

```text
T1 -> T5
T2 -> T5
T3 -> T5
T4 -> T5
```

### Phase 4: Documentation

```text
T6    T7    T8
```

The three documentation updates are independent.

---

## Task Breakdown

### T1: Creating user-owned conversation storage

**Status**: Done

**What**: Add the PostgreSQL conversation repository for idempotent, ordered session/message persistence, per-user reads and mutations, favorite state, and one-year expiry cleanup on the owner's list request.
**Where**: `database/conversations.py`
**Depends on**: None
**Reuses**: `database/postgres.py` parameterized commands and transaction handling.
**Requirement**: CHAT-10, CHAT-11, CHAT-14, CHAT-15, CHAT-16, CHAT-17, CHAT-18

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [x] Sessions and messages use UUID ownership, role validation, ordered IDs, and uniqueness on `(session_id, request_id, role)`.
- [x] Every list/load/append/favorite/delete operation is scoped to the supplied owner ID.
- [x] Expiry removes only the owner's non-favorite sessions at or beyond one year of inactivity.
- [x] Favorites survive expiry; deleting an owned session removes its messages.
- [x] Database failures propagate to the caller instead of returning success-shaped defaults.
- [x] 12 focused repository tests cover creation, duplicate writes, ordering, owner isolation, favorite, expiry, deletion, context bounds, and database errors.
- [x] Gate check passes: `venv/bin/python -m pytest test_conversations.py -q` (12 passed).

**Tests**: unit
**Gate**: quick

**Commit**: `feat(chat): add user-owned conversation storage`

### T2: Linking query history to conversations

**What**: Add nullable session linkage to query-history records, preserve legacy null-linked rows, scope de-duplication by session, and cascade linked records when a session is deleted.
**Where**: `database/query_history.py`
**Depends on**: T1
**Reuses**: Existing `QueryHistoryRepository` user-scoped list/pin/delete and deduplication behavior.
**Requirement**: CHAT-15, CHAT-16

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Initialization adds the nullable foreign key without assigning old rows to a new session.
- [ ] Session-linked records do not replace another session's matching query record.
- [ ] Existing calls without a session ID preserve legacy behavior.
- [ ] At least 4 focused tests cover linked writes, session-scoped de-duplication, null-linked legacy behavior, and migration/query parameters; all existing `test_query_history.py` tests still pass.
- [ ] Gate check passes: `python3 -m pytest test_query_history.py -q`.

**Tests**: unit
**Gate**: quick

**Commit**: `feat(history): link query history to conversations`

### T3: Supplying bounded conversation context to translation

**What**: Extend SQL translation to accept ordered prior user/assistant messages while preserving existing behavior when no context is supplied.
**Where**: `core/translator.py`
**Depends on**: None
**Reuses**: Current Ollama call and JSON response parser.
**Requirement**: CHAT-13

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] The translator passes supplied context in order between the system prompt and current prompt.
- [ ] A missing/empty context produces the current two-message request.
- [ ] At least 4 additional tests verify ordering, SQL context, empty-context compatibility, and propagated Ollama errors; all existing translator tests still pass.
- [ ] Gate check passes: `python3 -m pytest test_translator.py -q`.

**Tests**: unit
**Gate**: quick

**Commit**: `feat(ai): add bounded conversation context`

### T4: Rendering chat messages and pending query actions once

**What**: Refactor the chat rendering component so the transcript is the only source for displayed messages and review/error/result controls do not add transient duplicate content.
**Where**: `components.py`
**Depends on**: None
**Reuses**: Existing SQL display, DataFrame, chart, CSV, and pending SQL UI.
**Requirement**: CHAT-01, CHAT-03, CHAT-04, CHAT-07

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Rendering a stored user or assistant message creates one chat block for that message.
- [ ] Successful results retain SQL, DataFrame, chart, and CSV controls.
- [ ] Failures retain associated prompt/SQL and display one inline error.
- [ ] Review controls expose an explicit action rather than rendering a second transcript entry.
- [ ] At least 5 focused tests verify message count, result controls, errors, review display, and rerun-stable output.
- [ ] Gate check passes: `python3 -m pytest test_chat_ui.py -q`.

**Tests**: unit
**Gate**: quick

**Commit**: `fix(chat): render each message once`

### T5: Integrating resumable sessions and stable chat flow

**What**: Connect authenticated Streamlit state to the conversation repository and translator; implement new drafts, session persistence/resume, bounded context, query linkage, retry/progress state, and organized sidebar navigation while preserving role-gated features.
**Where**: `app.py`
**Depends on**: T1, T2, T3, T4
**Reuses**: Existing auth/profile gates, shared-query/history/admin repositories, and chat components.
**Requirement**: CHAT-02, CHAT-05, CHAT-06, CHAT-08, CHAT-09, CHAT-10, CHAT-11, CHAT-12, CHAT-13, CHAT-14, CHAT-16, CHAT-17, CHAT-18, CHAT-19, CHAT-20, CHAT-21, CHAT-22, CHAT-23

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] An approved user starts in a blank draft and can create, list, switch, and resume only their own sessions.
- [ ] Each submitted turn persists exactly once; reruns do not duplicate the prompt, result, query-history entry, or assistant error.
- [ ] A reopened query displays its SQL but fetches result rows only after explicit execution.
- [ ] The translator receives at most six completed prior turns from the active session.
- [ ] Favorites, confirmed deletion, expiry feedback, and linked query-history deletion are wired to the repository.
- [ ] Login, translation, execution, and persistence show explicit progress/failure states; unsafe mutations are never automatically retried.
- [ ] The chat is primary; session history, query history, shared queries, and admin/account tools remain organized and role-gated.
- [ ] At least 10 focused application tests cover new/old sessions, ownership, grouping, retries, exactly-once rendering/persistence, login feedback, and role-gated existing features.
- [ ] Gate check passes: `python3 -m pytest test_chat_ui.py -q`.

**Tests**: unit
**Gate**: full

**Commit**: `feat(chat): integrate private resumable sessions`

### T6: Documenting conversation behavior for users

**What**: Update the README with the new conversation-session workflow, data persistence boundaries, favorites, expiry, and deletion behavior.
**Where**: `README.md`
**Depends on**: None
**Reuses**: Existing installation and usage documentation.
**Requirement**: CHAT-09, CHAT-12, CHAT-14, CHAT-15, CHAT-16

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Usage explains creating a new conversation, reopening one, and the separate query-history feature.
- [ ] Documentation states that result rows are not saved and older SQL must be explicitly executed.
- [ ] Favorite, expiry, and manual deletion semantics match the specification.
- [ ] Documentation-only task; no automated tests apply.
- [ ] Gate check passes: Build gate command.

**Tests**: none
**Gate**: build

**Commit**: `docs(readme): document conversation sessions`

### T7: Updating architecture documentation

**What**: Update the architecture document with conversation persistence, ownership, translation context, and the rerun/render flow.
**Where**: `docs/arquitetura_e_funcionamento.md`
**Depends on**: None
**Reuses**: Existing module and data-flow sections.
**Requirement**: CHAT-10, CHAT-11, CHAT-13, CHAT-17, CHAT-19

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] The architecture describes session/message tables, query-history linkage, and owner scoping accurately.
- [ ] The documented translation and result flow matches the implemented six-turn context and non-persisted results.
- [ ] Documentation-only task; no automated tests apply.
- [ ] Gate check passes: Build gate command.

**Tests**: none
**Gate**: build

**Commit**: `docs(architecture): describe resumable chat sessions`

### T8: Documenting the UX regression test strategy

**What**: Update the test strategy document with the conversation repository, translator-context, and Streamlit interaction regression coverage and commands.
**Where**: `docs/testes.md`
**Depends on**: None
**Reuses**: Existing pytest and test-suite documentation.
**Requirement**: CHAT-01, CHAT-13, CHAT-17, CHAT-18, CHAT-20, CHAT-21

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] The document lists focused test files and the non-integration command.
- [ ] The described tests cover ownership, expiry/favorites, context bounds, reruns, failures, and preserved roles/features.
- [ ] Documentation-only task; no automated tests apply.
- [ ] Gate check passes: Build gate command.

**Tests**: none
**Gate**: build

**Commit**: `docs(testing): describe chat UX regression coverage`

---

## Diagram-Definition Cross-Check

| Task | Depends on | Diagram | Status |
| --- | --- | --- | --- |
| T1 | None | No incoming edge | Match |
| T2 | T1 | T1 -> T2 | Match |
| T3 | None | No incoming edge | Match |
| T4 | None | No incoming edge | Match |
| T5 | T1, T2, T3, T4 | T1 -> T5; T2 -> T5; T3 -> T5; T4 -> T5 | Match |
| T6 | None | No incoming edge | Match |
| T7 | None | No incoming edge | Match |
| T8 | None | No incoming edge | Match |

## Test Co-location Validation

| Task | Code layer | Matrix requires | Task says | Status |
| --- | --- | --- | --- | --- |
| T1: Creating user-owned conversation storage | Repository | unit | unit | Match |
| T2: Linking query history to conversations | Repository | unit | unit | Match |
| T3: Supplying bounded context to translation | Translator | unit | unit | Match |
| T4: Rendering chat messages and pending actions | Streamlit component | unit | unit | Match |
| T5: Integrating resumable sessions and stable chat flow | Streamlit application | unit | unit | Match |
| T6: Documenting conversation behavior | Documentation | none | none | Match |
| T7: Updating architecture documentation | Documentation | none | none | Match |
| T8: Documenting the UX regression test strategy | Documentation | none | none | Match |
