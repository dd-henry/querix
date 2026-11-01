from dataclasses import asdict
from typing import Callable, Dict

from fastapi import APIRouter, Depends

from api.app import APIError
from api.dependencies import get_chat_service, require_approved_user
from api.schemas.chat import (
    ChatExecuteRequest,
    ChatCancelResponse,
    ChatInsight as ChatInsightResponse,
    ChatProgressResponse,
    ChatResponse,
    ChatRetryRequest,
)
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
        interpretation=result.interpretation,
        diagnostics=result.diagnostics,
    )


def _run(action: Callable[[], ChatResult]) -> ChatResponse:
    try:
        return _response(action())
    except ChatServiceError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc


@router.post("/execute", response_model=ChatResponse)
def execute_chat(
    payload: ChatExecuteRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    user_id = _owner_id(profile)
    return _run(
        lambda: service.execute_stored_query(
            user_id,
            payload.conversation_id,
            payload.request_id,
        )
    )


@router.post("/cancel", response_model=ChatCancelResponse)
def cancel_chat(
    payload: ChatRetryRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatCancelResponse:
    try:
        service.cancel_request(
            _owner_id(profile),
            payload.conversation_id,
            payload.request_id,
        )
    except ChatServiceError as exc:
        raise APIError(exc.status_code, exc.code, exc.message) from exc
    return ChatCancelResponse(status="cancelled")


@router.post("/status", response_model=ChatProgressResponse)
def chat_status(
    payload: ChatRetryRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatProgressResponse:
    progress = service.get_request_progress(
        _owner_id(profile),
        payload.conversation_id,
        payload.request_id,
    )
    if progress is None:
        raise APIError(
            404,
            "request_not_active",
            "The chat request is no longer active.",
        )
    return ChatProgressResponse.model_validate(progress)


@router.post("/retry", response_model=ChatResponse)
def retry_chat(
    payload: ChatRetryRequest,
    profile: Dict[str, object] = Depends(require_approved_user),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    user_id = _owner_id(profile)
    return _run(
        lambda: service.retry_request(
            user_id,
            payload.conversation_id,
            payload.request_id,
        )
    )
