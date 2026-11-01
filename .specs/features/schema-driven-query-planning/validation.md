# Schema-Driven Query Planning Validation

**Verdict**: PASS  
**Date**: 2026-10-31  
**Spec**: `.specs/features/schema-driven-query-planning/spec.md`  
**Diff range**: `fe49279^..7f0a774` (`fe49279`, `9b7d8b3`, `7f0a774`)  
**Verifier**: independent verifier

The real tree was clean before validation. No production code or tests were
modified. The only new real-tree file is this report.

## Task Completion

| Task | Status | Evidence |
| --- | --- | --- |
| T1: Removing the deterministic domain planner | Done | `core/analytical_queries.py` deleted in `fe49279`; translator dispatch tests pass |
| T2: Generalizing the prompt and schema context | Done | Prompt and PostgreSQL relationship tests pass |
| T3: Updating architecture documentation and closing verification | Done | Documentation is in the committed diff; build gates pass |


## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | Evidence and assertion | Result |
| --- | --- | --- | --- |
| 1. Every non-empty question invokes the configured LLM; no deterministic domain SQL or intent path | `ollama.chat` is the sole planner dispatch path and former domain questions return model SQL | `core/translator.py:109-119` builds the messages and calls `ollama.chat(model=self.model_name, ...)`; `test_analytical_queries.py:6-25` asserts two former-domain responses and `chat.call_count == 2`; `test_translator.py:105-123` asserts the former-domain question is sent to Ollama once; `core/analytical_queries.py` is deleted | ✅ PASS |
| 2. A live-schema prompt includes the schema, requires schema-grounded SQL, and has no former sales-domain identifiers | Runtime schema is appended and prompt rules require declared identifiers and relationships only | `core/prompter.py:59-66` requires schema-grounded entities and relationships; `core/prompter.py:112-114` appends `live_schema`; `test_prompter.py:20-47` asserts generic rules and absence of former domain identifiers; `test_prompter.py:50-57` asserts the live schema appears | ✅ PASS |
| 3. A month without a year uses the runtime reference year | Prompt provides the injected reference date and instructs the model to use its year | `core/prompter.py:75-80` emits the instruction and ISO reference date; `test_prompter.py:23-30` asserts `2026-10-31` and the year instruction | ✅ PASS |
| 4. An omitted period does not receive an invented time filter unless the request means the current period | Prompt explicitly forbids invented temporal filters; Python does not inject period parameters | `core/prompter.py:75-78` states the no-period rule; `test_prompter.py:27-30` asserts it; `test_analytical_queries.py:41-54` asserts no pre-Ollama period injection; `test_analytical_queries.py:57-71` asserts a year-only request receives no fabricated month | ✅ PASS |
| 5. Foreign keys are exposed with source and target table and column | Each relationship is queried and rendered as `source_table.source_column -> target_table.target_column`; empty relationships remain valid | `database/postgres.py:134-160` queries public foreign keys and formats both sides; `test_postgres.py:88-129` asserts the relationship heading and `orders.customer_id -> customers.id`; `test_postgres.py:132-154` asserts a schema without relationships omits that section | ✅ PASS |
| 6. A returned plan preserves primary SQL, keeps at most three supports, and retains named parameters | Primary payload is preserved; supports are normalized to the bounded response shape | `core/translator.py:41-49` preserves the parsed payload while normalizing supports; `core/translator.py:56-91` rejects more than three and normalizes keys, SQL, and parameter mappings; `test_translator.py:43-78` asserts normalized named parameters and malformed support removal; `test_analytical_queries.py:74-99` asserts a generic support is retained; `test_analytical_queries.py:102-112` asserts primary SQL is unchanged | ✅ PASS |
| 7. Invalid, multi-statement, or non-read-only primary/supporting SQL is rejected before database execution | Existing validation returns the read-only error or a supporting-query warning without executing unsafe SQL | `api/services/chat.py:178-194` validates generated primary SQL; `api/services/chat.py:592-606` validates supports; `api/services/chat.py:643-661` prevents invalid supports from executing; `test_chat_service.py:270-324` asserts 422/read-only errors and no database calls for DELETE, multi-statement, and UPDATE; `test_chat_service.py:499-531` asserts an invalid support is reported while only the primary query executes | ✅ PASS |
| 8. Supporting queries preserve the primary result and expose successful or failed complements through `insights` | Primary result remains present and each complement is represented by a result or warning | `api/services/chat.py:289-329` executes supports after the primary and returns both `result` and `insights`; `api/services/chat.py:680-702` emits warning or result insights; `test_chat_service.py:364-449` asserts successful and failed complements preserve the primary rows; `api/tests/test_chat_execute_routes.py:139-167` asserts the API response contract; `api/tests/test_chat_translate_routes.py:115-150` asserts successful and warning insights | ✅ PASS |

**Spec-anchored status**: 8/8 acceptance criteria matched the specified
outcomes. No spec-precision gaps were required to interpret the assertions.

## Edge Cases

- ✅ Empty questions are not intercepted: `test_analytical_queries.py:28-38`.
- ✅ A month without a year uses the injected reference date: `test_prompter.py:23-30`.
- ✅ A year-only question receives no fabricated month: `test_analytical_queries.py:57-71`.
- ✅ A schema without foreign keys remains valid: `test_postgres.py:132-154`.
- ✅ Malformed or excessive supports normalize to an empty list: `core/translator.py:56-60,71-81`; `test_translator.py:60-78`.

## Gate Check

Required build gate:

```text
venv/bin/python -m compileall -q api core database
venv/bin/python -m pytest -m "not integration" -v
npm --prefix web run build
```

Results:

- Python compileall: passed.
- Python non-integration suite: **230 passed, 0 failed, 1 integration deselected**.
- Frontend `npm --prefix web run check`: typecheck passed, ESLint passed, and
  **14 Vitest files / 72 tests passed**.
- Frontend production build: passed. Vite emitted only a non-fatal chunk-size
  warning.
- Test count before the feature (`fe49279^`): **230/231 collected, 1
  integration deselected**.
- Test count after the feature: **230/231 selected/collected, 1 integration
  deselected**.
- Test-count delta: **0**. No assertions were weakened or tests removed to
  make the gate pass.

## Discrimination Sensor

Sensor depth: lightweight, two behavior-level mutations. Both mutations ran in
separate detached worktrees and were discarded. The real-tree porcelain was
empty both before and after the sensor.

| Mutation | Isolated mutation | Relevant test result | Result |
| --- | --- | --- | --- |
| 1 | Added a deterministic `"produtos"` interception returning `SELECT 1` before the Ollama call in the scratch `core/translator.py` at the `core/translator.py:116-119` dispatch site | `test_analytical_queries.py::test_domain_questions_share_the_same_llm_planning_path` and `test_translator.py::test_translate_to_sql_dispatches_former_domain_question_to_ollama` failed; mutant exit code 1 | ✅ Killed |
| 2 | Disabled the relationship-rendering branch at the `database/postgres.py:153-160` relationship output site in the scratch worktree | `test_postgres.py::test_get_schema_info_inclui_relacionamentos_de_chave_estrangeira` failed; mutant exit code 1 | ✅ Killed |

**Sensor result**: 2/2 killed, PASS.

## Code Quality

| Check | Result |
| --- | --- |
| No features beyond the request | ✅ |
| Surgical production changes | ✅ |
| Existing patterns and validation boundaries preserved | ✅ |
| Tests map to the acceptance criteria | ✅ |
| Read-only execution and insight contracts preserved | ✅ |
| Project testing guidelines followed | ✅ `README.md`, `docs/testes.md`, and `pytest.ini` |

## Ranked Gaps

No functional, documentation, or test-discrimination gaps remain.

## Summary

**Overall**: ✅ Ready  
**Acceptance criteria**: 8/8 PASS  
**Gate**: 230 Python tests passed; frontend checks and build passed  
**Sensor**: 2/2 mutants killed  
**Real-tree isolation**: baseline and post-sensor porcelain both clean before
this report was written
