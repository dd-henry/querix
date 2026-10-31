from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ChatStatus = Literal["review", "translated", "warning", "executed"]
RetryKind = Literal["translate", "execute"]


class ChatTranslateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID
    prompt: str = Field(min_length=1, max_length=2_000)
    review_mode: bool = True


class ChatExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID
    sql: Optional[str] = None


class ChatRetryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID
    status: ChatStatus
    content: str
    sql: Optional[str] = None
    chart: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    retryable: bool = False
    retry_kind: Optional[RetryKind] = None
    warnings: List[str] = Field(default_factory=list)
