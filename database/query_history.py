import json

from database.postgres import PostgresAdapter


class QueryHistoryRepository:
    """Persiste consultas executadas por cada usuário autenticado."""

    def __init__(self, db: PostgresAdapter):
        self.db = db

    def initialize(self):
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS ask_sql_query_history (
                id BIGSERIAL PRIMARY KEY,
                user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                prompt TEXT NOT NULL DEFAULT '',
                sql TEXT NOT NULL,
                parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
                is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
                source TEXT NOT NULL DEFAULT 'chat'
                    CHECK (source IN ('chat', 'predefined')),
                session_id UUID REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        self.db.execute_command(
            """
            ALTER TABLE ask_sql_query_history
            ADD COLUMN IF NOT EXISTS session_id UUID
                REFERENCES ask_sql_conversation_sessions(id) ON DELETE CASCADE
            """
        )
        self.db.execute_command(
            """
            ALTER TABLE ask_sql_query_history
            ADD COLUMN IF NOT EXISTS parameters JSONB NOT NULL DEFAULT '{}'::jsonb
            """
        )
        self.db.execute_command(
            """
            ALTER TABLE ask_sql_query_history
            ADD COLUMN IF NOT EXISTS is_pinned BOOLEAN NOT NULL DEFAULT FALSE
            """
        )
        self.db.execute_command(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                          PARTITION BY user_id, session_id, sql, parameters
                           ORDER BY is_pinned DESC, created_at DESC, id DESC
                       ) AS position
                FROM ask_sql_query_history
            )
            DELETE FROM ask_sql_query_history
            WHERE id IN (SELECT id FROM ranked WHERE position > 1)
            """
        )
        self.db.execute_command(
            """
            CREATE INDEX IF NOT EXISTS ask_sql_query_history_user_created_idx
            ON ask_sql_query_history (user_id, created_at DESC)
            """
        )
        self.db.execute_command(
            """
            CREATE INDEX IF NOT EXISTS ask_sql_query_history_session_idx
            ON ask_sql_query_history (session_id)
            WHERE session_id IS NOT NULL
            """
        )

    def record(self, user_id, prompt, sql, source="chat", parameters=None, session_id=None):
        if source not in {"chat", "predefined"}:
            raise ValueError("Origem de histórico inválida.")
        normalized_sql = sql.strip().rstrip(";").strip()
        self.db.execute_command(
            """
                WITH updated AS (
                    UPDATE ask_sql_query_history
                    SET prompt = :prompt, source = :source, created_at = NOW()
                    WHERE id = (
                        SELECT id
                        FROM ask_sql_query_history
                        WHERE user_id = CAST(:user_id AS uuid)
                          AND session_id IS NOT DISTINCT FROM CAST(:session_id AS uuid)
                          AND sql = :sql
                          AND parameters = CAST(:parameters AS jsonb)
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                    )
                    RETURNING id
                )
                INSERT INTO ask_sql_query_history
                    (user_id, prompt, sql, parameters, source, session_id)
                SELECT CAST(:user_id AS uuid), :prompt, :sql,
                       CAST(:parameters AS jsonb), :source, CAST(:session_id AS uuid)
                WHERE NOT EXISTS (SELECT 1 FROM updated)
            """,
            {
                "user_id": str(user_id),
                "prompt": (prompt or "").strip(),
                "sql": normalized_sql,
                "parameters": json.dumps(parameters or {}),
                "source": source,
                "session_id": str(session_id) if session_id is not None else None,
            },
        )

    def list(self, user_id, limit=20):
        result = self.db.execute_query(
            """
            SELECT id, prompt, sql, parameters, source, session_id, is_pinned, created_at
            FROM ask_sql_query_history
            WHERE user_id = CAST(:user_id AS uuid)
            ORDER BY is_pinned DESC, created_at DESC, id DESC
            LIMIT :limit
            """,
            {"user_id": str(user_id), "limit": limit},
        )
        return result.to_dict("records")

    def get(self, user_id, history_id):
        result = self.db.execute_query(
            """
            SELECT id, prompt, sql, parameters, source, session_id, is_pinned, created_at
            FROM ask_sql_query_history
            WHERE id = :history_id
              AND user_id = CAST(:user_id AS uuid)
            """,
            {"user_id": str(user_id), "history_id": history_id},
        )
        records = result.to_dict("records")
        return records[0] if records else None

    def set_pinned(self, user_id, history_id, pinned):
        self.db.execute_command(
            """
            UPDATE ask_sql_query_history
            SET is_pinned = :pinned
            WHERE id = :history_id AND user_id = CAST(:user_id AS uuid)
            """,
            {"user_id": str(user_id), "history_id": history_id, "pinned": pinned},
        )

    def delete(self, user_id, history_id):
        self.db.execute_command(
            """
            DELETE FROM ask_sql_query_history
            WHERE id = :history_id AND user_id = CAST(:user_id AS uuid)
            """,
            {"user_id": str(user_id), "history_id": history_id},
        )