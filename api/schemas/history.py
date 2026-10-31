from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

HistorySource = Literal["chat", "predefined"]


class HistoryRecordSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    prompt: str
    sql: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    source: HistorySource
    session_id: Optional[UUID] = None
    is_pinned: bool = False
    created_at: datetime


class HistoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: List[HistoryRecordSchema] = Field(default_factory=list)


class HistoryPinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_pinned: bool


class HistoryMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    is_pinned: bool


class HistoryRerunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID
    request_id: UUID
