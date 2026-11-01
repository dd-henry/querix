# Analytical Query Intelligence Tasks

## Execution Protocol

Implement one task at a time with the `tlc-spec-driven` skill. Each task is
tested, gated, marked done, and committed before the next task begins.

**Design**: `.specs/features/analytical-query-intelligence/design.md`
**Context**: `.specs/features/analytical-query-intelligence/context.md`
**Status**: Draft

## Test Coverage Matrix

> Generated from `README.md`, `docs/testes.md`, `pytest` configuration,
> `web/package.json`, and existing backend/frontend tests. Guidelines found:
> `README.md`, `docs/testes.md`, `web/package.json`; no separate lint
> configuration for Python.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Semantic profile and temporal/domain logic | unit | Every AC and listed edge case, including schema privacy and boundary dates | `api/tests/test_*.py`, `test_*.py` | `pytest -m "not integration" -v` |
| Planner, validator, repair, and result critic | unit | Every state transition and failure path, with exact contract assertions | `api/tests/test_*.py`, `test_*.py` | `pytest -m "not integration" -v` |
| API response contracts | unit | Happy path, malformed planner, validation failure, repair failure, and zero-result paths | `api/tests/test_*routes.py` | `pytest -m "not integration" -v` |
| React state and presentation | unit | Interpretation placement, diagnostics, no duplicate messages, and existing UX behavior | `web/src/**/*.test.tsx` | `npm --prefix web run check` |
| End-to-end chat | e2e | New interpretation/diagnostic flow and existing send/review/execute flows | `web/e2e/*.spec.ts` | `npm --prefix web run e2e` |
| Evaluation harness | unit | Exact aggregate metrics and domain-neutral input contract | `evaluation/test_*.py` | `pytest -m "not integration" -v` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Backend or evaluation unit tasks | `pytest -m "not integration" -v` |
| Frontend | React state/UI tasks | `npm --prefix web run check` |
| Full | API/UI integration tasks | `pytest -m "not integration" -v && npm --prefix web run check && npm --prefix web run e2e` |
| Build | Final task or phase | `pytest -m "not integration" -v && npm --prefix web run check && npm --prefix web run build && npm --prefix web run e2e` |

## Execution Plan

### Phase 1: Semantic foundation

```text
T1
T2
```

### Phase 2: Planning and validation

```text
T3
T4
```

### Phase 3: Recovery and transparency

```text
T5
T6
T7
```

### Phase 4: Evidence

```text
T8
```

## Task Breakdown

### T1: Building the semantic schema profile

**Status**: Complete

**What**: Add a typed semantic profile with structural PostgreSQL metadata,
safe candidates, process-local caching, and schema-sync invalidation.
**Where**: `database/base.py`, `database/postgres.py`,
`core/semantic_context.py`, `api/dependencies.py`, `api/routes/sync.py`,
`api/tests/test_schema_profile.py`
**Depends on**: None
**Reuses**: Existing `get_schema_info`, adapter interface, and schema sync route.
**Requirement**: AQI-01, AQI-02, AQI-03

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Profile includes structural metadata, relationships, and candidate
      columns without raw rows.
- [ ] Cache is invalidated by schema synchronization.
- [ ] Existing `get_schema_info` behavior remains compatible.
- [ ] Unit tests cover empty schemas, missing relationships, and profile
      privacy.
- [ ] Gate passes with the backend baseline test count unchanged or higher.

**Tests**: unit
**Gate**: quick

### T2: Resolving temporal expressions

**Status**: Complete

**What**: Implement deterministic Portuguese temporal interpretation with
explicit half-open date intervals and planning hints.
**Where**: `core/temporal.py`, `test_temporal.py`
**Depends on**: None
**Reuses**: Existing reference-date behavior in `core/prompter.py`.
**Requirement**: AQI-04, AQI-05, AQI-06

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Month-without-year uses the reference year.
- [ ] Current/previous month, current year, and relative day windows produce
      exact start-inclusive/end-exclusive intervals.
- [ ] Explicit years override the reference year.
- [ ] Questions without a temporal expression produce no temporal filter.
- [ ] Boundary and Portuguese accent variants are tested.

**Tests**: unit
**Gate**: quick

### T3: Separating plan and SQL generation

**Status**: Pending

**What**: Add typed `QueryPlan` normalization and two-stage Ollama
planning/SQL-generation contracts while preserving the existing translation
response shape.
**Where**: `core/query_plan.py`, `core/prompter.py`, `core/translator.py`,
`test_translator.py`, `test_prompter.py`
**Depends on**: T1, T2
**Reuses**: Existing conversation context, JSON extraction, and Ollama call.
**Requirement**: AQI-07, AQI-08

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Planner output normalizes into a typed plan with all required fields.
- [ ] SQL generation receives the normalized plan and temporal hints.
- [ ] Malformed planner or SQL-stage JSON produces a retryable typed error.
- [ ] No domain-specific SQL templates are introduced.
- [ ] Existing translator tests pass and new tests cover both stages.

**Tests**: unit
**Gate**: quick

### T4: Validating plans and SQL

**Status**: Pending

**What**: Reject unknown plan identifiers and preserve the existing read-only
SQL guard before any database execution.
**Where**: `core/query_validation.py`, `api/services/chat.py`,
`api/tests/test_query_validation.py`, `api/tests/test_chat_service.py`
**Depends on**: T1, T3
**Reuses**: `PredefinedQueryRepository.validate_query`.
**Requirement**: AQI-09, AQI-10

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Unknown tables, columns, and relationships are rejected with stable
      validation errors.
- [ ] Non-read-only and multi-statement SQL never reaches the database.
- [ ] Valid generic plans and SELECT/WITH SQL pass.
- [ ] Tests assert database calls are absent on validation failure.

**Tests**: unit
**Gate**: quick

### T5: Adding bounded execution repair

**Status**: Pending

**What**: Use database execution errors to attempt one validated SQL repair
and persist either the repaired result or a retryable terminal failure.
**Where**: `api/services/chat.py`, `core/translator.py`,
`api/tests/test_chat_service.py`, `api/tests/test_chat_execute_routes.py`
**Depends on**: T3, T4
**Reuses**: Stored SQL execution, retry metadata, and read-only adapter.
**Requirement**: AQI-11, AQI-12

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] A database error triggers no more than one repair attempt.
- [ ] A repaired query passes validation before execution.
- [ ] A successful repair updates the same assistant message and records the
      repaired SQL.
- [ ] A failed repair exposes one retryable error without a loop.
- [ ] Tests cover original failure, successful repair, and failed repair.

**Tests**: unit
**Gate**: quick

### T6: Critiquing result quality

**Status**: Pending

**What**: Add truthful result diagnostics for zero rows and missing expected
columns, preserving valid results and prohibiting invented numeric claims.
**Where**: `core/result_quality.py`, `api/services/chat.py`,
`api/schemas/chat.py`, `api/tests/test_chat_service.py`,
`api/tests/test_chat_translate_routes.py`
**Depends on**: T3, T4
**Reuses**: Result serializer, summaries, and optional response fields.
**Requirement**: AQI-13, AQI-14, AQI-15

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Zero-row results remain successful and carry an explicit diagnostic.
- [ ] Missing expected dimensions or metrics carry an explicit diagnostic.
- [ ] API responses include interpretation and diagnostics without breaking
      existing clients.
- [ ] Tests prove no fabricated numeric summary is emitted.

**Tests**: unit
**Gate**: quick

### T7: Showing interpretation and diagnostics

**Status**: Pending

**What**: Render plan interpretation and result diagnostics in the existing
assistant response without adding chat messages or disrupting review/execute.
**Where**: `web/src/api/client.ts`, `web/src/features/chat/useChat.ts`,
`web/src/features/chat/ChatWorkspace.tsx`,
`web/src/features/chat/useChat.test.tsx`,
`web/src/features/chat/ChatWorkspace.test.tsx`,
`web/e2e/chat.spec.ts`
**Depends on**: T5, T6
**Reuses**: Stable message replacement, result regions, and E2E mocks.
**Requirement**: AQI-16

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Interpretation displays dimensions, metrics, period, and assumptions.
- [ ] Diagnostics display beside the same assistant result.
- [ ] Existing review, execution, retry, and message-count behavior remains
      stable.
- [ ] Unit and E2E tests cover successful, empty, and failed states.

**Tests**: unit/e2e
**Gate**: full

### T8: Measuring query quality

**Status**: Pending

**What**: Add a domain-neutral benchmark harness, sample case contract, tests,
and documentation for comparing query quality.
**Where**: `evaluation/query_benchmark.py`,
`evaluation/test_query_benchmark.py`, `docs/avaliacao_consultas.md`,
`README.md`
**Depends on**: T5, T6, T7
**Reuses**: API result payload fields and existing test commands.
**Requirement**: AQI-17, AQI-18, AQI-19

**Tools**:

- MCP: NONE
- Skill: `tlc-spec-driven`

**Done when**:

- [ ] Harness accepts generic cases and recorded results without production
      database access.
- [ ] Report includes executable rate, expected-column coverage, zero-row
      rate, and latency.
- [ ] Unit tests assert exact aggregate metrics.
- [ ] Documentation explains how to add real cases without embedding SQL
      templates in the application.

**Tests**: unit
**Gate**: build

## Phase Execution Map

```text
T1 ------→ T3 ------→ T4 ------→ T5 ------→ T7 ------→ T8
T2 ------→ T3
T1 ------→ T4
T3 ------→ T6 ------→ T7
T4 ------→ T6
T3 ------→ T5
T5 ------→ T8
T6 ------→ T8
```

## Validation Tables

### Diagram-Definition Cross-Check

| Task | Depends on | Diagram | Status |
| --- | --- | --- | --- |
| T1 | None | None | ✅ |
| T2 | None | None | ✅ |
| T3 | T1, T2 | T1 → T3, T2 → T3 | ✅ |
| T4 | T1, T3 | T1 → T4, T3 → T4 | ✅ |
| T5 | T3, T4 | T3 → T5, T4 → T5 | ✅ |
| T6 | T3, T4 | T3 → T6, T4 → T6 | ✅ |
| T7 | T5, T6 | T5 → T7, T6 → T7 | ✅ |
| T8 | T5, T6, T7 | T5 → T8, T6 → T8, T7 → T8 | ✅ |

### Test Co-location Validation

| Task | Code layer | Matrix requires | Task says | Status |
| --- | --- | --- | --- | --- |
| T1 | Semantic profile | unit | unit | ✅ |
| T2 | Temporal/domain logic | unit | unit | ✅ |
| T3 | Planner/domain logic | unit | unit | ✅ |
| T4 | Validation/service | unit | unit | ✅ |
| T5 | Service/route | unit | unit | ✅ |
| T6 | Service/route | unit | unit | ✅ |
| T7 | React and e2e | unit/e2e | unit/e2e | ✅ |
| T8 | Evaluation logic | unit | unit | ✅ |
