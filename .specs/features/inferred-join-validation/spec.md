# Inferred Join Validation Specification

## Problem Statement

The planner currently rejects every relationship that is not declared as a
foreign key. Real databases can contain compatible columns without formal
constraints, so valid joins are blocked before SQL generation.

## Goals

- Accept planner relationships whose two tables and columns exist in the
  current schema, even when PostgreSQL has no foreign-key declaration.
- Keep rejecting unknown tables and columns.
- Mark accepted undeclared relationships as inferred so the user can review
  the join.
- Preserve the warning through translation, execution, persistence, and
  conversation restoration.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Inferring missing tables or columns | Identifiers must still come from the live schema. |
| Requiring compatible database types | The current policy is existence-based and remains agnostic to domain-specific typing. |
| Automatically changing generated SQL | The planner and SQL generator remain the source of the join expression. |

## Assumptions & Open Questions

| Decision | Chosen behavior | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Declared relationship | Treat foreign keys as high-confidence evidence | Existing metadata remains useful without blocking incomplete schemas. | yes |
| Undeclared relationship | Accept when both endpoints exist and emit a warning | Users can model valid logical relationships without database constraints. | yes |
| Invalid endpoint | Reject the plan | Accepting invented identifiers would weaken schema grounding. | yes |
| Type compatibility | Do not require it in this validation layer | Compatibility depends on the database and can be evaluated by execution or repair. | yes |

**Open questions:** none.

## User Stories

### P1: Flexible schema joins

As an operator, I want the chat to join existing columns without a declared
foreign key, so that legacy or loosely constrained databases remain usable.

### P1: Reviewable inference

As a user, I want inferred joins to be visible as warnings, so that I can
review the model's assumption before relying on the result.

## Acceptance Criteria

1. **IJV-01** WHEN a plan relationship references existing tables and columns
   but is absent from declared foreign keys THEN validation SHALL accept the
   plan and return one warning identifying the normalized relationship as an
   inferred join.
2. **IJV-02** IF either relationship endpoint references an unknown table or
   column THEN validation SHALL reject the plan with the existing validation
   error boundary.
3. **IJV-03** WHEN an inferred relationship is accepted THEN translation SHALL
   include its warning in the response and persisted assistant metadata.
4. **IJV-04** WHEN a conversation containing an inferred-join warning is
   executed or restored THEN the warning SHALL remain available in the result
   or restored chat message.

## Edge Cases

- A declared relationship in either direction produces no inferred warning.
- Repeating an inferred relationship does not duplicate its warning.
- A schema with no foreign keys can still validate a plan with existing
  endpoints.

## Requirement Traceability

| Requirement ID | Story | Verification |
| --- | --- | --- |
| IJV-01 | P1: Flexible schema joins | `api/tests/test_query_validation.py`, `api/tests/test_chat_service.py` |
| IJV-02 | P1: Flexible schema joins | `api/tests/test_query_validation.py` |
| IJV-03 | P1: Reviewable inference | `api/tests/test_chat_service.py` |
| IJV-04 | P1: Reviewable inference | `api/tests/test_chat_service.py`, `web/src/features/chat/useChat.test.tsx` |

## Success Criteria

- Existing-column joins no longer fail only because a foreign key is absent.
- Unknown identifiers remain blocked.
- The warning is visible after translation, execution, and conversation reload.
- Backend and frontend validation gates remain green.
