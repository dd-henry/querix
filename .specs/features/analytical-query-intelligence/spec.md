# Analytical Query Intelligence Specification

## Problem Statement

The current query flow sends a natural-language question and a large prompt to
one local model call. The model receives useful schema text, but the system
does not maintain a structured semantic profile, normalize temporal language
before planning, validate the generated plan against the live schema, or use
execution feedback to repair a query. As a result, technically valid queries
can still use the wrong period, omit requested measures, return empty results
without diagnosis, or fail to provide useful managerial context.

## Goals

- Build a reusable semantic context from the current database without
  hard-coding a business domain.
- Normalize common temporal expressions deterministically.
- Separate analytical planning from SQL generation.
- Validate the plan and generated SQL before execution.
- Repair one failed query using concrete execution feedback.
- Critique results without inventing numerical conclusions.
- Show the interpreted intent and assumptions in the chat.
- Provide a domain-neutral evaluation harness for real user questions.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Domain-specific SQL templates | The application must remain plug-in friendly. |
| Raw data rows in the semantic profile | Prompts must not receive unnecessary business data. |
| Unlimited autonomous retries | Unbounded retries can hide errors and create latency loops. |
| A separately deployed semantic microservice | The selected architecture is an in-process semantic layer for this feature. |
| Automatic production migrations | Schema metadata is read-only and derived from the current database. |

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Semantic cache lifetime | Process-local cache refreshed by the existing schema sync action | It avoids stale metadata after an explicit refresh while preserving simple deployment. | yes |
| Supported temporal language | Portuguese month names, current/previous month, current year, and relative day windows | These cover the reported date issue and are deterministic to test. | yes |
| SQL repair authority | One repair may replace the stored SQL only after the database rejects it and the repair passes validation | The user must not receive an unvalidated or silently looping query. | yes |
| Result quality signal | Return explicit diagnostics and assumptions; do not block valid zero-row results | Zero rows may be correct and require user-visible context. | yes |
| Model protocol | Keep Ollama as the provider and use typed JSON contracts between stages | It preserves the current integration boundary and makes stages testable. | yes |

**Open questions:** none.

## User Stories

### P1: Understand the live database

As a user, I want the assistant to understand the structure and relationships
of the current database, so that generated queries use real entities.

**Acceptance Criteria**:

1. The system SHALL expose a semantic profile containing table names, column
   names, data types, nullability, primary/unique keys, foreign keys, and
   candidate temporal and numeric columns.
2. The system SHALL exclude raw table rows and raw sample values from the
   semantic profile.
3. WHEN the schema synchronization action succeeds THEN the system SHALL
   invalidate the semantic cache and build a profile from the current schema.

**Independent Test**: Build a profile from a mocked adapter and assert the
required metadata and the absence of row values.

### P1: Plan an analytical question

As a user, I want the assistant to interpret my question before writing SQL,
so that the query reflects the requested dimensions, metrics, and period.

**Acceptance Criteria**:

4. WHEN a question is received THEN the system SHALL resolve supported temporal
   expressions into explicit date intervals using the configured reference
   date.
5. WHEN a month is supplied without a year THEN the system SHALL use the year
   of the reference date.
6. WHEN a question has no temporal expression THEN the system SHALL not add a
   temporal filter solely because a date column exists.
7. WHEN planning succeeds THEN the planner SHALL return a typed JSON plan with
   entities, relationships, dimensions, metrics, filters, grain, and
   assumptions before SQL generation.
8. WHEN SQL generation runs THEN it SHALL use the validated plan and return
   the existing response contract without domain-specific query templates.

**Independent Test**: Run the planner and date resolver with synthetic schema
metadata and assert exact plan fields and date intervals.

### P1: Validate and recover query execution

As a user, I want invalid or unhelpful queries to be caught and corrected,
so that I receive useful results instead of silent failures.

**Acceptance Criteria**:

9. IF a plan references an unknown table or column THEN the system SHALL reject
   it before database execution with a stable validation error.
10. IF generated SQL is not a single read-only SELECT or WITH statement THEN
    the system SHALL reject it before database execution.
11. IF the database rejects a validated query THEN the system SHALL attempt at
    most one repair using the database error and the original plan.
12. IF the repair fails validation or execution THEN the system SHALL preserve
    the original request, expose a retryable error, and SHALL NOT loop.
13. WHEN a query returns zero rows THEN the system SHALL preserve the valid
    result and attach a diagnostic that distinguishes no matching data from an
    execution failure.
14. The system SHALL not emit numerical conclusions that are absent from the
    returned result.

**Independent Test**: Mock validation failures, database errors, repair
responses, and zero-row results and assert bounded state transitions.

### P2: Explain the interpretation

As a user, I want to see how my question was interpreted, so that I can
correct assumptions before trusting the result.

**Acceptance Criteria**:

15. WHEN a plan is available THEN the API SHALL return a concise interpretation
    containing selected dimensions, metrics, period, and assumptions.
16. WHEN the chat receives an interpretation or diagnostic THEN the frontend
    SHALL render it associated with the same assistant response and SHALL NOT
    create a duplicate chat message.

**Independent Test**: Render a response with an interpretation and assert its
placement and stable message count.

### P2: Measure query quality

As a maintainer, I want to evaluate representative questions, so that model
and prompt changes can be compared using evidence.

**Acceptance Criteria**:

17. The evaluation harness SHALL accept domain-neutral cases containing a
    question, expected columns, and optional expected row constraints.
18. The evaluation harness SHALL report executable-query rate, expected-column
    coverage, zero-row rate, and latency for a case set.
19. The evaluation harness SHALL not embed business-specific SQL templates or
    require a production database to run its metric tests.

**Independent Test**: Run the harness against synthetic case results and assert
the exact aggregate metrics.

## Edge Cases

- A Portuguese month name is followed by an explicit year that differs from
  the reference year.
- A relative date phrase crosses a month or year boundary.
- A schema has no foreign keys or no candidate date columns.
- A plan contains an unknown identifier.
- A valid query returns zero rows.
- A database error persists after the single repair attempt.
- The planner returns malformed JSON or an empty assumptions list.
- Two requests attempt execution concurrently for the same request ID.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| AQI-01 | P1: Understand the live database | Design | Complete |
| AQI-02 | P1: Understand the live database | Design | Complete |
| AQI-03 | P1: Understand the live database | Design | Complete |
| AQI-04 | P1: Plan an analytical question | Design | Complete |
| AQI-05 | P1: Plan an analytical question | Design | Complete |
| AQI-06 | P1: Plan an analytical question | Design | Complete |
| AQI-07 | P1: Plan an analytical question | Design | Complete |
| AQI-08 | P1: Plan an analytical question | Design | Complete |
| AQI-09 | P1: Validate and recover query execution | Design | Complete |
| AQI-10 | P1: Validate and recover query execution | Design | Complete |
| AQI-11 | P1: Validate and recover query execution | Design | Pending |
| AQI-12 | P1: Validate and recover query execution | Design | Pending |
| AQI-13 | P1: Validate and recover query execution | Design | Pending |
| AQI-14 | P1: Validate and recover query execution | Design | Pending |
| AQI-15 | P2: Explain the interpretation | Design | Pending |
| AQI-16 | P2: Explain the interpretation | Design | Pending |
| AQI-17 | P2: Measure query quality | Design | Pending |
| AQI-18 | P2: Measure query quality | Design | Pending |
| AQI-19 | P2: Measure query quality | Design | Pending |

**Coverage**: 10 complete, 9 pending.

## Success Criteria

- A question with an incomplete month receives an explicit, deterministic
  interval before SQL generation.
- Unknown identifiers are rejected before reaching the database.
- A database failure causes at most one repair attempt.
- Users can see the selected dimensions, metrics, period, and assumptions.
- A benchmark run reports comparable quality metrics without hard-coded domain
  queries.
