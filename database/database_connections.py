import base64
import hashlib
from datetime import datetime
from typing import Optional

import pandas as pd
from cryptography.fernet import Fernet, InvalidToken

from database.postgres import PostgresAdapter


class DatabaseConfigurationError(RuntimeError):
    """Raised when the stored target connection cannot be decrypted."""


def _encryption_key(session_secret: str) -> bytes:
    digest = hashlib.sha256(session_secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


class DatabaseConnectionRepository:
    """Stores the single encrypted target database connection."""

    def __init__(self, db: PostgresAdapter, session_secret: str):
        if not session_secret:
            raise ValueError("SESSION_SECRET must be configured.")
        self.db = db
        self._cipher = Fernet(_encryption_key(session_secret))
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        self.db.execute_command(
            """
            CREATE TABLE IF NOT EXISTS public.ask_sql_database_connections (
                id SMALLINT PRIMARY KEY CHECK (id = 1),
                encrypted_connection_string TEXT NOT NULL,
                updated_by UUID NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        self._initialized = True

    def get_status(self) -> dict[str, object]:
        self.initialize()
        result = self.db.execute_query(
            """
            SELECT updated_at
            FROM public.ask_sql_database_connections
            WHERE id = 1
            """
        )
        if result.empty:
            return {"configured": False, "updated_at": None}
        return {
            "configured": True,
            "updated_at": _timestamp_value(result.iloc[0]["updated_at"]),
        }

    def get_connection_string(self) -> Optional[str]:
        self.initialize()
        result = self.db.execute_query(
            """
            SELECT encrypted_connection_string
            FROM public.ask_sql_database_connections
            WHERE id = 1
            """
        )
        if result.empty:
            return None
        encrypted = result.iloc[0]["encrypted_connection_string"]
        try:
            return self._cipher.decrypt(str(encrypted).encode("utf-8")).decode(
                "utf-8"
            )
        except InvalidToken as exc:
            raise DatabaseConfigurationError(
                "The stored database configuration is invalid."
            ) from exc

    def save(self, connection_string: str, updated_by: str) -> None:
        self.initialize()
        encrypted = self._cipher.encrypt(connection_string.encode("utf-8")).decode(
            "utf-8"
        )
        self.db.execute_command(
            """
            INSERT INTO public.ask_sql_database_connections
                (id, encrypted_connection_string, updated_by)
            VALUES (1, :encrypted_connection_string, CAST(:updated_by AS uuid))
            ON CONFLICT (id) DO UPDATE SET
                encrypted_connection_string = EXCLUDED.encrypted_connection_string,
                updated_by = EXCLUDED.updated_by,
                updated_at = NOW()
            """,
            {
                "encrypted_connection_string": encrypted,
                "updated_by": str(updated_by),
            },
        )


def _timestamp_value(value: object) -> Optional[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
