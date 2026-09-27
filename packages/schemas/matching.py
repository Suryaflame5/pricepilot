"""Matching API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class MatchCandidateOut(BaseModel):
    id: uuid.UUID
    raw_observation_id: int | None = None
    listing_id: uuid.UUID | None = None
    suggested_variant_id: uuid.UUID | None = None
    score: float
    method: str | None = None
    identity: dict | None = None
    status: str
    created_at: datetime


class MatchDecisionRequest(BaseModel):
    approve: bool
    notes: str | None = None


class MatchDecisionOut(BaseModel):
    candidate_id: uuid.UUID
    status: str  # APPROVED / REJECTED
    listing_id: uuid.UUID | None = None
