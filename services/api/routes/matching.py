"""Matching routes: review queue + decisions.

The conservative policy (auto >=0.995, review 0.95-0.995, never below) means
a human-in-the-loop step exists exactly here. Approving a candidate relinks
the distinct listing to the suggested variant - the only sanctioned merge.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import Listing, MatchCandidate
from schemas.matching import MatchCandidateOut, MatchDecisionOut, MatchDecisionRequest

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/candidates", response_model=list[MatchCandidateOut])
async def list_candidates(
    status: str = "PENDING",
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(MatchCandidate)
        .where(MatchCandidate.status == status)
        .order_by(MatchCandidate.score.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        MatchCandidateOut(
            id=c.id,
            raw_observation_id=c.raw_observation_id,
            listing_id=c.listing_id,
            suggested_variant_id=c.suggested_variant_id,
            score=float(c.score),
            method=c.method,
            identity=c.identity,
            status=c.status,
            created_at=c.created_at,
        )
        for c in rows
    ]


@router.post("/candidates/{candidate_id}/decision", response_model=MatchDecisionOut)
async def decide_candidate(
    candidate_id: uuid.UUID,
    payload: MatchDecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    candidate = await db.get(MatchCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(404, "candidate not found")
    if candidate.status != "PENDING":
        raise HTTPException(409, f"candidate already {candidate.status}")

    if payload.approve:
        if candidate.suggested_variant_id is None or candidate.listing_id is None:
            raise HTTPException(422, "cannot approve: missing variant or listing link")
        listing = await db.get(Listing, candidate.listing_id)
        if listing is None:
            raise HTTPException(404, "listing not found")
        listing.product_variant_id = candidate.suggested_variant_id  # sanctioned merge
        candidate.status = "APPROVED"
    else:
        candidate.status = "REJECTED"
    candidate.reviewed_at = datetime.now(timezone.utc)
    await db.commit()
    return MatchDecisionOut(
        candidate_id=candidate.id,
        status=candidate.status,
        listing_id=candidate.listing_id,
    )
