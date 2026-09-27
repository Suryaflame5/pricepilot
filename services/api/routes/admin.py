"""Admin surface (V2): planner traces.

One row per agent turn with the full tool-call trail and reasoning steps, so
operators can audit what the AI actually did (which backend planned, which
typed tools ran with which arguments, what it replied, and whether it errored).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import ConversationTrace
from schemas.admin import TraceOut, TracePage

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/traces", response_model=TracePage)
async def list_traces(
    conversation_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> TracePage:
    count_stmt = select(func.count()).select_from(ConversationTrace)
    stmt = select(ConversationTrace)
    if conversation_id:
        count_stmt = count_stmt.where(
            ConversationTrace.conversation_id == conversation_id
        )
        stmt = stmt.where(ConversationTrace.conversation_id == conversation_id)
    total = (await db.execute(count_stmt)).scalar_one()
    rows = (
        await db.execute(
            stmt.order_by(
                ConversationTrace.created_at.desc(),
                ConversationTrace.turn_index.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    return TracePage(total=total, items=[TraceOut.model_validate(r) for r in rows])


@router.get("/traces/{trace_id}", response_model=TraceOut)
async def get_trace(trace_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> TraceOut:
    row = (
        await db.execute(select(ConversationTrace).where(ConversationTrace.id == trace_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return TraceOut.model_validate(row)