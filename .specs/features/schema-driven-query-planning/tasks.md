# Schema-Driven Query Planning Tasks

## Execution Protocol

Implement one task at a time. Each task is tested, gated, marked done, and
committed before the next task begins.

**Design**: `.specs/features/schema-driven-query-planning/design.md`
**Status**: In Progress

## Test Coverage Matrix

> Generated from `README.md`, `docs/testes.md`, `pytest.ini`, and existing
> pytest tests. No project lint command is configured.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Prompt and translator | unit | Every planner invariant and listed edge case | `test_prompter.py`, `test_translator.py` | `venv/bin/python -m pytest -m "not integration" -v` |
| Schema adapter | unit | Relationship formatting, empty relationships, and existing adapter behavior | `test_postgres.py` | `venv/bin/python -m pytest -m "not integration" -v` |
| Existing API and frontend contracts | unit/e2e | Regression coverage for unchanged execution and insight behavior | `api/tests/`, `web/src/`, `web/e2e/` | `venv/bin/python -m pytest -m "not integration" -v && npm --prefix web run check` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | After planner or adapter unit tasks | `venv/bin/python -m pytest -m "not integration" -v` |
| Full | After frontend or API contract changes | `venv/bin/python -m pytest -m "not integration" -v && npm --prefix web run check` |
| Build | Final task | `venv/bin/python -m compileall -q api core database && venv/bin/python -m pytest -m "not integration" -v && npm --prefix web run build` |

## Execution Plan

### Phase 1: Remove domain coupling

```text
T1
```

### Phase 2: Make runtime context complete

```text
T1 -> T2
```

### Phase 3: Document and verify

```text
T2 -> T3
```

## Task Breakdown

### T1: Removing the deterministic domain planner

**Status**: Done

**What**: Delete the sales-specific query builder and make the translator
always use the configured LLM path. Replace its domain-specific tests with
behavioral assertions that former sales questions are still dispatched with
the current prompt/context.
**Where**: `core/translator.py`, `core/analytical_queries.py`,
`test_translator.py`, `test_analytical_queries.py`
**Depends on**: None
**Requirement**: SDQP-01, SDQP-06

**Done when**:

- [x] `core/translator.py` has no import or call to a deterministic
      domain-query builder.
- [x] A former sales-style question invokes Ollama and returns the structured
      model response.
- [x] No production module contains the deleted sales SQL builder.

**Tests**: unit
**Gate**: quick

### T2: Generalizing the prompt and schema context

**Status**: Done

**What**: Replace sales rules with generic schema-grounded analytical
guidance, include a runtime reference date, and expose foreign-key
relationships from PostgreSQL introspection.
**Where**: `core/prompter.py`, `database/postgres.py`, `test_prompter.py`,
`test_postgres.py`
**Depends on**: T1
**Requirement**: SDQP-02, SDQP-03, SDQP-04, SDQP-05

**Done when**:

- [x] The prompt contains no former sales entities or metrics.
- [x] The prompt includes generic period behavior, bounded supporting-query
      rules, named parameters, and live schema grounding.
- [x] Foreign-key metadata is rendered with source and target identifiers.
- [x] Empty relationship results remain valid schema context.

**Tests**: unit
**Gate**: quick

### T3: Updating architecture documentation and closing verification

**Status**: Pending

**What**: Update the public architecture documentation and run the complete
non-integration/build validation for the schema-driven planner.
**Where**: `README.md`, `docs/arquitetura_e_funcionamento.md`,
`.specs/features/schema-driven-query-planning/spec.md`
**Depends on**: T2
**Requirement**: SDQP-07, SDQP-08

**Done when**:

- [ ] Documentation states that query plans are generated from runtime schema
      context rather than domain-specific SQL.
- [ ] Requirement traceability is marked verified with test evidence.
- [ ] Build and non-integration gates pass.

**Tests**: unit
**Gate**: build
