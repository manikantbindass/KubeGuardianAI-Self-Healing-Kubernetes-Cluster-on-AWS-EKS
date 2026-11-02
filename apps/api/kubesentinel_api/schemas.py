from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["kubesentinel-api"] = "kubesentinel-api"
    version: str = "0.1.0"


class Readiness(BaseModel):
    status: Literal["ready", "unavailable"]
    dependencies: dict[str, Literal["ok", "unavailable"]]


class GreetingInput(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")


class GreetingOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    status: Literal["queued", "completed"]
    message: str | None
    created_at: datetime
