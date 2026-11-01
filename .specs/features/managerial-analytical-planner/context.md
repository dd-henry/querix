# Managerial Analytical Planner Context

**Gathered:** 2026-10-31
**Spec:** `.specs/features/managerial-analytical-planner/spec.md`
**Status:** Ready for design

## Feature Boundary

Extend the analytical chat from fixed totals/product queries to a bounded
schema-grounded plan: answer the user's direct question, then calculate up to
three complementary managerial indicators from related sales tables.

## Implementation Decisions

### Period resolution

- An explicit month without a year uses the current server year.
- A missing month uses the current server month and year.
- The backend, not the LLM, owns these defaults.

### Result behavior

- The direct answer remains the primary result and appears first.
- Complementary metrics appear in a separate "Leitura gerencial" section.
- The default depth is essential: two or three relevant indicators, not a
  long narrative.

### Plan execution

- A plan has one primary query and up to three supporting queries.
- All queries are read-only, parameterized, bounded, and validated independently.
- A supporting failure is visible but does not erase a successful primary result.

### Agent's Discretion

- Exact supporting metrics selected for each recognized sales intent.
- Exact labels and summary wording.
- Whether a generic fallback response has zero or fewer than three insights when
  the live schema cannot support a metric.

## Specific References

- The user explicitly wants the system to infer what a manager would want to
  see when the user does not know how to ask.
- The user selected the plan architecture: primary query plus supporting
  queries.

## Deferred Ideas

- User-specific managerial profiles and saved preferences.
- Cross-domain planning for every arbitrary schema.
- Automatic data-quality reconciliation between sales headers and items.
