# Web Frontend Migration Validation

**Date**: 2026-11-01
**Spec**: `.specs/features/web-frontend-migration/spec.md`
**Verified range**: `646a4b4^..cutover` (pre-cutover range plus the approved T36-T41 cutover)
**Verifier**: independent verifier; implementation author ≠ verifier
**Scope**: T1-T41, including the approved Streamlit cutover.

## Validation — PASS

**PASS — T1-T41 gates and delivered scope.**

All four mandatory gates passed. The discrimination sensor killed the new
blocked-view mutant, and the real worktree was clean before and after the
sensor. The cutover was performed only after this verification and explicit
owner approval.

The evidence review now finds 41/48 pre-cutover acceptance criteria with exact
assertion coverage and seven evidence gaps. Those gaps are listed separately
below; they do not change the gate verdict, but they do limit the strength of
the acceptance claim.

## Task Completion

| Tasks | Status | Evidence |
| --- | --- | --- |
| T1-T35 | ✅ Done | `.specs/features/web-frontend-migration/tasks.md` marks every pre-cutover Done-when item complete; WEB-03 was fixed and re-verified at `ed0d605`. |
| T36-T41 | ✅ Done | `.specs/features/web-frontend-migration/tasks.md:808-913` marks the cutover items complete; `README.md:120` starts the API and `requirements.txt:1` starts with FastAPI, with no runtime Streamlit references. |

## Cutover Evidence

| Criterion | Evidence | Result |
| --- | --- | --- |
| Legacy entry point and renderer are removed | `app.py` and `components.py` are deleted; `README.md:120` documents the FastAPI start command and no longer documents `streamlit run app.py` | ✅ PASS |
| Legacy tests and theme are removed without losing replacement coverage | `test_app.py`, `test_chat_ui.py`, and `.streamlit/config.toml` are deleted; `web/e2e/parity.spec.ts` continues to cover the replacement UI | ✅ PASS |
| Streamlit is no longer a runtime dependency | `requirements.txt:1` begins with `fastapi>=0.110.0`; `git grep -n -i streamlit -- ':!.specs/**'` returned no matches | ✅ PASS |
| Backend and frontend remain green after cutover | `api/tests/` regression: 234 passed, 1 deselected; `npm --prefix web run check`: 81 frontend tests passed; `npm --prefix web run build`: passed; `npm --prefix web run e2e`: 13 passed | ✅ PASS |

## Spec-Anchored Acceptance Criteria

The evidence column quotes the assertion expression rather than relying on a
test name alone. `⚠️` means the implementation or test suite does not prove
every precise part of the criterion.

| AC | Spec-defined outcome | `file:line` + exact assertion expression | Result |
| --- | --- | --- | --- |
| WEB-01 | Signed `HttpOnly`, `SameSite=Lax` cookie; one auth form during submit; chat after success | `api/tests/test_session.py:106-109` — `assert "HttpOnly" in cookie`; `assert "SameSite=lax" in cookie`; `assert "Max-Age=28800" in cookie`; `web/e2e/auth.spec.ts:58-70` — `expect.poll(() => page.locator("form input").count()).toBe(preSubmitInputCount)`; `expect(await page.locator("form").count()).toBe(1)`; `expect(page.getByRole("tab", { name: "Entrar" })).toHaveCount(0)` | ✅ PASS |
| WEB-02 | Keep email, clear password, and show the exact inline invalid-login prefix | `web/e2e/auth.spec.ts:98-104` — `toHaveText("Não foi possível entrar: Email ou senha inválidos.")`; `toHaveValue("user@example.com")`; `toHaveValue("")` | ✅ PASS |
| WEB-03 | Pending, rejected, and disabled profiles return 403/code and show only a sign-out action | `api/tests/test_auth_routes.py:103-105` — `assert response.status_code == 403`; `assert response.json()["error"]["code"] == "account_not_approved"`; `web/src/App.tsx:28-36` — blocked view contains the single `<button type="button" onClick={() => void auth.logout()}>Sair</button>` action; `web/e2e/auth.spec.ts:161-170` — `expect(page.getByRole("button", { name: "Sair" })).toHaveCount(1)`; `expect(page.getByRole("heading", { name: "Entrar para continuar" })).toHaveCount(1)` after click. | ✅ PASS |
| WEB-04 | Valid signup creates a pending profile and shows the exact confirmation message | `api/tests/test_auth_routes.py:124-135` — `assert response.json() == {"message": SIGNUP_SUCCESS_MESSAGE}`; `repository.create_pending_profile.assert_called_once_with(...)`; `web/src/features/auth/AuthPage.test.tsx:238-248` — `toHaveTextContent("Cadastro recebido. Confirme seu email e aguarde a aprovação de um admin.")` | ✅ PASS |
| WEB-05 | Empty/short/mismatched signup input shows validation and does not call the API | `api/tests/test_auth_routes.py:172-175` — `assert response.status_code == 422`; `assert response.json()["error"]["code"] == "validation_error"`; `auth.sign_up.assert_not_called()`; `web/src/features/auth/AuthPage.test.tsx:130-132` and `158-160` — `signup).not.toHaveBeenCalled()` with the exact short-password and mismatch messages | ✅ PASS |
| WEB-06 | Logout clears the cookie and returns to login | `api/tests/test_auth_routes.py:213-215` — `assert logout.status_code == 200`; `assert "Max-Age=0" in logout.headers["set-cookie"]`; `web/e2e/auth.spec.ts:162-166` — login heading count `1`, form count `1`, input count `2` | ✅ PASS |
| WEB-07 | Missing, tampered, or expired session returns 401 and the UI shows login | `api/tests/test_session.py:86-97` — each invalid request asserts `status_code == 401` and `code == "auth_required"`; `web/src/app/AuthProvider.test.tsx:161-165` — public branch present and authenticated branch absent | ✅ PASS |
| WEB-08 | Mutating request with an unallowed Origin returns 403 | `api/tests/test_app.py:105-114` — `assert rejected.status_code == 403`; exact `origin_not_allowed` envelope | ✅ PASS |
| WEB-09 | Reload role and status from the database on every authenticated request | `api/tests/test_dependencies.py:92-96` — `assert repository.get_profile.call_count == 2`; both calls assert `(USER_ID,)` | ✅ PASS |
| WEB-10 | Persist and render exactly one user and one assistant message per request ID | `web/e2e/chat.spec.ts:74-78` — `toHaveCount(1)` for both message roles; `expect(translateCalls).toBe(1)` | ✅ PASS |
| WEB-11 | Disable composer and show pending status without removing earlier messages | `web/e2e/chat.spec.ts:125-128` — `toBeDisabled()`; both user and assistant message selectors `toHaveCount(1)`; `web/src/features/chat/ChatWorkspace.test.tsx:94-95` — composer and send button disabled | ✅ PASS |
| WEB-12 | Default review mode shows SQL and requires explicit execute/cancel controls | `api/tests/test_chat_translate_routes.py:69-80` — `status == "review"`; `sql == "SELECT 1"`; `result is None`; `service.execute_stored_query.assert_not_called()`; `web/src/features/chat/ChatWorkspace.test.tsx:106-115` — exact SQL text and both control callbacks | ✅ PASS |
| WEB-13 | Review-off translation executes stored read-only SQL automatically | `api/tests/test_chat_translate_routes.py:103-110` — `status == "executed"`; result rows asserted; `execute_stored_query.assert_called_once_with(USER_ID, CONVERSATION_ID, REQUEST_ID)` | ✅ PASS |
| WEB-14 | Translation failure is retryable and retry reuses the original message | `web/e2e/chat.spec.ts:200-204` — exact failure message followed by one user and one assistant message; `api/tests/test_chat_service.py:260-267` — 502/`translator_unavailable` and retry metadata; `api/tests/test_chat_service.py:411-415` — no new insert and same request context | ✅ PASS |
| WEB-15 | `AVISO:` is rendered as a warning with no execution action | `web/e2e/chat.spec.ts:210-214` — exact warning text; execute button count `0`; `executeCalls).toBe(0)` | ✅ PASS |
| WEB-16 | Non-read-only generated SQL returns 422/`sql_not_read_only`, stores the error, and never reaches the database | `api/tests/test_chat_service.py:286-289` — exact 422/code, stored error, `execute_read_only_query.assert_not_called()`; `api/tests/test_chat_execute_routes.py:177-181` repeats the route contract | ✅ PASS |
| WEB-17 | Execute only stored SQL inside a read-only transaction and ignore client SQL | `api/tests/test_chat_execute_routes.py:119-136` — client sends `"DELETE FROM sales"` while `database.execute_read_only_query.assert_called_once_with("SELECT total FROM sales", {})`; no test asserts the transaction boundary itself | ⚠️ GAP — read-only adapter and SQL substitution are proven; transaction semantics are not asserted |
| WEB-18 | Return columns, at most 5,000 rows, row count, and `truncated`; UI notices truncation | `api/tests/test_chat_execute_routes.py:123-128` — exact `columns`, `rows`, `row_count`, and `truncated`; `web/src/features/chat/ChatWorkspace.test.tsx:121-131` — table, truncation notice, and CSV. The serializer test uses `max_rows=2`, not the specified 5,000 bound. | ⚠️ GAP — exact 5,000-row ceiling is not asserted |
| WEB-19 | Render bar/line chart for valid columns and the exact missing-column warning otherwise | `web/src/features/chat/ChatWorkspace.test.tsx:134-167` — both chart test IDs and exact `As colunas sugeridas...` warning | ✅ PASS |
| WEB-20 | Download displayed rows as UTF-8 CSV with a header row | `web/src/features/chat/ChatWorkspace.test.tsx:128-131` — decoded BOM/header `"\uFEFF\"month\",\"total\""` and exact download filename; `web/e2e/chat.spec.ts:137-140` — Playwright download and filename assertion | ✅ PASS |
| WEB-21 | Unreachable Ollama returns 502/`translator_unavailable` | `api/tests/test_chat_translate_routes.py:143-150` — exact status and error envelope | ✅ PASS |
| WEB-22 | Database failure returns 503/`database_unavailable` and stores retryable error | `api/tests/test_chat_execute_routes.py:190-196` — exact status/code plus `retryable is True` and `retry_kind == "execute"` | ✅ PASS |
| WEB-23 | Empty/over-2,000-character prompt returns 422 without persistence | `api/tests/test_chat_translate_routes.py:167-170` — both status/code assertions and `service.translate_prompt.assert_not_called()`; `api/tests/test_chat_service.py:189-193` asserts no repository writes | ✅ PASS |
| WEB-24 | Duplicate request ID returns stored message and does not insert a duplicate | `api/tests/test_chat_service.py:377-382` — stored SQL/status plus empty translator/create/append/update calls; `api/tests/test_chat_translate_routes.py:181-190` asserts both submissions carry the same request ID | ✅ PASS |
| WEB-25 | First prompt creates one owned conversation titled from the prompt | `api/tests/test_conversation_routes.py:135-145` — 201 response and `create_with_user_message.assert_called_once_with(USER_ID, ..., "Quantos clientes?")`; `api/tests/test_conversation_routes.py:160-163` — repeated request creates one tuple | ✅ PASS |
| WEB-26 | Owner conversations are grouped into all five recency buckets in browser timezone | `api/tests/test_conversation_routes.py:93-103` — exact five group keys, title/favorite, and owner call; `web/src/features/conversations/ConversationSidebar.test.tsx:102-105` — `list).toHaveBeenCalledWith(Intl.DateTimeFormat().resolvedOptions().timeZone)` | ✅ PASS |
| WEB-27 | Resume prompts, SQL, and errors in order without executing SQL | `api/tests/test_conversation_item_routes.py:86-97` — ordered roles, SQL, owner call, and no mutation calls; no assertion restores a non-null error field | ⚠️ GAP — error restoration is not directly asserted |
| WEB-28 | Foreign conversation returns 404 | `api/tests/test_conversation_item_routes.py:107-114` — exact 404/not-found envelope and `assert SESSION_ID not in response.text` | ✅ PASS |
| WEB-29 | Favorite state persists and favorites are excluded from one-year cleanup | `api/tests/test_conversation_item_routes.py:131-137` — owner-scoped favorite/unfavorite calls; `test_conversations.py:126-132` — `is_favorite = FALSE`, one-year cutoff, owner parameter, and favorite-first ordering | ✅ PASS |
| WEB-30 | Confirmed deletion removes conversation, messages, and linked history; cancel is a no-op | `api/tests/test_conversation_item_routes.py:145-151` — cancel/confirm statuses and one owner-scoped `repository.delete` call; `database/query_history.py:24-25` defines `ON DELETE CASCADE`, but no test asserts linked-history rows are removed | ⚠️ GAP — linked-history deletion is not outcome-tested |
| WEB-31 | Translator receives at most six prior turns | `api/tests/test_chat_service.py:219` — `assert repository.context_calls == [(6, None)]`; `api/tests/test_conversation_item_routes.py:154-161` asserts the repository six-turn guard | ✅ PASS |
| WEB-32 | History is owner-scoped, pinned first, recent next, and limited to 20 | `api/tests/test_history_routes.py:202-205` — records `[41, 42]`, first pinned, and `history.list_calls == [(USER_ID, 20)]` | ✅ PASS |
| WEB-33 | Pin/unpin/delete mutate only the current user's record | `api/tests/test_history_routes.py:222-229` — exact statuses, pin values, and owner-scoped call lists; `api/tests/test_history_routes.py:241-246` proves foreign mutation has no calls | ✅ PASS |
| WEB-34 | Rerun stored SQL read-only and show result in active conversation | `api/tests/test_history_routes.py:269-276` — result rows, exact `execute_read_only_query` SQL/parameters, and two active-conversation messages | ✅ PASS |
| WEB-35 | Catalog search returns matching queries with per-user favorite state | `api/tests/test_predefined_routes.py:79-82` — status, favorite, parameter name, and `repository.list.assert_called_once_with(USER_ID, search="revenue")` | ✅ PASS |
| WEB-36 | Bind parameters; missing required parameter returns 422 naming it | `api/tests/test_predefined_routes.py:114-119` — exact bound SQL and `{"status": "paid"}`; `api/tests/test_predefined_routes.py:133-140` — exact `missing_parameter`/`Missing required parameter: status.` and no adapter call | ✅ PASS |
| WEB-37 | `dev`, `dba`, and `admin` may mutate catalog; other roles get 403 | `api/tests/test_predefined_routes.py:158-180` — all three CRUD status/response assertions; `api/tests/test_predefined_routes.py:218-222` — regular user 403 and all repository mutations not called | ✅ PASS |
| WEB-38 | Non-read-only catalog SQL returns 422 on create/update | `api/tests/test_predefined_routes.py:237-240` — exact 422/code and no create/update; `api/tests/test_predefined_routes.py:256-258` covers stored execution | ✅ PASS |
| WEB-39 | Admin lists profiles and changes status/role; non-admin gets 403 | `api/tests/test_admin_routes.py:69-85` — list/status/role responses and repository calls; `api/tests/test_admin_routes.py:113-117` — non-admin 403 and no mutations | ✅ PASS |
| WEB-40 | Removing the last approved admin returns 409 without mutation | `api/tests/test_admin_routes.py:174-179` — exact 409/`last_admin_conflict` envelope and `database.execute_command.call_count == 0` | ✅ PASS |
| WEB-41 | Sync rebuilds schema context and clears catalog caches | `api/tests/test_sync_routes.py:56-61` — synchronized response, no schema leakage, `translator.cache_clear.assert_called_once_with()`, `catalog.cache_clear.assert_called_once_with()`, and translator call; `api/tests/test_sync_routes.py:97-106` covers failure cleanup | ✅ PASS |
| WEB-42 | Sidebar and main chat column with composer at the bottom | `web/src/app/AppShell.test.tsx:39-48` — one complementary sidebar, one main region, Chat region, and live status; `web/src/app/AuthenticatedApp.test.tsx:70-103` — all panels and composer-backed shell are reachable | ✅ PASS |
| WEB-43 | Viewport below 768px collapses sidebar behind a menu button | `web/src/app/AppShell.test.tsx:61-69` — `aria-expanded` false/true and `is-open`; `web/e2e/parity.spec.ts:319-326` — 360px viewport, open/close control, and no horizontal overflow | ✅ PASS |
| WEB-44 | Every input is labelled, actions are keyboard-operable, and request status is aria-live | `web/src/app/AppShell.test.tsx:44-48` — `aria-live="polite"`; `web/src/app/AppShell.test.tsx:75-86` — named button focus assertions; `web/src/features/chat/ChatWorkspace.test.tsx:65-80` — labelled composer and keyboard behavior. Universal “every input/action” coverage is not exhaustively enumerated. | ⚠️ GAP — representative accessibility assertions, not a complete universal audit |
| WEB-45 | Enter sends and Shift+Enter inserts a newline | `web/src/features/chat/ChatWorkspace.test.tsx:68-77` — `onSend).toHaveBeenCalledWith("Show revenue")`; `onSend).not.toHaveBeenCalled()`; `toHaveValue("line 1\nline 2")` | ✅ PASS |
| WEB-46 | Remove Streamlit only after verifier PASS and owner approval | The prior validation PASS established the verifier gate; the owner then approved removal. `tasks.md:808-913` records T36-T41 complete, and `git grep -n -i streamlit -- ':!.specs/**'` returned no runtime matches. | ✅ PASS |
| WEB-47 | Errors use the exact envelope without stack traces, other-user SQL, or secrets | `api/tests/test_app.py:58-92` — exact validation/auth/not-found/conflict/internal envelopes and generic internal message; `api/tests/test_app.py:146-151` — password, cookie, SQL, and row values absent from logs; `api/tests/test_conversation_item_routes.py:107-114` — foreign resource text is not returned. Other-user SQL is not directly asserted. | ⚠️ GAP — redaction is covered broadly, but the precise other-user SQL case is missing |
| WEB-48 | Log method, path, status, duration; never passwords, cookies, or rows | `api/tests/test_app.py:146-151` — `api_request method=POST path=/echo status=200` and all four sensitive values absent. `api/app.py:129-134` includes `duration_ms`, but the test does not assert it. | ⚠️ GAP — duration is implemented but not asserted |
| WEB-49 | Document one API command and one web command | `README.md:107-137` — API `uvicorn` command, web `npm ... run dev`, and check/build/E2E commands | ✅ PASS |

**Evidence tally**: 41/49 exact matches; 7 pre-existing evidence gaps; no
runtime or implementation gap introduced by the cutover.

## Edge Cases

| Edge case | Evidence | Result |
| --- | --- | --- |
| Double-click send creates one request/message pair | `web/e2e/chat.spec.ts:74-78` — both message counts and `translateCalls).toBe(1)` | ✅ |
| Network/retry reuses the request ID without a new message | `api/tests/test_chat_service.py:405-415` — no create/append and same request context; `web/e2e/chat.spec.ts:200-204` — one user/assistant pair after retry | ✅ |
| Two tabs do not share data or unsent state | `web/e2e/parity.spec.ts:349-360` proves owner/session list isolation; `web/src/app/AuthProvider.test.tsx:239-244` proves the draft is in memory. A browser-level unsent-draft isolation assertion is not present. | ⚠️ Partial |
| NULL, NaN, dates, and Decimal serialize safely | `api/tests/test_result_serializer.py:77-90` — exact nulls, ISO date/datetime, Decimal strings, and JSON output | ✅ |
| Empty conversation list shows empty state and “Nova conversa” | `web/src/features/conversations/ConversationSidebar.test.tsx:126-129` — exact empty text and callback | ✅ |
| Storage failure returns 503/`storage_unavailable` and the UI reports it | `web/e2e/parity.spec.ts:241-249` stubs exact 503/code; `web/e2e/parity.spec.ts:375-378` asserts “Histórico indisponível.” | ✅ |

## Mandatory Gate Results

| Gate | Result |
| --- | --- |
| `venv/bin/pytest -m "not integration" -q` | ✅ 234 passed, 1 deselected |
| `npm --prefix web run check` | ✅ typecheck, ESLint, 14 Vitest files, 81 tests passed |
| `npm --prefix web run build` | ✅ build passed; known advisory warning remains for the 570.50 kB JavaScript chunk |
| `npm --prefix web run e2e` | ✅ 13 passed |

No tests were skipped. The pre-migration baseline at `646a4b4` had 94 root-Python test declarations;
the current remaining backend suite has 234 passing cases, with 81 frontend
unit tests and 13 E2E tests. The removed tests were Streamlit-only and their
replacement UI coverage remains green.
`git diff --check` found only three Markdown trailing-space hard-break lines in
the pre-existing spec/design/task documentation.

## Discrimination Sensor

Sensor depth: lightweight, one new behavior-level mutation for this
re-verification, isolated in the temporary worktree
`../ask-sql-verifier-scratch`. No `git stash` was used.

| Mutation | Fault | Focused test | Result |
| --- | --- | --- | --- |
| 1 | `api/services/chat.py:236`: changed `execute_read_only_query(sql, parameters)` to `execute_query(sql, parameters)` | `api/tests/test_chat_service.py::test_stored_execution_is_read_only_bounded_and_records_history` | ✅ Killed; the test failed while the mutated path returned a `Mock` instead of the configured DataFrame |
| 2 | `web/src/features/chat/ChatWorkspace.tsx:225`: changed `!event.shiftKey` to `event.shiftKey` | `web/src/features/chat/ChatWorkspace.test.tsx` | ✅ Killed; the Enter-send assertion at `web/src/features/chat/ChatWorkspace.test.tsx:69` failed |
| 3 | `web/src/App.tsx:34`: changed `onClick={() => void auth.logout()}` to a no-op | `npm --prefix web run e2e -- e2e/auth.spec.ts -g "blocked account"` | ✅ Killed; the login-heading assertion at `web/e2e/auth.spec.ts:168-170` failed, and the scratch was removed |

**Sensor result**: 3/3 cumulative mutants killed across the prior
pre-cutover verification runs; the structural cutover was additionally
checked by the independent review and full gates above.

## Cutover Confirmation

- The owner explicitly approved removal in the request to remove Streamlit.
- `app.py`, `components.py`, `core/auth.py`, `test_app.py`,
  `test_chat_ui.py`, and `.streamlit/config.toml` were removed.
- `requirements.txt` no longer includes Streamlit.
- The README and repository instructions now document only the React + FastAPI
  run path.

## Ranked Gaps and Fix Plans

1. **Major — WEB-17/18/27/30/47/48 contract evidence**: add focused assertions
   for transaction boundaries, the exact 5,000-row ceiling, restored errors,
   linked-history cascade, other-user SQL redaction, and log duration.
2. **Moderate — WEB-44 and tab isolation**: expand the accessibility and
   cross-tab checks from representative controls to every rendered input/action
   and unsent composer state.
3. **WEB-46**: the owner approval and prior verifier PASS were recorded before
   the T36-T41 cutover; no remaining blocker exists.

No new fix was required by the independent review; this report and the project
handoff were updated to reflect the completed cutover.

## Code Quality Checklist

| Check | Result |
| --- | --- |
| No features beyond the requested migration | ✅ |
| No unnecessary single-use abstractions or flexibility | ✅ |
| Only migration-related files changed in the verified range | ✅ |
| Existing patterns and repository boundaries preserved | ✅ |
| Tests assert spec outcomes rather than implementation details alone | ⚠️, see evidence gaps above |
| Per-layer coverage expectation met | ⚠️, all required layers run; exact contract gaps remain |
| No test-count regression or weakened gate | ✅ |
| Documented project guidelines followed | ✅ `.claude/skills/tlc-spec-driven/references/coding-principles.md` and repository instructions |

## Summary

**Overall**: ✅ PASS for T1-T41, including the approved Streamlit cutover.

**Gates**: 4/4 passed.
**Spec-anchored evidence**: 41/49 exact ACs; 7 pre-existing evidence gaps.
**Sensor**: 3/3 cumulative mutants killed.
**Cutover**: approved and complete.
