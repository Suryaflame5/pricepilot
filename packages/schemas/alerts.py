"""Alert and chat API schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AlertCreate(BaseModel):
    product_variant_id: uuid.UUID
    target_price: float
    direction: Literal["below", "at"] = "below"


class AlertOut(BaseModel):
    id: uuid.UUID
    product_variant_id: uuid.UUID
    target_price: float
    direction: str
    active: bool
    triggered_at: datetime | None
    created_at: datetime


class ChatRequest(BaseModel):
    message: str
    user_id: uuid.UUID | None = None
    conversation_id: str | None = Field(default=None, max_length=64)


class ChatToolCall(BaseModel):
    tool: str
    arguments: dict


class ChatStep(BaseModel):
    kind: str  # search | compare | history | forecast | calibrate | decide | alert | info
    summary: str
    details: dict = {}


class ChatResponse(BaseModel):
    reply: str
    steps: list[ChatStep] = []
    tool_calls: list[ChatToolCall] = []
    # V1.2 planning state surfaced to the client for multi-turn continuity
    conversation_id: str | None = None
    intent: str | None = None
    constraints: dict = {}
    strategy: str | None = None
