# Managerial Analytical Planner Tasks

## Execution Protocol

Implement one task at a time with the `tlc-spec-driven` skill. Each task is
tested, gated, marked done, and committed before the next task begins.

**Design**: `.specs/features/managerial-analytical-planner/design.md`
**Status**: In Progress

## Test Coverage Matrix

> Generated from `.github/copilot-instructions.md`, `docs/testes.md`,
> `pytest.ini`, and `web/package.json`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Analytical planner and prompt | unit | Every supported intent, period edge, plan bound, fallback shape, and invalid plan case | `test_analytical_queries.py`, `test_prompter.py`, `test_translator.py` | `venv/bin/python -m pytest -m "not integration" -v` |
| API plan execution and schema | unit | Primary success, support success, support failure, primary failure, read-only validation, retry/idempotency | `api/tests/test_chat_service.py`, `api/tests/test_chat_translate_routes.py` | `venv/bin/python -m pytest -m "not integration" -v` |
| React state and UI | unit | Insight mapping, primary-before-insights order, warning/empty states, collapsed SQL, stable timeline | `web/src/features/chat/*.test.tsx`, `web/src/app/*.test.tsx` | `npm --prefix web run check` |
| Web integration | e2e | Automatic plan, visible managerial section, explicit review compatibility, partial warning, stable message count | `web/e2e/chat.spec.ts` | `cd web && npx playwright test` |
| Entity/config/schema | none | Type/build validation | API/frontend schema files | build gate |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Planner or API unit task | `venv/bin/python -m pytest -m "not integration" -v` |
| Full | Frontend or contract task | `venv/bin/python -m pytest -m "not integration" -v && npm --prefix web run check && cd web && npx playwright test` |
| Build | Final task or phase completion | `venv/bin/python -m compileall -q api core database && venv/bin/python -m pytest -m "not integration" -v && npm --prefix web run build` |

## Execution Plan

### Phase 1: Plan foundation

```
T1 → T2
```

### Phase 2: Safe API execution

```
T2 → T3 → T4
```

### Phase 3: Managerial presentation

```
T4 → T5 → T6
```

## Task Breakdown

### T1: Extend deterministic period and sales intent planning

**Status**: Done

**What**: Resolve current-year/current-month defaults and recognize detailed
sales-period questions, returning a primary query plus bounded supporting query
specs.
**Where**: `core/analytical_queries.py`, `test_analytical_queries.py`
**Depends on**: None
**Requirement**: MANAGER-01, MANAGER-02, MANAGER-03

**Done when**:

- [x] Explicit August without year uses August of the injected current year.
- [x] No explicit month uses the injected current month.
- [x] "Quais foram as vendas do mês de agosto?" returns sale-level primary SQL
      and no more than three labeled support queries.
- [x] Every support query uses known schema relationships and named parameters.
- [x] Invalid periods remain an LLM fallback.

**Tests**: unit
**Gate**: quick

### T2: Add structured managerial fallback planning

**Status**: Done

**What**: Extend prompt instructions and translator parsing for optional
supporting-query specs while preserving the existing single-query fallback.
**Where**: `core/prompter.py`, `core/translator.py`, `test_prompter.py`,
`test_translator.py`
**Depends on**: T1
**Requirement**: MANAGER-03, MANAGER-05

**Done when**:

- [x] The prompt requires schema-grounded, parameterized supporting queries.
- [x] Valid fallback plans are parsed with titles, keys, SQL, and parameters.
- [x] Missing or malformed support data produces an empty support list.
- [x] Existing Ollama fallback tests remain green.

**Tests**: unit
**Gate**: quick

### T3: Execute bounded analytical plans in the chat service

**Status**: Done

**What**: Validate and execute the primary query followed by up to three
supporting queries, preserving primary success when a support fails.
**Where**: `api/services/chat.py`, `api/tests/test_chat_service.py`
**Depends on**: T2
**Requirement**: MANAGER-04, MANAGER-05, MANAGER-06

**Done when**:

- [x] Primary and support queries are independently read-only validated.
- [x] Supports are bounded to three and five thousand rows each.
- [x] A support database error becomes a warning insight without erasing the
      primary result.
- [x] A primary database error remains retryable.
- [x] Stored plan metadata supports idempotent retry.

**Tests**: unit
**Gate**: quick

### T4: Expose managerial insights through the API

**Status**: Done

**What**: Add optional insight response models and map plan results/warnings
through translate and execute routes without changing the primary result.
**Where**: `api/schemas/chat.py`, `api/routes/chat_translate.py`,
`api/routes/chat_execute.py`, API route tests
**Depends on**: T3
**Requirement**: MANAGER-04, MANAGER-06

**Done when**:

- [x] Existing clients still receive the primary `result`.
- [x] Successful supports are returned as labeled insights with result and
      deterministic summary.
- [x] Failed supports include explicit warnings.
- [x] Review and automatic execution response modes remain compatible.

**Tests**: unit
**Gate**: quick

### T5: Carry insights through React state and render the managerial section

**Status**: Done

**What**: Type, map, and render optional insights after the primary result
without adding timeline messages or hiding the direct answer.
**Where**: `web/src/api/client.ts`, `web/src/features/chat/useChat.ts`,
`web/src/features/chat/ChatWorkspace.tsx`, related frontend tests
**Depends on**: T4
**Requirement**: MANAGER-03, MANAGER-04, MANAGER-06

**Done when**:

- [x] Primary result renders before the "Leitura gerencial" section.
- [x] Each insight has its own summary/result or warning and collapsed SQL.
- [x] Empty insight results remain truthful and visible.
- [x] Timeline message count remains unchanged.

**Tests**: unit
**Gate**: full

### T6: Cover managerial plan behavior end to end

**Status**: Done

**What**: Add E2E scenarios for automatic primary-plus-insights execution,
partial support warning, and explicit review compatibility.
**Where**: `web/e2e/chat.spec.ts`
**Depends on**: T5
**Requirement**: MANAGER-03, MANAGER-04, MANAGER-05, MANAGER-06

**Done when**:

- [x] A sales-period question displays the primary result and managerial
      section without duplicate messages.
- [x] Support warnings are visible while the primary answer remains visible.
- [x] Review-mode behavior remains covered.

**Tests**: e2e
**Gate**: build
