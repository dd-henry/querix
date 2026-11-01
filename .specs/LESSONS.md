# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Assert active-state blocking on the actual submit and execution controls, not only retry controls.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-02
- last seen: 2026-10-25T05:00:11Z

### L-002 - Failure-path tests should assert retained transcript payload and the absence of stale transient state.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-04
- last seen: 2026-10-25T05:00:11Z

### L-003 - Test recovery by submitting a new action after failure and asserting the failed action is not replayed.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-06
- last seen: 2026-10-25T05:00:11Z

### L-004 - Assert each record's expected recency bucket, not only that bucket labels render.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-09
- last seen: 2026-10-25T05:00:11Z

### L-005 - At resume boundaries, assert every persisted payload field promised by the specification.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-11
- last seen: 2026-10-25T05:00:11Z

### L-006 - Exercise user-visible failure handling for mutations of existing persisted records, not only initial saves.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-18
- last seen: 2026-10-25T05:00:11Z

### L-007 - Test success, progress, and failure separately for each authentication entry flow.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-20
- last seen: 2026-10-25T05:00:11Z

### L-008 - Define visual acceptance criteria as measurable rendered properties before claiming style coverage.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-23
- last seen: 2026-10-25T05:00:11Z

### L-009 - Verify deletion behavior with both linked rows and null-linked legacy rows in the same outcome test.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-16
- last seen: 2026-10-25T05:00:41Z

### L-010 - For layout requirements, assert widget placement and primary-area hierarchy, not only widget presence.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: CHAT-19
- last seen: 2026-10-25T05:00:41Z

### L-011 - After a successful action rerun, assert both the rendered result and persisted side effects remain singular.
- signal: `ac_gap` · recurrence: 1 feature(s) · harmful: 0
- features: chat-ux-stability
- evidence: Edge case 3
- last seen: 2026-10-25T05:00:41Z

### L-012 - Assert that first-prompt persistence creates a non-null owned session before appending any conversation messages
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `chat` · harmful: 0
- features: chat-ux-stability
- evidence: MUT-1 (validation.md) (chat)
- last seen: 2026-10-25T05:15:56Z

### L-013 - When a period parser sees an explicit year without a month, test or define the year intent before applying a current-month fallback.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `analytics` · harmful: 0
- features: managerial-analytical-planner
- evidence: core/analytical_queries.py:102 | explicit-year edge (analytics)
- last seen: 2026-11-01T02:09:42Z

### L-014 - Assert every safety clause in structured LLM prompts, including named parameters and schema relations, rather than only the JSON shape.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `prompt` · harmful: 0
- features: managerial-analytical-planner
- evidence: test_prompter.py:30-32 | AC-09 (prompt)
- last seen: 2026-11-01T02:09:42Z

### L-015 - Exercise each read-only safety branch, including multi-statement rejection, with an assertion that the adapter is not called.
- signal: `ac_gap` · recurrence: 1 feature(s) · scope: `api` · harmful: 0
- features: managerial-analytical-planner
- evidence: api/tests/test_chat_service.py:431-463 | AC-10 (api)
- last seen: 2026-11-01T02:09:42Z

### L-016 - Specify observable response equality and execution semantics before claiming idempotency for compound primary-and-insight requests.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `idempotency` · harmful: 0
- features: managerial-analytical-planner
- evidence: api/tests/test_chat_translate_routes.py:213-228 | AC-12 (idempotency)
- last seen: 2026-11-01T02:09:42Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
