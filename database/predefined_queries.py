import json
import re

from database.postgres import PostgresAdapter


class PredefinedQueryRepository:
    """Persiste consultas compartilhadas e favoritos dos usuários."""

    _name_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    _select_pattern = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

    def __init__(self, db: PostgresAdapter):
        self.db = db

    def initialize(self):
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS ask_sql_predefined_queries (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                sql TEXT NOT NULL,
                tags TEXT[] NOT NULL DEFAULT '{}',
                author TEXT NOT NULL,
                parameters JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                CONSTRAINT predefined_queries_read_only CHECK (
                    sql ~* '^[[:space:]]*(SELECT|WITH)([[:space:]]|$)'
                )
            )
            """
        )
        self.db.execute_command(
            """
            ALTER TABLE ask_sql_predefined_queries
            DROP CONSTRAINT IF EXISTS predefined_queries_read_only
            """
        )
        self.db.execute_command(
            """
            ALTER TABLE ask_sql_predefined_queries
            ADD CONSTRAINT predefined_queries_read_only CHECK (
                sql ~* '^[[:space:]]*(SELECT|WITH)([[:space:]]|$)'
            )
            """
        )
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS ask_sql_query_favorites_v2 (
                user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
                query_id BIGINT NOT NULL REFERENCES ask_sql_predefined_queries(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, query_id)
            )
            """
        )

    @classmethod
    def validate_query(cls, sql, parameters):
        normalized_sql = sql.strip().rstrip(";").strip()
        if not cls._select_pattern.match(normalized_sql) or ";" in normalized_sql:
            raise ValueError("Consultas compartilhadas devem conter apenas SELECT ou WITH.")
        if not isinstance(parameters, list):
            raise ValueError("Os parâmetros devem ser uma lista JSON.")
        for parameter in parameters:
            name = parameter.get("name", "")
            if not cls._name_pattern.match(name):
                raise ValueError(f"Nome de parâmetro inválido: {name}")
        return normalized_sql

    def list(self, user_id, search=""):
        result = self.db.execute_query(
            """
            SELECT q.id, q.name, q.description, q.sql, q.tags, q.author,
                   q.parameters, q.updated_at,
                   (f.query_id IS NOT NULL) AS is_favorite
            FROM ask_sql_predefined_queries q
            LEFT JOIN ask_sql_query_favorites_v2 f
              ON f.query_id = q.id AND f.user_id = CAST(:user_id AS uuid)
            WHERE (:search = '' OR q.name ILIKE :pattern OR q.description ILIKE :pattern)
            ORDER BY is_favorite DESC, q.name
            """,
            {"user_id": str(user_id), "search": search, "pattern": f"%{search}%"},
        )
        return result.to_dict("records")

    def get(self, user_id, query_id):
        result = self.db.execute_query(
            """
            SELECT q.id, q.name, q.description, q.sql, q.tags, q.author,
                   q.parameters, q.updated_at,
                   (f.query_id IS NOT NULL) AS is_favorite
            FROM ask_sql_predefined_queries q
            LEFT JOIN ask_sql_query_favorites_v2 f
              ON f.query_id = q.id AND f.user_id = CAST(:user_id AS uuid)
            WHERE q.id = :query_id
            """,
            {"user_id": str(user_id), "query_id": query_id},
        )
        records = result.to_dict("records")
        return records[0] if records else None

    def create(self, name, description, sql, tags, author, parameters):
        sql = self.validate_query(sql, parameters)
        self.db.execute_command(
            """
            INSERT INTO ask_sql_predefined_queries
                (name, description, sql, tags, author, parameters)
            VALUES (:name, :description, :sql, :tags, :author, CAST(:parameters AS jsonb))
            """,
            {"name": name.strip(), "description": description.strip(), "sql": sql,
             "tags": tags, "author": author, "parameters": json.dumps(parameters)},
        )

    def update(self, query_id, name, description, sql, tags, parameters):
        sql = self.validate_query(sql, parameters)
        self.db.execute_command(
            """
            UPDATE ask_sql_predefined_queries
            SET name = :name, description = :description, sql = :sql, tags = :tags,
                parameters = CAST(:parameters AS jsonb), updated_at = NOW()
            WHERE id = :query_id
            """,
            {"query_id": query_id, "name": name.strip(), "description": description.strip(),
             "sql": sql, "tags": tags, "parameters": json.dumps(parameters)},
        )

    def delete(self, query_id):
        self.db.execute_command(
            "DELETE FROM ask_sql_predefined_queries WHERE id = :query_id",
            {"query_id": query_id},
        )

    def toggle_favorite(self, user_id, query_id, favorite):
        if favorite:
            self.db.execute_command(
                """
                INSERT INTO ask_sql_query_favorites_v2 (user_id, query_id)
                VALUES (CAST(:user_id AS uuid), :query_id)
                ON CONFLICT (user_id, query_id) DO NOTHING
                """,
                {"user_id": str(user_id), "query_id": query_id},
            )
        else:
            self.db.execute_command(
                "DELETE FROM ask_sql_query_favorites_v2 WHERE user_id = CAST(:user_id AS uuid) AND query_id = :query_id",
                {"user_id": str(user_id), "query_id": query_id},
            )