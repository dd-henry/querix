from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

AdminRole = Literal["user", "dev", "admin"]
AdminStatus = Literal["approved", "rejected", "disabled"]


class AdminProfileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    name: str
    role: AdminRole
    status: Literal["pending", "approved", "rejected", "disabled"]
    created_at: datetime
    approved_at: Optional[datetime] = None
    disabled_at: Optional[datetime] = None


class AdminProfileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profiles: List[AdminProfileSchema]


class AdminStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AdminStatus


class AdminRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: AdminRole


class AdminStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: AdminStatus


class AdminRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    role: AdminRole
