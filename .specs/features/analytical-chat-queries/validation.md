# analytical-chat-queries Validation

**Date**: 2026-10-31
**Spec**: `.specs/features/analytical-chat-queries/spec.md`
**Diff range**: `0ffe523..aae7b40`
**Verifier**: fresh independent verifier; author ≠ verifier

## Validation: analytical-chat-queries - PASS ✅

**Spec-anchored check**: 12/12 acceptance criteria match the specified
outcomes; 0 spec-precision gaps.
**Required build gate**: passed.
**Feature E2E**: 3/3 analytical chat scenarios passed.
**Sensor**: 3 mutations injected, 3 killed, 0 survived.
**Report**: `.specs/features/analytical-chat-queries/validation.md`

## Task Completion

| Task | Status | Evidence |
| --- | --- | --- |
| T1 | ✅ Done | `bcefc08`; semantic prompt rules and tests |
| T2 | ✅ Done | `6730c5b`; deterministic query builder and tests |
| T3 | ✅ Done | `442ccca`; deterministic translator path and fallback |
| T4 | ✅ Done | `afc1ce4`; bounded result summaries and tests |
| T5 | ✅ Done | `39d28f2`; API summary and automatic execution wiring |
| T6 | ✅ Done | `3ab39c3`; React state and default automatic mode |
| T7 | ✅ Done | `ccd6c38`; summary-before-table and SQL details |
| T8 | ✅ Done | `964df8c`; automatic/review/warning E2E contracts |
| Verifier fixes | ✅ Done | `aae7b40`; unknown month, bounded count, product alias coverage |

All eight task rows are `Done`. The tasks document header still says
`Status: In Progress`, which is stale metadata but does not describe an
unfinished task row.

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion evidence | Result |
| --- | --- | --- | --- |
| AC-01: Recognized revenue question with a period | Aggregate `vendas.valor_total`, keep `status = 'concluida'`, and use `[start, end)` timestamps | `test_analytical_queries.py:6-21` asserts exact August parameters, `COALESCE(SUM(v.valor_total), 0)`, completed status, `>= :period_start`, and `< :period_end`; implementation is `core/analytical_queries.py:166-177` | ✅ PASS |
| AC-02: Recognized product-sales question with a period | Join sales/items/products, keep completed sales, group by product identity/name, and return product, quantity, and item subtotal | `test_analytical_queries.py:24-40` asserts `p.nome AS produto`, both sums, both joins, `GROUP BY p.id, p.nome`, status, and exact interval parameters; implementation is `core/analytical_queries.py:147-164` | ✅ PASS |
| AC-03: Recognized question without a period | Use the API server's current calendar period | `test_analytical_queries.py:43-53` asserts October 2026 `[2026-10-01, 2026-11-01)` from the supplied reference date; implementation defaults via `core/analytical_queries.py:70-85` | ✅ PASS |
| AC-04: Unsupported intent | Use Ollama with semantic prompt context and retain the read-only validation boundary | `test_translator.py:49-55` asserts the unsupported request is sent with the system prompt; `api/tests/test_chat_service.py:270-289` asserts invalid generated SQL returns `sql_not_read_only` and never reaches the database | ✅ PASS |
| AC-05: Non-read-only or multi-statement query | Reject before database execution | `test_predefined_queries.py:8-15` rejects `DELETE` and `SELECT 1; DROP TABLE`; `api/tests/test_chat_service.py:270-304` asserts generated and stored invalid SQL return 422 and no database call | ✅ PASS |
| AC-06: Product/quantity/value result | Summarize count, quantity, and value from returned rows only | `api/tests/test_result_serializer.py:94-108` asserts exact product metrics; `:122-135` asserts a truncated payload with one returned row says `Encontrei 1 produto(s)` and retains the bounded-result notice; implementation uses `len(rows)` at `api/serializers/results.py:55-67` | ✅ PASS |
| AC-07: Single numeric revenue result | Summarize only the returned revenue total | `api/tests/test_result_serializer.py:111-119` asserts exact `R$ 1.498,00`; implementation is `api/serializers/results.py:69-72` | ✅ PASS |
| AC-08: Executed frontend result | Render summary before the table and keep SQL in collapsed details | `web/src/features/chat/ChatWorkspace.test.tsx:119-137` asserts summary document order precedes the table and `<details>` starts closed; implementation is `web/src/features/chat/ChatWorkspace.tsx:144-157` | ✅ PASS |
| AC-09: Unrecognized result shape | Return a truthful generic row-count summary | `api/tests/test_chat_service.py:307-333` asserts executed generic data returns `A consulta retornou 1 linha(s).` | ✅ PASS |
| AC-10: Normal authenticated chat | Request automatic execution mode | `web/src/app/AuthenticatedApp.test.tsx:61-89` requires `review_mode: false`; `web/src/features/chat/useChat.test.tsx:260-282` also asserts executed response mapping and no manual execute call; implementation defaults `reviewMode: false` in `web/src/app/AuthenticatedApp.tsx:54-60` | ✅ PASS |
| AC-11: Automatic warning/failure handling | Preserve warning/retryable states and never execute missing/invalid SQL | `api/tests/test_chat_translate_routes.py:83-134` asserts automatic execution for success but no execution for warnings; `api/tests/test_chat_service.py:247-268` and `:378-393` assert retry metadata for translation/database failures; `web/src/features/chat/useChat.test.tsx:283-307` asserts warning has no execute path; `web/e2e/chat.spec.ts:168-239` passes the retry/warning scenario | ✅ PASS |
| AC-12: Explicit review mode | Preserve review response and manual controls | `api/tests/test_chat_translate_routes.py:62-81` asserts review returns SQL with no result/execution; `web/src/features/chat/ChatWorkspace.test.tsx:99-117` asserts execute and cancel controls remain available; `web/e2e/chat.spec.ts:103-166` passes the reviewed execution scenario | ✅ PASS |

**Status**: ✅ All 12 acceptance criteria covered with matching outcomes.

## Edge Cases

| Edge case | Evidence | Result |
| --- | --- | --- |
| Unknown textual month falls back to LLM | `test_analytical_queries.py:70-77` asserts `smarch` yields no deterministic query; `core/analytical_queries.py:70-79` rejects explicit unknown month tokens, and `core/translator.py:64-78` sends the resulting fallback to Ollama. An independent mocked translator probe returned `SELECT 1` with exactly one Ollama call. | ✅ PASS |
| Null/non-numeric metrics remain truthful | `api/tests/test_result_serializer.py:122-135` asserts invalid metrics are omitted while the bounded-row summary remains truthful. | ✅ PASS |
| Truncated result summary uses bounded returned rows | `api/tests/test_result_serializer.py:122-135` asserts one returned row, despite `row_count = 5001`, is summarized as one product with the truncation notice. | ✅ PASS |
| Repeated request ID remains idempotent | `api/tests/test_chat_service.py:396-417` and `api/tests/test_chat_translate_routes.py:175-193` assert stored request reuse and stable request ID behavior. | ✅ PASS |

## Discrimination Sensor

The real-tree baseline was `?? .specs/features/analytical-chat-queries/validation.md`.
Each mutation ran in a separate detached worktree rooted at `aae7b40`; all
scratch worktrees were removed, no stash was used, and the real-tree porcelain
matched the baseline afterward.

| Mutation | File:line | Behavior-level fault | Result |
| --- | --- | --- | --- |
| 1 | `core/analytical_queries.py:75-79` | Disabled the explicit unknown-month rejection, causing `smarch` to use the current month | ✅ Killed: `test_analytical_queries.py` failed 1 test |
| 2 | `api/serializers/results.py:58` | Replaced bounded `len(rows)` with total `row_count` | ✅ Killed: `api/tests/test_result_serializer.py` failed 1 test |
| 3 | `core/analytical_queries.py:150` | Changed `p.nome AS produto` to `p.id AS produto` | ✅ Killed: `test_analytical_queries.py` failed 1 test |

**Sensor depth**: lightweight, targeted at all three verifier-gap behaviors.
**Result**: 3/3 killed — PASS ✅.

## Gate Check

- **Structural gates**: `validate_spec.py` — 0 errors; `validate_tasks.py` —
  0 errors and 6 non-blocking granularity warnings.
- **Required Build command**:
  `venv/bin/python -m compileall -q api core database &&
  venv/bin/python -m pytest -m "not integration" -v &&
  npm --prefix web run build`
- **Build result**: ✅ compileall passed; 216 Python tests passed, 1
  integration test deselected; frontend production build passed.
- **Frontend check**: ✅ `npm --prefix web run check`; 14 files and 71 tests
  passed, with typecheck and lint passing.
- **Feature E2E**: ✅ `npm --prefix web run e2e -- e2e/chat.spec.ts`; 3/3
  analytical chat scenarios passed.
- **Supplemental full E2E**: 11/12 passed; the unrelated
  `auth.spec.ts:173` logout test timed out because the `Sair` button was
  repeatedly detached. The same full suite passed in the `0ffe523` baseline
  worktree; this is recorded as a repository/test-environment gap, not an
  analytical-chat acceptance failure.
- **Test count before feature** (`0ffe523`): 204/205 Python tests selected
  (`1` integration deselected), 70 frontend tests, 12 E2E scenarios.
- **Test count after feature** (`aae7b40`): 216/217 Python tests selected
  (`1` integration deselected), 71 frontend tests, 12 E2E scenarios.
- **Delta**: +12 Python, +1 frontend, 0 E2E; no test-count decrease.
- **Diff quality**: `git diff --check 0ffe523..aae7b40` passed.

## Code Quality

| Principle | Status |
| --- | --- |
| No features beyond the request | ✅ |
| No single-use abstractions or unnecessary flexibility | ✅ |
| Surgical feature-surface changes | ✅ |
| Existing patterns preserved | ✅ |
| Spec-anchored outcomes match the spec | ✅ |
| Domain/API/frontend coverage expectations met | ✅ |
| Every feature test maps to an AC, edge case, or task criterion | ✅ |
| Documented project guidelines followed | ✅ |

## Requirement Traceability

The spec traceability table remains unchanged because this verification was
restricted to replacing `validation.md`.

| Requirement | Verification result |
| --- | --- |
| ANALYTICAL-01 through ANALYTICAL-12 | ✅ Verified |

## Ranked Remaining Gaps

1. **P2 — Repository E2E stability**: `web/e2e/auth.spec.ts:173` fails in the
   current full-suite run due to a detached logout button; the analytical chat
   E2E subset and required build gate pass, and the baseline full suite passed.
2. **P3 — Task metadata hygiene**: `tasks.md` header says `In Progress` while
   T1-T8 are all marked `Done`.

Neither item leaves an analytical-chat acceptance criterion uncovered.

## Summary

**Overall**: ✅ Ready
**Spec-anchored check**: 12/12 matched; 0 precision gaps.
**Sensor**: 3/3 mutations killed.
**Required gate**: ✅ Passed.

The unknown textual-month fallback, bounded truncated summaries, and
product-name alias contract are now both behaviorally correct and
discriminating. No feature fix task remains.
