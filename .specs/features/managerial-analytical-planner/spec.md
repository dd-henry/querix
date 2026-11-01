# Managerial Analytical Planner Specification

## Problem Statement

The current analytical fast path handles revenue totals and product
aggregation, but a natural-language request such as "quais foram as vendas de
agosto?" can fall through to the LLM. The fallback may invent a year or answer
only the literal question instead of using related tables to provide useful
managerial context.

## Goals

- Resolve incomplete periods deterministically and consistently.
- Recognize sale-list questions as well as revenue and product questions.
- Build a bounded analytical plan from the existing schema relationships.
- Return the requested result first and a separate, truthful managerial reading.
- Preserve read-only validation, retry/idempotency, automatic execution, and
  explicit review mode.

## Out of Scope

| Feature | Reason |
| --- | --- |
| An autonomous agent for every possible database domain | This slice targets the existing sales schema and its known relationships. |
| Database writes or schema changes | Chat remains read-only. |
| Automatic reconciliation of header totals and item subtotals | Existing data-quality discrepancy needs a separate business decision. |
| User-configurable managerial profiles | No preference model is required for this slice. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Missing year with explicit month | Use the current server year | "agosto" means August of the current year unless a year is stated. | yes |
| Missing month | Use the current server month and year | Avoids an invented historical period for "este mês" or an omitted period. | yes |
| Managerial depth | Direct result plus a labeled "Leitura gerencial" with 2–3 relevant indicators | Adds useful context without overwhelming the requested answer. | yes |
| Plan execution | One primary query plus at most three supporting read-only queries | Bounds latency, database load, and response size. | yes |
| Insight generation | Derive summaries from returned rows; no LLM-generated numeric prose | Prevents hallucinated metrics. | yes |
| Missing supporting relationship | Omit that insight and state why | The planner must not invent tables or columns. | assumed |
| Supporting-query failure | Preserve the primary answer and expose an explicit warning for that insight | Partial analytical success is more useful than hiding the primary result. | assumed |

**Open questions:** none - product decisions were resolved or recorded as
assumptions above.

## User Stories

### P1: Correct period interpretation

As a user, I want "vendas de agosto" to use the current year when no year is
provided, so that the result matches the data period instead of an invented
year.

### P1: Direct sales answer

As a manager, I want "quais foram as vendas do período?" to return sale-level
rows from the `vendas` table with the correct completed-sale and date semantics.

### P1: Managerial context

As a manager, I want the chat to add a small, clearly labeled set of useful
indicators from related tables without replacing or duplicating my requested
answer.

### P1: Safe partial execution

As a user, I want a useful primary result even when a complementary insight
cannot be calculated, with a visible explanation of the missing insight.

## Acceptance Criteria

1. WHEN a question contains a recognized month but no year THEN the planner
   SHALL bind the month to the current server year.
2. WHEN a recognized question contains no month THEN the planner SHALL bind the
   current server month and year.
3. WHEN a question asks which sales occurred in a period THEN the primary plan
   SHALL select sale-level fields from `vendas`, filter
   `status = 'concluida'`, and use an inclusive-start/exclusive-end interval.
4. WHEN a primary sales question is recognized THEN the planner SHALL produce
   no more than three supporting queries using only known schema relationships.
5. WHEN a plan is executed THEN every primary and supporting query SHALL pass
   single-statement read-only validation before database execution.
6. WHEN a plan executes successfully THEN the API SHALL keep the primary result
   in the existing result field and return supporting results as labeled
   insights.
7. IF a supporting query fails THEN the API SHALL preserve a successful primary
   result and return an explicit warning attached to that insight.
8. WHEN the frontend receives insights THEN it SHALL render the primary answer
   first and a separate "Leitura gerencial" section afterward without adding
   duplicate timeline messages.
9. WHEN a fallback LLM plan is used THEN the prompt SHALL require schema-grounded
   supporting queries, bound parameters, and no invented tables or columns.
10. IF any generated plan query is invalid, multi-statement, or non-read-only
    THEN the system SHALL reject that query before database execution and expose
    the existing retryable error behavior.
11. WHEN an insight summary is displayed THEN its numeric values SHALL be
    calculated only from the bounded rows returned for that insight.
12. WHEN the same request ID is retried THEN the system SHALL preserve existing
    idempotent request behavior for the primary plan and its insights.

## Edge Cases

- An explicit invalid month or unknown month name falls back to the LLM path
  rather than fabricating a date.
- A question with an explicit year but no month uses the full year only when
  the planner has a defined year intent; otherwise it remains an LLM fallback.
- A supporting query with no rows returns a truthful empty insight, not a
  fabricated metric.
- A result exceeding the row limit marks its own summary as bounded.
- A primary database failure remains a retryable request failure.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| MANAGER-01 | P1: Correct period interpretation | Design | Pending |
| MANAGER-02 | P1: Direct sales answer | Design | Pending |
| MANAGER-03 | P1: Managerial context | Design | Pending |
| MANAGER-04 | P1: Safe partial execution | Design | Pending |
| MANAGER-05 | P1: Safe partial execution | Design | Pending |
| MANAGER-06 | P1: Managerial context | Design | Pending |

## Success Criteria

- "Quais foram as vendas do mês de agosto?" produces August 2026 parameters when
  the server date is October 2026.
- The primary result contains sale-level rows and completed sales only.
- The response contains at most three labeled managerial insights based on
  `vendas`, `itens_venda`, and `produtos`.
- Invalid or failed supporting queries do not erase a valid primary result.
- Existing automatic execution, explicit review, retry, and read-only tests
  remain green.
