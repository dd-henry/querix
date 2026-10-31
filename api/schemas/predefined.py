from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PredefinedParameterSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    label: Optional[str] = None
    required: bool = True


class PredefinedQuerySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: str = ""
    sql: str
    tags: List[str] = Field(default_factory=list)
    author: str
    parameters: List[PredefinedParameterSchema] = Field(
        default_factory=list
    )
    updated_at: datetime
    is_favorite: bool = False


class PredefinedQueryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queries: List[PredefinedQuerySchema] = Field(default_factory=list)


class PredefinedFavoriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_favorite: bool


class PredefinedFavoriteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    is_favorite: bool


class PredefinedQueryWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    sql: str = Field(min_length=1, max_length=20_000)
    tags: List[str] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)


class PredefinedQueryExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: Dict[str, Any] = Field(default_factory=dict)


class PredefinedQueryMutationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str


class PredefinedQueryExecutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query_id: int
    result: Dict[str, Any]
