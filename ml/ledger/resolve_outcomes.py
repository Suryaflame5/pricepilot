"""Prediction Ledger outcome resolver (V1.2).

Every forecast is ledgered when generated (predictions table rows carry
model_version, calibration_version, retailer, confidence). Once the forecast
horizon has elapsed, this CLI records the ACTUAL outcome against the forecast:

    actual = minimum effective price observed for the variant during the window
             (same definition the forecast engine sees: market = cheapest active)
    in_interval = p05 <= actual <= p95          (calibrated 90% interval)
    error_median = actual - p50

This is the raw material for the "PricePilot Model Performance" truth table
(per category/horizon coverage and accuracy) - never self-reported claims.

Run: python -m ml.ledger.resolve_outcomes [--include-pending-when-ready]
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from sqlalchemy import select

from database.models import Listing, Prediction, PredictionOutcome, PriceObservation
from database.session import create_engine, create_session_factory, init_db

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://pricepilot:pricepilot@localhost:5432/pricepilot",
)


async def _resolve_one(db, pred: Prediction) -> bool:
    # SQLite stores naive timestamps; compare naive-to-naive for portability.
    ended = pred.generated_at.replace(tzinfo=None) if pred.generated_at.tzinfo else pred.generated_at
    horizon_end = ended + timedelta(hours=pred.horizon_hours)
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    if horizon_end > now_naive:
        return False  # not elapsed yet
    existing = (
        await db.execute(
            select(PredictionOutcome.id).where(PredictionOutcome.prediction_id == pred.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    rows = (
        await db.execute(
            select(PriceObservation.effective_price)
            .join(Listing, PriceObservation.listing_id == Listing.id)
            .where(
                Listing.product_variant_id == pred.product_variant_id,
                PriceObservation.observed_at >= ended,
                PriceObservation.observed_at <= horizon_end,
                PriceObservation.effective_price.isnot(None),
            )
        )
    ).all()
    if not rows:
        return False  # no observations in window -> stays pending

    actual = min(float(r[0]) for r in rows)
    p50 = float(pred.p50) if pred.p50 is not None else None
    p05 = float(pred.p05) if pred.p05 is not None else None
    p95 = float(pred.p95) if pred.p95 is not None else None
    in_interval = (p05 is not None and p95 is not None and p05 <= actual <= p95) if p50 is not None else None
    db.add(
        PredictionOutcome(
            prediction_id=pred.id,
            actual_price=None,
            actual_effective_price=actual,
            realized_at=horizon_end,
            in_interval=in_interval,
            error_median=(actual - p50) if p50 is not None else None,
            error_abs=abs(actual - p50) if p50 is not None else None,
        )
    )
    return True


async def resolve_predictions(db, limit: int = 2000) -> dict:
    """Resolve every elapsed prediction that has no outcome yet."""
    predictions = (
        await db.execute(select(Prediction).order_by(Prediction.generated_at).limit(limit))
    ).scalars().all()
    resolved = skipped = pending = 0
    for pred in predictions:
        done = await _resolve_one(db, pred)
        if done:
            resolved += 1
        elif pred.generated_at.replace(tzinfo=timezone.utc) + timedelta(hours=pred.horizon_hours) <= datetime.now(timezone.utc):
            skipped += 1
        else:
            pending += 1
    return {"resolved": resolved, "skipped_no_observations": skipped, "pending_not_elapsed": pending}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", type=str, default=None, help="restrict to one variant id")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)
    await init_db(engine)
    factory = create_session_factory(engine)

    async with factory() as db:
        stmt = select(Prediction)
        if args.variant:
            stmt = stmt.where(Prediction.product_variant_id == uuid.UUID(args.variant))
        report = await resolve_predictions(db)
        await db.commit()
    print(report)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())