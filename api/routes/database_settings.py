import logging
from typing import Dict

from fastapi import APIRouter, Depends

from api.app import APIError
from api.dependencies import (
    clear_target_database_caches,
    get_database_connection_repository,
    require_roles,
)
from api.schemas.database_settings import (
    DatabaseConnectionRequest,
    DatabaseConnectionResponse,
    DatabaseConnectionStatusResponse,
)
from database.database_connections import DatabaseConnectionRepository
from database.postgres import PostgresAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings/database", tags=["settings"])


def _admin_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


@router.get("", response_model=DatabaseConnectionStatusResponse)
def get_database_status(
    _profile: Dict[str, object] = Depends(require_roles("admin")),
    repository: DatabaseConnectionRepository = Depends(
        get_database_connection_repository
    ),
) -> DatabaseConnectionStatusResponse:
    return DatabaseConnectionStatusResponse(**repository.get_status())


@router.put("", response_model=DatabaseConnectionResponse)
def save_database_connection(
    payload: DatabaseConnectionRequest,
    profile: Dict[str, object] = Depends(require_roles("admin")),
    repository: DatabaseConnectionRepository = Depends(
        get_database_connection_repository
    ),
) -> DatabaseConnectionResponse:
    connection_string = payload.connection_string.strip()
    try:
        normalized = PostgresAdapter.validate_database_url(connection_string)
    except ValueError as exc:
        raise APIError(
            422,
            "validation_error",
            "A valid PostgreSQL connection string is required.",
        ) from exc

    target = PostgresAdapter(database_url=normalized)
    if not target.test_connection():
        raise APIError(
            503,
            "database_connection_failed",
            "The target database connection could not be established.",
        )

    try:
        repository.save(normalized, _admin_id(profile))
        status = repository.get_status()
        clear_target_database_caches()
    except Exception as exc:
        logger.exception("Target database configuration could not be saved.")
        raise APIError(
            503,
            "database_configuration_save_failed",
            "The target database configuration could not be saved.",
        ) from exc
    return DatabaseConnectionResponse(**status)
