import pandas as pd
import pytest
from unittest.mock import MagicMock
from uuid import UUID

from database.users import UserRepository


def test_create_pending_profile_uses_auth_user_id():
    db = MagicMock()
    UserRepository(db).create_pending_profile("user-id", "ana@example.com", "Ana")

    params = db.execute_command.call_args.args[1]
    assert params == {"id": "user-id", "email": "ana@example.com", "name": "Ana"}


def test_admin_cannot_remove_own_role():
    with pytest.raises(ValueError, match="próprio papel"):
        UserRepository(MagicMock()).set_role("admin-id", "dev", "admin-id")


def test_last_admin_cannot_be_disabled():
    db = MagicMock()
    db.execute_query.return_value = pd.DataFrame([{"admin_count": 1}])

    with pytest.raises(ValueError, match="último admin"):
        UserRepository(db).set_status("admin-id", "disabled", "other-admin")


def test_get_profile_normalizes_database_uuid_to_string():
    db = MagicMock()
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    db.execute_query.return_value = pd.DataFrame(
        [
            {
                "id": user_id,
                "email": "user@example.com",
                "name": "User",
                "role": "admin",
                "status": "approved",
            }
        ]
    )

    profile = UserRepository(db).get_profile(user_id)

    assert profile["id"] == str(user_id)