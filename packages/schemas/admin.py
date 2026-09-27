"""Admin surface schemas (V2): AI planner traces."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TraceToolCall(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool: str
    arguments: dict


class TraceStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    summary: str
    details: dict = {}


class TraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: str
    user_id: uuid.UUID | None
    turn_index: int
    intent: str | None
    backend: str | None
    requires: list[str]
    tool_calls: list[TraceToolCall]
    steps: list[TraceStep]
    reply: str | None
    error: str | None
    latency_ms: int | None
    created_at: datetime


class TracePage(BaseModel):
    total: int
    items: list[TraceOut]