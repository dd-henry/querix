from dataclasses import asdict
from typing import Dict

from fastapi import APIRouter, Depends

from api.app import APIError
from api.dependencies import get_chat_service, require_approved_user
from api.schemas.chat import ChatInsight as ChatInsightResponse
from api.schemas.chat import ChatResponse, ChatTranslateRequest
from api.services.chat import ChatResult, ChatService, ChatServiceError

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _owner_id(profile: Dict[str, object]) -> str:
    user_id = profile.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise APIError(
            500,
            "invalid_profile",
            "The authenticated profile is incomplete.",
        )
    return user_id


def _response(result: ChatResult) -> ChatResponse:
    return ChatResponse(
        conversation_id=result.conversation_id,
        request_id=result.request_id,
        status=result.status,
        content=result.content,
        sql=result.sql,
        chart=result.chart,
        summary=result.summary,
        result=result.result,
        insights=[
            ChatInsightResponse.model_validate(asdict(insight))
            for insight in result.insights
        ],
        retryable=result.retryable,
        retry_kind=result.retry_kind,
        warnings=result.warnings,
    )


@router.post("/translate", response_model=ChatResponse)
def translate_chat(
    payload: ChatTranslateRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    if not payload.prompt.strip():
        raise APIError(
            422,
            "validation_error",
            "Prompt must contain between 1 and 2,000 characters.",
        )
    try:
        result = service.translate_prompt(
            _owner_id(profile),
            payload.conversation_id,
            payload.request_id,
            payload.prompt,
            review_mode=payload.review_mode,
        )
        if not payload.review_mode and result.status != "warning":
            result = service.execute_stored_query(
                _owner_id(profile),
                payload.conversation_id,
                payload.request_id,
            )
        return _response(result)
    except ChatServiceError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc
