# Analytical Chat Queries Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: activate it by name and
follow its Execute flow and Critical Rules. Each task is verified and committed
before the next task begins.

---

**Design**: `.specs/features/analytical-chat-queries/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from repository guidelines in `.github/copilot-instructions.md`,
> `docs/testes.md`, `pytest` configuration, and `web/package.json`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Core analytical/query logic | unit | Every supported intent, date boundary, fallback, and invalid-date edge case | `test_analytical_queries.py`, `test_prompter.py`, `test_translator.py` | `pytest -m "not integration" -v` |
| API service/serializer | unit | Summary shapes, truncation, non-numeric values, execution mode, and failure paths | `api/tests/test_chat_service.py`, `api/tests/test_result_serializer.py`, `api/tests/test_chat_translate_routes.py` | `pytest -m "not integration" -v` |
| React state/UI | unit | Automatic response, review compatibility, summary ordering, and SQL details | `web/src/**/*.test.tsx`, `web/src/**/*.test.ts` | `npm --prefix web run check` |
| Web integration | e2e | Automatic execution, warning/retry, explicit review, and stable message count | `web/e2e/chat.spec.ts` | `npm --prefix web run e2e` |
| Entity/config/schema | none | Build/type validation only | API/frontend schema files | `pytest -m "not integration" -v` and `npm --prefix web run check` |

## Gate Check Commands

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Core or API unit task | `pytest -m "not integration" -v` |
| Full | Frontend or API contract task | `pytest -m "not integration" -v && npm --prefix web run check && npm --prefix web run e2e` |
| Build | Phase completion | `python -m compileall -q api core database && pytest -m "not integration" -v && npm --prefix web run build` |

---

## Execution Plan

### Phase 1: Analytical foundation

```
T1 → T2 → T3
```

### Phase 2: Result contract

```
T3 → T4 → T5
```

### Phase 3: React experience and regression coverage

```
T5 → T6 → T7 → T8
```

## Task Breakdown

### T1: Add supermarket semantic rules to the fallback prompt

**Status**: Done

**What**: Extend the system prompt with explicit status, date, join, metric,
grouping, and reconciliation rules.
**Where**: `core/prompter.py`, `test_prompter.py`
**Depends on**: None
**Reuses**: Existing prompt assembly and temporary-directory tests
**Requirement**: ANALYTICAL-04

**Done when**:

- [ ] The prompt defines completed-sales, receipt-revenue, product-value, date
      interval, and product-grouping semantics.
- [ ] Existing prompt assembly tests remain green and assert the new rules.
- [ ] Quick gate passes with no test deletion.

**Tests**: unit
**Gate**: quick

### T2: Implement deterministic common sales query recognition

**What**: Add a pure query builder for revenue totals and product sales with
Portuguese month parsing, current-period defaults, and half-open date intervals.
**Where**: `core/analytical_queries.py`, `test_analytical_queries.py`
**Depends on**: T1
**Reuses**: Live schema names and Python standard library
**Requirement**: ANALYTICAL-01, ANALYTICAL-02, ANALYTICAL-03

**Done when**:

- [ ] August revenue produces a single aggregate over completed sales.
- [ ] August product sales produce product, quantity, and value grouped rows.
- [ ] Relative current-period and invalid-date cases are covered.
- [ ] Quick gate passes with no test deletion.

**Tests**: unit
**Gate**: quick

### T3: Prefer deterministic analytical queries before LLM fallback

**What**: Integrate the query builder into the translator while preserving the
existing Ollama JSON parsing and fallback behavior.
**Where**: `core/translator.py`, `test_translator.py`
**Depends on**: T2
**Reuses**: Existing `Translator` and mocked Ollama tests
**Requirement**: ANALYTICAL-04, ANALYTICAL-05

**Done when**:

- [ ] Recognized sales questions return deterministic SQL without calling
      Ollama.
- [ ] Unsupported questions still call Ollama with semantic prompt context.
- [ ] Read-only validation remains the service boundary.
- [ ] Quick gate passes with no test deletion.

**Tests**: unit
**Gate**: quick

### T4: Add deterministic summaries to serialized results

**What**: Add summary generation for product metrics, revenue totals, generic
results, null/non-numeric values, and truncated payloads.
**Where**: `api/serializers/results.py`, `api/tests/test_result_serializer.py`
**Depends on**: T3
**Reuses**: Existing bounded JSON-safe serializer
**Requirement**: ANALYTICAL-06, ANALYTICAL-07, ANALYTICAL-09

**Done when**:

- [ ] Product results summarize row count, quantity, and value from returned
      rows.
- [ ] Revenue totals summarize the returned numeric total.
- [ ] Generic, null, non-numeric, and truncated results remain truthful.
- [ ] Quick gate passes with no test deletion.

**Tests**: unit
**Gate**: quick

### T5: Expose summaries and automatic execution through the API

**What**: Add the optional summary to API response models and ChatService
execution results while preserving explicit review mode and retry behavior.
**Where**: `api/services/chat.py`, `api/schemas/chat.py`,
`api/tests/test_chat_service.py`, `api/tests/test_chat_translate_routes.py`
**Depends on**: T4
**Reuses**: Existing ChatResult, response envelope, and service tests
**Requirement**: ANALYTICAL-05, ANALYTICAL-06, ANALYTICAL-10, ANALYTICAL-11,
ANALYTICAL-12

**Done when**:

- [ ] Executed responses carry the deterministic summary.
- [ ] Automatic mode executes only after successful translation and validation.
- [ ] Warning, translator failure, database failure, and explicit review mode
      retain their existing behavior.
- [ ] Full gate passes with no test deletion.

**Tests**: unit
**Gate**: full

### T6: Carry summaries and automatic mode through React chat state

**What**: Add summary typing/state propagation and configure the authenticated
chat to request automatic execution by default.
**Where**: `web/src/api/client.ts`, `web/src/features/chat/useChat.ts`,
`web/src/app/AuthenticatedApp.tsx`, related unit tests
**Depends on**: T5
**Reuses**: Existing ChatResponse mapping and `useChat` request lifecycle
**Requirement**: ANALYTICAL-10, ANALYTICAL-11, ANALYTICAL-12

**Done when**:

- [ ] The normal authenticated chat sends `review_mode: false`.
- [ ] Summary fields survive translate/execute response mapping.
- [ ] Explicit review-mode hook tests remain green.
- [ ] Full gate passes with no test deletion.

**Tests**: unit
**Gate**: full

### T7: Render summary and collapsed SQL details

**What**: Render the summary before the result table and expose SQL through an
accessible collapsed details element without duplicating the timeline.
**Where**: `web/src/features/chat/ChatWorkspace.tsx`,
`web/src/features/chat/ChatWorkspace.test.tsx`
**Depends on**: T6
**Reuses**: Existing result action region and chart/CSV controls
**Requirement**: ANALYTICAL-08

**Done when**:

- [ ] Summary appears before the table for executed results.
- [ ] SQL is available through an accessible details control.
- [ ] Existing chart, CSV, review, and truncation behavior remains intact.
- [ ] Full gate passes with no test deletion.

**Tests**: unit
**Gate**: full

### T8: Update end-to-end chat contracts

**What**: Update E2E fixtures and scenarios for automatic execution while
retaining explicit review and warning/retry coverage.
**Where**: `web/e2e/chat.spec.ts`
**Depends on**: T7
**Reuses**: Existing authenticated page and stable-message assertions
**Requirement**: ANALYTICAL-08, ANALYTICAL-10, ANALYTICAL-11, ANALYTICAL-12

**Done when**:

- [ ] Automatic execution is verified without clicking a review button.
- [ ] Explicit review remains covered.
- [ ] Warning/retry does not execute invalid SQL.
- [ ] Build gate passes with no test deletion.

**Tests**: e2e
**Gate**: build

## Phase Execution Map

```
Phase 1: T1 → T2 → T3
Phase 2: T3 → T4 → T5
Phase 3: T5 → T6 → T7 → T8
```

## Validation Tables

### Granularity

| Task | Scope | Status |
| --- | --- | --- |
| T1 | Prompt rules plus co-located prompt tests | ✅ Granular |
| T2 | Pure query builder plus co-located unit tests | ✅ Granular |
| T3 | Translator integration plus co-located translator tests | ✅ Granular |
| T4 | Result summary plus co-located serializer tests | ✅ Granular |
| T5 | API response/service wiring plus co-located API tests | ✅ Granular |
| T6 | React state/default mode plus co-located unit tests | ✅ Granular |
| T7 | React result presentation plus co-located unit tests | ✅ Granular |
| T8 | E2E contract updates | ✅ Granular |

### Dependency cross-check

| Task | Depends on | Diagram | Status |
| --- | --- | --- | --- |
| T1 | None | Phase 1 root | ✅ |
| T2 | T1 | T1 → T2 | ✅ |
| T3 | T2 | T2 → T3 | ✅ |
| T4 | T3 | Phase 2 root after Phase 1 | ✅ |
| T5 | T4 | T4 → T5 | ✅ |
| T6 | T5 | Phase 3 root after Phase 2 | ✅ |
| T7 | T6 | T6 → T7 | ✅ |
| T8 | T7 | T7 → T8 | ✅ |

### Test co-location

| Task | Code layer | Matrix requirement | Task field | Status |
| --- | --- | --- | --- | --- |
| T1 | Core prompt | unit | unit | ✅ |
| T2 | Core analytical logic | unit | unit | ✅ |
| T3 | Core translator | unit | unit | ✅ |
| T4 | API serializer | unit | unit | ✅ |
| T5 | API service/schema | unit | unit | ✅ |
| T6 | React state | unit | unit | ✅ |
| T7 | React UI | unit | unit | ✅ |
| T8 | Web integration | e2e | e2e | ✅ |
