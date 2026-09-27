"""Price routes: ingest, raw pipeline intake, history, statistics."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from database.models import Listing, PriceObservation, Retailer
from events.bus import BaseEvent
from price_engine.collectors.base import CollectionResult
from price_engine.history import load_listing_series, price_stats, series_to_points
from price_engine.normalizer import normalize_observation
from price_engine.pipeline import IngestionPipeline
from schemas.prices import (
    PriceHistoryOut,
    PriceObservationIn,
    PriceObservationOut,
    PriceStatsOut,
    RawObservationIn,
    RawObservationOut,
    ResampleInterval,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.post("/ingest", response_model=RawObservationOut, status_code=201)
async def ingest_raw_observation(
    payload: RawObservationIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """V1.1 intake: full observation state through the quarantine-first pipeline."""
    pipeline: IngestionPipeline = getattr(request.app.state, "ingestion_pipeline", None)
    if pipeline is None:
        from api.dependencies import session_factory

        pipeline = IngestionPipeline(session_factory, getattr(request.app.state, "event_bus", None))
        request.app.state.ingestion_pipeline = pipeline

    result = CollectionResult(
        listing_id=str(payload.listing_id) if payload.listing_id else str(uuid.uuid4()),
        price=payload.price or 0.0,
        mrp=payload.mrp,
        shipping=payload.shipping,
        coupon_discount=payload.coupon_discount,
        bank_discount=payload.bank_discount,
        availability=payload.availability,
        seller_name=payload.seller_name,
        title=payload.title,
        rating=payload.rating,
        review_count=payload.review_count,
        delivery_estimate=payload.delivery_estimate,
        identity=dict(payload.identity or {}),
        raw={},
        source_metadata={
            "name": payload.source,
            "retailer": payload.retailer,
            "url": payload.url or "",
            "mode": payload.source_mode,
        },
    )
    report = (await pipeline.ingest_results(
        [result], source_mode=payload.source_mode, collected_at=payload.collected_at
    ))[0]
    return RawObservationOut(
        raw_id=report.get("raw_id"),
        listing_id=report.get("listing_id"),
        status=report.get("status", "QUARANTINED"),
        quality=report.get("quality"),
        anomaly=report.get("anomaly"),
        tier=report.get("tier"),
        match_decision=report.get("match_decision"),
        match_score=report.get("match_score"),
        events=report.get("events", []),
        reasons=report.get("reasons"),
        effective_price=report.get("effective_price"),
    )


@router.post("/observations", status_code=201)
async def ingest_observation(
    payload: PriceObservationIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Normalize + validate + store a scraped price observation."""
    listing = await db.get(Listing, payload.listing_id)
    if not listing:
        raise HTTPException(404, "listing not found")

    normalized = normalize_observation(
        price=payload.price,
        mrp=payload.mrp,
        shipping=payload.shipping,
        coupon_discount=payload.coupon_discount,
        bank_discount=payload.bank_discount,
        availability=payload.availability,
    )

    obs = PriceObservation(
        listing_id=listing.id,
        price=normalized.price,
        mrp=normalized.mrp,
        shipping=normalized.shipping,
        coupon_discount=normalized.coupon_discount,
        bank_discount=normalized.bank_discount,
        effective_price=normalized.effective_price,
        availability=normalized.availability,
        observed_at=payload.observed_at or datetime.now(timezone.utc),
    )
    db.add(obs)
    await db.commit()
    await db.refresh(obs)

    bus = getattr(request.app.state, "event_bus", None)
    if bus:
        await bus.publish(
            BaseEvent(
                event_type="price.collected",
                payload={"listing_id": str(listing.id), "effective_price": normalized.effective_price},
            )
        )
    return {"id": obs.id, "effective_price": normalized.effective_price}


@router.get("/history", response_model=PriceHistoryOut)
async def get_history(
    listing_id: uuid.UUID,
    variant_id: uuid.UUID,
    resample: ResampleInterval = Query("1d"),
    since_days: int = Query(365, ge=1, le=3650),
    db: AsyncSession = Depends(get_db),
):
    series = await load_listing_series(db, listing_id, since_days=since_days)
    if series.empty:
        raise HTTPException(404, "no price history for this listing")
    series = series.resample(resample).mean().dropna()
    return PriceHistoryOut(
        listing_id=listing_id,
        variant_id=variant_id,
        points=[{"t": ts.isoformat(), "price": float(v)} for ts, v in series.items()],
    )


@router.get("/stats", response_model=PriceStatsOut)
async def get_stats(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    series = await load_listing_series(db, listing_id, since_days=365)
    if series.empty:
        raise HTTPException(404, "no price history for this listing")
    stats = price_stats(series)
    return PriceStatsOut(
        listing_id=listing_id,
        current_price=stats.get("current_price"),
        mean_7d=stats.get("mean_7d"),
        mean_30d=stats.get("mean_30d"),
        mean_90d=stats.get("mean_90d"),
        min_7d=stats.get("min_7d"),
        min_30d=stats.get("min_30d"),
        min_90d=stats.get("min_90d"),
        max_7d=stats.get("max_7d"),
        max_30d=stats.get("max_30d"),
        max_90d=stats.get("max_90d"),
        price_percentile_90d=stats.get("price_percentile_90d"),
        observations_90d=stats.get("observations_90d", 0),
    )
