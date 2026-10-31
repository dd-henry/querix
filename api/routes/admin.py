from typing import Dict
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from api.app import APIError
from api.dependencies import get_user_repository, require_roles
from api.schemas.admin import (
    AdminProfileListResponse,
    AdminProfileSchema,
    AdminRoleRequest,
    AdminRoleResponse,
    AdminStatusRequest,
    AdminStatusResponse,
)
from database.users import UserRepository

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


def _admin_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _profiles(records) -> AdminProfileListResponse:
    try:
        profiles = [
            AdminProfileSchema.model_validate(record) for record in records
        ]
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_profile",
            "The user profile record is incomplete.",
        ) from exc
    return AdminProfileListResponse(profiles=profiles)


def _map_user_change_error(exc: ValueError) -> APIError:
    message = str(exc)
    if "último admin" in message:
        return APIError(
            409,
            "last_admin_conflict",
            "The last approved admin cannot be removed.",
        )
    return APIError(422, "invalid_user_change", message)


@router.get(
    "",
    response_model=AdminProfileListResponse,
)
def list_users(
    profile: Dict[str, object] = Depends(require_roles("admin")),
    repository: UserRepository = Depends(get_user_repository),
) -> AdminProfileListResponse:
    return _profiles(repository.list_profiles())


@router.patch(
    "/{user_id}/status",
    response_model=AdminStatusResponse,
)
def update_user_status(
    user_id: UUID,
    payload: AdminStatusRequest,
    profile: Dict[str, object] = Depends(require_roles("admin")),
    repository: UserRepository = Depends(get_user_repository),
) -> AdminStatusResponse:
    try:
        repository.set_status(user_id, payload.status, _admin_id(profile))
    except ValueError as exc:
        raise _map_user_change_error(exc) from exc
    return AdminStatusResponse(id=user_id, status=payload.status)


@router.patch(
    "/{user_id}/role",
    response_model=AdminRoleResponse,
)
def update_user_role(
    user_id: UUID,
    payload: AdminRoleRequest,
    profile: Dict[str, object] = Depends(require_roles("admin")),
    repository: UserRepository = Depends(get_user_repository),
) -> AdminRoleResponse:
    try:
        repository.set_role(user_id, payload.role, _admin_id(profile))
    except ValueError as exc:
        raise _map_user_change_error(exc) from exc
    return AdminRoleResponse(id=user_id, role=payload.role)
