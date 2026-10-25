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

**Status**: Done

**What**: Add nullable session linkage to query-history records, preserve legacy null-linked rows, scope de-duplication by session, and cascade linked records when a session is deleted.
**Where**: `database/query_history.py`
**Depends on**: T1
**Reuses**: Existing `QueryHistoryRepository` user-scoped list/pin/delete and deduplication behavior.
**Requirement**: CHAT-15, CHAT-16

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [x] Initialization adds the nullable foreign key without assigning old rows to a new session.
- [x] Session-linked records do not replace another session's matching query record.
- [x] Existing calls without a session ID preserve legacy behavior.
- [x] 4 focused tests cover linked writes, session-scoped de-duplication, null-linked legacy behavior, and migration/query parameters; all existing `test_query_history.py` tests still pass (10 total).
- [x] Gate check passes: `venv/bin/python -m pytest -m 'not integration' -q` (39 passed, 1 deselected).

**Tests**: unit
**Gate**: quick

**Commit**: `feat(history): link query history to conversations`

**Post-gate evidence**:

| Criterion | Test evidence | Expected outcome | Result |
| --- | --- | --- | --- |
| Nullable FK and cascade; legacy rows remain null | `test_query_history.py:61` - `assert "NOT NULL" not in session_column`; `assert "DEFAULT" not in session_column`; `assert "REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE" in session_column` | Existing rows are not assigned a session; deleting a session cascades linked rows only. | Covered |
| Duplicate cleanup is scoped per session | `test_query_history.py:61` - `assert "PARTITION BY user_id, session_id, sql, parameters" in deduplication` | The same query in separate sessions is not merged during initialization. | Covered |
| Legacy calls use null-session scope | `test_query_history.py:8` - `assert params == {..., "session_id": None}`; `assert "session_id IS NOT DISTINCT FROM CAST(:session_id AS uuid)" in ...` | Calls without a session keep legacy rows in the null-session group. | Covered |
| New writes carry session linkage and keep repeated queries session-scoped | `test_query_history.py:73` - `assert params["session_id"] == "session-id"`; `test_query_history.py:85` - asserts both session IDs and null-safe session predicate | A query history row belongs to its own conversation and is not reused across sessions. | Covered |
| Listed rows expose their session relationship | `test_query_history.py:99` - `assert QueryHistoryRepository(db).list("user-id") == [{"id": 1, "session_id": "session-id"}]` | Callers can distinguish session-linked from legacy history. | Covered |

Every T2 test maps to CHAT-15/16 or the task's compatibility criteria. Existing project conventions from `docs/testes.md` and `pytest.ini` are followed. No database service is configured, so PostgreSQL DDL behavior is verified through generated SQL assertions rather than a live migration.

### T3: Supplying bounded conversation context to translation

**Status**: Done

**What**: Extend SQL translation to accept ordered prior user/assistant messages while preserving existing behavior when no context is supplied.
**Where**: `core/translator.py`
**Depends on**: None
**Reuses**: Current Ollama call and JSON response parser.
**Requirement**: CHAT-13

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [x] The translator passes supplied context in order between the system prompt and current prompt.
- [x] A missing/empty context produces the current two-message request.
- [x] 5 additional tests verify ordering, SQL context, empty-context compatibility, six-turn bounds, and propagated Ollama errors; all existing translator tests still pass (8 total).
- [x] Gate check passes: `venv/bin/python -m pytest -m 'not integration' -q` (44 passed, 1 deselected).

**Tests**: unit
**Gate**: quick

**Commit**: `feat(ai): add bounded conversation context`

**Post-gate evidence**:

| Criterion | Test evidence | Expected outcome | Result |
| --- | --- | --- | --- |
| Prior context precedes current question and includes SQL | `test_translator.py:60` - `assert chat.call_args.kwargs["messages"] == [{"role": "system", ...}, *context, {"role": "user", ...}]` | Prior user/assistant turns remain in order between system and current prompt. | Covered |
| Missing and empty context preserve existing request | `test_translator.py:74` - exact two-message list; `test_translator.py:87` - `assert len(chat.call_args.kwargs["messages"]) == 2` | Both calls send only system and current user messages. | Covered |
| Context is bounded to six turns and contains the latest SQL | `test_translator.py:108` - `assert messages[1] == {"role": "user", "content": "Question 2"}`; `test_translator.py:109` - asserts latest assistant SQL | Seven supplied turns reduce to the latest six while preserving turn order and SQL. | Covered |
| Ollama failure remains visible to caller | `test_translator.py:118` - `with pytest.raises(RuntimeError, match="Ollama unavailable")` | Translation failures raise the existing explicit runtime error. | Covered |

Every T3 test maps to CHAT-13 or the task's compatibility criteria. Existing pytest and mock conventions from `docs/testes.md` are followed.

### T4: Rendering chat messages and pending query actions once

**Status**: Done

**What**: Refactor the chat rendering component so the transcript is the only source for displayed messages and review/error/result controls do not add transient duplicate content.
**Where**: `components.py`
**Depends on**: None
**Reuses**: Existing SQL display, DataFrame, chart, CSV, and pending SQL UI.
**Requirement**: CHAT-01, CHAT-03, CHAT-04, CHAT-07

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [x] Rendering a stored user or assistant message creates one chat block for that message.
- [x] Successful results retain SQL, DataFrame, chart, and CSV controls.
- [x] Failures retain associated prompt/SQL and display one inline error.
- [x] Review controls expose an explicit action rather than rendering a second transcript entry.
- [x] 7 focused tests verify message count, result controls, errors, review display, rerun-stable output, and failure persistence.
- [x] Gate check passes: `venv/bin/python -m pytest -m 'not integration' -q` (51 passed, 1 deselected).

**Tests**: unit
**Gate**: quick

**Commit**: `fix(chat): render each message once`

**Post-gate evidence**:

| Criterion | Test evidence | Expected outcome | Result |
| --- | --- | --- | --- |
| Each stored user/assistant message is rendered once | `test_chat_ui.py:32` - asserts chat roles exactly `["user", "assistant"]`; `test_chat_ui.py:36` - asserts each message content is written once | One chat block per transcript entry. | Covered |
| Full rerenders do not add explicit rerun/duplicate output | `test_chat_ui.py:50` - `assert streamlit.chat_message.call_count == 1`; `test_chat_ui.py:51` - asserts role remains user; `test_chat_ui.py:52` - `streamlit.rerun.assert_not_called()` | A rerender shows one copy and chart state does not trigger a second forced rerun. | Covered |
| Successful results preserve SQL/table/CSV | `test_chat_ui.py:67` - asserts SQL language; `test_chat_ui.py:68` - asserts SQL text; `test_chat_ui.py:69` - asserts DataFrame; `test_chat_ui.py:70` - asserts CSV bytes | Result controls use the query result and expected SQL. | Covered |
| Chart controls render suggested data without a second forced rerun | `test_chat_ui.py:104` - `assert message["show_chart"] is True`; `test_chat_ui.py:105` - `assert streamlit.bar_chart.call_args.kwargs == {"x": "mes", "y": "total"}`; `test_chat_ui.py:106` - `streamlit.rerun.assert_not_called()` | The generated chart uses the selected columns and renders once. | Covered |
| Errors remain associated with prompt/query and appear inline once | `test_chat_ui.py:85` - one chat block; `test_chat_ui.py:87` - asserts SQL; `test_chat_ui.py:88` - asserts exact error text; `test_chat_ui.py:89` - one error call | One assistant message contains the error and associated SQL. | Covered |
| Review UI is distinct from transcript | `test_chat_ui.py:115` - `streamlit.container.assert_called_once_with(border=True)`; `test_chat_ui.py:116` - `streamlit.chat_message.assert_not_called()` | Pending review is an action card, not another transcript message. | Covered |
| Failed execution adds one transcript item rather than a transient global error | `test_chat_ui.py:130` - asserts one assistant message with SQL/error; `test_chat_ui.py:138` - `assert streamlit.error.call_count == 0`; `test_chat_ui.py:139` - asserts one rerun | Error appears once from the canonical transcript after rerun. | Covered |

Every T4 test maps to CHAT-01, CHAT-03, CHAT-04, CHAT-07 or the task's display criteria. Tests follow pytest conventions in `docs/testes.md`.

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
