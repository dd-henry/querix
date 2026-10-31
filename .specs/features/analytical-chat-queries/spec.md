# Analytical Chat Queries Specification

## Problem Statement

The chat currently translates natural-language questions directly into SQL without
an explicit analytical intent or the supermarket's business rules. As a result,
questions about sales can include cancelled transactions, omit the year, return
duplicate product rows, and omit quantity or item value. The default review step
also adds an avoidable interaction before a validated read-only query can run.

## Goals

- [ ] Generate business-correct queries for revenue totals and product sales for
      the supported supermarket schema.
- [ ] Return a concise, deterministic summary plus the detailed result table.
- [ ] Execute validated read-only chat queries automatically by default.
- [ ] Preserve the existing LLM fallback, safety validation, retry behavior, and
      manual review path for explicit callers.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Repairing inconsistent historical sales data | Requires a separate data-quality decision and migration. |
| Replacing the LLM for every possible natural-language query | This feature targets common sales analysis and strengthens the fallback prompt. |
| Removing Streamlit | The frontend cutover remains a separate approved task. |
| Persisting user-specific analytical preferences | No settings model is required for this slice. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Default result presentation | Summary followed by a detailed table | User selected the executive-summary-plus-table behavior. | yes |
| Default execution mode | Automatically execute validated read-only SQL; keep SQL available in a details section | User selected automatic execution to remove the extra review wait. | yes |
| Revenue definition | `SUM(vendas.valor_total)` for rows with `status = 'concluida'` | The sales header is the source of truth for receipt-level revenue. | yes |
| Product-value definition | `SUM(itens_venda.subtotal)` grouped by product | Item subtotal preserves the historical price at the time of sale. | yes |
| Relative date resolution | Resolve relative dates using the API server's current date and use an inclusive lower/exclusive upper interval | Avoids month-only filters that mix years and handles timestamps safely. | yes |
| Unknown analytical intent | Use the existing LLM translation path with the strengthened semantic rules | Preserves broad query coverage without inventing a template for every domain. | yes |
| Data reconciliation | Do not silently reconcile `vendas.valor_total` and item subtotals | The discrepancy needs a separate business decision; this feature keeps the two metrics explicit. | yes |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Correct sales analysis ⭐ MVP

**User Story**: As a manager, I want sales questions to use the correct business
definitions so that the result supports decisions instead of requiring repeated
follow-up questions.

**Why P1**: Incorrect inclusion of cancelled sales and ungrouped product rows
directly undermines trust in the application.

**Acceptance Criteria**:

1. WHEN a recognized revenue-total question includes a period THEN the query
   SHALL aggregate `vendas.valor_total`, filter `status = 'concluida'`, and use
   an inclusive lower/exclusive upper timestamp interval for that period.
2. WHEN a recognized product-sales question includes a period THEN the query
   SHALL join `vendas`, `itens_venda`, and `produtos`, filter
   `status = 'concluida'`, group by product identity and name, and return
   product, summed quantity, and summed item subtotal.
3. WHEN a recognized question omits a period THEN the query SHALL use the
   current calendar period defined by the API server clock.
4. IF the recognized-query builder cannot determine a supported intent THEN the
   system SHALL use the existing LLM translation path without bypassing the
   read-only SQL validator.
5. IF a generated or stored query is not a single read-only `SELECT` or `WITH`
   statement THEN the system SHALL reject it before database execution.

**Independent Test**: Submit the Portuguese questions about August sales total
and products sold, then inspect the stored SQL and returned columns without
calling the real Ollama service.

### P1: Useful result presentation ⭐ MVP

**User Story**: As a manager, I want the result summarized before the raw table
so that I can understand the answer without manually scanning every row.

**Why P1**: The current raw result requires multiple follow-up questions even
when the database contains the requested product and quantity data.

**Acceptance Criteria**:

1. WHEN an executed result contains product, quantity, and value columns THEN the
   API SHALL return a summary containing the product-row count, total quantity,
   and total value derived only from the returned rows.
2. WHEN an executed result contains a single numeric revenue total THEN the API
   SHALL return a summary containing that total without inventing additional
   dimensions.
3. WHEN the frontend receives an executed result with a summary THEN it SHALL
   render the summary before the result table and keep the SQL available in a
   collapsed details control.
4. IF a result cannot be summarized by a recognized shape THEN the API SHALL
   return a truthful generic row-count summary.

**Independent Test**: Render representative API responses in the backend and
frontend unit suites and assert the exact summary fields and visible ordering.

### P1: Low-friction execution ⭐ MVP

**User Story**: As a user, I want safe read-only questions to execute without an
extra confirmation click so that answers arrive with less friction.

**Why P1**: The current translate-then-review-then-execute flow adds a second
round trip for every normal question.

**Acceptance Criteria**:

1. WHEN the authenticated web application sends a normal chat question THEN it
   SHALL request automatic execution mode.
2. WHEN automatic execution mode receives a warning or translation/database
   failure THEN it SHALL preserve the existing warning or retryable error state
   and SHALL NOT execute a missing or invalid query.
3. WHERE a caller explicitly requests review mode THEN the API SHALL preserve the
   existing review response and manual execution controls.

**Independent Test**: Exercise the web mock API with an automatic executed
response, a warning response, and an explicit review response.

---

## Edge Cases

- IF the month name is not recognized or the requested period is invalid THEN
  the system SHALL fall back to the LLM path rather than fabricate dates.
- IF the result contains null or non-numeric metric values THEN the summary
  SHALL ignore non-numeric values and remain truthful.
- IF the query result is truncated THEN the summary SHALL state that it is based
  on the returned bounded rows.
- IF a retry repeats the same request ID THEN the existing idempotent persistence
  behavior SHALL remain unchanged.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| ANALYTICAL-01 | P1: Correct sales analysis | Design | Implementing |
| ANALYTICAL-02 | P1: Correct sales analysis | Design | Implementing |
| ANALYTICAL-03 | P1: Correct sales analysis | Design | Implementing |
| ANALYTICAL-04 | P1: Correct sales analysis | Design | Implementing |
| ANALYTICAL-05 | P1: Correct sales analysis | Design | Pending |
| ANALYTICAL-06 | P1: Useful result presentation | Design | Pending |
| ANALYTICAL-07 | P1: Useful result presentation | Design | Pending |
| ANALYTICAL-08 | P1: Useful result presentation | Design | Pending |
| ANALYTICAL-09 | P1: Useful result presentation | Design | Pending |
| ANALYTICAL-10 | P1: Low-friction execution | Design | Pending |
| ANALYTICAL-11 | P1: Low-friction execution | Design | Pending |
| ANALYTICAL-12 | P1: Low-friction execution | Design | Pending |

**Coverage:** 12 total, 0 mapped to tasks, 12 unmapped.

---

## Success Criteria

- [ ] The August product question returns one row per product with product,
      quantity, and value columns and excludes cancelled sales.
- [ ] The August revenue question excludes the five cancelled August sales.
- [ ] The normal web chat path returns executed results without a manual review
      click.
- [ ] Backend and frontend gates pass without reducing existing test counts.
