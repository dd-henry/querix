# Chat UX and Interaction Stability Context

**Gathered:** 2026-10-25
**Spec:** `.specs/features/chat-ux-stability/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Stabilize the current chat/authentication interaction flows and reorganize their presentation while preserving the application's existing features and access rules.

---

## Implementation Decisions

### Chat layout

- Keep the conversation as the central workspace.
- Group conversation sessions, query history, shared queries, and account/administration tools in an organized sidebar.

### Visual style

- Use a professional light appearance with readable hierarchy, deliberate spacing, and a restrained accent.

### Action feedback and query review

- Keep SQL review enabled by default and retain direct execution as an option.
- Show the active authentication, translation, or execution stage.
- Prevent repeated action while the same action is pending.
- Keep failures inline with the relevant prompt and SQL; provide user-triggered retry only for safe, retryable operations.

### Conversation sessions

- Start with a blank draft; create a saved session on the first prompt.
- Show each user's sessions grouped by Today, Yesterday, Last 7 days, Last 30 days, and Older; title each session from its first prompt.
- Persist prompts, assistant messages, SQL, and errors, but not returned result rows. Reopening an old query requires explicit execution to retrieve current results.
- Continue a reopened session with the six most recent completed user/assistant turns, including SQL, as translation context.
- Keep favorites beyond the one-year inactivity period. Delete non-favorites after a year of inactivity when the owner next opens history.
- Allow manual deletion after confirmation. Delete messages and query-history entries linked to the session; retain legacy query-history entries without a session link.
- Keep old query-history entries accessible separately; do not auto-migrate them into new conversation sessions.

### Preserved behavior

- Retain login, registration and approval, shared query catalog, role-gated administration, personal history and favorites, SQL review, result tables, charts, and CSV downloads.
- Preserve existing authentication and authorization boundaries.
- Scope all session reads and mutations to the authenticated user's ID.

### Agent's Discretion

- Keep Streamlit unless implementation evidence shows it cannot satisfy the stability requirements; only then consider a frontend migration.
- Make small corrections tightly coupled to the duplicate-rendering, progress/error feedback, or usability issues.
- Use database timestamps for session recency and expiry; no background scheduler will be added. Expired sessions are deleted when their owner next requests the session list.

### Declined / Undiscussed Gray Areas → Assumptions

- Retry behavior for account and administrative mutations is not automatic; a retry is shown only where repeating the operation is safe.
- Saving full result sets, migrating old unlinked query-history rows, and adding unrelated query/data capabilities are out of scope.

---

## Specific References

The user accepted a central chat with an organized sidebar, a professional light visual style, inline progress/error feedback with duplicate prevention, and SQL review enabled by default with an option for direct execution.

## Deferred Ideas

No unrelated feature additions were requested.
