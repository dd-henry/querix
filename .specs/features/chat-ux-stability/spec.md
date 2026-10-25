# Chat UX and Interaction Stability Specification

## Problem Statement

The Streamlit chat can briefly render the same user action in more than one place because submitted content is drawn immediately and then drawn again from session history after a rerun. Long-running authentication and query actions have inconsistent progress and error feedback, and the current sidebar makes core tools compete with the conversation. Query history is stored per query, but conversation messages are not persisted or grouped into resumable sessions. Users need a stable, readable chat with private, resumable conversation sessions that preserves existing capabilities.

## Goals

- [ ] Render each submitted chat action and its outcome once, including across Streamlit reruns.
- [ ] Show clear in-progress and failure feedback for authentication, translation, and query execution while preventing repeated submissions of the same active action.
- [ ] Persist each user's conversation sessions, support starting a new session and resuming an earlier one with bounded conversational context.
- [ ] Allow users to favorite and manually delete their sessions, and expire non-favorites after one year of inactivity when that user's history is next opened.
- [ ] Reorganize the interface around a central chat and clearly grouped sidebar tools without removing existing capabilities.
- [ ] Preserve SQL review as the default and retain an option for direct execution.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Replacing Ollama or PostgreSQL | The reported issue concerns interaction and rendering; backend service replacement is not required by the request. |
| Storing query result rows in conversation history | Result rows may be sensitive or large; reopened sessions retain the prompt and SQL and require an explicit re-execution to fetch current rows. |
| Migrating old unlinked query-history rows into conversations | Existing records lack session relationships; they remain available through the existing query-history feature. |
| Adding query authoring or database-management capabilities | This change adds conversation persistence only; unrelated capabilities need a separate feature. |
| Rewriting authentication, authorization, or existing query-execution rules | Existing access boundaries and database execution semantics must remain unchanged. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Frontend technology | Keep Streamlit unless implementation evidence shows the UX requirements cannot be met reliably with it. | The root issue appears in rerun/rendering flows; a framework migration adds risk and does not itself guarantee stability. | Yes (delegated) |
| Existing feature scope | Preserve login, registration and approval, shared-query catalog and administration, per-user history and favorites, SQL review, result tables, charts, and CSV downloads. | The user asked to keep a chat with its current capabilities and approved preserving them. | Yes |
| Visual direction | Use a professional light appearance with clear hierarchy and restrained accent styling. | The user selected this direction. | Yes |
| Failure recovery | Preserve the submitted prompt and available SQL in the conversation, show an inline error, and offer an explicit retry where retry is safe. | The user approved inline feedback and retry; unsafe or non-idempotent actions must not be automatically retried. | Yes |
| Database effects on retries | Only retry translation or read-only query execution; do not repeat account creation, login, or administrative mutations automatically. | Repeating a non-idempotent operation can create duplicate or unintended changes. | No |
| Query scope | Maintain existing SQL review enabled by default and keep the direct-execution setting. | The user confirmed this behavior. | Yes |
| New conversation behavior | Open a blank draft by default; create a persisted session on its first prompt; show saved sessions grouped by recency and titled from the first prompt. | The user asked to start ready for a new session while retaining access to earlier conversations. | Yes |
| Persisted conversation content | Save user/assistant messages, SQL, and errors, but not result rows. Reopened results can be fetched only through an explicit query execution. | The user selected message/SQL persistence without copying result data and accepted re-execution on resume. | Yes |
| Continuation context | Send the last six completed user/assistant turns, including prior SQL, when translating a prompt in a resumed session. | This supplies useful continuity while bounding prompt growth. | Yes |
| Session ownership | Every list, load, favorite, delete, and append operation is scoped to the authenticated user. | Conversation content is private to its owner. | Yes |
| Session favorites and expiry | Favorite sessions do not expire; non-favorites expire one year after last activity and are physically purged when that user's session history is next opened. | The user requested one-year cleanup except for favorites and accepted cleanup on the next visit because no scheduler exists. | Yes |
| Session deletion | Require confirmation and remove the selected session, its messages, and query-history entries linked to it. Keep legacy query-history entries with no session link. | The user approved deletion of linked records while preserving older unlinked history. | Yes |

**Open questions:** none - all scope decisions are resolved or recorded above.

---

## User Stories

### P1: Stable chat and query feedback ⭐ MVP

**User Story**: As an authenticated analyst, I want each question and result to appear once with clear progress and failure feedback so that I can trust what the application is doing.

**Why P1**: Duplicate-looking content and ambiguous action states are the main usability problem.

**Acceptance Criteria**:

1. WHEN a user submits a chat prompt THEN the system SHALL render exactly one user message for that submission across the submit rerun and subsequent reruns.
2. WHILE a translation or query execution is active THEN the system SHALL show which stage is active and prevent a second submission or execution of that same pending action.
3. WHEN a read-only query succeeds THEN the system SHALL render exactly one assistant result containing the SQL, result table, and the existing applicable chart and CSV controls.
4. IF translation or query execution fails THEN the system SHALL render one inline assistant error associated with the submitted prompt and any generated SQL, without removing prior conversation messages.
5. WHEN a retryable translation or read-only query fails THEN the system SHALL offer a user-triggered retry that runs at most once per click.
6. WHEN the user submits a new prompt after a failure THEN the system SHALL accept it without replaying or duplicating the failed action.
7. WHILE SQL review is enabled THEN the system SHALL show the generated SQL for review before query execution.
8. The system SHALL initialize SQL review as enabled and SHALL preserve the user's ability to disable review for direct execution.

**Independent Test**: Submit a prompt, trigger a rerun, and verify one user message; simulate successful and failed translation/query actions and verify one corresponding result/error, visible stage feedback, retry behavior, and no duplicate database call for a single click.

### P1: Private resumable conversation sessions

**User Story**: As an authenticated user, I want my conversations saved in separate sessions that I can reopen or favorite so that I can start fresh without losing the ability to continue previous work.

**Why P1**: The user explicitly needs to continue conversations across visits and distinguish them from one another.

**Acceptance Criteria**:

1. WHEN an approved user opens the chat THEN the system SHALL show a new blank draft and SHALL list only that user's saved sessions grouped as Today, Yesterday, Last 7 days, Last 30 days, and Older.
2. WHEN the user sends the first prompt in a blank draft THEN the system SHALL create one saved session titled from the first prompt and persist the prompt exactly once.
3. WHEN the user selects a saved session THEN the system SHALL restore its ordered prompts, assistant messages, SQL, and errors without restoring query result rows.
4. WHEN a reopened session contains a previous query THEN the system SHALL show its SQL and SHALL require an explicit user action to retrieve current result rows.
5. WHEN the user continues a saved session THEN the system SHALL provide the last six completed user/assistant turns, including prior SQL, as translation context.
6. WHEN the user marks a session as favorite THEN the system SHALL retain it beyond the one-year inactivity expiry.
7. IF a non-favorite session has had no activity for one year and its owner opens conversation history THEN the system SHALL delete the expired session, its messages, and its linked query-history entries before listing sessions.
8. WHEN the owner confirms session deletion THEN the system SHALL delete that session, its messages, and its linked query-history entries while preserving unlinked legacy query-history entries.
9. IF a user requests a session that belongs to another user THEN the system SHALL return no session data and SHALL make no changes to that session.
10. IF a saved conversation cannot be loaded or updated THEN the system SHALL show an actionable error and SHALL not present the operation as successful.

**Independent Test**: Create sessions as two users; verify session ownership, ordering, date grouping, persistence and resume context; verify favorite retention, expiry and linked deletion without persisting result rows.

### P1: Clear workspace and preserved capabilities

**User Story**: As an analyst or administrator, I want the chat to remain the primary workspace and the supporting tools to be organized so that I can find them without losing existing functionality.

**Why P1**: The requested redesign must improve visual hierarchy while preserving workflows already in use.

**Acceptance Criteria**:

1. WHEN an approved user opens the application THEN the system SHALL present the conversation as the primary content area and organize session history, query history, shared queries, and account/admin controls in the sidebar.
2. WHEN an unauthenticated user opens the application THEN the system SHALL present the login and account-request flows with clear success, progress, and error feedback.
3. WHEN an approved user with an administrative role opens the application THEN the system SHALL keep existing administrative actions available only to authorized roles.
4. The system SHALL preserve access to query history, shared queries and favorites, SQL review, result tables, charts, and CSV downloads.
5. WHEN the authentication or chat view is shown THEN the system SHALL use Streamlit's `light` theme; on the authenticated chat view, the main area SHALL show the `Ask SQL` title and `Converse com seus dados` subheading before the transcript and chat input.

**Independent Test**: Use authenticated and unauthenticated sessions with different roles to verify the agreed layout, feedback, role-gated tools, and existing query/result features.

---

## Edge Cases

- IF translation fails before producing SQL THEN the system SHALL associate the single error message with the prompt and SHALL not display stale pending SQL.
- IF query execution fails after SQL review THEN the system SHALL retain the SQL and error in the conversation and SHALL not silently execute it again.
- IF an action rerun occurs after a successful query THEN the system SHALL not append the same result or record the same execution twice for that action.
- IF a user logs out THEN the system SHALL clear the authenticated chat state and pending query state before showing the login view.
- IF a user's role does not grant administration THEN the system SHALL not expose administrative actions.
- IF conversation storage is unavailable THEN the system SHALL report the failure and SHALL not claim the prompt or session was saved.
- IF an expired favorite session is opened THEN the system SHALL preserve it because favorites are excluded from automatic expiry.
- IF a session is deleted THEN the system SHALL not delete query-history records that have no session relationship.

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| CHAT-01 | P1: Stable chat and query feedback (T4, T8) | Execute | Implemented |
| CHAT-02 | P1: Stable chat and query feedback (T5, T9) | Execute | Implemented |
| CHAT-03 | P1: Stable chat and query feedback (T4, T5, T9) | Execute | Implemented |
| CHAT-04 | P1: Stable chat and query feedback (T4, T5, T9) | Execute | Implemented |
| CHAT-05 | P1: Stable chat and query feedback (T5) | Execute | Implemented |
| CHAT-06 | P1: Stable chat and query feedback (T5, T9) | Execute | Implemented |
| CHAT-07 | P1: Stable chat and query feedback (T4, T5) | Execute | Implemented |
| CHAT-08 | P1: Stable chat and query feedback (T5) | Execute | Implemented |
| CHAT-09 | P1: Private resumable conversation sessions (T5, T6, T10) | Execute | Implemented |
| CHAT-10 | P1: Private resumable conversation sessions (T1, T5, T7) | Execute | Implemented |
| CHAT-11 | P1: Private resumable conversation sessions (T1, T5, T7, T10) | Execute | Implemented |
| CHAT-12 | P1: Private resumable conversation sessions (T5, T6) | Execute | Implemented |
| CHAT-13 | P1: Private resumable conversation sessions (T3, T5, T7, T8) | Execute | Implemented |
| CHAT-14 | P1: Private resumable conversation sessions (T1, T5, T6) | Execute | Implemented |
| CHAT-15 | P1: Private resumable conversation sessions (T1, T2, T5, T6) | Execute | Implemented |
| CHAT-16 | P1: Private resumable conversation sessions (T1, T2, T5, T6, T10) | Execute | Implemented |
| CHAT-17 | P1: Private resumable conversation sessions (T1, T2, T5, T7, T8) | Execute | Implemented |
| CHAT-18 | P1: Private resumable conversation sessions (T1, T5, T8, T10) | Execute | Implemented |
| CHAT-19 | P1: Clear workspace and preserved capabilities (T5, T7, T11) | Execute | Implemented |
| CHAT-20 | P1: Clear workspace and preserved capabilities (T5, T8, T11) | Execute | Implemented |
| CHAT-21 | P1: Clear workspace and preserved capabilities (T5, T8) | Execute | Implemented |
| CHAT-22 | P1: Clear workspace and preserved capabilities (T5) | Execute | Implemented |
| CHAT-23 | P1: Clear workspace and preserved capabilities (T5, T11) | Execute | Implemented |

**Coverage:** 23 total, 23 mapped to tasks, 0 unmapped.

## Success Criteria

- [ ] A submitted prompt, query result, or action failure is present once in the rendered conversation after reruns.
- [ ] A single active action cannot be submitted or executed a second time through its pending UI control.
- [ ] Existing authentication, authorization, query history, shared query, SQL review, result, chart, and CSV workflows remain available.
- [ ] Users can reopen only their own conversation sessions, and resumed prompts receive no more than the six latest completed turns as model context.
- [ ] Non-favorite sessions are removed after one year of inactivity when their owner next opens history; favorites remain until manually deleted.
- [ ] The default login and chat views follow the selected professional-light, chat-centered layout.
