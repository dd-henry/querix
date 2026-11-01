# Inferred Join Validation

**Overall**: PASS  
**Date**: 2026-11-01  
**Spec**: `.specs/features/inferred-join-validation/spec.md`  
**Diff range**: `fee70d12d5566ccb4a0879d68c91b4ff8cffc87b..0f6b3f75c29ba0fa70d377736547ae8b80d4636f`  
**Verifier**: independent verifier; author ≠ verifier

## Task Completion

No `tasks.md` exists for this feature. The implementation and its tests are
contained in the committed feature change `0f6b3f7`.

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | Test evidence | Result |
| --- | --- | --- | --- |
| IJV-01: an undeclared relationship whose endpoints exist is accepted | Validation returns exactly one warning identifying the normalized inferred join | `api/tests/test_query_validation.py:60-68` asserts the exact warning; `api/tests/test_query_validation.py:122-131` asserts repeated relationships yield one warning | PASS |
| IJV-02: an unknown endpoint is rejected at the existing validation boundary | `QueryValidationError` preserves the stable error code and message boundary | `api/tests/test_query_validation.py:96-109` asserts `unknown_table`, `unknown_column`, and `unknown_relationship` for unknown table/column endpoints | PASS |
| IJV-03: an accepted inferred relationship warning survives translation and persistence | The response warning and assistant metadata contain the exact warning | `api/tests/test_chat_service.py:616-671` asserts `result.warnings` and persisted metadata equal the exact warning | PASS |
| IJV-04: execution or restoration preserves the warning | Executed results and restored chat messages expose the stored warning | `api/tests/test_chat_service.py:723-743` asserts execution warnings; `web/src/features/chat/useChat.test.tsx:548-566` asserts restored message warnings | PASS |

**Status**: All four acceptance criteria have exact assertion evidence.

## Edge Cases

- PASS: A declared relationship in reverse direction produces no warning:
  `api/tests/test_query_validation.py:112-117`.
- PASS: Repeated inferred relationships produce one warning:
  `api/tests/test_query_validation.py:120-131`.
- PASS: A schema with no foreign keys accepts existing endpoints and persists
  the warning:
  `api/tests/test_chat_service.py:640-671`.
- PASS: Unknown table and both unknown relationship-column/table endpoint
  forms retain stable validation errors:
  `api/tests/test_query_validation.py:93-109`.

## Gate Check

**Command**:

```text
venv/bin/python -m compileall -q api core database && venv/bin/pytest -m "not integration" -q && cd web && npm run check && npm run build
```

Result: PASS.

- Python compilation: passed.
- Backend tests: 276 passed, 1 integration test deselected, 0 failed.
- Frontend `npm run check`: typecheck passed, ESLint passed, 14 Vitest files
  passed with 92 tests passed.
- Frontend production build: passed. Vite emitted only the existing
  non-blocking chunk-size warning.
- Backend test count: 270 selected before the feature, 276 after, a net gain
  of 6.
- Frontend test count: 91 before the feature, 92 after, a net gain of 1.

## Discrimination Sensor

Sensor mutations ran only in the isolated git worktree
`.git/verifier-scratch`; the real tree was never mutated or stashed. Both
mutants were killed, and the worktree was removed.

| Mutation | Location | Behavior-level fault | Result |
| --- | --- | --- | --- |
| 1 | `core/query_validation.py:67` | Changed `normalized not in known_relationships` to `normalized in known_relationships`, reversing declared/inferred warning behavior | KILLED: validator tests failed (4 failures) |
| 2 | `core/query_validation.py:60` | Replaced the left-endpoint `_has_column` check with `False`, allowing an unknown relationship column | KILLED: validator tests failed (7 failures) |

**Sensor result**: 2/2 killed, PASS.

The real-tree porcelain was empty before sensor work and remains empty before
this report was added.

## Code Quality

| Review | Result |
| --- | --- |
| Scope limited to inferred-join validation, warning propagation, tests, and related prompt/documentation | PASS |
| Unknown identifiers remain blocked while declared relationships remain warning-free | PASS |
| Warning handling follows existing repository metadata and frontend restoration patterns | PASS |
| Tests assert spec-defined values rather than only exercising code paths | PASS |
| No production code or tests were changed during verification | PASS |
| Commit message is Conventional Commits compliant | PASS |

## Diff Review

The committed feature changes the validator, chat warning propagation,
prompting/documentation, backend tests, and frontend restoration test/code.
No unrelated production behavior was identified. The spec structure validator
also passes with zero errors and zero warnings.

## Verdict

**PASS**. The committed implementation satisfies IJV-01 through IJV-04, all
listed edge cases, the required build gate, and the discrimination sensor.

