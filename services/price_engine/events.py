"""Event calendar access (causal/event layer, blueprint section 14)."""

import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Event


async def upcoming_events(
    session: AsyncSession,
    days_ahead: int = 60,
    category: str | None = None,
    retailer_id: uuid.UUID | None = None,
) -> list[Event]:
    now = datetime.now(timezone.utc)
    horizon = now + pd.Timedelta(days=days_ahead).to_pytimedelta()
    stmt = select(Event).where(
        Event.starts_at >= now,
        Event.starts_at <= horizon,
    )
    if category:
        stmt = stmt.where(Event.category == category)
    if retailer_id:
        stmt = stmt.where((Event.retailer_id == retailer_id) | (Event.retailer_id.is_(None)))
    stmt = stmt.order_by(Event.starts_at)
    return list((await session.execute(stmt)).scalars().all())


def days_until(event: Event, now: datetime | None = None) -> int | None:
    if not event.starts_at:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, int((event.starts_at - now).total_seconds() // 86400))
