"""Watchlist routes (v1 demo user; auth comes in Sprint 1's follow-up)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import ProductVariant, WatchlistItem
from schemas.products import VariantOut

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@router.get("", response_model=list[VariantOut])
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ProductVariant)
        .join(WatchlistItem, WatchlistItem.product_variant_id == ProductVariant.id)
        .where(WatchlistItem.user_id == DEMO_USER_ID)
        .order_by(WatchlistItem.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


@router.post("/{variant_id}", status_code=201)
async def add_to_watchlist(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    variant = await db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(404, "variant not found")
    exists = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == DEMO_USER_ID,
                WatchlistItem.product_variant_id == variant_id,
            )
        )
    ).scalar_one_or_none()
    if exists:
        return {"status": "already_tracked", "variant_id": str(variant_id)}
    db.add(WatchlistItem(user_id=DEMO_USER_ID, product_variant_id=variant_id))
    await db.commit()
    return {"status": "added", "variant_id": str(variant_id)}


@router.delete("/{variant_id}", status_code=204)
async def remove_from_watchlist(variant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = (
        await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.user_id == DEMO_USER_ID,
                WatchlistItem.product_variant_id == variant_id,
            )
        )
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "not tracked")
    await db.delete(item)
    await db.commit()
