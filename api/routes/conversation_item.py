from typing import Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, ValidationError

from api.app import APIError
from api.dependencies import get_conversation_repository, require_approved_user
from api.schemas.conversations import (
    ConversationDetailResponse,
    ConversationMessageSchema,
    ConversationSummarySchema,
)
from database.conversations import ConversationRepository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class FavoriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_favorite: bool


def _not_found() -> APIError:
    return APIError(404, "not_found", "Conversation not found.")


def _owner_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _owned_summary(
    repository: ConversationRepository,
    user_id: str,
    conversation_id: UUID,
) -> ConversationSummarySchema:
    records, _expired_count = repository.list_sessions_with_expired_count(user_id)
    try:
        summaries = [
            ConversationSummarySchema.model_validate(record) for record in records
        ]
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_conversation",
            "The conversation record is incomplete.",
        ) from exc

    for summary in summaries:
        if summary.id == conversation_id:
            return summary
    raise _not_found()


def _messages(
    records: List[Dict[str, object]],
) -> List[ConversationMessageSchema]:
    try:
        return [
            ConversationMessageSchema.model_validate(record) for record in records
        ]
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_conversation",
            "The conversation message is incomplete.",
        ) from exc


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation(
    conversation_id: UUID,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationDetailResponse:
    user_id = _owner_id(profile)
    summary = _owned_summary(repository, user_id, conversation_id)
    return ConversationDetailResponse(
        **summary.model_dump(),
        messages=_messages(repository.get_messages(user_id, conversation_id)),
    )


@router.patch(
    "/{conversation_id}",
    response_model=ConversationSummarySchema,
)
def update_favorite(
    conversation_id: UUID,
    payload: FavoriteRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationSummarySchema:
    user_id = _owner_id(profile)
    summary = _owned_summary(repository, user_id, conversation_id)
    repository.set_favorite(user_id, conversation_id, payload.is_favorite)
    return summary.model_copy(update={"is_favorite": payload.is_favorite})


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: UUID,
    confirm: bool = Query(False),
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: ConversationRepository = Depends(get_conversation_repository),
) -> Response:
    user_id = _owner_id(profile)
    _owned_summary(repository, user_id, conversation_id)
    if confirm:
        repository.delete(user_id, conversation_id)
    return Response(status_code=204)
