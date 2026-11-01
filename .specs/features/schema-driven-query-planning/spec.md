# Schema-Driven Query Planning Specification

## Problem Statement

The current planner contains SQL and business rules for one sales schema. That
couples a supposedly reusable chat to specific tables, columns, statuses, and
metrics. A different database can therefore receive an invalid or misleading
query before the model has a chance to inspect its actual schema.

## Goals

- Generate every chat plan from the live schema, optional DDLs, and business
  rules available at runtime.
- Keep generic analytical reasoning strategies without embedding domain SQL.
- Expose real foreign-key relationships to the planner.
- Preserve the existing primary result, managerial insights, read-only
  validation, retry, and review-mode contracts.
- Resolve incomplete periods with a runtime reference date without coupling the
  planner to a business entity.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Adding a second database engine adapter | The current change removes domain coupling; engine support remains an adapter concern. |
| Removing the shared-query catalog | Catalog SQL is user-managed data, not planner logic. |
| Changing the insight response contract | Existing clients must remain compatible. |
| Replacing the LLM with a new model | The current Ollama integration remains the execution boundary. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Planner source of truth | Live schema, relationships, DDLs, and business rules | Runtime context is the only portable source for entity names and semantics. | yes |
| Incomplete month without year | Use the year from the runtime reference date | This preserves the requested period behavior without naming a domain table or column. | yes |
| No explicit period | Do not invent a period unless the request means the current period | A fabricated filter can silently remove valid records. | yes |
| Managerial complements | At most three schema-grounded read-only supporting queries | The existing API bound controls latency and response size. | yes |
| SQL engine | PostgreSQL remains the current adapter dialect | Generalizing the domain does not require changing the database adapter in this slice. | yes |

**Open questions:** none.

## User Stories

### P1: Portable planning

As an operator, I want the chat to work with a different business schema
without changing Python code, so that the application is reusable.

### P1: Useful analysis

As a manager, I want the model to infer relevant dimensions, measures, joins,
and complementary readings from the current schema, so that the answer is more
useful than a hardcoded literal query.

### P1: Safe execution

As a user, I want generated queries to keep the existing read-only and schema
validation boundaries, so that a model error does not become a database write
or a fabricated result.

## Acceptance Criteria

1. The planner SHALL invoke the configured LLM for every non-empty question and
   SHALL contain no domain-specific SQL builder or deterministic domain intent
   path.
2. WHEN the planner builds a system prompt with a live schema THEN the prompt
   SHALL include that schema, require schema-grounded SQL, and contain no
   fixed business entity, column, status, or metric from the former sales
   domain.
3. WHEN a request contains a month without a year THEN the system prompt SHALL
   provide a runtime reference date and instruct the model to use its year.
4. WHEN a request omits a period THEN the prompt SHALL instruct the model not
   to invent a time filter unless the request explicitly means the current
   period.
5. WHEN the database schema contains foreign keys THEN schema introspection
   SHALL include each relationship with its source and target table and
   column.
6. WHEN the LLM returns a plan THEN the translator SHALL preserve the primary
   SQL, normalize at most three supporting queries, and retain named
   parameters in the existing response shape.
7. IF a generated primary or supporting query is invalid, multi-statement, or
   non-read-only THEN the existing execution service SHALL reject it before
   database execution.
8. WHEN the planner supplies schema-grounded supporting queries THEN the API
   SHALL preserve the primary result and expose successful or failed
   complements through the existing insights contract.

## Edge Cases

- An empty question still produces no deterministic query and follows the
  existing model/error boundary.
- A month name without a year uses the injected reference date, not a fixed
  year.
- A question naming a year but no month does not receive a fabricated month
  from planner code.
- A schema with no foreign keys remains valid and simply has no relationship
  section.
- Malformed or excessive supporting queries are normalized to an empty list as
  before.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| SDQP-01 | P1: Portable planning | Execute | Verified by T1 |
| SDQP-02 | P1: Portable planning | Execute | Verified by T2 |
| SDQP-03 | P1: Portable planning | Execute | Verified by T2 |
| SDQP-04 | P1: Portable planning | Execute | Verified by T2 |
| SDQP-05 | P1: Portable planning | Execute | Verified by T2 |
| SDQP-06 | P1: Safe execution | Execute | Verified by T1 |
| SDQP-07 | P1: Useful analysis | Execute | Pending |
| SDQP-08 | P1: Useful analysis | Execute | Pending |

## Success Criteria

- No production planner module contains SQL naming the former sales tables or
  columns.
- A prompt built from a customer-like schema and one built from an inventory-
  like schema differ only in runtime context, not in hardcoded entity rules.
- Foreign-key relationships are available to the model.
- Existing chat, insight, retry, and read-only tests remain green.
