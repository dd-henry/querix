import json
import math

from database.postgres import PostgresAdapter


class ConversationRepository:
    """Persists private conversation sessions and their messages."""

    _context_limit = 6

    def __init__(self, db: PostgresAdapter):
        self.db = db

    def initialize(self):
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS ask_sql_conversation_sessions (
                id UUID PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        self.db.execute_command(
            """
            CREATE INDEX IF NOT EXISTS ask_sql_conversation_sessions_owner_activity_idx
            ON ask_sql_conversation_sessions (user_id, is_favorite DESC, last_activity DESC)
            """
        )
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS ask_sql_conversation_messages (
                id BIGSERIAL PRIMARY KEY,
                session_id UUID NOT NULL
                    REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE,
                request_id UUID NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL DEFAULT '',
                sql TEXT,
                error TEXT,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (session_id, request_id, role)
            )
            """
        )
        self.db.execute_command(
            """
            CREATE INDEX IF NOT EXISTS ask_sql_conversation_messages_order_idx
            ON ask_sql_conversation_messages (session_id, id)
            """
        )

    def create_with_user_message(self, user_id, session_id, request_id, prompt):
        normalized_prompt = (prompt or "").strip()
        if not normalized_prompt:
            raise ValueError("The conversation prompt cannot be empty.")

        self.db.execute_command(
            """
            WITH target AS (
                INSERT INTO ask_sql_conversation_sessions (id, user_id, title)
                VALUES (
                    CAST(:session_id AS uuid),
                    CAST(:user_id AS uuid),
                    :title
                )
                ON CONFLICT (id) DO UPDATE
                SET id = EXCLUDED.id
                WHERE ask_sql_conversation_sessions.user_id = EXCLUDED.user_id
                RETURNING id
            )
            INSERT INTO ask_sql_conversation_messages
                (session_id, request_id, role, content)
            SELECT id, CAST(:request_id AS uuid), 'user', :prompt
            FROM target
            ON CONFLICT (session_id, request_id, role) DO NOTHING
            """,
            {
                "session_id": str(session_id),
                "user_id": str(user_id),
                "request_id": str(request_id),
                "title": normalized_prompt[:80],
                "prompt": normalized_prompt,
            },
        )

    def append_message(
        self,
        user_id,
        session_id,
        request_id,
        role,
        content,
        sql=None,
        error=None,
        metadata=None,
    ):
        if role not in {"user", "assistant"}:
            raise ValueError("Invalid conversation message role.")

        self.db.execute_command(
            """
            WITH inserted AS (
                INSERT INTO ask_sql_conversation_messages
                    (session_id, request_id, role, content, sql, error, metadata)
                SELECT s.id, CAST(:request_id AS uuid), :role, :content, :sql, :error,
                       CAST(:metadata AS jsonb)
                FROM ask_sql_conversation_sessions s
                WHERE s.id = CAST(:session_id AS uuid)
                  AND s.user_id = CAST(:user_id AS uuid)
                ON CONFLICT (session_id, request_id, role) DO NOTHING
                RETURNING session_id
            )
            UPDATE ask_sql_conversation_sessions s
            SET last_activity = GREATEST(s.last_activity, NOW())
            WHERE s.id = CAST(:session_id AS uuid)
              AND s.user_id = CAST(:user_id AS uuid)
              AND EXISTS (SELECT 1 FROM inserted)
            """,
            {
                "user_id": str(user_id),
                "session_id": str(session_id),
                "request_id": str(request_id),
                "role": role,
                "content": content or "",
                "sql": sql,
                "error": error,
                "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            },
        )

    def list_sessions(self, user_id):
        sessions, _expired_count = self.list_sessions_with_expired_count(user_id)
        return sessions

    def list_sessions_with_expired_count(self, user_id):
        expired_count = self.db.execute_command(
            """
            DELETE FROM ask_sql_conversation_sessions
            WHERE user_id = CAST(:user_id AS uuid)
              AND is_favorite = FALSE
              AND last_activity <= NOW() - INTERVAL '1 year'
            """,
            {"user_id": str(user_id)},
        )
        result = self.db.execute_query(
            """
            SELECT id, title, is_favorite, created_at, last_activity
            FROM ask_sql_conversation_sessions
            WHERE user_id = CAST(:user_id AS uuid)
            ORDER BY is_favorite DESC, last_activity DESC
            """,
            {"user_id": str(user_id)},
        )
        return result.to_dict("records"), max(expired_count, 0)

    def update_assistant_message(
        self,
        user_id,
        session_id,
        request_id,
        content,
        sql=None,
        error=None,
        metadata=None,
        role="assistant",
    ):
        if role != "assistant":
            raise ValueError("Only assistant messages can be replaced.")

        self.db.execute_command(
            """
            WITH updated AS (
                UPDATE ask_sql_conversation_messages m
                SET content = :content,
                    sql = :sql,
                    error = :error,
                    metadata = CAST(:metadata AS jsonb)
                FROM ask_sql_conversation_sessions s
                WHERE m.session_id = s.id
                  AND m.session_id = CAST(:session_id AS uuid)
                  AND m.request_id = CAST(:request_id AS uuid)
                  AND m.role = 'assistant'
                  AND s.user_id = CAST(:user_id AS uuid)
                RETURNING m.session_id
            )
            UPDATE ask_sql_conversation_sessions s
            SET last_activity = GREATEST(s.last_activity, NOW())
            WHERE s.id = CAST(:session_id AS uuid)
              AND s.user_id = CAST(:user_id AS uuid)
              AND EXISTS (SELECT 1 FROM updated)
            """,
            {
                "user_id": str(user_id),
                "session_id": str(session_id),
                "request_id": str(request_id),
                "content": content or "",
                "sql": sql,
                "error": error,
                "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            },
        )

    def get_messages(self, user_id, session_id):
        result = self.db.execute_query(
            """
            SELECT m.id, m.request_id, m.role, m.content, m.sql, m.error,
                   m.metadata, m.created_at
            FROM ask_sql_conversation_messages m
            JOIN ask_sql_conversation_sessions s ON s.id = m.session_id
            WHERE s.id = CAST(:session_id AS uuid)
              AND s.user_id = CAST(:user_id AS uuid)
            ORDER BY m.id
            """,
            {"user_id": str(user_id), "session_id": str(session_id)},
        )
        records = result.to_dict("records")
        for record in records:
            for field in ("sql", "error"):
                value = record.get(field)
                if isinstance(value, float) and math.isnan(value):
                    record[field] = None
        return records

    def get_context(self, user_id, session_id, limit=6, exclude_request_id=None):
        if not isinstance(limit, int) or limit < 0 or limit > self._context_limit:
            raise ValueError("Conversation context limit must be between zero and six.")
        if limit == 0:
            return []

        result = self.db.execute_query(
            """
            SELECT u.content AS prompt, a.content AS assistant_content,
                   a.sql AS assistant_sql, a.error AS assistant_error
            FROM ask_sql_conversation_messages u
            JOIN ask_sql_conversation_messages a
              ON a.session_id = u.session_id
             AND a.request_id = u.request_id
             AND a.role = 'assistant'
            JOIN ask_sql_conversation_sessions s ON s.id = u.session_id
            WHERE s.id = CAST(:session_id AS uuid)
              AND s.user_id = CAST(:user_id AS uuid)
              AND u.role = 'user'
              AND u.request_id IS DISTINCT FROM CAST(:exclude_request_id AS uuid)
            ORDER BY u.id DESC
            LIMIT :limit
            """,
            {
                "user_id": str(user_id),
                "session_id": str(session_id),
                "limit": limit,
                "exclude_request_id": (
                    str(exclude_request_id) if exclude_request_id is not None else None
                ),
            },
        )

        context = []
        for turn in reversed(result.to_dict("records")):
            context.append({"role": "user", "content": turn["prompt"]})
            context.append(
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "message": turn["assistant_content"],
                            "sql": turn["assistant_sql"],
                            "error": turn["assistant_error"],
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        return context

    def set_favorite(self, user_id, session_id, favorite):
        self.db.execute_command(
            """
            UPDATE ask_sql_conversation_sessions
            SET is_favorite = :favorite
            WHERE id = CAST(:session_id AS uuid)
              AND user_id = CAST(:user_id AS uuid)
            """,
            {
                "user_id": str(user_id),
                "session_id": str(session_id),
                "favorite": bool(favorite),
            },
        )

    def delete(self, user_id, session_id):
        self.db.execute_command(
            """
            DELETE FROM ask_sql_conversation_sessions
            WHERE id = CAST(:session_id AS uuid)
              AND user_id = CAST(:user_id AS uuid)
            """,
            {"user_id": str(user_id), "session_id": str(session_id)},
        )
