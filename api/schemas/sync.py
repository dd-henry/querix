from typing import Literal

from pydantic import BaseModel, ConfigDict


class SchemaSyncResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["synchronized"]
