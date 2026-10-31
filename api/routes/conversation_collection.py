from datetime import datetime, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError

from api.app import APIError
from api.dependencies import get_conversation_repository, require_approved_user
from api.schemas.conversations import (
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationGroupSchema,
    ConversationListResponse,
    ConversationSummarySchema,
)
from database.conversations import ConversationRepository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

_GROUPS = (
    ("today", "Hoje"),
    ("yesterday", "Ontem"),
    ("last_7_days", "Últimos 7 dias"),
    ("last_30_days", "Últimos 30 dias"),
    ("older", "Mais antigas"),
)


def _owner_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise APIError(
            422,
            "validation_error",
            "Timezone is invalid.",
        ) from exc


def _group_key(activity: datetime, current: datetime) -> str:
    if activity.tzinfo is None:
        activity = activity.replace(tzinfo=timezone.utc)
    age_days = (current.date() - activity.astimezone(current.tzinfo).date()).days
    if age_days <= 0:
        return "today"
    if age_days == 1:
        return "yesterday"
    if age_days <= 7:
        return "last_7_days"
    if age_days <= 30:
        return "last_30_days"
    return "older"


def _group_sessions(
    records: List[Dict[str, object]],
    timezone_name: str,
) -> List[ConversationGroupSchema]:
    location = _timezone(timezone_name)
    current = datetime.now(timezone.utc).astimezone(location)
    grouped = {key: [] for key, _label in _GROUPS}

    try:
        sessions = [
            ConversationSummarySchema.model_validate(record) for record in records
        ]
    except ValidationError as exc:
        raise APIError(
            500,
            "invalid_conversation",
            "The conversation record is incomplete.",
        ) from exc

    for session in sessions:
        grouped[_group_key(session.last_activity, current)].append(session)

    return [
        ConversationGroupSchema(
            key=key,
            label=label,
            conversations=grouped[key],
        )
        for key, label in _GROUPS
    ]


@router.get("", response_model=ConversationListResponse)
def list_conversations(
    timezone_name: str = Query("UTC", alias="timezone"),
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationListResponse:
    sessions, expired_count = repository.list_sessions_with_expired_count(
        _owner_id(profile)
    )
    return ConversationListResponse(
        groups=_group_sessions(sessions, timezone_name),
        expired_count=expired_count,
    )


@router.post("", response_model=ConversationCreateResponse, status_code=201)
def create_conversation(
    payload: ConversationCreateRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    repository: ConversationRepository = Depends(get_conversation_repository),
) -> ConversationCreateResponse:
    prompt = payload.prompt.strip()
    if not prompt:
        raise APIError(
            422,
            "validation_error",
            "Conversation prompt cannot be empty.",
        )
    repository.create_with_user_message(
        _owner_id(profile),
        payload.conversation_id,
        payload.request_id,
        prompt,
    )
    return ConversationCreateResponse(
        conversation_id=payload.conversation_id,
        request_id=payload.request_id,
    )
