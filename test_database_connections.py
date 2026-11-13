from unittest.mock import MagicMock

import pandas as pd
import pytest

from database.database_connections import (
    DatabaseConfigurationError,
    DatabaseConnectionRepository,
)


SESSION_SECRET = "test-session-secret"
CONNECTION_STRING = "postgresql://target-user:target-pass@target.example/analytics"


def test_repository_encrypts_and_decrypts_the_target_connection():
    db = MagicMock()
    repository = DatabaseConnectionRepository(db, SESSION_SECRET)

    repository.save(CONNECTION_STRING, "00000000-0000-0000-0000-000000000001")

    parameters = db.execute_command.call_args.args[1]
    assert parameters["encrypted_connection_string"] != CONNECTION_STRING
    assert CONNECTION_STRING not in str(db.execute_command.call_args)

    db.execute_query.return_value = pd.DataFrame(
        [{"encrypted_connection_string": parameters["encrypted_connection_string"]}]
    )
    assert repository.get_connection_string() == CONNECTION_STRING


def test_status_does_not_return_the_connection_string():
    db = MagicMock()
    repository = DatabaseConnectionRepository(db, SESSION_SECRET)
    db.execute_query.return_value = pd.DataFrame()

    assert repository.get_status() == {
        "configured": False,
        "updated_at": None,
    }


def test_repository_initializes_the_table_once():
    db = MagicMock()
    repository = DatabaseConnectionRepository(db, SESSION_SECRET)
    db.execute_query.return_value = pd.DataFrame()

    repository.get_status()
    repository.get_status()

    assert db.execute_command.call_count == 1


def test_corrupt_encrypted_connection_is_reported():
    db = MagicMock()
    repository = DatabaseConnectionRepository(db, SESSION_SECRET)
    db.execute_query.return_value = pd.DataFrame(
        [{"encrypted_connection_string": "not-a-fernet-token"}]
    )

    with pytest.raises(
        DatabaseConfigurationError,
        match="stored database configuration is invalid",
    ):
        repository.get_connection_string()
