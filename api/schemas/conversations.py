from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProfileRole = Literal["user", "dev", "dba", "admin"]
ProfileStatus = Literal["pending", "approved", "rejected", "disabled"]
MessageRole = Literal["user", "assistant"]
RetryKind = Literal["translate", "execute"]
ConversationGroupKey = Literal[
    "today",
    "yesterday",
    "last_7_days",
    "last_30_days",
    "older",
]


class ProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    name: str
    role: ProfileRole
    status: ProfileStatus


class MessageMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    retryable: bool = False
    retry_kind: Optional[RetryKind] = None


class ConversationMessageSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    request_id: UUID
    role: MessageRole
    content: str
    sql: Optional[str] = None
    error: Optional[str] = None
    metadata: MessageMetadata = Field(default_factory=MessageMetadata)
    created_at: datetime


class ConversationSummarySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    is_favorite: bool = False
    created_at: datetime
    last_activity: datetime


class ConversationGroupSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: ConversationGroupKey
    label: str
    conversations: list[ConversationSummarySchema] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    groups: list[ConversationGroupSchema] = Field(default_factory=list)
    expired_count: int = 0


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID
    prompt: str = Field(min_length=1, max_length=2000)


class ConversationCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID


class ConversationDetailResponse(ConversationSummarySchema):
    messages: list[ConversationMessageSchema] = Field(default_factory=list)


class ErrorDetailSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetailSchema


class ConversationNotFoundResponse(ErrorResponse):
    error: ErrorDetailSchema = Field(
        default_factory=lambda: ErrorDetailSchema(
            code="not_found",
            message="Conversation not found.",
        )
    )


def metadata_from_record(record: dict[str, Any]) -> MessageMetadata:
    """Validate repository JSON metadata before exposing it in a response."""

    return MessageMetadata.model_validate(record or {})
