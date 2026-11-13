from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DatabaseConnectionStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    configured: bool
    updated_at: Optional[str] = None


class DatabaseConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_string: str = Field(min_length=1, max_length=2_048)


class DatabaseConnectionResponse(DatabaseConnectionStatusResponse):
    pass
