from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import ValidationError

from api.app import APIError
from api.dependencies import (
    get_chat_service,
    get_query_history_repository,
    require_approved_user,
)
from api.schemas.history import (
    HistoryListResponse,
    HistoryMutationResponse,
    HistoryPinRequest,
    HistoryRecordSchema,
    HistoryRerunRequest,
)
from api.schemas.chat import ChatResponse
from api.services.chat import ChatResult, ChatService, ChatServiceError
from database.query_history import QueryHistoryRepository

router = APIRouter(prefix="/api/history", tags=["history"])


def _owner_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _history_record(record: Dict[str, object]) -> HistoryRecordSchema:
    try:
        return HistoryRecordSchema.model_validate(record)
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_history",
            "The history record is incomplete.",
        ) from exc


def _owned_history(
    repository: QueryHistoryRepository,
    user_id: str,
    history_id: int,
) -> HistoryRecordSchema:
    record = repository.get(user_id, history_id)
    if record is None:
        raise APIError(404, "not_found", "History record not found.")
    return _history_record(record)


def _chat_response(result: ChatResult):
    from api.routes.chat_execute import _response

    return _response(result)


@router.get("", response_model=HistoryListResponse)
def list_history(
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: QueryHistoryRepository = Depends(get_query_history_repository),
) -> HistoryListResponse:
    records = repository.list(_owner_id(profile), limit=20)
    return HistoryListResponse(
        records=[_history_record(record) for record in records]
    )


@router.patch(
    "/{history_id}",
    response_model=HistoryMutationResponse,
)
def update_history_pin(
    history_id: int,
    payload: HistoryPinRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: QueryHistoryRepository = Depends(get_query_history_repository),
) -> HistoryMutationResponse:
    user_id = _owner_id(profile)
    _owned_history(repository, user_id, history_id)
    repository.set_pinned(user_id, history_id, payload.is_pinned)
    return HistoryMutationResponse(id=history_id, is_pinned=payload.is_pinned)


@router.delete("/{history_id}", response_model=HistoryMutationResponse)
def delete_history(
    history_id: int,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: QueryHistoryRepository = Depends(get_query_history_repository),
) -> HistoryMutationResponse:
    user_id = _owner_id(profile)
    record = _owned_history(repository, user_id, history_id)
    repository.delete(user_id, history_id)
    return HistoryMutationResponse(id=record.id, is_pinned=record.is_pinned)


@router.post(
    "/{history_id}/rerun",
    response_model=ChatResponse,
)
def rerun_history(
    history_id: int,
    payload: HistoryRerunRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
):
    try:
        return _chat_response(
            service.execute_history_query(
                _owner_id(profile),
                history_id,
                payload.conversation_id,
                payload.request_id,
            )
        )
    except ChatServiceError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc
