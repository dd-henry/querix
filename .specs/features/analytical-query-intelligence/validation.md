# Analytical Query Intelligence Validation

**Date**: 2026-11-01
**Spec**: `.specs/features/analytical-query-intelligence/spec.md`
**Diff range**: `f3d0af1^..ba34c01`
**Verifier**: independent verifier; author ≠ verifier
**Verdict**: **PASS**

## Task Completion

| Task | Status | Notes |
| --- | --- | --- |
| T1 | ✅ Complete | Semantic profile and cache implementation present. |
| T2 | ✅ Complete | Temporal interpreter implementation present. |
| T3 | ✅ Complete | Staged planning and SQL generation implementation present. |
| T4 | ✅ Complete | Plan and SQL validation implementation present. |
| T5 | ✅ Complete | Bounded repair implementation present. |
| T6 | ✅ Complete | Result diagnostics and interpretation implementation present. |
| T7 | ✅ Complete | Frontend interpretation/diagnostic rendering present. |
| T8 | ✅ Complete | Domain-neutral benchmark implementation present. |

`tasks.md` marks all eight tasks and all `Done when` items complete.
`validate_tasks.py` reports 0 errors and 7 granularity warnings.

## Spec-Anchored Acceptance Criteria

| Requirement | Spec-defined outcome | Behavior-level evidence | Result |
| --- | --- | --- | --- |
| AQI-01 | The semantic profile exposes tables, columns, types, nullability, primary/unique keys, foreign keys, and temporal/numeric candidates. | `api/tests/test_schema_profile.py:56-82` asserts table and column names, data types, nullability, keys, relationship, and candidates. | ✅ PASS |
| AQI-02 | Raw rows and sample values are absent from the semantic profile. | `api/tests/test_schema_profile.py:81-82` asserts the synthetic row value and row marker are absent from prompt context. | ✅ PASS |
| AQI-03 | Successful schema synchronization invalidates the semantic cache and builds a current profile. | `api/tests/test_schema_profile.py:86-96` proves invalidation rebuilds a profile; `:158-177` asserts the observable order `invalidate` then `build`. | ✅ PASS |
| AQI-04 | Supported temporal expressions resolve to explicit reference-date intervals. | `test_temporal.py:28-71` asserts current/previous month, current year, relative window, half-open boundaries, and a year boundary. | ✅ PASS |
| AQI-05 | A month without a year uses the reference year. | `test_temporal.py:6-14` asserts March 2025 from a 2025 reference date. | ✅ PASS |
| AQI-06 | A question without temporal language receives no date filter. | `test_temporal.py:74-83` asserts null bounds, null label, and `has_filter is False`. | ✅ PASS |
| AQI-07 | Planning returns a typed plan containing intent/entities, relationships, dimensions, metrics, filters, grain, and assumptions before SQL generation. | `test_translator.py:196-225` asserts every typed field including exact intent; `:286-303` rejects empty assumptions. | ✅ PASS |
| AQI-08 | SQL generation uses the validated plan, preserves the response contract, and remains domain-neutral. | `test_translator.py:228-283` asserts validator-before-generation and normalized plan/temporal prompt data; `api/tests/test_dependencies.py:173-188` proves production factory wiring; `test_prompter.py:27-47` checks generic constraints. | ✅ PASS |
| AQI-09 | Unknown plan identifiers are rejected with a stable error before database execution. | `api/tests/test_query_validation.py:60-78` asserts stable identifier codes; `api/tests/test_chat_service.py:326-373` asserts 422 and no database call. | ✅ PASS |
| AQI-10 | Non-read-only or multi-statement SQL is rejected before database execution. | `api/tests/test_query_validation.py:81-92` asserts read-only acceptance/rejection; `api/tests/test_chat_service.py:284-322` asserts no adapter call. | ✅ PASS |
| AQI-11 | A rejected validated query gets at most one repair using the database error and original plan. | `api/tests/test_chat_service.py:815-853` asserts one repair, two executions, exact `"missing column"` feedback, and the original plan. | ✅ PASS |
| AQI-12 | Invalid or failed repair preserves the request, exposes a retryable error, and does not loop. | `api/tests/test_chat_service.py:858-879` asserts invalid repair is not executed, retains the original request/SQL, and persists retryable metadata; `:880-905` asserts one bounded execution retry and identity. | ✅ PASS |
| AQI-13 | A valid zero-row result remains successful and has a no-match diagnostic distinct from execution failure. | `api/tests/test_result_quality.py:20-33` and `api/tests/test_chat_service.py:477-519` assert successful zero rows and diagnostic; `api/tests/test_chat_service.py:798-812` covers database failure separately. | ✅ PASS |
| AQI-14 | No numerical conclusion is emitted unless supported by returned results. | `api/tests/test_chat_service.py:521-556` asserts the exact row-count summary from returned results and no missing metric/fabricated sentinel. | ✅ PASS |
| AQI-15 | The API interpretation contains dimensions, metrics, period, and assumptions when a plan exists. | `api/tests/test_result_quality.py:51-73` asserts the complete helper dictionary; `api/tests/test_chat_translate_routes.py:153-180` asserts all API fields and diagnostics. | ✅ PASS |
| AQI-16 | The frontend renders interpretation/diagnostics on the same assistant response without a duplicate message. | `web/src/features/chat/useChat.test.tsx:231-278`, `web/src/features/chat/ChatWorkspace.test.tsx:216-251`, and `web/e2e/chat.spec.ts:119-136` assert placement, fields, and stable message count. | ✅ PASS |
| AQI-17 | The benchmark accepts domain-neutral questions, expected columns, and optional row constraints. | `evaluation/test_query_benchmark.py:10-28` and `:60-78` use generic cases and mapping inputs. | ✅ PASS |
| AQI-18 | The benchmark reports executable rate, expected-column coverage, zero-row rate, and latency. | `evaluation/test_query_benchmark.py:49-57` and `:80-88` assert exact aggregate and serialized metrics. | ✅ PASS |
| AQI-19 | Metric tests run without production database access or embedded business SQL templates. | `evaluation/test_query_benchmark.py:10-49` uses synthetic values; `evaluation/query_benchmark.py:1-2` imports only standard-library modules. | ✅ PASS |

**Spec-anchored result**: **19/19** criteria matched by exact
behavior-level evidence. No spec-precision gaps remain.

## Discrimination Sensor

The real-tree baseline before sensor work was:

```text
 M .specs/STATE.md
?? .specs/features/analytical-query-intelligence/validation.md
```

An isolated `.aqi-verifier-scratch` git worktree at `ba34c01` was used and
removed afterward. No `git stash` was used. The real-tree porcelain matched the
baseline after cleanup.

| Mutation | Target | Outcome | Result |
| --- | --- | --- | --- |
| Build the schema profile before cache invalidation. | `api/routes/sync.py:24-28`; `api/tests/test_schema_profile.py:158-177` failed. | Killed | ✅ |
| Return a wrong planner intent. | `core/query_plan.py:26`; `test_translator.py:196-225` failed. | Killed | ✅ |
| Remove dependency wiring for `validate_translation_plan`. | `api/dependencies.py:80`; `api/tests/test_dependencies.py:173-188` failed. | Killed | ✅ |
| Make invalid-repair terminal metadata non-retryable. | `api/services/chat.py:506`; `api/tests/test_chat_service.py:858-879` failed. | Killed | ✅ |
| Emit a fabricated `123` instead of the returned row count. | `api/serializers/results.py:74`; `api/tests/test_chat_service.py:521-556` failed. | Killed | ✅ |

**Sensor depth**: targeted final-gap sensor in an isolated worktree.
**Sensor result**: **5/5 killed — PASS**.

## Edge Cases

| Edge case | Result | Evidence |
| --- | --- | --- |
| Explicit Portuguese month year differs from reference year | ✅ | `test_temporal.py:17-25` |
| Relative window crosses month/year boundary | ✅ | `test_temporal.py:62-71` |
| Schema has no foreign keys or candidate temporal columns | ✅ | `api/tests/test_schema_profile.py:99-121` |
| Unknown plan identifier | ✅ | `api/tests/test_query_validation.py:60-78` |
| Valid query returns zero rows | ✅ | `api/tests/test_chat_service.py:477-519` |
| Database error persists after one repair attempt | ✅ | `api/tests/test_chat_service.py:880-905` |
| Malformed planner JSON or empty assumptions | ✅ | `test_translator.py:286-303` and `:305-331` |
| Concurrent same request ID | ✅ | `api/tests/test_chat_service.py:907-929` and `web/src/features/chat/useChat.test.tsx:267-278` |

## Gate Check

| Gate | Result |
| --- | --- |
| Backend (`venv/bin/pytest -m "not integration" -q`) | **270 passed, 1 deselected** |
| Frontend check (`npm --prefix web run check`) | **14 files / 81 tests passed** |
| Frontend build (`npm --prefix web run build`) | **Passed** |
| Full E2E (`npm --prefix web run e2e`) | **13 passed** |
| Task metadata (`validate_tasks.py`) | **0 errors, 7 warnings** |

The pre-feature backend baseline was 230 selected tests; the current gate has
270 selected tests, a net increase of 40. The one deselected test is the
integration test requiring external Ollama/PostgreSQL services. No remote
services or credentials were accessed.

## Code Quality

| Check | Result |
| --- | --- |
| Scope and existing architectural boundaries | ✅ |
| Surgical changes and existing patterns | ✅ |
| Feature-specific tests are behavior-oriented | ✅ |
| Spec-anchored asserted outcomes | ✅ |
| Per-layer coverage expectation | ✅ |
| Full build gate | ✅ |

## Summary

**Overall**: ✅ Ready
**Spec-anchored check**: 19/19 ACs matched; 0 spec-precision gaps
**Sensor**: 5/5 final-gap mutations killed
**Gate**: 270 backend tests, 81 frontend tests, build, and 13 E2E tests passed

No production code or tests were changed. No commits were created. The
pre-existing `.specs/STATE.md` modification remains; this report is the only
new real-tree verification artifact.
